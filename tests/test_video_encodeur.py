"""nc-video choisit l'encodeur matériel, avec repli : NVENC si la NVIDIA est la carte des applis et que ffmpeg connaît
h264_nvenc ; sinon VAAPI sur la carte qui affiche la session (render node lu dans /sys), si vainfo y voit un encodeur
H.264 ; sinon le processeur (libx264). Réglage VIDEO_ENCODEUR : auto, carte, processeur.

Faux wf-recorder (journalise ses arguments, puis attend comme un vrai enregistrement), ffmpeg (-encoders avec ou sans
h264_nvenc), vainfo (succès, décodage seul ou échec), slurp, notify-send ; faux /sys (NC_SYSFS) avec deux cartes ;
faux $XDG_RUNTIME_DIR/nc-gpu-default. Le PATH ne contient que les faux et les outils de base nécessaires : un vrai
vainfo ou ffmpeg de la machine ne peut pas se glisser dans un test.
"""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-video"
SEP = "\x1f"

# Outils de base dont nc-video a besoin (liens vers les vrais), et rien d'autre
OUTILS = ("bash", "sh", "sed", "tail", "tr", "mkdir", "date", "setsid", "sleep", "cat", "readlink", "timeout", "grep",
          "head", "seq", "rm", "env", "flock", "cut")

PROFILS_OK = """vainfo: VA-API version: 1.22 (libva 2.22.0)
vainfo: Driver version: Mesa Gallium driver for AMD Radeon 610M
vainfo: Supported profile and entrypoints
      VAProfileH264ConstrainedBaseline: VAEntrypointVLD
      VAProfileH264ConstrainedBaseline: VAEntrypointEncSlice
      VAProfileH264Main               : VAEntrypointVLD
      VAProfileH264Main               : VAEntrypointEncSlice
      VAProfileHEVCMain               : VAEntrypointEncSlice"""
# Fedora sans RPM Fusion : la carte décode, mais n'encode pas en H.264
PROFILS_DECODAGE = """vainfo: Supported profile and entrypoints
      VAProfileH264Main               : VAEntrypointVLD
      VAProfileAV1Profile0            : VAEntrypointVLD"""

ENCODEURS = """Encoders:
 V..... = Video
 ------
 V....D libx264              libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10 (codec h264)
{nvenc} V....D h264_vaapi           H.264/AVC (VAAPI) (codec h264)
 A....D aac                  AAC (Advanced Audio Coding)"""
LIGNE_NVENC = " V....D h264_nvenc           NVIDIA NVENC H.264 encoder (codec h264)\n"

FAUX = {
    "slurp": 'echo "0,0 2560x1600"',
    "xdg-user-dir": 'echo "$HOME/Videos"',
    "notify-send": 'echo "notify-send $*" >> "$JOURNAL"',
    "pactl": "exit 0",
    # Un enregistrement : arguments journalisés, puis il dure (exec : même pid que celui gardé par nc-video).
    # NC_TEST_WF_ECHEC=<codec> : ne démarre pas avec ce codec (pilote absent, carte qui refuse)
    "wf-recorder": f'''printf '%s{SEP}' "$@" >> "$NC_TEST_WF"; echo >> "$NC_TEST_WF"
if [ -n "${{NC_TEST_WF_ECHEC:-}}" ]; then
  for a; do [ "$a" = "$NC_TEST_WF_ECHEC" ] && {{ echo "Failed to open encoder" >&2; exit 1; }}; done
fi
exec sleep 30''',
}


