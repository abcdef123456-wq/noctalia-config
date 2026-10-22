"""La NVIDIA d'un PC hybride doit dormir (0 W) quand rien ne s'en sert : nc-rtx-veille (état en JSON, causes :
nvidia-persistenced, processus qui tiennent /dev/nvidia* ou le render node trouvé par /dev/dri/by-path, alertes une
fois par cause, relance sur la carte intégrée seulement après un clic), sa section « RTX » dans nc-diag, le guet de
nc-profile-sync (30 s, sans bloquer la boucle) et la question d'install.sh sur nvidia-persistenced (portable hybride
seulement).

Rien ne touche au vrai PC : faux /sys (NC_SYSFS), faux /proc (NC_PROC), faux /dev (NC_DEV), faux pilotes EGL
(NC_EGL_DIR) ; faux systemctl, notify-send, nvidia-smi, gdbus, hyprctl et systemd-run en tête du PATH ; HOME et
XDG_RUNTIME_DIR temporaires. Le seul vrai processus touché est un « sleep » lancé par le test lui-même.
"""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
VEILLE = BIN / "nc-rtx-veille"
PROFILE_SYNC = BIN / "nc-profile-sync"
DIAG = BIN / "nc-diag"
INSTALL = (REPO / "install.sh").read_text()
BUS = "0000:01:00.0"

FAUX = {
    # nvidia-persistenced actif ou non (NC_TEST_PERSIST), activé ou non (NC_TEST_PERSIST_ACTIVE)
    "systemctl": 'echo "systemctl $*" >> "$JOURNAL"\n'
                 'case "$*" in\n'
                 '  "is-active nvidia-persistenced") echo "${NC_TEST_PERSIST:-inactive}"; [ "$NC_TEST_PERSIST" = active ] ;;\n'
                 '  "is-enabled nvidia-persistenced") echo "${NC_TEST_PERSIST_ACTIVE:-disabled}"; [ "$NC_TEST_PERSIST_ACTIVE" = enabled ] ;;\n'
                 '  *) exit 1 ;;\nesac',
    "nvidia-smi": 'echo "nvidia-smi $*" >> "$JOURNAL"\necho 5.60',
    "gdbus": 'case "$*" in *Properties.Get*) echo "(<\'$NC_TEST_PROFIL\'>,)" ;; esac\nexit 0',
    "hyprctl": 'echo "hyprctl $*" >> "$JOURNAL"\nexit 0',
    "noctalia": "exit 0",
    "brightnessctl": "exit 0",
    "bluetoothctl": "exit 0",
    # Jamais de vraie scope systemd : la commande est lancée telle quelle
    "systemd-run": 'echo "systemd-run $*" >> "$JOURNAL"\nwhile [ "$1" != -- ]; do shift; done; shift\nexec "$@"',
}
# Fausse notify-send : une ligne JSON par appel, répond l'action « cliquée » (NC_TEST_CLIC, vide : fermée)
NOTIFY = ("#!/usr/bin/env python3\nimport json, os, sys\n"
          "open(os.environ['JOURNAL'], 'a').write('notify ' + json.dumps(sys.argv[1:], ensure_ascii=False) + '\\n')\n"
          "print(os.environ.get('NC_TEST_CLIC', ''))\n")


