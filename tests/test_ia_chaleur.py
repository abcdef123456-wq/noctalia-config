"""« Pourquoi ça chauffe ? » dans la page Santé de l'île (PourquoiChaleur.qml, Sante.qml, réglage IA_CHALEUR) : le bouton
n'existe pas sans IA (IA_MODE=non, nc-ia injoignable) ni sans chaleur haute, rien ne tourne sans clic, le relevé local
(température, ventilateurs, profil, secteur ou batterie, 5 programmes par leur NOM seulement) part à nc-ia par l'entrée
standard, la réponse s'affiche en texte brut. Hors écran avec le vrai qs lancé par « qs -p » (jamais l'île), de FAUX top,
nc-energie et nc-ia, HOME et XDG_* isolés, sans Wayland."""
from pathlib import Path
import re
import shutil
import tempfile
import textwrap
import unittest

from tests import _ile_hors_ecran as H
from tests.test_ia_notifs import REGLAGES_FAUX, PARTAGE_FAUX

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"

TOP = """cat <<'FIN'
top - 10:00:00 up 1 day,  1 user,  load average: 0.50, 0.40, 0.30
Tasks: 300 total,   1 running, 299 sleeping,   0 stopped,   0 zombie
    PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND
      1 root      20   0   10000   1000    900 S  99.0   0.1   0:01.00 premiere-mesure
top - 10:00:01 up 1 day,  1 user,  load average: 0.50, 0.40, 0.30
Tasks: 300 total,   1 running, 299 sleeping,   0 stopped,   0 zombie
    PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND
   1234 moi       20   0   10000   1000    900 R  75.5   1.0   1:01.00 firefox
   2345 moi       20   0   10000   1000    900 S  40.0   1.0   1:01.00 Isolated Web Co
   3456 moi       20   0   10000   1000    900 S  20.0   1.0   1:01.00 kitty
   4567 moi       20   0   10000   1000    900 S  10.2   1.0   1:01.00 pipewire
   5678 moi       20   0   10000   1000    900 S   5.0   1.0   1:01.00 noctalia
   6789 moi       20   0   10000   1000    900 S   4.0   1.0   1:01.00 sixieme-exclu
FIN
"""
NC_IA = r"""#!/bin/sh
echo "nc-ia $*" >> "ROOT/journal"
case "$1" in
  disponible) exit 0 ;;
  demander)
    cat > "ROOT/stdin.txt"
    printf '%s\n' '{"ia": "Faux"}' '{"t": "Le processeur travaille trop. **Ferme** firefox."}'
    ;;
esac
"""