class VideoEncodeur(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-video-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        self.faux = self.home / "faux"
        self.faux.mkdir()
        for nom in OUTILS:
            chemin = shutil.which(nom)
            self.assertIsNotNone(chemin, nom)
            (self.faux / nom).symlink_to(chemin)
        for nom, corps in FAUX.items():
            self.ecrire_faux(nom, corps)
        (self.home / ".config/nc").mkdir(parents=True)
        self.reglages("")
        self.run_dir = self.home / "run"
        self.run_dir.mkdir(mode=0o700)
        self.journal = self.home / "journal"
        self.journal.write_text("")
        self.wf = self.home / "wf"
        self.addCleanup(self.arreter_enregistrement)
        # Faux /sys : card0 = NVIDIA (renderD129, écran interne éteint), card1 = AMD intégrée (renderD128, écran
        # interne allumé). Comme dans le vrai /sys, cardN/device est un lien vers le périphérique PCI.
        self.sysfs = self.home / "sys"
        for carte, pci, rendu, prise, etat in (("card0", "0000:01:00.0", "renderD129", "eDP-2", "disconnected"),
                                               ("card1", "0000:ee:1f.7", "renderD128", "eDP-1", "connected")):
            peripherique = self.sysfs / "devices" / pci
            (peripherique / "drm" / rendu).mkdir(parents=True)
            (peripherique / "drm" / carte).mkdir()
            (self.sysfs / "class/drm" / carte).mkdir(parents=True)
            (self.sysfs / "class/drm" / carte / "device").symlink_to(peripherique)
            (self.sysfs / "class/drm" / f"{carte}-{prise}").mkdir()
            (self.sysfs / "class/drm" / f"{carte}-{prise}/status").write_text(etat + "\n")

    def ecrire_faux(self, nom, corps):
        f = self.faux / nom
        f.write_text("#!/bin/sh\n" + corps + "\n")
        f.chmod(0o755)

    def reglages(self, texte):
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\n" + texte)

    def carte_des_applis(self, carte):
        (self.run_dir / "nc-gpu-default").write_text(carte + "\n")

    def ffmpeg(self, nvenc=True, vaapi=True):
        liste = ENCODEURS.format(nvenc=LIGNE_NVENC if nvenc else "")
        if not vaapi:
            liste = "\n".join(l for l in liste.splitlines() if "h264_vaapi" not in l)
        (self.home / "encodeurs.txt").write_text(liste + "\n")
        self.ecrire_faux("ffmpeg", f'case "$*" in *-encoders*) cat "{self.home}/encodeurs.txt" ;; esac\nexit 0')

    def vainfo(self, sortie=None):
        """sortie : texte affiché (succès) ; None : échec (pas de pilote VA pour cette carte)."""
        if sortie is None:
            corps = 'echo "vainfo $*" >> "$JOURNAL"\necho "libva error: vaGetDriverNames() failed" >&2\nexit 1'
        else:
            (self.home / "vainfo.txt").write_text(sortie + "\n")
            corps = f'echo "vainfo $*" >> "$JOURNAL"\ncat "{self.home}/vainfo.txt"\nexit 0'
        self.ecrire_faux("vainfo", corps)

    def arreter_enregistrement(self):
        etat = self.run_dir / "nc-video"
        if etat.exists() and etat.read_text().strip():
            try:
                os.kill(int(etat.read_text().split()[0]), signal.SIGKILL)
            except (ProcessLookupError, ValueError):
                pass

    def lancer(self, **env_plus):
        env = dict(HOME=str(self.home), PATH=str(self.faux), NC_LANGUE="fr", JOURNAL=str(self.journal),
                   XDG_RUNTIME_DIR=str(self.run_dir), XDG_CONFIG_HOME=str(self.home / ".config"),
                   NC_SYSFS=str(self.sysfs), NC_TEST_WF=str(self.wf))
        env.update(env_plus)
        r = subprocess.run([shutil.which("bash"), str(SCRIPT)], env=env, capture_output=True, text=True, timeout=30,
                           stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr + self.journal.read_text())
        appels = [l.rstrip(SEP).split(SEP) for l in self.wf.read_text().splitlines() if l]
        self.assertTrue(appels, "wf-recorder n'a pas été lancé")
        self.assertTrue((self.run_dir / "nc-video").read_text().strip(), "l'île ne verrait pas l'enregistrement")
        return appels

    @staticmethod
    def encodeur(args):
        """Ce qui suit le fichier et le son : -c … et ses paramètres."""
        return args[args.index("-c"):]

    def vainfo_appele(self):
        return [l for l in self.journal.read_text().splitlines() if l.startswith("vainfo ")]

    # ── NVENC ──
    def test_nvidia_carte_des_applis_et_nvenc_connu(self):
        self.carte_des_applis("nvidia")
        self.ffmpeg(nvenc=True)
        self.vainfo(PROFILS_OK)
        appels = self.lancer(AQ_DRM_DEVICES="/dev/dri/card1")
        self.assertEqual(len(appels), 1)
        self.assertEqual(self.encodeur(appels[0]), ["-c", "h264_nvenc", "-p", "preset=p4", "-p", "cq=23"])
        self.assertEqual(appels[0][:2], ["-g", "0,0 2560x1600"])
        self.assertFalse(self.vainfo_appele(), "NVENC choisi : rien d'autre à vérifier")

    def test_nvidia_mais_ffmpeg_sans_nvenc_passe_a_vaapi(self):
        self.carte_des_applis("nvidia")
        self.ffmpeg(nvenc=False)
        self.vainfo(PROFILS_OK)
        appels = self.lancer(AQ_DRM_DEVICES="/dev/dri/card1")
        self.assertEqual(self.encodeur(appels[0]), ["-c", "h264_vaapi", "-d", "/dev/dri/renderD128"])

    def test_sans_ffmpeg_nvenc_jamais_suppose(self):
        self.carte_des_applis("nvidia")
        self.vainfo(PROFILS_OK)
        appels = self.lancer(AQ_DRM_DEVICES="/dev/dri/card1")
        self.assertEqual(self.encodeur(appels[0]), ["-c", "h264_vaapi", "-d", "/dev/dri/renderD128"])

    # ── VAAPI ──
    def test_integree_et_vainfo_ok_bon_render_node(self):
        self.carte_des_applis("integree")
        self.ffmpeg(nvenc=True)
        self.vainfo(PROFILS_OK)
        appels = self.lancer(AQ_DRM_DEVICES="/dev/dri/card1:/dev/dri/card0")
        self.assertEqual(self.encodeur(appels[0]), ["-c", "h264_vaapi", "-d", "/dev/dri/renderD128"])
        self.assertEqual(self.vainfo_appele(), ["vainfo --display drm --device /dev/dri/renderD128"])

    def test_premiere_carte_de_aq_drm_devices_et_non_l_ecran_branche(self):
        self.ffmpeg()
        self.vainfo(PROFILS_OK)
        appels = self.lancer(AQ_DRM_DEVICES="/dev/dri/card0:/dev/dri/card1")
        self.assertEqual(self.encodeur(appels[0]), ["-c", "h264_vaapi", "-d", "/dev/dri/renderD129"])

    def test_lien_vers_la_carte_suivi(self):
        # Wiki Hyprland : un lien udev (/dev/dri/amd-igpu -> card1), les liens by-path ayant des « : »
        dri = self.home / "dev/dri"
        dri.mkdir(parents=True)
        (dri / "card1").touch()
        (dri / "amd-igpu").symlink_to("card1")
        self.ffmpeg()
        self.vainfo(PROFILS_OK)
        appels = self.lancer(AQ_DRM_DEVICES=f"{dri}/amd-igpu:{dri}/card0")
        self.assertEqual(self.encodeur(appels[0]), ["-c", "h264_vaapi", "-d", "/dev/dri/renderD128"])

    def test_sans_aq_drm_devices_la_carte_qui_porte_l_ecran(self):
        self.ffmpeg()
        self.vainfo(PROFILS_OK)
        appels = self.lancer()
        self.assertEqual(self.encodeur(appels[0]), ["-c", "h264_vaapi", "-d", "/dev/dri/renderD128"])

    # ── Repli sur le processeur ──
    def test_vainfo_en_echec_libx264(self):
        self.ffmpeg()
        self.vainfo(None)
        appels = self.lancer(AQ_DRM_DEVICES="/dev/dri/card1")
        self.assertEqual(self.encodeur(appels[0]), ["-c", "libx264", "-p", "preset=veryfast", "-p", "crf=23"])
        self.assertEqual(len(self.vainfo_appele()), 1)

    def test_carte_qui_decode_sans_encoder_libx264(self):
        self.ffmpeg()
        self.vainfo(PROFILS_DECODAGE)
        appels = self.lancer(AQ_DRM_DEVICES="/dev/dri/card1")
        self.assertEqual(self.encodeur(appels[0])[:2], ["-c", "libx264"])

    def test_ffmpeg_sans_vaapi_libx264(self):
        self.ffmpeg(vaapi=False)
        self.vainfo(PROFILS_OK)
        appels = self.lancer(AQ_DRM_DEVICES="/dev/dri/card1")
        self.assertEqual(self.encodeur(appels[0])[:2], ["-c", "libx264"])

    def test_vainfo_absent_libx264_en_auto_vaapi_en_carte(self):
        self.ffmpeg()
        appels = self.lancer(AQ_DRM_DEVICES="/dev/dri/card1")
        self.assertEqual(self.encodeur(appels[0])[:2], ["-c", "libx264"])
        self.arreter_enregistrement()
        self.wf.write_text("")
        self.reglages("VIDEO_ENCODEUR=carte\n")
        appels = self.lancer(AQ_DRM_DEVICES="/dev/dri/card1")
        self.assertEqual(self.encodeur(appels[0]), ["-c", "h264_vaapi", "-d", "/dev/dri/renderD128"])

    def test_ancien_enregistreur_zombie_n_empeche_pas_le_suivant(self):
        """Dans un conteneur sans init qui recueille les orphelins (CI), un enregistreur tué restait zombie : kill -0
        réussissait, nc-video croyait l'enregistrement en cours et « l'arrêtait » au lieu d'en lancer un."""
        mort = subprocess.Popen(["true"])
        self.addCleanup(mort.wait)
        fin = time.monotonic() + 5
        while time.monotonic() < fin and Path(f"/proc/{mort.pid}/stat").read_text().rpartition(")")[2].split()[0] != "Z":
            time.sleep(0.01)
        (self.run_dir / "nc-video").write_text(f"{mort.pid}\n0\n{self.home}/ancien.mp4\n")
        self.ffmpeg()
        appels = self.lancer(AQ_DRM_DEVICES="/dev/dri/card1")
        self.assertEqual(self.encodeur(appels[0])[:2], ["-c", "libx264"])

    def test_pid_reutilise_n_est_pas_notre_enregistreur(self):
        """Après un redémarrage de session, le pid du fichier d'état peut être celui d'un autre processus : il ne doit
        ni passer pour l'enregistrement en cours, ni recevoir le signal d'arrêt (ancien fichier, trois lignes, et
        nouveau, avec l'heure de démarrage d'un autre)."""
        for contenu in ("{pid}\n0\n{home}/ancien.mp4\n", "{pid}\n0\n{home}/ancien.mp4\n1\n"):
            autre = subprocess.Popen(["sleep", "30"])
            self.addCleanup(lambda p=autre: (p.kill(), p.wait()))
            (self.run_dir / "nc-video").write_text(contenu.format(pid=autre.pid, home=self.home))
            self.ffmpeg()
            appels = self.lancer(AQ_DRM_DEVICES="/dev/dri/card1")
            self.assertEqual(self.encodeur(appels[0])[:2], ["-c", "libx264"])
            self.assertIsNone(autre.poll(), "l'autre processus n'a pas à recevoir SIGINT")

    def test_reglage_processeur_libx264(self):
        self.reglages('VIDEO_ENCODEUR="processeur"\n')
        self.carte_des_applis("nvidia")
        self.ffmpeg(nvenc=True)
        self.vainfo(PROFILS_OK)
        appels = self.lancer(AQ_DRM_DEVICES="/dev/dri/card1")
        self.assertEqual(self.encodeur(appels[0]), ["-c", "libx264", "-p", "preset=veryfast", "-p", "crf=23"])
        self.assertFalse(self.vainfo_appele())

    def test_carte_qui_refuse_de_demarrer_repart_sur_le_processeur(self):
        self.ffmpeg()
        self.vainfo(PROFILS_OK)
        appels = self.lancer(AQ_DRM_DEVICES="/dev/dri/card1", NC_TEST_WF_ECHEC="h264_vaapi")
        self.assertEqual([a[a.index("-c") + 1] for a in appels], ["h264_vaapi", "libx264"])
        self.assertNotIn("pas démarré", self.journal.read_text())

    def test_son_garde_avec_l_encodeur_materiel(self):
        self.reglages("VIDEO_SON=micro\n")
        self.ffmpeg()
        self.vainfo(PROFILS_OK)
        appels = self.lancer(AQ_DRM_DEVICES="/dev/dri/card1")
        self.assertIn("--audio", appels[0])
        self.assertEqual(self.encodeur(appels[0]), ["-c", "h264_vaapi", "-d", "/dev/dri/renderD128"])

    # ── Audit E4 : deux appuis pendant slurp, encodeur qui meurt un peu après le départ ──
    def commande(self, **env_plus):
        env = dict(HOME=str(self.home), PATH=str(self.faux), NC_LANGUE="fr", JOURNAL=str(self.journal),
                   XDG_RUNTIME_DIR=str(self.run_dir), XDG_CONFIG_HOME=str(self.home / ".config"),
                   NC_SYSFS=str(self.sysfs), NC_TEST_WF=str(self.wf))
        env.update(env_plus)
        return subprocess.Popen([shutil.which("bash"), str(SCRIPT)], env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True)

    def test_deux_appuis_pendant_slurp_un_seul_enregistrement(self):
        self.ecrire_faux("slurp", 'sleep 1; echo "0,0 2560x1600"')
        premier = self.commande()
        time.sleep(0.3)                      # le 1er attend toujours la zone
        second = self.commande()
        for p in (premier, second):
            sortie = p.communicate(timeout=20)
            self.assertEqual(p.returncode, 0, sortie)
        appels = [l for l in self.wf.read_text().splitlines() if l]
        self.assertEqual(len(appels), 1, appels)
        pid = int((self.run_dir / "nc-video").read_text().split()[0])
        os.kill(pid, 0)                      # l'état désigne bien le seul enregistrement, vivant
        # Le verrou n'est pas gardé par wf-recorder : l'appui suivant arrête, puis un autre redémarre
        arret = self.commande()
        arret.communicate(timeout=20)
        self.assertFalse((self.run_dir / "nc-video").exists())
        redemarre = self.commande()
        redemarre.communicate(timeout=20)
        self.assertEqual(len([l for l in self.wf.read_text().splitlines() if l]), 2)

    def test_encodeur_qui_meurt_apres_une_seconde(self):
        self.reglages("VIDEO_ENCODEUR=processeur\n")
        self.ecrire_faux("wf-recorder", f'''printf '%s{SEP}' "$@" >> "$NC_TEST_WF"; echo >> "$NC_TEST_WF"
sleep 1; echo "encodeur perdu" >&2; exit 1''')
        p = self.commande()
        sortie = p.communicate(timeout=20)
        self.assertEqual(p.returncode, 0, sortie)
        etat = self.run_dir / "nc-video"
        self.assertTrue(etat.read_text().strip(), "à 0,5 s il tourne encore : l'état est écrit")
        for _ in range(60):                  # revérifié vers 2 s, en arrière-plan
            if not etat.exists():
                break
            time.sleep(0.1)
        self.assertFalse(etat.exists(), "pid mort : l'état doit être effacé")
        for _ in range(20):
            if "notify-send" in self.journal.read_text():
                break
            time.sleep(0.1)
        self.assertIn("encodeur perdu", self.journal.read_text())



class PaquetsVA(unittest.TestCase):
    """install.sh : pilotes VA seulement depuis les dépôts de base (rien pour Fedora, qui exigerait RPM Fusion), et
    vainfo, rangés avec wf-recorder."""
    def test_paquet_par_famille(self):
        texte = (REPO / "install.sh").read_text()
        debut = texte.index("pname() {")
        fonction = texte[debut:texte.index("\n}\n", debut) + 3]
        attendu = {"pilotes-va": {"arch": "libva-mesa-driver", "debian": "mesa-va-drivers", "fedora": "", "suse": ""},
                   "vainfo": {"arch": "libva-utils", "debian": "vainfo", "fedora": "libva-utils", "suse": "libva-utils"}}
        for nom, familles in attendu.items():
            for famille, paquet in familles.items():
                r = subprocess.run(["bash", "-c", fonction + f"FAMILY={famille}; pname {nom}"], capture_output=True,
                                   text=True)
                self.assertEqual(r.stdout.strip(), paquet, (nom, famille))
        generic = texte[texte.index("GENERIC=("):texte.index(")", texte.index("GENERIC=("))]
        self.assertIn("wf-recorder pilotes-va vainfo", generic)



if __name__ == "__main__":
    unittest.main()
