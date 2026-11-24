"""L'île et ses widgets de barre restent utilisables avec les modules Quickshell facultatifs absents."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tests import _ile_hors_ecran as he

QML = Path(__file__).resolve().parents[1] / "home/.config/quickshell/nc-ile"


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class ConnexionIle(unittest.TestCase):
    def charger(self, module):
        with tempfile.TemporaryDirectory(prefix="nc-connexion-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            (root / "Connexion.qml").write_text((QML / "Connexion.qml").read_text().replace("Quickshell.Networking", module))
            (root / "qmldir").write_text("singleton Connexion 1.0 Connexion.qml\n")
            (root / "shell.qml").write_text('import QtQuick\nimport Quickshell\nShellRoot {\n'
                                            '  Timer { interval: 300; running: true; onTriggered: { console.log("RESULTAT " + Connexion.enLigne + " " + Connexion.disponible); Qt.quit() } }\n}\n')
            env = dict(os.environ, HOME=d, XDG_RUNTIME_DIR=str(root / "run"), QT_QPA_PLATFORM="offscreen")
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env, text=True, capture_output=True, timeout=20)
            return r.stdout + r.stderr

    def test_sans_le_module_l_ile_demarre(self):
        sortie = self.charger("Quickshell.ModuleAbsent")
        self.assertNotIn("Failed to load configuration", sortie)
        self.assertIn("RESULTAT true false", sortie, "supposé en ligne, module signalé absent")

    def test_avec_le_module(self):
        sortie = self.charger("Quickshell.Networking")
        self.assertRegex(sortie, r"RESULTAT (true|false) true")


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class ModulesFacultatifsBarre(unittest.TestCase):
    def test_absence_des_modules(self):
        # Même avec un binaire qui fournit les modules, rendre les imports des vrais widgets introuvables.
        modules = {
            "WidgetBarreStatus": {"Quickshell.Networking": "Quickshell.ReseauAbsent",
                                  "Quickshell.Bluetooth": "Quickshell.BluetoothAbsent"},
            "WidgetBarreTray": {"Quickshell.Services.SystemTray": "Quickshell.Services.TrayAbsent"},
        }
        with tempfile.TemporaryDirectory(prefix="nc-barre-modules-") as d:
            fichiers = {}
            for nom, imports in modules.items():
                texte = (QML / (nom + ".qml")).read_text()
                for module, absent in imports.items():
                    texte = texte.replace(module, absent)
                fichiers[nom + ".qml"] = texte
            fichiers["VpnEtat.qml"] = ('pragma Singleton\nimport QtQuick\n'
                                       'QtObject { property bool actif: false; property string libelle: "Test VPN" }')
            root = he.preparer(d, ("WidgetBarreLibelle", "WidgetBarreBulle", "WidgetBarrePopup", "Couleurs", "Ico"),
                               etat="property real luminosite: 0.42\nfunction lireLuminosite(force) {}",
                               extra=fichiers, singletons=("VpnEtat",))
            (root / "shell.qml").write_text(he.ENTETE + "ShellRoot {\n" + he.OUTILS + """
                Item {
                    id: hote
                    property string type: "brightness"
                    property var definition: ({ peek: true, vpn_status: "both", show_vpn_label: true })
                    property bool vertical: false
                    property string position: "top"
                    property color premierPlan: "white"
                    property string police: "Sans"
                    property real tailleIcone: 15
                    property real tailleTexte: 12
                    property real echelle: 1
                    property int graisse: Font.DemiBold
                    property int bordInterieur: Edges.Bottom
                    WidgetBarreStatus { id: etats; barre: hote }
                    WidgetBarreTray { id: tray; barre: hote }
                }
                Timer {
                    interval: 20; repeat: true; running: true
                    property int etape: 0
                    onTriggered: {
                        switch (etape++) {
                        case 0:
                            if (!verifier(etats.affiche && etats.libelle === "42%", "luminosité intacte")) return
                            if (!verifier(!tray.affiche && !tray.boutonVisible && tray.implicitWidth === 0,
                                          "pas de zone de notification ni de chevron sans module")) return
                            hote.type = "network"
                            break
                        case 1:
                            if (!verifier(!etats.affiche, "réseau masqué sans module")) return
                            etats.droit()
                            VpnEtat.actif = true
                            break
                        case 2:
                            if (!verifier(etats.affiche && etats.glyphe === "shield" && !etats.visuel
                                          && etats.infobulle === "Test VPN", "VPN seul sans module réseau")) return
                            hote.type = "bluetooth"
                            break
                        case 3:
                            if (!verifier(!etats.affiche, "Bluetooth masqué sans module")) return
                            etats.droit()
                            hote.type = "brightness"
                            break
                        case 4:
                            if (!verifier(etats.affiche, "le widget reste utilisable après changement de type")) return
                            console.log("BARRE SANS MODULES OK")
                            Qt.quit()
                        }
                    }
                }
            }
            """)
            code, journal = he.lancer(root)
        self.assertEqual(code, 0, journal)
        self.assertIn("BARRE SANS MODULES OK", journal)
        for erreur in he.ERREURS:
            self.assertNotIn(erreur, journal)
        for imports in modules.values():
            for absent in imports.values():
                self.assertIn(f'module "{absent}" is not installed', journal)


class ModulesCompilesSurDebian(unittest.TestCase):
    """Un import obligatoire absent suffit à empêcher le chargement de l'île, même sans utiliser le widget.
    Le réseau est activé aujourd'hui, mais reste facultatif pour les anciennes compilations sans -DNETWORK=ON."""
    MODULES = {"Quickshell.Networking": "NETWORK", "Quickshell.Bluetooth": "BLUETOOTH", "Quickshell.Services.Pam": "SERVICE_PAM",
               "Quickshell.Services.Polkit": "SERVICE_POLKIT", "Quickshell.Services.Greetd": "SERVICE_GREETD",
               "Quickshell.Services.SystemTray": "SERVICE_STATUS_NOTIFIER"}
    TYPES = {"WlSessionLock": "WAYLAND_SESSION_LOCK", "GlobalShortcut": "HYPRLAND_GLOBAL_SHORTCUTS"}

    def test_aucun_module_desactive_importe(self):
        import re
        install = (Path(__file__).resolve().parents[1] / "install.sh").read_text()
        compilation = install[install.index("compiler_quickshell() {"):install.index("\n}\n", install.index("compiler_quickshell() {"))]
        desactives = set(re.findall(r"-D([A-Z_]+)=OFF", compilation))
        self.assertIn("BLUETOOTH", desactives)
        for f in QML.glob("*.qml"):
            texte = f.read_text()
            for module, option in self.MODULES.items():
                if option in desactives or option == "NETWORK":
                    self.assertNotRegex(texte, r"(?m)^[ \t]*import[ \t]+" + re.escape(module) + r"(?![\w.])",
                                        f"{f.name} importe {module} statiquement (facultatif : -D{option})")
            for type_, option in self.TYPES.items():
                if option in desactives:
                    self.assertNotRegex(texte, r"\b" + type_ + r"\s*\{", f"{f.name} utilise {type_} (-D{option}=OFF)")