def charger_diag():
    """nc-diag comme module (sa section RTX seule), en français."""
    with mock.patch.dict(os.environ, NC_LANGUE="fr"):
        chargeur = importlib.machinery.SourceFileLoader("nc_diag_rtx", str(DIAG))
        spec = importlib.util.spec_from_loader("nc_diag_rtx", chargeur)
        m = importlib.util.module_from_spec(spec)
        chargeur.exec_module(m)
    return m


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-rtx-veille-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name).resolve()
        self.faux = self.home / "faux"
        self.faux.mkdir()
        for nom, corps in FAUX.items():
            self.programme(nom, "#!/bin/sh\n" + corps + "\n")
        self.programme("notify-send", NOTIFY)
        (self.home / ".local/bin").mkdir(parents=True)
        (self.home / ".local/bin/nc-langue").symlink_to(BIN / "nc-langue")
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\n")
        self.run_dir = self.home / "run"
        self.run_dir.mkdir(mode=0o700)
        self.journal = self.home / "journal"
        self.journal.write_text("")
        self.sys, self.proc, self.dev, self.egl = (self.home / n for n in ("sys", "proc", "dev", "egl"))
        self.egl.mkdir()
        for f in ("10_nvidia.json", "50_mesa.json"):
            (self.egl / f).write_text("{}\n")
        self.portable_hybride()
        self.etat_carte("suspended")
        self.ecrire(self.proc / "driver/nvidia/params", "ResmanDebugLevel: 4294967295\nDynamicPowerManagement: 3")
        # Nœuds DRM : la carte AMD (renderD128) et la NVIDIA (renderD129), liens by-path relatifs comme udev
        for n in ("renderD128", "renderD129", "card0", "card1"):
            self.ecrire(self.dev / "dri" / n, "")
        bp = self.dev / "dri/by-path"
        bp.mkdir(parents=True)
        (bp / f"pci-{BUS}-render").symlink_to("../renderD129")
        (bp / f"pci-{BUS}-card").symlink_to("../card0")
        (bp / "pci-0000:05:00.0-render").symlink_to("../renderD128")
        self.env_base = dict(
            HOME=str(self.home), PATH=f"{self.faux}:/usr/bin:/bin", NC_LANGUE="fr", JOURNAL=str(self.journal),
            XDG_RUNTIME_DIR=str(self.run_dir), XDG_CONFIG_HOME=str(self.home / ".config"),
            NC_SYSFS=str(self.sys), NC_PROC=str(self.proc), NC_DEV=str(self.dev), NC_EGL_DIR=str(self.egl),
            NC_TEST_PROFIL="power-saver", WAYLAND_DISPLAY="faux-wayland")

    # --- faux système ---
    def programme(self, nom, texte):
        f = self.faux / nom
        f.write_text(texte)
        f.chmod(0o755)

    def ecrire(self, chemin, texte):
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte + ("\n" if texte else ""))

    def portable_hybride(self, batterie=True, ecran_sur_nvidia=False, nvidia=True):
        """Carte AMD intégrée (0000:05:00.0, card1) et NVIDIA (0000:01:00.0, card0), écran interne sur l'une des deux."""
        pci = self.sys / "bus/pci/devices"
        cartes = [("0000:05:00.0", "0x1002", "card1")] + ([(BUS, "0x10de", "card0")] if nvidia else [])
        for bus, vendeur, carte in cartes:
            self.ecrire(pci / bus / "class", "0x030000")
            self.ecrire(pci / bus / "vendor", vendeur)
            self.ecrire(self.sys / "class/drm" / carte / "device/vendor", vendeur)
        if nvidia:
            self.ecrire(pci / BUS / "power/control", "auto")
            (self.sys / "bus/pci/drivers/nvidia").mkdir(parents=True)
            (pci / BUS / "driver").symlink_to(self.sys / "bus/pci/drivers/nvidia")
        sur = "card0" if ecran_sur_nvidia else "card1"
        self.ecrire(self.sys / "class/drm" / f"{sur}-eDP-1/status", "connected")
        alim = self.sys / "class/power_supply"
        self.ecrire(alim / "AC/type", "Mains")
        self.ecrire(alim / "AC/online", "0")
        if batterie:
            self.ecrire(alim / "BAT0/type", "Battery")
            self.ecrire(alim / "BAT0/capacity", "80")

    def etat_carte(self, etat):
        self.ecrire(self.sys / "bus/pci/devices" / BUS / "power/runtime_status", etat)

    def processus(self, pid, comm, fichiers, ppid=1, exe="/usr/lib/firefox/firefox", debut="777", environ=None, cmdline=None):
        p = self.proc / str(pid)
        (p / "fd").mkdir(parents=True)
        self.ecrire(p / "comm", comm)
        (p / "cmdline").write_bytes(b"\0".join(x.encode() for x in (cmdline or [exe])) + b"\0")
        # Champ 22 (début) : 20e après le nom entre parenthèses
        (p / "stat").write_text(f"{pid} ({comm}) S {ppid} " + " ".join(["0"] * 17) + f" {debut} 0 0\n")
        (p / "exe").symlink_to(exe)
        (p / "cwd").symlink_to(self.home)
        (p / "environ").write_bytes(b"\0".join(f"{k}={v}".encode() for k, v in (environ or {}).items()) + b"\0")
        for i, f in enumerate(fichiers, start=3):
            (p / "fd" / str(i)).symlink_to(f)
        (p / "fd/0").symlink_to("/dev/null")

    # --- lancements ---
    def env(self, **e):
        base = dict(self.env_base)
        base.update(e)
        return base

    def veille(self, *args, **e):
        return subprocess.run([str(VEILLE), *args], env=self.env(**e), capture_output=True, text=True, timeout=60,
                              stdin=subprocess.DEVNULL)

    def etat(self, *args, **e):
        r = self.veille("etat", *args, **e)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def notifications(self):
        return [json.loads(l[len("notify "):]) for l in self.journal.read_text().splitlines() if l.startswith("notify ")]

    def appels(self, nom):
        return [l for l in self.journal.read_text().splitlines() if l.startswith(nom + " ")]


