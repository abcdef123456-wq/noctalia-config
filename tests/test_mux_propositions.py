"""Portable à MUX (nc-gpu-mode : Hybride ou Dédiée), propositions de nc-profile-sync aux changements d'alimentation :
débranché en Dédiée, une notification [Changer de mode] [Non] (carte de l'île gpuModeVers hybride, sinon nc-reglages
mode-graphique), plus jamais après trois « Non » de suite, rien avec GPU_MUX_AVERTIR=non ; branché en Hybride,
[Passer en Dédiée] [Non] au plus une fois par jour, plus jamais après trois « Non » de suite, rien avec
GPU_MUX_PROPOSER=non. Deux comptes séparés ; remettre un réglage à « oui » (nc-reglages set) relance son rappel.
nc-gpu-mode n'est lu qu'aux changements, une seule fois. En Dédiée, la carte des applis, la question de la session et
le guet de la NVIDIA ne font rien.

Faux gdbus : son « monitor » UPower change l'alimentation du faux /sys (NC_TEST_EVENEMENTS : 0 débranché, 1 branché,
dans l'ordre), annonce chaque changement, puis ferme le flux (le service sort). Faux nc-gpu-mode, nc-reglages, qs,
notify-send (répond le bouton de NC_TEST_CLIC), hyprctl, noctalia, brightnessctl, bluetoothctl : chacun écrit dans un
journal au chemin écrit en dur dans le faux script (dossier temporaire). HOME, XDG_* et /sys temporaires : rien ne
touche au vrai PC, ni la vraie île, ni le vrai mode graphique.
"""
from datetime import date
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-profile-sync"
REGLAGES = REPO / "home/.local/bin/nc-reglages"

# Faux programmes ; @J@ : le journal (chemin absolu du dossier temporaire)
FAUX = {
    "gdbus": 'case "$*" in\n'
             '  *Properties.Get*) echo "(<\'$NC_TEST_PROFIL\'>,)" ;;\n'
             '  *monitor*UPower*)\n'
             '    for e in $NC_TEST_EVENEMENTS; do\n'
             '      sleep 1.2; echo "$e" > "$NC_POWER_SUPPLY/AC/online"; echo "/org/freedesktop/UPower: OnBattery"\n'
             '    done\n'
             '    sleep 1.2 ;;\n'
             'esac\nexit 0',
    "hyprctl": 'echo "hyprctl $*" >> "@J@"\nexit 0',
    "noctalia": "exit 0",
    "brightnessctl": "exit 0",
    "bluetoothctl": "exit 0",
    "nc-gpu-mode": 'echo "nc-gpu-mode $*" >> "@J@"\necho "$NC_TEST_MODE"',
    "nc-reglages": 'echo "nc-reglages $*" >> "@J@"\nexit 0',
    # Le vrai nc-reglages set (groupe energie) relance le service : jamais le vrai systemctl
    "systemctl": 'echo "systemctl $*" >> "@J@"\nexit 0',
    # NC_TEST_QS : ok (l'île répond), arretee (aucune île, comme Quickshell : code 255), inconnue (ancienne île),
    # lente (ne répond pas)
    "qs": 'echo "qs $*" >> "@J@"\n'
          'case "$NC_TEST_QS" in\n'
          '  arretee) echo "No running instances for nc-ile" >&2; exit 255 ;;\n'
          '  inconnue) echo "Function not found." ;;\n'
          '  lente) exec sleep 30 ;;\n'
          'esac\nexit 0',
}
NOTIFY = ("#!/usr/bin/env python3\nimport json, os, sys\n"
          "open('@J@', 'a').write('notify ' + json.dumps(sys.argv[1:], ensure_ascii=False) + '\\n')\n"
          "print(os.environ.get('NC_TEST_CLIC', ''))\n")

DEBRANCHE = "Sur batterie en mode Dédiée : la carte NVIDIA reste allumée, l'autonomie fond. Repasser en mode Hybride ?"
BRANCHE = "Branché : passer en mode Dédiée pour un bureau plus fluide ?"


