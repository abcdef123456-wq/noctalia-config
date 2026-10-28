"""Panneau VPN de l'île (Vpn.qml, VpnEtat.qml, VpnLigne.qml) : lu depuis des sources (aucun sondage, aucun component inline,
LazyLoader, IPC, raccourci, réglages) et hors écran avec le vrai qs lancé par « qs -p » (jamais l'île réelle), HOME et XDG_*
isolés, un faux nc-vpn, un faux nmcli (« monitor » envoie une ligne puis se tait), un faux zenity et un faux notify-send :
tunnels affichés (plusieurs montés), clics (connecter, déconnecter, tout déconnecter), noms masqués pendant un partage d'écran,
IP publique jamais demandée par défaut ni en partage, mises à jour sur événements seulement, NetworkManager absent, écran éteint."""
import json
from pathlib import Path
import shutil
import tempfile
import textwrap
import unittest

from tests import _ile_hors_ecran as H

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
U1 = "11111111-1111-4111-8111-111111111111"
U2 = "22222222-2222-4222-8222-222222222222"
U3 = "33333333-3333-4333-8333-333333333333"

FAUX_PARTAGE = "pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }\n"
FAUX_NC_VPN = r'''#!/usr/bin/env python3
import json, os, sys
H = os.environ["HOME"]
a = sys.argv[1:]
open(H + "/appels", "a").write(json.dumps(a) + "\n")
if a[:1] == ["etat-json"]:
    n = sum(1 for l in open(H + "/appels") if json.loads(l) == ["etat-json"]) - 1
    f = H + "/etat-%d.json" % n
    print(open(f if os.path.exists(f) else H + "/etat.json").read())
elif a[:1] == ["ip-publique"]:
    print('{"ip": "203.0.113.7"}')
'''
FAUX_NMCLI = r'''#!/usr/bin/env python3
import os, sys, time
H = os.environ["HOME"]
open(H + "/appels-nmcli", "a").write(" ".join(sys.argv[1:]) + "\n")
if sys.argv[1:] == ["monitor"]:
    time.sleep(1.0)
    print("tun0: connected", flush=True)
    time.sleep(20)
'''
LIGNE_J = lambda uuid, nom, typ, active, iface: dict(uuid=uuid, nom=nom, type=typ, active=active, interface=iface if active else "")


def etat_deux_tunnels():
    c = [LIGNE_J(U1, "Labo", "vpn", False, ""), LIGNE_J(U2, "Maison", "wireguard", True, "wg-maison"), LIGNE_J(U3, "Bureau", "vpn", True, "tun1")]
    return dict(disponible=True, connexions=c, actives=[x for x in c if x["active"]])


def panneau_hors_fenetre():
    """Vpn.qml comme dans test_code_qml : une fenêtre ordinaire à la place du calque Wayland."""
    source = (QML / "Vpn.qml").read_text()
    source = source.replace("import Quickshell.Wayland\n", "import QtQuick.Window\n").replace("PanelWindow {", "Window {")
    for l in ("import Quickshell.Hyprland\n", "    anchors { top: true; bottom: true; left: true; right: true }\n", "    exclusionMode: ExclusionMode.Ignore\n",
              "    WlrLayershell.layer: Hyprland.activeToplevel && Hyprland.activeToplevel.lastIpcObject\n"
              "                         && (Hyprland.activeToplevel.lastIpcObject.fullscreen || 0) > 0 ? WlrLayer.Overlay : WlrLayer.Top\n",
              '    WlrLayershell.namespace: "nc-vpn"\n', "    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive\n"):
        assert l in source, l
        source = source.replace(l, "")
    source = source.replace("vpn.screen ? vpn.screen.width : 1600", "1600").replace("vpn.screen ? vpn.screen.height : 1000", "1000")
    return source.replace('    color: "transparent"\n', '    color: "transparent"; width: 1600; height: 1000; visible: true\n')