class Etat(Base):
    def test_suspendue_rien(self):
        # Même avec nvidia-persistenced et une appli dessus : endormie, rien à dire ni à signaler
        self.processus(4242, "firefox", [str(self.dev / "nvidia0")])
        e = self.etat(NC_TEST_PERSIST="active")
        self.assertTrue(e["hybride"])
        self.assertEqual((e["runtime_status"], e["mode"], e["causes"]), ("suspended", "hybride", []))
        self.assertTrue(e["doit_dormir"])
        r = self.veille("alerter", NC_TEST_PERSIST="active")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.notifications(), [])

    def test_nvidia_smi_jamais_sur_carte_endormie(self):
        self.etat("--conso")
        self.assertEqual(self.appels("nvidia-smi"), [], "nvidia-smi réveillerait la carte")
        charger = charger_diag()
        with mock.patch.dict(os.environ, self.env()):
            b = charger.Bilan(False)
            charger.rtx(b)
        self.assertEqual(self.appels("nvidia-smi"), [])
        # Déjà allumée : la consommation est lue
        self.etat_carte("active")
        e = self.etat("--conso")
        self.assertEqual(e["conso"], "5.6 W")
        self.assertEqual(len(self.appels("nvidia-smi")), 1)

    def test_active_persistenced(self):
        self.etat_carte("active")
        e = self.etat(NC_TEST_PERSIST="active")
        self.assertTrue(e["persistenced"])
        self.assertEqual(e["causes"][0]["cle"], "persistenced")
        self.assertEqual(e["causes"][0]["texte"], "nvidia-persistenced garde la carte NVIDIA allumée")

    def test_active_processus_nvidia0(self):
        self.etat_carte("active")
        # Firefox et son « GPU Process » (même programme) : une seule appli, au nom du parent
        self.processus(4242, "firefox", [str(self.dev / "nvidia0")])
        self.processus(4250, "GPU Process", [str(self.dev / "nvidiactl")], ppid=4242)
        self.processus(5000, "bash", ["/dev/pts/1"], exe="/usr/bin/bash")       # rien sur la NVIDIA : ignoré
        e = self.etat()
        self.assertEqual(len(e["processus"]), 1, e["processus"])
        p = e["processus"][0]
        self.assertEqual((p["pid"], p["comm"], p["nom"], p["pids"]), (4242, "firefox", "Firefox", [4242, 4250]))
        self.assertEqual(p["fichiers"], ["/dev/nvidia0", "/dev/nvidiactl"])
        self.assertEqual([c["texte"] for c in e["causes"]], ["Firefox utilise la carte NVIDIA"])

    def test_render_node_par_by_path(self):
        self.etat_carte("active")
        self.processus(6000, "mpv", [str(self.dev / "dri/renderD129")], exe="/usr/bin/mpv")
        self.processus(6001, "kitty", [str(self.dev / "dri/renderD128")], exe="/usr/bin/kitty")   # carte AMD
        e = self.etat()
        self.assertEqual([(p["comm"], p["fichiers"]) for p in e["processus"]], [("mpv", ["/dev/dri/renderD129"])])
        # Le render node vient du lien by-path : un autre numéro est suivi sans rien coder en dur
        bp = self.dev / f"dri/by-path/pci-{BUS}-render"
        bp.unlink()
        bp.symlink_to("../renderD128")
        e = self.etat()
        self.assertEqual([p["comm"] for p in e["processus"]], ["kitty"])

    def test_sans_cause_trouvee(self):
        self.etat_carte("active")
        e = self.etat()
        self.assertEqual([c["cle"] for c in e["causes"]], ["inconnue"])
        self.ecrire(self.sys / "bus/pci/devices" / BUS / "power/control", "on")
        e = self.etat()
        self.assertEqual([c["cle"] for c in e["causes"]], ["control"])

    def test_pc_non_hybride(self):
        for f in self.egl.iterdir():
            f.unlink()
        e = self.etat()
        self.assertFalse(e["hybride"])
        self.assertIsNone(e["runtime_status"])

    def test_regle_secteur_performance(self):
        self.etat_carte("active")
        self.ecrire(self.sys / "class/power_supply/AC/online", "1")
        e = self.etat(NC_TEST_PROFIL="performance")
        self.assertTrue(e["rtx_voulue"])
        self.assertFalse(e["doit_dormir"])
        # Mode Dédiée (écran interne sur la NVIDIA) : jamais « doit dormir »
        (self.sys / "class/drm/card1-eDP-1/status").write_text("disconnected\n")
        self.ecrire(self.sys / "class/drm/card0-eDP-1/status", "connected")
        e = self.etat()
        self.assertEqual(e["mode"], "dediee")
        self.assertFalse(e["doit_dormir"])