class PaquetsQmlDebian(unittest.TestCase):
    """Sur Debian, chaque module QML de Qt est un paquet à part (qml6-module-*) : un seul import de l'île sans son
    paquet et toute l'île refuse de se charger. Chaque module importé (en tête de fichier, mais aussi dans une chaîne
    passée à Qt.createQmlObject) doit être fourni par la compilation de Quickshell ou avoir son paquet dans la liste
    QS_QML_DEBIAN d'install.sh, installée à la compilation et quand Quickshell est déjà là."""
    # Module QML -> paquet Debian 13 (trixie), noms vérifiés sur packages.debian.org
    TABLE = {
        "QtQml": "qml6-module-qtqml",
        "QtQml.Models": "qml6-module-qtqml-models",
        "QtQml.WorkerScript": "qml6-module-qtqml-workerscript",
        "QtQml.XmlListModel": "qml6-module-qtqml-xmllistmodel",
        "QtQml.StateMachine": "qml6-module-qtqml-statemachine",
        "QtCore": "qml6-module-qtcore",
        "QtQuick": "qml6-module-qtquick",
        "QtQuick.Window": "qml6-module-qtquick-window",
        "QtQuick.Shapes": "qml6-module-qtquick-shapes",
        "QtQuick.Effects": "qml6-module-qtquick-effects",
        "QtQuick.Controls": "qml6-module-qtquick-controls",
        "QtQuick.Templates": "qml6-module-qtquick-templates",
        "QtQuick.Layouts": "qml6-module-qtquick-layouts",
        "QtQuick.Dialogs": "qml6-module-qtquick-dialogs",
        "QtQuick.Particles": "qml6-module-qtquick-particles",
        "QtQuick.LocalStorage": "qml6-module-qtquick-localstorage",
        "QtQuick.VectorImage": "qml6-module-qtquick-vectorimage",
        "QtQuick.VirtualKeyboard": "qml6-module-qtquick-virtualkeyboard",
        "Qt.labs.folderlistmodel": "qml6-module-qt-labs-folderlistmodel",
        "Qt.labs.platform": "qml6-module-qt-labs-platform",
        "Qt.labs.settings": "qml6-module-qt-labs-settings",
        "Qt.labs.qmlmodels": "qml6-module-qt-labs-qmlmodels",
        "Qt5Compat.GraphicalEffects": "qml6-module-qt5compat-graphicaleffects",
        "QtMultimedia": "qml6-module-qtmultimedia",
        "QtNetwork": "qml6-module-qtnetwork",
        "QtPositioning": "qml6-module-qtpositioning",
    }

    @staticmethod
    def imports(texte, js=False):
        """Modules importés par un fichier : lignes « import X » (« .import X » en JavaScript) et « import X » écrits
        dans une chaîne (Qt.createQmlObject, Qt.createComponent depuis un texte…)."""
        import re
        nom = r"([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
        trouves = set(re.findall(r"(?m)^\s*" + (r"\." if js else "") + r"import\s+" + nom, texte))
        for chaine in re.findall(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|`[^`]*`', texte):
            trouves |= set(re.findall(r"(?:^|[\s;{])import\s+" + nom, chaine[1:-1]))
        return trouves

    def test_chaque_import_a_son_paquet(self):
        import re
        install = (Path(__file__).resolve().parents[1] / "install.sh").read_text()
        m = re.search(r'(?m)^QS_QML_DEBIAN="([^"]*)"', install)
        self.assertIsNotNone(m, "liste QS_QML_DEBIAN introuvable dans install.sh")
        liste = set(m.group(1).split())
        # Les deux usages : à la compilation, et pour un Quickshell déjà compilé
        debut = install.index("compiler_quickshell() {")
        compilation = install[debut:install.index("\n}\n", debut)]
        self.assertRegex(compilation, r"pkg_try [^\n]*(\\\n[^\n]*)*\$QS_QML_DEBIAN", "compilation sans QS_QML_DEBIAN")
        self.assertRegex(install[install.index("\n}\n", debut):], r"have qs; then pkg_try \$QS_QML_DEBIAN",
                         "Quickshell déjà compilé : QS_QML_DEBIAN n'est pas installée")

        trouves = {}
        for f in sorted(QML.rglob("*.qml")) + sorted(QML.rglob("*.js")):
            for module in self.imports(f.read_text(), js=f.suffix == ".js"):
                trouves.setdefault(module, set()).add(f.name)
        # L'extraction voit bien les imports écrits dans une chaîne (Connexion.qml, Qt.createQmlObject)
        self.assertIn("Connexion.qml", trouves.get("Quickshell.Networking", set()))
        for module, fichiers in sorted(trouves.items()):
            if module == "Quickshell" or module.startswith("Quickshell."):
                continue   # fourni par la compilation (modules désactivés : ModulesCompilesSurDebian)
            with self.subTest(module=module):
                self.assertTrue(module in self.TABLE,
                                f"{', '.join(sorted(fichiers))} importe {module}, absent de la table : ajoute son paquet "
                                "Debian à install.sh (QS_QML_DEBIAN) et à la table de ce test")
                self.assertTrue(self.TABLE[module] in liste,
                                f"{', '.join(sorted(fichiers))} importe {module} : ajoute son paquet Debian "
                                f"{self.TABLE[module]} à install.sh (QS_QML_DEBIAN)")


if __name__ == "__main__":
    unittest.main()