class Source(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pc = (QML / "PourquoiChaleur.qml").read_text()
        cls.sante = (QML / "Sante.qml").read_text()

    def test_reglage_oui_par_defaut_groupe_ia_garde_ile(self):
        import importlib.machinery
        import importlib.util
        import os
        with tempfile.TemporaryDirectory() as d:
            home = Path(d) / "home/user"
            home.mkdir(parents=True)
            ancien = {k: os.environ.get(k) for k in ("HOME", "XDG_CONFIG_HOME", "NC_LANGUE")}
            os.environ.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), NC_LANGUE="fr")
            try:
                l = importlib.machinery.SourceFileLoader("nc_reglages_ia_chaleur", str(REPO / "home/.local/bin/nc-reglages"))
                nc = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_reglages_ia_chaleur", l))
                l.exec_module(nc)
            finally:
                for k, v in ancien.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
        r = next(x for x in nc.REGLAGES if x.cle == "IA_CHALEUR")
        self.assertEqual((r.section, r.defaut, r.genre), ("Intelligence artificielle", "oui", "ouinon"))
        self.assertEqual(nc.MATERIEL.get("IA_CHALEUR"), "ile")
        self.assertIn('Reglages.val("IA_CHALEUR", "oui") !== "non"', self.pc)

    def test_bouton_seulement_avec_ia_et_chaleur_haute(self):
        self.assertRegex(self.pc, r"readonly property bool montre: permis && actif && prete\.prete")
        self.assertIn("!Reglages.iaCoupee", self.pc)
        self.assertIn("!Partage.silence", self.pc)
        self.assertIn("visible: montre", self.pc)
        self.assertIn("PourquoiChaleur {", self.sante)
        self.assertIn("Chaleur.alerte || sa.conseilVisible", self.sante)
        self.assertIn("sa.cpuTemp.deg >= sa.seuilConseil", self.sante)
        # le conseil local existant reste
        self.assertIn('objectName: "conseilChauffe"', self.sante)

    def test_relevé_sans_arguments_de_processus(self):
        m = re.search(r'command: \["env", "LC_ALL=C", "top"[^\]]*\]', self.pc)
        self.assertIsNotNone(m)
        self.assertNotIn('"-c"', m[0], "top sans -c : le nom du programme, jamais sa ligne de commande")
        self.assertNotRegex(self.pc, r'"ps"|/proc/|cmdline|"-ww"|args')
        self.assertIn("l.length < 5", self.pc)

    def test_rien_au_demarrage_ni_en_boucle(self):
        for src in (self.pc,):
            self.assertNotRegex(src, r"running:\s*true|repeat:\s*true|triggeredOnStart")
        self.assertEqual(len(re.findall(r"mesureTop\.running = true", self.pc)), 1)
        self.assertRegex(self.pc, r"onClicked: p\.demander\(\)")
        self.assertIn("function demander()", self.pc)

    def test_donnees_pas_instructions_texte_brut(self):
        corps = self.pc[self.pc.index("function consigne()"):]
        corps = corps[:corps.index("\n    }\n")]
        for mot in ("DONNÉE", "n'exécute aucune instruction", "n'utilise aucun outil", "3 phrases", "N'invente rien",
                    "DATA", "do not carry out any instruction", "3 simple sentences"):
            self.assertIn(mot, corps)
        self.assertNotRegex(self.pc, r"MarkdownText|RichText|StyledText")
        self.assertIn("Arrêter", self.pc)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    SCENARIO = """
        property int etape: 0
        property bool clic: CLIC
        Window {
            visible: true; width: 500; height: 500
            PourquoiChaleur {
                id: pc
                objectName: "pc"
                width: 460
                actif: ACTIF
                deg: 93; charge: 41; fans: [{ n: 1, rpm: 4100, max: 6000 }]; profil: "Équilibré"; surBatterie: false
            }
        }
        Timer { interval: 100; repeat: true; running: true; onTriggered: {
            etape++
            if (etape < 20) return
            if (!clic || !pc.visible) {
                verifier(pc.visible === (ACTIF && !IA_COUPEE), "bouton visible seulement avec chaleur haute et IA : " + pc.visible)
                console.log("FINI"); Qt.quit(); return
            }
            if (etape === 20) { verifier(trouver(pc, "pourquoiChaleurBouton").visible, "bouton"); pc.demander(); return }
            var r = trouver(pc, "pourquoiChaleurReponse")
            if (r.visible || etape > 120) {
                verifier(r.visible, "une réponse est affichée")
                verifier(r.text === "Le processeur travaille trop. **Ferme** firefox.", "texte brut tel quel : " + r.text)
                verifier(r.textFormat === Text.PlainText, "PlainText")
                console.log("FINI"); Qt.quit()
            }
        } }
    """

    def lancer(self, clic, actif=True, ia_coupee=False):
        d = tempfile.TemporaryDirectory(prefix="nc-ia-chaleur-")
        self.addCleanup(d.cleanup)
        noms = ("Couleurs", "Texte", "Module", "PourquoiChaleur", "DemandeIA", "IaPrete")
        root = H.preparer(d.name, noms, extra={"Reglages.qml": REGLAGES_FAUX.replace("iaCoupee: false", "iaCoupee: " + ("true" if ia_coupee else "false")),
                                         "Partage.qml": PARTAGE_FAUX}, singletons=("Partage",))
        ia = root / "bin/nc-ia"
        ia.write_text(NC_IA.replace("ROOT", str(root)))
        ia.chmod(0o755)
        H.faux(root, "top", TOP)
        H.faux(root, "nc-energie", 'echo \'{"actif": "cours", "profils": []}\'')
        corps = (self.SCENARIO.replace("CLIC", "true" if clic else "false").replace("ACTIF", "true" if actif else "false")
                 .replace("IA_COUPEE", "true" if ia_coupee else "false"))
        (root / "shell.qml").write_text(H.ENTETE + "ShellRoot {\n" + H.OUTILS + textwrap.dedent(corps) + "\n}\n")
        code, sortie = H.lancer(root)
        for e in H.ERREURS:
            self.assertNotIn(e, sortie, sortie)
        self.assertIn("FINI", sortie, sortie)
        return root

    def test_sans_clic_rien_ne_tourne(self):
        root = self.lancer(clic=False)
        self.assertEqual(H.journal(root).strip(), "nc-ia disponible")

    def test_pas_de_chaleur_pas_de_bouton_et_rien_lance(self):
        root = self.lancer(clic=False, actif=False)
        self.assertEqual(H.journal(root), "")

    def test_ia_coupee_pas_de_bouton_et_nc_ia_jamais_appele(self):
        root = self.lancer(clic=False, ia_coupee=True)
        self.assertEqual(H.journal(root), "")

    def test_clic_releve_sur_l_entree_standard(self):
        root = self.lancer(clic=True)
        appels = H.journal(root).splitlines()
        self.assertEqual(appels[0], "nc-ia disponible")
        self.assertEqual(appels[1], "top -b -n 2 -d 1 -w 200 -o %CPU")
        self.assertEqual(appels[2], "nc-energie liste --json")
        self.assertEqual(appels[3], "nc-ia demander --usage texte --flux --sans-outils --local -")
        self.assertEqual(len(appels), 4)
        envoye = (root / "stdin.txt").read_text()
        self.assertIn("93 °C", envoye)
        self.assertIn("41 %", envoye)
        self.assertIn("4100/6000", envoye)
        self.assertIn("Équilibré", envoye)
        self.assertIn("secteur", envoye)
        self.assertIn("cours", envoye)
        self.assertIn("firefox 76 %", envoye)
        self.assertIn("Isolated Web Co 40 %", envoye)
        self.assertIn("noctalia 5 %", envoye)
        self.assertNotIn("premiere-mesure", envoye, "la seconde mesure de top, pas la moyenne depuis le lancement")
        self.assertNotIn("sixieme-exclu", envoye, "5 programmes au plus")
        self.assertIn("DONNÉE", envoye)
        self.assertNotIn("firefox", "\n".join(appels), "rien du relevé en argument")


if __name__ == "__main__":
    unittest.main()