class Alertes(Base):
    def test_persistenced_une_fois(self):
        self.etat_carte("active")
        self.veille("alerter", NC_TEST_PERSIST="active")
        n = self.notifications()
        self.assertEqual(len(n), 1, n)
        self.assertIn("nvidia-persistenced garde la carte NVIDIA allumée", n[0])
        self.assertNotIn("-A", n[0])
        self.veille("alerter", NC_TEST_PERSIST="active")
        self.assertEqual(len(self.notifications()), 1, "une seule fois par cause")

    def test_processus_propose_la_relance_sans_rien_fermer(self):
        self.etat_carte("active")
        self.processus(4242, "firefox", [str(self.dev / "nvidia0")])
        self.processus(4243, "firefox", [str(self.dev / "nvidia0")])          # deux fenêtres : une seule alerte
        r = self.veille("alerter")
        self.assertEqual(r.returncode, 0, r.stderr)
        n = self.notifications()
        self.assertEqual(len(n), 1, n)
        self.assertIn("Firefox utilise la carte NVIDIA", n[0])
        self.assertIn("relancer=Relancer Firefox sur la carte intégrée", n[0])
        # Bouton non cliqué : aucune confirmation demandée, rien de lancé
        self.assertEqual(self.appels("systemd-run"), [])

    def test_rien_en_performance_sur_secteur(self):
        self.etat_carte("active")
        self.ecrire(self.sys / "class/power_supply/AC/online", "1")
        self.veille("alerter", NC_TEST_PERSIST="active", NC_TEST_PROFIL="balanced")
        self.assertEqual(self.notifications(), [])

    def test_rien_en_mode_dediee(self):
        # Mode Dédiée (écran interne sur la NVIDIA) : elle porte l'écran, rester allumée est normal. Même en Économie
        # sur batterie, avec nvidia-persistenced et une appli dessus : aucune alerte, rien de noté
        (self.sys / "class/drm/card1-eDP-1/status").write_text("disconnected\n")
        self.ecrire(self.sys / "class/drm/card0-eDP-1/status", "connected")
        self.etat_carte("active")
        self.processus(4242, "firefox", [str(self.dev / "nvidia0")])
        r = self.veille("alerter", NC_TEST_PERSIST="active")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertEqual(self.notifications(), [])
        self.assertFalse((self.run_dir / "nc-rtx-alertes").exists())


