"""Emoji dans le Spotlight (« : coeur ») : le script de génération sur de petites sources fabriquées ici, le fichier de
données versionné (taille, format, licence), puis Recherche.qml réel hors écran avec un faux wl-copy : liste lue
seulement après « : », recherche sans accents en français et en anglais, récents en tête et bornés, cachés pendant un
partage d'écran, Entrée -> wl-copy avec le bon emoji, réglage SPOTLIGHT_EMOJI=non -> rien."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
DONNEES = REPO / "home/.local/share/nc/emoji"
GENERATEUR = REPO / "outils/emoji-generer.py"

EMOJI_TEST = """# emoji-test.txt
# Version: 17.0
# group: Smileys & Emotion
1F600                                                  ; fully-qualified     # 😀 E1.0 grinning face
2764 FE0F                                              ; fully-qualified     # ❤️ E0.6 red heart
2764                                                   ; unqualified         # ❤ E0.6 red heart
1F44B 1F3FD                                            ; fully-qualified     # 👋🏽 E1.0 waving hand: medium skin tone
1F1EB 1F1F7                                            ; fully-qualified     # 🇫🇷 E2.0 flag: France
1F4A4                                                  ; fully-qualified     # 💤 E0.6 zzz
"""
FR = """<?xml version="1.0" encoding="UTF-8" ?>
<ldml><annotations>
<annotation cp="😀">content | sourire | été</annotation>
<annotation cp="😀" type="tts">visage rieur</annotation>
<annotation cp="❤">amour | sentiment</annotation>
<annotation cp="❤" type="tts">cœur rouge</annotation>
</annotations></ldml>
"""
EN = """<?xml version="1.0" encoding="UTF-8" ?>
<ldml><annotations>
<annotation cp="😀">face | grin | smile</annotation>
<annotation cp="😀" type="tts">grinning face</annotation>
<annotation cp="❤">love | heart</annotation>
<annotation cp="❤" type="tts">red heart</annotation>
</annotations></ldml>
"""
FR_DERIVE = """<?xml version="1.0" encoding="UTF-8" ?>
<ldml><annotations>
<annotation cp="🇫🇷">drapeau | France</annotation>
<annotation cp="🇫🇷" type="tts">drapeau : France</annotation>
</annotations></ldml>
"""


class Generateur(unittest.TestCase):
    def test_petites_sources(self):
        with tempfile.TemporaryDirectory(prefix="nc-emo-") as d:
            d = Path(d)
            src = d / "src"; src.mkdir()
            for nom, texte in (("emoji-test.txt", EMOJI_TEST), ("fr.xml", FR), ("en.xml", EN), ("fr-derive.xml", FR_DERIVE)):
                (src / nom).write_text(texte, encoding="utf-8")
            sortie = d / "emoji.tsv"
            r = subprocess.run([sys.executable, "-I", str(GENERATEUR), "-o", str(sortie), "--unicode", "17.0", "--cldr", "48.2",
                                "--emoji-test", str(src / "emoji-test.txt"), "--fr", str(src / "fr.xml"), "--en", str(src / "en.xml"),
                                "--fr-derive", str(src / "fr-derive.xml")], cwd=str(d), capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            lignes = sortie.read_text(encoding="utf-8").splitlines()
            self.assertIn("Unicode 17.0", lignes[0]); self.assertIn("CLDR 48.2", lignes[0])
            champs = [l.split("\t") for l in lignes[1:]]
            self.assertEqual([c[0] for c in champs], ["😀", "❤️", "🇫🇷", "💤"], "ni peau, ni non qualifié, ni doublon")
            self.assertTrue(all(len(c) == 4 for c in champs))
            coeur = next(c for c in champs if c[0] == "❤️")
            self.assertEqual(coeur[1:3], ["cœur rouge", "red heart"])       # clé sans U+FE0F retrouvée
            self.assertEqual(coeur[3], "amour|sentiment|love")      # « heart » est déjà dans le nom anglais
            self.assertEqual(next(c for c in champs if c[0] == "🇫🇷")[1], "drapeau : France")      # annotationsDerived
            self.assertEqual(next(c for c in champs if c[0] == "💤")[1:3], ["zzz", "zzz"])      # repli : nom d'emoji-test.txt
            # Avec --avec-peau la variante revient
            r = subprocess.run([sys.executable, "-I", str(GENERATEUR), "-o", str(sortie), "--unicode", "17.0", "--cldr", "48.2",
                                "--emoji-test", str(src / "emoji-test.txt"), "--fr", str(src / "fr.xml"), "--en", str(src / "en.xml"),
                                "--avec-peau"], cwd=str(d), capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("👋🏽", sortie.read_text(encoding="utf-8"))

    def test_aucun_telechargement_dans_le_script(self):
        src = GENERATEUR.read_text(encoding="utf-8")
        for mot in ("urllib", "http.client", "requests", "socket", "subprocess", "urlopen"):
            self.assertNotIn(mot, src)


class FichierVersionne(unittest.TestCase):
    def test_taille_format_licence(self):
        f = DONNEES / "emoji.tsv"
        self.assertLess(f.stat().st_size, 200 * 1024)
        lignes = f.read_text(encoding="utf-8").splitlines()
        self.assertTrue(lignes[0].startswith("# Unicode ") and "CLDR" in lignes[0])
        emoji = [l.split("\t") for l in lignes[1:]]
        self.assertGreater(len(emoji), 1500)
        self.assertTrue(all(len(c) == 4 and c[0] and c[1] and c[2] for c in emoji))
        self.assertEqual(len({c[0] for c in emoji}), len(emoji), "pas de doublon")
        self.assertFalse(any(0x1F3FB <= ord(ch) <= 0x1F3FF for c in emoji for ch in c[0]), "sans couleurs de peau")
        self.assertIn("UNICODE LICENSE", (DONNEES / "LICENSE-UNICODE.txt").read_text(encoding="utf-8"))
        # Rien de personnel dans un fichier public
        self.assertNotIn("/home/", f.read_text(encoding="utf-8"))


SCRIPT = '''import QtQuick
import Quickshell
ShellRoot {
 id: racine
 property int etape: 0
 property int attente: 0
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function verifier(ok,message){if(!ok){console.error(message);Qt.exit(2);throw new Error(message)}}
 function titres(){ return spot.resultats.map(x => x.titre) }
 function emojis(){ return spot.resultats.map(x => x.emoji) }
 FloatingWindow { id: fen; visible: true; implicitWidth: 700; implicitHeight: 600
  Recherche { id: spot; width: 700; actif: true } }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  var champ = trouver(spot, "nc-spotlight-champ")
  if (etape === 0) { if (spot.nomIA === "") return
   etape++; return }
  if (etape === 1) {
   // Au démarrage et avec une saisie ordinaire : la liste n'est ni demandée ni lue
   verifier(!spot.children.some(c => c.demande === true), "liste demandée trop tôt")
   champ.text = "firefox"; etape++; return }
  if (etape === 2) {
   verifier(!spot.children.some(c => c.demande === true), "liste demandée par une saisie ordinaire")
   champ.text = ":coeur"; etape++; return }
  if (etape === 3) {
   var e = spot.children.filter(c => c.demande !== undefined)[0]
   verifier(e && e.demande, "liste demandée par « : »")
   if (!e.pret) return
   var t = emojis()
   verifier(t.indexOf("❤️") >= 0 && t.length <= 24 && titres()[0].toLowerCase().indexOf("cœur") >= 0, "coeur : " + JSON.stringify(titres()))
   champ.text = ":heart"; etape++; return }
  if (etape === 4) {
   verifier(emojis().indexOf("❤️") >= 0 && emojis().length <= 8, "heart : " + JSON.stringify(titres()))
   var e3 = spot.children.filter(c => c.demande !== undefined)[0]
   verifier(e3.chercher("a").length === 24, "résultats bornés à 24 : " + e3.chercher("a").length)
   verifier(e3.chercher("coeur")[0].fr.indexOf("cœur") >= 0 && e3.chercher("COEUR").length === e3.chercher("cœur").length, "sans accents ni casse")
   champ.text = ":ete"; etape++; return }
  if (etape === 5) {
   verifier(titres().length > 0 && emojis()[0] !== undefined, "ete (sans accents) : " + JSON.stringify(titres()))
   champ.text = ":rire"; etape++; return }
  if (etape === 6) {
   // Récents en tête (😂 est dans le fichier de récents) ; cachés pendant un partage d'écran
   verifier(emojis()[0] === "😂" && spot.resultats[0].sous.indexOf("Récent") === 0, "récent en tête : " + JSON.stringify(spot.resultats.slice(0, 3)))
   Partage.silence = true
   champ.text = ":rir"; champ.text = ":rire"; etape++; return }
  if (etape === 7) {
   verifier(emojis()[0] !== "😂" || spot.resultats[0].sous.indexOf("Récent") !== 0, "récents cachés pendant le partage")
   Partage.silence = false
   champ.text = ":"; etape++; return }
  if (etape === 8) {
   var e2 = spot.children.filter(c => c.demande !== undefined)[0]
   verifier(e2.recents.length === 24, "récents lus : 24 au plus : " + e2.recents.length)
   verifier(emojis().length === 8 && emojis()[0] === "😂", "« : » seul = les récents (8 montrés) : " + emojis().length)
   champ.text = ":coeur"; etape++; return }
  if (etape === 9) {
   var i = emojis().indexOf("❤️"); verifier(i >= 0, "cœur rouge présent")
   spot.valider(i, false)
   verifier(Etat.fermetures === 1, "Entrée referme"); etape++; return }
  if (etape === 10) {
   attente++; if (attente < 8) return      // le temps que sh écrive les récents
   Reglages.v = { SPOTLIGHT_EMOJI: "non" }
   champ.text = ":coeu"; champ.text = ":coeur"; etape++; return }
  if (etape === 11) {
   verifier(emojis().every(x => x === undefined), "réglage non : aucun emoji " + JSON.stringify(titres()))
   Qt.quit() }
 } }
 Timer { interval: 15000; running: true; onTriggered: Qt.exit(9) }
}'''


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class SpotlightEmoji(unittest.TestCase):
    def test_de_la_frappe_a_la_copie(self):
        os.makedirs("/tmp/claude-1000", exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="nce-", dir="/tmp/claude-1000") as d:
            root = Path(d); q = root / "qml"
            shutil.copytree(QML, q)
            for sous in ("run", "cache", "state", "data", "config", "tmp"):
                (root / sous).mkdir(mode=0o700)
            (q / "Reglages.qml").write_text('''pragma Singleton
import QtQuick
QtObject {
 property var v: ({})
 readonly property bool iaCoupee: true
 readonly property bool en: false
 function t(fr,en){return fr}
 function val(k,d){return v[k] !== undefined ? v[k] : d}
 function pageActive(n){return true}
}''')
            (q / "Etat.qml").write_text('''pragma Singleton
import QtQuick
import Quickshell
QtObject {
 property string saisie: ""
 property string texteIA: ""
 property bool recherche: true
 property bool nuit: false
 readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
 property int fermetures: 0
 signal validerRecherche()
 function faire(c) {} function fermer() { fermetures++ } function aller(p) {} function basculer(e, c) {}
}''')
            (q / "Partage.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }')
            (q / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function formater(t){return t}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            noms = ["Reglages", "Etat", "Partage", "AssistantEtat", "Couleurs", "Connexion", "Recherche", "Emoji", "Diagnostic", "Etincelle", "Texte", "Ico"]
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Etat", "Partage", "AssistantEtat", "Couleurs", "Connexion") else "") + n + " 1.0 " + n + ".qml" for n in noms))
            # Données : le vrai fichier versionné, copié dans le faux HOME ; 30 récents (dont 😂 en tête), les 24 premiers comptent
            (root / ".local/share/nc").mkdir(parents=True)
            shutil.copytree(DONNEES, root / ".local/share/nc/emoji")
            (root / ".local/state/nc").mkdir(parents=True)
            anciens = ["😂", "😀", "❤️"] + [c for c in "🍎🍌🍇🍉🍓🍒🍑🍍🥝🍅🥑🍆🥕🌽🌶🥔🍠🥐🍞🥖🧀"] + list("🍳🥞🥓🍔🍟🌭")
            (root / ".local/state/nc/emoji-recents").write_text("\n".join(anciens) + "\n", encoding="utf-8")
            b = root / ".local/bin"; b.mkdir(parents=True)
            scripts = {
                "nc-apps": '#!/bin/sh\necho "[]"\n',
                "hyprctl": "#!/bin/sh\necho '[]'\n",
                "nc-aide-config": "#!/bin/sh\nexit 0\n",
                "nc-demander": '#!/bin/sh\ncase "$1" in --ia) echo \'{"nom": "-", "agent": "claude", "coupee": true}\' ;; esac\n',
                "wl-copy": '#!/bin/sh\necho "wl-copy $*" >> "$HOME/appels"\n',
            }
            for nom, code in scripts.items():
                (b / nom).write_text(code); (b / nom).chmod(0o755)
            (q / "shell.qml").write_text(SCRIPT)
            env = dict(os.environ, HOME=d, XDG_CONFIG_HOME=str(root / "config"), XDG_CACHE_HOME=str(root / "cache"),
                       XDG_STATE_HOME=str(root / "state"), XDG_DATA_HOME=str(root / "data"), XDG_RUNTIME_DIR=str(root / "run"),
                       TMPDIR=str(root / "tmp"), QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       PATH=str(b) + os.pathsep + os.environ["PATH"])
            for k in ("WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE", "DISPLAY"):
                env.pop(k, None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=40,
                               stdin=subprocess.DEVNULL)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for erreur in ("ReferenceError", "TypeError", "is not a type", "Binding loop"):
                self.assertNotIn(erreur, sortie)
            appels = (root / "appels").read_text(encoding="utf-8").splitlines()
            self.assertEqual(appels, ["wl-copy -- ❤️"], "Entrée copie l'emoji choisi, et rien d'autre n'est copié")
            recents = (root / ".local/state/nc/emoji-recents").read_text(encoding="utf-8").splitlines()
            self.assertEqual(recents[0], "❤️")
            self.assertLessEqual(len(recents), 24)
            self.assertEqual(len(set(recents)), len(recents))
            self.assertEqual(recents[1], "😂")
            self.assertEqual([p.name for p in (root / ".local/state/nc").iterdir()], ["emoji-recents"], "pas de fichier temporaire oublié")
            self.assertEqual(oct((root / ".local/state/nc/emoji-recents").stat().st_mode & 0o777), "0o600")


if __name__ == "__main__":
    unittest.main()