class Mux(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-mux-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name).resolve()
        self.journal = self.home / "journal"
        self.faux = self.home / "faux"
        self.faux.mkdir()
        for nom, corps in FAUX.items():
            self.programme(nom, "#!/bin/sh\n" + corps + "\n")
        self.programme("notify-send", NOTIFY)
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".config/noctalia").mkdir(parents=True)
        self.reglages("")
        self.run_dir = self.home / "run"
        self.run_dir.mkdir(mode=0o700)
        self.etat = self.home / "state/noctalia-config/gpu-mux"
        self.alim = self.home / "sys/class/power_supply"
        for nom, contenu in (("AC", {"type": "Mains", "online": "1"}), ("BAT0", {"type": "Battery", "capacity": "80"})):
            (self.alim / nom).mkdir(parents=True)
            for k, v in contenu.items():
                (self.alim / nom / k).write_text(v + "\n")
        (self.home / "egl").mkdir()

    def programme(self, nom, texte):
        f = self.faux / nom
        f.write_text(texte.replace("@J@", str(self.journal)))
        f.chmod(0o755)

    def reglages(self, texte):
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\n" + texte)

    def lancer(self, mode, evenements, secteur=True, clic="", qs="ok", **e):
        """Un service : premier passage (alimentation de départ), puis les changements, puis la fin du flux D-Bus."""
        self.journal.write_text("")
        (self.alim / "AC/online").write_text("1\n" if secteur else "0\n")
        env = dict(HOME=str(self.home), PATH=f"{self.faux}:/usr/bin:/bin", NC_LANGUE="fr",
                   XDG_RUNTIME_DIR=str(self.run_dir), XDG_CONFIG_HOME=str(self.home / ".config"),
                   XDG_STATE_HOME=str(self.home / "state"), NC_SYSFS=str(self.home / "sys"),
                   NC_EGL_DIR=str(self.home / "egl"), NC_POWER_SUPPLY=str(self.alim), NC_LEDS=str(self.home / "leds"),
                   NC_GPU_MODE_CMD=str(self.faux / "nc-gpu-mode"), NC_REGLAGES_CMD=str(self.faux / "nc-reglages"),
                   NC_TEST_PROFIL="balanced", NC_TEST_MODE=mode, NC_TEST_EVENEMENTS=evenements, NC_TEST_CLIC=clic,
                   NC_TEST_QS=qs, **e)
        r = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60,
                           stdin=subprocess.DEVNULL)
        self.assertIn("flux D-Bus interrompu", r.stdout, r.stdout + r.stderr)
        self.assertNotIn("command not found", r.stderr)
        self.assertNotIn("erreur", r.stderr.lower())
        return r

    def lignes(self, nom):
        return [l for l in self.journal.read_text().splitlines() if l.startswith(nom + " ")]

    def notifications(self, texte):
        return [n for n in (json.loads(l[len("notify "):]) for l in self.lignes("notify")) if texte in n]

    def etat_vals(self):
        """Le fichier d'état gpu-mux, ligne par ligne (cle=valeur)."""
        if not self.etat.exists():
            return {}
        return dict(l.split("=", 1) for l in self.etat.read_text().splitlines() if "=" in l)

    def nc_reglages(self, *args):
        """Le vrai nc-reglages, HOME temporaire (systemctl et hyprctl : les faux)."""
        env = dict(HOME=str(self.home), PATH=f"{self.faux}:/usr/bin:/bin", NC_LANGUE="fr",
                   XDG_RUNTIME_DIR=str(self.run_dir), XDG_CONFIG_HOME=str(self.home / ".config"),
                   XDG_STATE_HOME=str(self.home / "state"))
        r = subprocess.run(["python3", str(REGLAGES), *args], env=env, capture_output=True, text=True, timeout=60,
                           stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def hier(self):
        """La dernière proposition date d'avant aujourd'hui (le compte des « Non » reste)."""
        t = self.etat.read_text().replace(f"jour={date.today():%Y-%m-%d}", "jour=2000-01-01")
        self.etat.write_text(t)

    # ── Débranchement ──
    def test_debranche_en_dediee_notifie_et_ouvre_l_ile(self):
        self.lancer("dediee", "0", clic="changer")
        n = self.notifications(DEBRANCHE)
        self.assertEqual(len(n), 1, self.journal.read_text())
        self.assertIn("--action=changer=Changer de mode", n[0])
        self.assertIn("--action=non=Non", n[0])
        self.assertEqual(self.lignes("qs"), ["qs -c nc-ile ipc call ile gpuModeVers hybride"])
        self.assertEqual(self.lignes("nc-reglages"), [], "l'île a répondu : pas de repli")
        self.assertEqual(self.etat_vals().get("avertir_non"), "0")

    def test_debranche_sans_clic_rien_ne_change(self):
        self.lancer("dediee", "0")
        self.assertEqual(len(self.notifications(DEBRANCHE)), 1)
        self.assertEqual(self.lignes("qs") + self.lignes("nc-reglages"), [])

    def test_sans_ile_nc_reglages(self):
        # Aucune île (Quickshell : code 255), ancienne île sans gpuModeVers (code 0 et « Function not found. »), île
        # qui ne répond pas (coupée au bout de 5 s)
        for qs in ("arretee", "inconnue", "lente"):
            with self.subTest(qs=qs):
                self.lancer("dediee", "0", clic="changer", qs=qs)
                self.assertEqual(len(self.lignes("qs")), 1)
                self.assertEqual(self.lignes("nc-reglages"), ["nc-reglages mode-graphique"])

    def test_une_notification_par_debranchement(self):
        self.lancer("dediee", "0 1 0")
        self.assertEqual(len(self.notifications(DEBRANCHE)), 2)
        self.assertEqual(self.notifications(BRANCHE), [], "en Dédiée, rien à proposer au branchement")

    def test_trois_non_a_l_avertissement(self):
        # Plus d'avertissement au débranchement, mais la proposition au branchement continue (compte à part)
        for i in range(3):
            self.lancer("dediee", "0", clic="non")
            self.assertEqual(len(self.notifications(DEBRANCHE)), 1, f"avertissement {i + 1}")
            self.assertEqual(self.lignes("qs"), [])
        self.assertEqual(self.etat_vals(), {"avertir_non": "3"})
        self.lancer("dediee", "0")
        self.assertEqual(self.lignes("notify"), [])
        self.assertEqual(self.lignes("nc-gpu-mode"), [], "plus d'avertissement : nc-gpu-mode n'est même pas lu")
        self.lancer("hybride", "1", secteur=False, clic="non")
        self.assertEqual(len(self.notifications(BRANCHE)), 1)
        self.assertEqual(self.etat_vals(), {"avertir_non": "3", "jour": f"{date.today():%Y-%m-%d}", "non": "1"})

    def test_fermee_sans_reponse_ne_compte_pas(self):
        self.lancer("dediee", "0", clic="non")
        self.lancer("dediee", "0", clic="")
        self.assertEqual(self.etat_vals(), {"avertir_non": "1"})

    def test_avertir_non_rien(self):
        self.reglages("GPU_MUX_AVERTIR=non\n")
        self.lancer("dediee", "0")
        self.assertEqual(self.lignes("notify"), [])
        self.assertEqual(self.lignes("nc-gpu-mode"), [])

    def test_proposer_non_avertit_quand_meme(self):
        # L'avertissement est une alerte d'autonomie : GPU_MUX_PROPOSER ne le coupe pas
        self.reglages("GPU_MUX_PROPOSER=non\n")
        self.lancer("dediee", "0")
        self.assertEqual(len(self.notifications(DEBRANCHE)), 1)

    def test_remettre_oui_relance(self):
        auj = f"{date.today():%Y-%m-%d}"
        self.etat.parent.mkdir(parents=True)
        self.etat.write_text(f"jour={auj}\nnon=3\navertir_non=3\n")
        # Déjà « oui » : rien n'est effacé
        self.nc_reglages("set", "GPU_MUX_AVERTIR", "oui")
        self.assertEqual(self.etat_vals(), {"jour": auj, "non": "3", "avertir_non": "3"})
        # GPU_MUX_AVERTIR : non puis oui → son compte seul est effacé, l'avertissement revient
        self.nc_reglages("set", "GPU_MUX_AVERTIR", "non")
        self.assertEqual(self.etat_vals(), {"jour": auj, "non": "3", "avertir_non": "3"})
        self.nc_reglages("set", "GPU_MUX_AVERTIR", "oui")
        self.assertEqual(self.etat_vals(), {"jour": auj, "non": "3"})
        self.assertIn("systemctl --user restart nc-profile-sync.service", self.journal.read_text())
        self.lancer("dediee", "0")
        self.assertEqual(len(self.notifications(DEBRANCHE)), 1)
        self.lancer("hybride", "1", secteur=False)
        self.assertEqual(self.notifications(BRANCHE), [], "la proposition reste muette")
        # GPU_MUX_PROPOSER : non puis oui → la proposition revient, même aujourd'hui ; le compte de l'avertissement reste
        self.nc_reglages("set", "GPU_MUX_PROPOSER", "non")
        self.nc_reglages("set", "GPU_MUX_PROPOSER", "oui")
        self.assertNotIn("non", self.etat_vals())
        self.assertNotIn("jour", self.etat_vals())
        self.lancer("hybride", "1", secteur=False)
        self.assertEqual(len(self.notifications(BRANCHE)), 1)
        # Retour à « oui » par reset (la valeur de la config) : même effet
        self.etat.write_text(f"jour={auj}\nnon=3\n")
        self.nc_reglages("set", "GPU_MUX_PROPOSER", "non")
        self.nc_reglages("reset", "GPU_MUX_PROPOSER")
        self.assertEqual(self.etat_vals(), {})

    def test_debranche_en_hybride_rien(self):
        self.lancer("hybride", "0")
        self.assertEqual(self.lignes("notify"), [])

    def test_demarrage_sur_batterie_rien(self):
        # Le service démarre (nouvelle session) déjà sur batterie : pas un débranchement, nc-gpu-mode n'est pas lu
        self.lancer("dediee", "", secteur=False)
        self.assertEqual(self.lignes("notify"), [])
        self.assertEqual(self.lignes("nc-gpu-mode"), [])

    # ── Branchement ──
    def test_branche_en_hybride_propose_une_fois_par_jour(self):
        self.lancer("hybride", "1 0 1", secteur=False, clic="dediee")
        n = self.notifications(BRANCHE)
        self.assertEqual(len(n), 1, self.journal.read_text())
        self.assertIn("--action=dediee=Passer en Dédiée", n[0])
        self.assertIn("--action=non=Non", n[0])
        self.assertEqual(self.lignes("qs"), ["qs -c nc-ile ipc call ile gpuModeVers dediee"])
        # Même jour, nouveau service (session rouverte) : rien
        self.lancer("hybride", "1", secteur=False)
        self.assertEqual(self.notifications(BRANCHE), [])
        # Le lendemain : de nouveau
        self.hier()
        self.lancer("hybride", "1", secteur=False)
        self.assertEqual(len(self.notifications(BRANCHE)), 1)

    def test_trois_non_de_suite_plus_jamais(self):
        for i in range(3):
            self.lancer("hybride", "1", secteur=False, clic="non")
            self.assertEqual(len(self.notifications(BRANCHE)), 1, f"proposition {i + 1}")
            self.assertEqual(self.lignes("qs"), [])
            self.hier()
        self.assertIn("non=3", self.etat.read_text())
        self.lancer("hybride", "1", secteur=False, clic="non")
        self.assertEqual(self.notifications(BRANCHE), [])
        self.assertEqual(self.lignes("nc-gpu-mode"), [], "plus de proposition : nc-gpu-mode n'est même pas lu")

    def test_non_puis_oui_remet_le_compte(self):
        self.lancer("hybride", "1", secteur=False, clic="non")
        self.hier()
        self.lancer("hybride", "1", secteur=False, clic="non")
        self.hier()
        # Fermée sans réponse : ne compte pas
        self.lancer("hybride", "1", secteur=False, clic="")
        self.assertIn("non=2", self.etat.read_text())
        self.hier()
        self.lancer("hybride", "1", secteur=False, clic="dediee")
        self.assertIn("non=0", self.etat.read_text())

    def test_reglage_non_jamais(self):
        self.reglages("GPU_MUX_PROPOSER=non\n")
        self.lancer("hybride", "1 0 1", secteur=False, clic="dediee")
        self.assertEqual(self.lignes("notify"), [])
        self.assertEqual(self.lignes("qs"), [])
        self.assertFalse(self.etat.exists())

    def test_sans_objet_rien(self):
        self.lancer("sans-objet", "1 0 1 0", secteur=False)
        self.assertEqual(self.lignes("notify"), [])
        self.assertFalse(self.etat.exists())

    # ── nc-gpu-mode : aux changements seulement, une fois ──
    def test_nc_gpu_mode_lu_une_fois(self):
        self.lancer("hybride", "")
        self.assertEqual(self.lignes("nc-gpu-mode"), [], "aucun changement : pas de lecture")
        self.lancer("dediee", "0 1 0 1")
        self.assertEqual(self.lignes("nc-gpu-mode"), ["nc-gpu-mode actuel"])

    def test_en_fond(self):
        # Les notifications à bouton attendent le clic : jamais dans la boucle D-Bus
        source = SCRIPT.read_text()
        for f in ("mux_debranche() {", "mux_branche() {"):
            corps = source[source.index(f):source.index("\n}\n", source.index(f))]
            self.assertIn(") &", corps, f)
            self.assertLess(corps.index("("), corps.index("notify-send"), f)


class Dediee(unittest.TestCase):
    """En Dédiée, session ouverte avec AQ_DRM_DEVICES (par exemple par une autre version d'env-hyprland) : la carte
    des applis, la question « Rouvrir la session » et le guet de la NVIDIA restent muets."""

    def test_gardes(self):
        source = SCRIPT.read_text()
        for f in ("set_gpu_default() {", "proposer_nvidia() {", "guetter_rtx() {"):
            corps = source[source.index(f):source.index("\n}\n", source.index(f))]
            self.assertIn("en_dediee && return 0", corps, f)

    def test_reglage_cache_sans_mux(self):
        texte = REGLAGES.read_text()
        self.assertIn('R("GPU_MUX_PROPOSER", "Énergie"', texte)
        self.assertIn('"GPU_MUX_PROPOSER": "mux"', texte)
        self.assertIn('R("GPU_MUX_AVERTIR", "Énergie"', texte)
        self.assertIn('"GPU_MUX_AVERTIR": "mux"', texte)
        self.assertIn('"mux": True in cartes and existe(sys_ + "/class/drm/card*-eDP-*")', texte)


if __name__ == "__main__":
    unittest.main()