class Relance(Base):
    def vrai_sleep(self):
        """Un vrai « sleep » orphelin (repris par init, donc ramassé dès sa fin) ; tué au besoin à la fin du test."""
        r = subprocess.run(["sh", "-c", "sleep 300 >/dev/null 2>&1 & echo $!"], capture_output=True, text=True)
        pid = int(r.stdout)
        self.addCleanup(lambda: subprocess.run(["kill", str(pid)], capture_output=True))
        return pid

    def preparer(self):
        pid = self.vrai_sleep()
        sortie = self.home / "relance.env"
        env = {"PATH": f"{self.faux}:/usr/bin:/bin", "JOURNAL": str(self.journal), "SORTIE": str(sortie),
               "__NV_PRIME_RENDER_OFFLOAD": "1",
               "__GLX_VENDOR_LIBRARY_NAME": "nvidia", "__VK_LAYER_NV_optimus": "NVIDIA_only",
               "__EGL_VENDOR_LIBRARY_FILENAMES": f"{self.egl}/10_nvidia.json:{self.egl}/50_mesa.json"}
        self.processus(pid, "firefox", [str(self.dev / "nvidia0")], debut="999", environ=env,
                       cmdline=["sh", "-c", 'env > "$SORTIE.tmp" && mv "$SORTIE.tmp" "$SORTIE"'])
        return pid, sortie

    def vivant(self, pid):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        etat = Path(f"/proc/{pid}/stat").read_text()
        return etat[etat.rfind(")") + 2] != "Z"

    def test_sans_clic_rien_ne_ferme(self):
        pid, sortie = self.preparer()
        r = self.veille("relancer", str(pid), "999", NC_TEST_CLIC="")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.vivant(pid), "fermé sans clic")
        self.assertFalse(sortie.exists())
        self.assertIn("Relancer Firefox sur la carte intégrée ?", json.dumps(self.notifications(), ensure_ascii=False))

    def test_processus_change_rien(self):
        pid, sortie = self.preparer()
        r = self.veille("relancer", str(pid), "123", NC_TEST_CLIC="oui")        # autre début : PID réutilisé
        self.assertEqual(r.returncode, 1)
        self.assertTrue(self.vivant(pid))
        self.assertEqual(self.notifications(), [])

    def test_clic_relance_sur_la_carte_integree(self):
        pid, sortie = self.preparer()
        r = self.veille("relancer", str(pid), "999", NC_TEST_CLIC="oui", NC_RTX_ATTENTE="10")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(self.vivant(pid))
        fin = time.monotonic() + 10
        while not sortie.exists() and time.monotonic() < fin:
            time.sleep(0.1)
        env = dict(l.split("=", 1) for l in sortie.read_text().splitlines() if "=" in l)
        self.assertEqual(env["__NV_PRIME_RENDER_OFFLOAD"], "0")
        self.assertEqual(env["__GLX_VENDOR_LIBRARY_NAME"], "mesa")
        self.assertEqual(env["__EGL_VENDOR_LIBRARY_FILENAMES"], f"{self.egl}/50_mesa.json")
        self.assertEqual(env["SORTIE"], str(sortie))                             # le reste de son environnement
        self.assertEqual(len(self.appels("systemd-run")), 1)