class Sources(unittest.TestCase):
    def setUp(self):
        self.etat = (QML / "VpnEtat.qml").read_text()
        self.vpn = (QML / "Vpn.qml").read_text()
        self.shell = (QML / "shell.qml").read_text()

    def test_aucun_sondage_ni_component_inline(self):
        for nom in ("Vpn", "VpnEtat", "VpnLigne"):
            src = (QML / (nom + ".qml")).read_text()
            self.assertNotRegex(src, r"(?m)^\s*component ", nom)
            self.assertNotRegex(src, r"repeat:\s*true", nom + " : jamais de relevé toutes les N secondes")
        self.assertIn('command: ["nmcli", "monitor"]', self.etat)
        self.assertIn("running: v.veille", self.etat)
        self.assertIn("Etat.ecranVu", self.etat)

    def test_panneau_charge_a_la_demande_et_ipc(self):
        self.assertIn("function vpn(): void", self.shell)
        self.assertRegex(self.shell, r"LazyLoader \{\s*id: chargeurVpn\s*active: racine\.vpnOuvert")
        self.assertIn("Keys.onEscapePressed", self.vpn)

    def test_noms_en_texte_brut_et_masques_en_partage(self):
        self.assertIn("Partage.silence", self.etat)
        self.assertNotIn("RichText", self.vpn + (QML / "VpnLigne.qml").read_text())
        self.assertNotIn("textFormat", self.vpn)          # Texte.qml est en Text.PlainText
        self.assertNotRegex(self.vpn, r'(?m)^\s*Text \{')

    def test_ip_publique_https_et_hors_partage(self):
        self.assertIn('Reglages.val("VPN_IP_PUBLIQUE", "non") === "oui"', self.etat)
        self.assertIn('indexOf("https://") === 0', self.etat)
        self.assertIn("!masque", self.etat)

    def test_raccourci_reglages_et_documentation(self):
        lua = (REPO / "home/.config/hypr/nc/raccourcis.lua").read_text()
        self.assertIn('SUPER .. " + ALT + code:55"', lua)
        self.assertIn("ile vpn", lua)
        self.assertIn("Super` + `Alt` + `V", (REPO / "RACCOURCIS.md").read_text())
        self.assertIn("Super + Alt + V", (REPO / "README.md").read_text())
        self.assertIn('namespace = "^nc-vpn$"', (REPO / "home/.config/hypr/nc/regles.lua").read_text())
        compact = (QML / "Compact.qml").read_text()
        self.assertIn("visible: VpnEtat.indicateur", compact)
        self.assertEqual(lua.count('SUPER .. " + ALT + code:55"'), 1)

    def test_aucune_ligne_de_shell_construite_avec_un_nom(self):
        self.assertEqual(self.etat.count('["sh", "-c"'), 1)      # le seul : l'enveloppe de zenity, texte fixe, fichier choisi jamais dedans
        self.assertNotIn("execDetached([\"sh\"", self.etat)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def lancer(self, corps, etats=None, reglages=None, delai=30):
        """etats : {0: état de départ, 1: état à la 2e lecture…} ; renvoie (journal de qs, appels de nc-vpn, appels de nmcli)."""
        with tempfile.TemporaryDirectory(prefix="nc-vpnqml-") as d:
            root = H.preparer(d, ("Couleurs", "Texte", "Ico", "VpnEtat", "VpnLigne"),
                              extra={"Vpn.qml": panneau_hors_fenetre(), "Partage.qml": FAUX_PARTAGE}, singletons=("VpnEtat", "Partage"))
            home = root / "home"
            (home / ".local/bin").mkdir(parents=True)
            for nom, texte, ou in (("nc-vpn", FAUX_NC_VPN, home / ".local/bin"), ("nmcli", FAUX_NMCLI, root / "bin")):
                (ou / nom).write_text(texte)
                (ou / nom).chmod(0o755)
            H.faux(root, "notify-send")
            H.faux(root, "zenity", "echo /ailleurs/labo.ovpn")
            etats = etats or {0: etat_deux_tunnels()}
            (home / "etat.json").write_text(json.dumps(etats[0]))
            for k, v in etats.items():
                (home / ("etat-%d.json" % k)).write_text(json.dumps(v))
            entete = H.ENTETE + "import QtTest\n"
            reg = ("Reglages.valeurs = " + json.dumps(reglages) + "\n") if reglages else ""
            (root / "shell.qml").write_text(entete + "ShellRoot {\n id: racine\n property var fen: null\n property bool fermee: false\n property int etape: 0\n"
                                            " property int ticks: 0\n" + H.OUTILS + OUTILS_VPN
                                            + " TestCase { id: t; name: \"Vpn\"; when: false }\n"
                                            + " Component.onCompleted: { " + reg + "}\n"
                                            + textwrap.dedent(corps) + "\n Timer { interval: 20000; running: true; onTriggered: { console.error(\"ECHEC délai\"); Qt.exit(3) } }\n}\n")
            code, sortie = H.lancer(root, delai=delai)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)
            lire = lambda n: [x for x in (home / n).read_text().splitlines()] if (home / n).exists() else []
            return sortie, [json.loads(x) for x in lire("appels")], lire("appels-nmcli")

    def test_tunnels_affiches_clics_masquage_et_echap(self):
        _, appels, _ = self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var c = Qt.createComponent("Vpn.qml"); verifier(c.status === Component.Ready, c.errorString())
                                   fen = c.createObject(racine); fen.fermer.connect(function () { fermee = true }); etape++; return }
                if (etape === 1) {
                    if (!VpnEtat.lu) return
                    var corps = fen.contentItem
                    verifier(tous(corps, "nc-vpn-actif").length === 2, "deux tunnels montés : " + tous(corps, "nc-vpn-actif").length)
                    verifier(tous(corps, "nc-vpn-autre").length === 1, "une autre connexion")
                    var tx = textes(corps)
                    verifier(tx.indexOf("Maison") >= 0 && tx.indexOf("Bureau") >= 0 && tx.indexOf("Labo") >= 0, "noms : " + tx)
                    verifier(tx.indexOf("WireGuard · wg-maison") >= 0, "type et interface : " + tx)
                    verifier(tx.indexOf("Connectés") >= 0, "titre : " + tx)
                    verifier(trouver(corps, "nc-vpn-tout").visible, "Tout déconnecter")
                    verifier(!trouver(corps, "nc-vpn-ip").visible, "pas d'IP par défaut")
                    verifier(tous(corps, "nc-vpn-bouton").filter(b => b.visible).length === 2, "un Déconnecter par tunnel")
                    Partage.silence = true; etape++; ticks = 0; return }
                if (etape === 2) {
                    if (ticks < 2) return
                    var tx2 = textes(fen.contentItem).join("|")
                    verifier(tx2.indexOf("Maison") < 0 && tx2.indexOf("Bureau") < 0 && tx2.indexOf("Labo") < 0, "noms masqués en partage : " + tx2)
                    verifier(tx2.indexOf("wg-maison") < 0 && tx2.indexOf("tun1") < 0, "interfaces masquées : " + tx2)
                    verifier(tx2.indexOf("Tunnel 1") >= 0 && tx2.indexOf("Tunnel 3") >= 0, "noms génériques : " + tx2)
                    Partage.silence = false; etape++; ticks = 0; return }
                if (etape === 3) {                                             // Déconnecter le premier tunnel monté
                    if (ticks < 2) return
                    t.mouseClick(tous(fen.contentItem, "nc-vpn-bouton").filter(b => b.visible)[0]); etape++; ticks = 0; return }
                if (etape === 4) { if (ticks < 8) return
                    t.mouseClick(tous(fen.contentItem, "nc-vpn-autre")[0]); etape++; ticks = 0; return }       // Connecter Labo
                if (etape === 5) { if (ticks < 8) return
                    t.mouseClick(trouver(fen.contentItem, "nc-vpn-tout")); etape++; ticks = 0; return }
                if (etape === 6) { if (ticks < 8) return
                    t.keyClick(Qt.Key_Escape); verifier(fermee, "Échap ferme"); etape++; ticks = 0; return }
                if (etape === 7) { if (ticks < 2) return
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''')
        self.assertIn(["deconnecter", U2], appels, "bouton Déconnecter du premier tunnel")
        self.assertIn(["connecter", U1], appels, "clic sur une autre connexion")
        self.assertIn(["tout-deconnecter"], appels)
        self.assertFalse([a for a in appels if a[:1] == ["ip-publique"]], "IP publique jamais demandée par défaut")

    def test_ip_publique_demandee_a_l_ouverture_seulement_si_voulue_et_jamais_en_partage(self):
        _, appels, _ = self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var c = Qt.createComponent("Vpn.qml"); fen = c.createObject(racine); etape++; return }
                if (etape === 1) { if (VpnEtat.ip === "") return
                    verifier(VpnEtat.ip === "203.0.113.7", "IP lue : " + VpnEtat.ip)
                    verifier(textes(fen.contentItem).indexOf("IP publique : 203.0.113.7") >= 0, "IP affichée : " + textes(fen.contentItem))
                    Partage.silence = true; etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 3) return
                    verifier(VpnEtat.ip === "", "IP effacée en partage")
                    verifier(!trouver(fen.contentItem, "nc-vpn-ip").visible, "IP masquée en partage")
                    etape++; ticks = 0; return }
                if (etape === 3) { if (ticks < 8) return; console.log("FINI"); Qt.exit(0) }
            } }
        ''', reglages={"VPN_IP_PUBLIQUE": "oui", "VPN_IP_SERVICE": "https://exemple.invalid/ip"})
        self.assertEqual([a for a in appels if a[:1] == ["ip-publique"]], [["ip-publique"]], "une seule demande, à l'ouverture")

    def test_ip_publique_refusee_sans_https_ou_sans_adresse_et_en_partage_des_l_ouverture(self):
        for reglages, partage in (({"VPN_IP_PUBLIQUE": "oui", "VPN_IP_SERVICE": "http://exemple.invalid/ip"}, False),
                                  ({"VPN_IP_PUBLIQUE": "oui", "VPN_IP_SERVICE": ""}, False),
                                  ({"VPN_IP_PUBLIQUE": "non", "VPN_IP_SERVICE": "https://exemple.invalid/ip"}, False),
                                  ({"VPN_IP_PUBLIQUE": "oui", "VPN_IP_SERVICE": "https://exemple.invalid/ip"}, True)):
            with self.subTest(reglages=reglages, partage=partage):
                _, appels, _ = self.lancer('''
                    Timer { interval: 100; running: true; repeat: true; onTriggered: {
                        ticks++
                        if (etape === 0) { Partage.silence = %s; var c = Qt.createComponent("Vpn.qml"); fen = c.createObject(racine); etape++; return }
                        if (etape === 1) { if (ticks < 12) return; verifier(VpnEtat.lu && VpnEtat.ip === "", "pas d'IP"); console.log("FINI"); Qt.exit(0) }
                    } }
                ''' % ("true" if partage else "false"), reglages=reglages)
                self.assertFalse([a for a in appels if a[:1] == ["ip-publique"]], appels)

    def test_mises_a_jour_sur_evenements_seulement(self):
        un = etat_deux_tunnels()
        zero = dict(disponible=True, connexions=un["connexions"][:1] + [dict(un["connexions"][1], active=False, interface="")], actives=[])
        _, appels, nmcli = self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var d = VpnEtat.disponible; etape++; ticks = 0; return }
                if (etape === 1) {
                    if (ticks === 8) verifier(VpnEtat.lu && VpnEtat.actives.length === 0 && !VpnEtat.indicateur, "départ : aucun tunnel, pas de bouclier")
                    if (ticks < 38) return
                    verifier(VpnEtat.actives.length === 2 && VpnEtat.indicateur, "l'événement de nmcli a relancé la lecture : " + VpnEtat.actives.length)
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', etats={0: zero, 1: un})
        self.assertEqual(nmcli, ["monitor"], "nmcli monitor lancé une seule fois")
        self.assertEqual([a for a in appels if a == ["etat-json"]], [["etat-json"]] * 2, "un relevé au départ, un seul après l'événement, aucun entre les deux")

    def test_networkmanager_absent_rien_ne_tourne(self):
        _, appels, nmcli = self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var d = VpnEtat.disponible; etape++; ticks = 0; return }
                if (etape === 1) { if (ticks < 8) return
                    verifier(VpnEtat.lu && !VpnEtat.disponible && !VpnEtat.indicateur && !VpnEtat.veille, "indisponible")
                    var c = Qt.createComponent("Vpn.qml"); fen = c.createObject(racine); etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 8) return
                    verifier(trouver(fen.contentItem, "nc-vpn-indisponible").visible, "message d'indisponibilité")
                    verifier(!trouver(fen.contentItem, "nc-vpn-tout").visible && !trouver(fen.contentItem, "nc-vpn-importer").visible, "rien à piloter")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', etats={0: {"disponible": False}})
        self.assertEqual(nmcli, [], "nmcli monitor n'est jamais lancé sans NetworkManager")
        self.assertFalse([a for a in appels if a[0] != "etat-json"])

    def test_ecran_eteint_rien_ne_tourne_puis_reprise_au_reveil(self):
        _, appels, nmcli = self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { Etat.ecranVu = false; var d = VpnEtat.disponible; etape++; ticks = 0; return }
                if (etape === 1) { if (ticks < 10) return
                    verifier(!VpnEtat.lu && !VpnEtat.veille, "écran éteint : aucune lecture")
                    Etat.ecranVu = true; etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 8) return
                    verifier(VpnEtat.lu && VpnEtat.veille, "écran rallumé : lecture et veille")
                    Etat.ecranVu = false; etape++; ticks = 0; return }
                if (etape === 3) { if (ticks < 3) return
                    verifier(!VpnEtat.veille, "écran éteint : la veille s'arrête")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''')
        self.assertEqual(appels, [["etat-json"]], "un seul relevé, au réveil")

    def test_importer_ferme_le_panneau_et_lance_le_selecteur_puis_nc_vpn(self):
        _, appels, _ = self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var c = Qt.createComponent("Vpn.qml"); fen = c.createObject(racine); fen.fermer.connect(function () { fermee = true }); etape++; return }
                if (etape === 1) { if (!VpnEtat.lu) return
                    t.mouseClick(trouver(fen.contentItem, "nc-vpn-importer")); verifier(fermee, "le panneau se ferme pour laisser la place à zenity")
                    etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 12) return; console.log("FINI"); Qt.exit(0) }
            } }
        ''')
        self.assertIn(["importer", "/ailleurs/labo.ovpn"], appels, "le fichier choisi est passé à nc-vpn en argument")


OUTILS_VPN = """
 function textes(item, l) { l = l || []; if (item.text !== undefined && item.visible && item.text !== "") l.push(String(item.text))
   for (var i = 0; i < item.children.length; i++) textes(item.children[i], l); return l }
"""

if __name__ == "__main__":
    unittest.main()