class Diag(Base):
    def bilan(self, **e):
        m = charger_diag()
        with mock.patch.dict(os.environ, self.env(**e)):
            b = m.Bilan(False)
            m.rtx(b)
        return b

    def test_tout_va_bien_rien_en_mode_court(self):
        b = self.bilan()
        self.assertIn("RTX", b.texte())
        self.assertIn("carte NVIDIA endormie (0 W)", b.texte())
        self.assertIn("DynamicPowerManagement = 3", b.texte())
        self.assertEqual(b.texte(court=True), "")

    def test_persistenced_sur_batterie_une_ligne(self):
        self.etat_carte("active")
        b = self.bilan(NC_TEST_PERSIST="active")
        court = [l for l in b.texte(court=True).splitlines() if l.strip().startswith("!")]
        self.assertEqual(len(court), 1, b.texte(court=True))
        self.assertIn("nvidia-persistenced garde la carte NVIDIA allumée", court[0])
        self.assertIn("5.6 W", court[0])

    def test_persistenced_actif_carte_endormie_signale(self):
        # Rare (le service a été lancé après coup), mais il l'empêchera de dormir : signalé sur un portable
        b = self.bilan(NC_TEST_PERSIST="active")
        self.assertIn("nvidia-persistenced actif", b.texte(court=True))

    def test_processus_sur_batterie(self):
        self.etat_carte("active")
        self.processus(4242, "firefox", [str(self.dev / "nvidia0")])
        b = self.bilan()
        self.assertIn("Firefox utilise la carte NVIDIA", b.texte(court=True))
        self.assertIn("relance Firefox sur la carte intégrée", b.texte(court=True))

    def test_pilote_nouveau(self):
        (self.proc / "driver/nvidia/params").unlink()
        (self.sys / "bus/pci/devices" / BUS / "driver").unlink()
        (self.sys / "bus/pci/devices" / BUS / "driver").symlink_to(self.sys / "bus/pci/drivers/nouveau")
        b = self.bilan()
        self.assertIn("pilote nouveau : pas de /proc/driver/nvidia", b.texte())
        self.assertEqual(b.texte(court=True), "")

    def test_absente_hors_pc_hybride(self):
        for f in self.egl.iterdir():
            f.unlink()
        self.assertEqual(self.bilan().texte(), "")

    def test_mode_dediee(self):
        (self.sys / "class/drm/card1-eDP-1/status").write_text("disconnected\n")
        self.ecrire(self.sys / "class/drm/card0-eDP-1/status", "connected")
        self.etat_carte("active")
        b = self.bilan(NC_TEST_PERSIST="active")
        self.assertIn("mode Dédiée", b.texte())
        self.assertEqual(b.texte(court=True), "")


class ProfileSync(Base):
    def lancer(self, **e):
        env = self.env(**dict(dict(NC_POWER_SUPPLY=str(self.sys / "class/power_supply"), NC_LEDS=str(self.home / "leds"),
                                   AQ_DRM_DEVICES="/dev/dri/card1", NC_RTX_DELAI="0"), **e))
        r = subprocess.run(["bash", str(PROFILE_SYNC)], env=env, capture_output=True, text=True, timeout=60,
                           stdin=subprocess.DEVNULL)
        self.assertIn("flux D-Bus interrompu", r.stdout, r.stdout + r.stderr)
        return r

    def test_active_persistenced_notifie(self):
        self.etat_carte("active")
        r = self.lancer(NC_TEST_PERSIST="active")
        n = self.notifications()
        self.assertEqual(len(n), 1, r.stdout + r.stderr)
        self.assertIn("nvidia-persistenced garde la carte NVIDIA allumée", n[0])
        self.assertIn("nvidia-persistenced garde la carte NVIDIA allumée", r.stdout)   # dans le journal du service
        self.lancer(NC_TEST_PERSIST="active")
        self.assertEqual(len(self.notifications()), 1, "une seule fois par cause")

    def test_suspendue_aucun_guet(self):
        self.lancer(NC_TEST_PERSIST="active")
        self.assertEqual(self.notifications(), [])
        self.assertEqual(self.appels("systemctl"), [], "nc-rtx-veille n'est même pas lancé")
        self.assertEqual(self.appels("nvidia-smi"), [])

    def test_regle_veut_la_nvidia_rien(self):
        self.etat_carte("active")
        self.ecrire(self.sys / "class/power_supply/AC/online", "1")
        self.lancer(NC_TEST_PERSIST="active", NC_TEST_PROFIL="balanced")
        self.assertEqual(self.notifications(), [])

    def test_session_non_ouverte_par_env_hyprland_rien(self):
        self.etat_carte("active")
        self.lancer(NC_TEST_PERSIST="active", AQ_DRM_DEVICES="")
        self.assertEqual(self.notifications(), [])

    def test_mode_dediee_aucun_guet(self):
        # En Dédiée, même si la session a été ouverte avec AQ_DRM_DEVICES : ni guet, ni carte des applis, ni alerte
        (self.sys / "class/drm/card1-eDP-1/status").write_text("disconnected\n")
        self.ecrire(self.sys / "class/drm/card0-eDP-1/status", "connected")
        self.etat_carte("active")
        r = self.lancer(NC_TEST_PERSIST="active", AQ_DRM_DEVICES="/dev/dri/card0")
        self.assertEqual(self.notifications(), [])
        self.assertEqual(self.appels("systemctl"), [], "nc-rtx-veille n'est même pas lancé")
        self.assertNotIn("hl.env", self.journal.read_text(), "la carte des applis ne change pas")
        self.assertFalse((self.run_dir / "nc-gpu-default").exists())
        self.assertNotIn("en_dediee", r.stderr)
        self.assertNotIn("nc-gpu-mode", r.stderr)

    def test_guet_en_fond(self):
        # Le minuteur ne bloque pas le service : avec 30 s d'attente, le passage finit tout de suite
        self.etat_carte("active")
        source = PROFILE_SYNC.read_text()
        guet = source[source.index("guetter_rtx() {"):source.index("\n}\n", source.index("guetter_rtx() {"))]
        self.assertIn('sleep "$RTX_DELAI"', guet)
        self.assertIn(") &", guet)
        self.assertIn('"$RTX_VEILLE" alerter &', guet)
        self.assertIn('RTX_DELAI="${NC_RTX_DELAI:-30}"', source)


class Install(Base):
    def decision(self, **e):
        debut = INSTALL.index("persistenced_a_proposer() {")
        fonction = INSTALL[debut:INSTALL.index("\n}\n", debut) + 3]
        code = f'set -euo pipefail\nREPO="{REPO}"\n{fonction}\nif persistenced_a_proposer; then echo oui; else echo non; fi'
        r = subprocess.run(["bash", "-c", code], env=self.env(**e), capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip() == "oui"

    def test_portable_hybride_active(self):
        self.assertTrue(self.decision(NC_TEST_PERSIST_ACTIVE="enabled"))
        self.assertIn("systemctl is-enabled nvidia-persistenced", self.journal.read_text())

    def test_service_desactive(self):
        self.assertFalse(self.decision(NC_TEST_PERSIST_ACTIVE="disabled"))

    def test_pc_fixe(self):
        for f in ("type", "capacity"):
            (self.sys / "class/power_supply/BAT0" / f).unlink()
        (self.sys / "class/power_supply/BAT0").rmdir()
        self.assertFalse(self.decision(NC_TEST_PERSIST_ACTIVE="enabled"))

    def test_mode_dediee(self):
        (self.sys / "class/drm/card1-eDP-1/status").write_text("disconnected\n")
        self.ecrire(self.sys / "class/drm/card0-eDP-1/status", "connected")
        self.assertFalse(self.decision(NC_TEST_PERSIST_ACTIVE="enabled"))

    def test_sans_nvidia(self):
        d = Path(tempfile.mkdtemp(prefix="nc-rtx-sans-", dir=self.home))
        self.sys = d / "sys"
        self.portable_hybride(nvidia=False)
        self.assertFalse(self.decision(NC_SYSFS=str(self.sys), NC_TEST_PERSIST_ACTIVE="enabled"))

    def test_question_jamais_en_silence(self):
        # La question passe par ask (affichée, réponse par défaut annoncée sans terminal), puis sudo systemctl
        debut = INSTALL.index("if persistenced_a_proposer; then")
        etape = INSTALL[debut:debut + 900]
        self.assertIn('ask "$(t "La carte NVIDIA reste allumée même inutilisée (environ 5 W) : couper le service '
                      'nvidia-persistenced ?"', etape)
        self.assertIn("sudo systemctl disable --now nvidia-persistenced", etape)
        self.assertLess(etape.index("ask "), etape.index("sudo systemctl"))
        # Dans les étapes système (5e, carte NVIDIA), donc jamais avec --no-system ni --files-only
        self.assertGreater(debut, INSTALL.index('say "$(t "5e. Carte NVIDIA"'))
        self.assertGreater(debut, INSTALL.index('if [ "$MODE" = full ]; then'))


if __name__ == "__main__":
    unittest.main()
