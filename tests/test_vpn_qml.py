"""Panneau VPN de l'île (Vpn.qml, VpnEtat.qml, VpnLigne.qml) : lu depuis des sources (aucun sondage, aucun component inline,
LazyLoader, IPC, raccourci, réglages) et hors écran avec le vrai qs lancé par « qs -p » (jamais l'île réelle), HOME et XDG_*
isolés, un faux nc-vpn, un faux nmcli (« monitor » envoie une ligne puis se tait), un faux zenity et un faux notify-send :
tunnels affichés (plusieurs montés), clics (connecter, déconnecter, tout déconnecter), noms masqués pendant un partage d'écran,
IP publique jamais demandée par défaut ni en partage, mises à jour sur événements seulement, NetworkManager absent, écran éteint."""
import json
import re
from pathlib import Path
import shutil
import tempfile
import threading
import time
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
elif a[:2] == ["indicateur", "--json"]:
    n = sum(1 for l in open(H + "/appels") if json.loads(l) == ["indicateur", "--json"]) - 1
    f = H + "/etat-%d.json" % n
    e = json.loads(open(f if os.path.exists(f) else H + "/etat.json").read())
    act = e.get("actives", [])
    if not e.get("disponible"):
        print(json.dumps(dict(disponible=False, actif=False, fournisseur="", pays="", nom="", nombre=0)))
    elif not act:
        print(json.dumps(dict(disponible=True, actif=False, fournisseur="", pays="", nom="", nombre=0, mullvad=e.get("mullvad", False))))
    else:
        print(json.dumps(dict(disponible=True, actif=True, fournisseur=act[0].get("fournisseur", ""), pays=act[0].get("pays", ""),
                              nom=act[0]["nom"], nombre=len(act), mullvad=e.get("mullvad", False))))
elif a[:2] == ["killswitch", "etat-json"]:
    f = H + "/ks.json"
    print(open(f).read() if os.path.exists(f) else json.dumps(dict(installe=True, voulu=True, actif=False, refus="", limites=["Limite un", "Limite deux"])))
elif a[:2] == ["killswitch", "activer"] or a[:2] == ["killswitch", "desactiver"]:
    open(H + "/ks.json", "w").write(json.dumps(dict(installe=True, voulu=True, actif=a[1] == "activer", refus="", limites=["Limite un", "Limite deux"])))
elif a[:1] == ["fournisseurs-json"]:
    e = json.loads(open(H + "/etat.json").read())
    if "fournisseurs" in e: print(json.dumps(dict(contrat=1, fournisseurs=e["fournisseurs"])))
elif a[:2] == ["mullvad", "pays-json"]:
    e = json.loads(open(H + "/etat.json").read())
    print(json.dumps(dict(pays=e.get("mullvad_pays", []))))
elif a[:2] == ["mullvad", "etat-json"]:
    e = json.loads(open(H + "/etat.json").read()).get("mullvad_etat", dict(installe=False))
    if e.get("dynamique"):                  # l'état suit les actions déjà notées : pays choisi, connecter, deconnecter
        pays, con = "", False
        for l in open(H + "/appels"):
            x = json.loads(l)
            if x[:2] == ["mullvad", "pays"]: pays = x[2].upper()
            elif x[:2] == ["mullvad", "connecter"]: con = True
            elif x[:2] == ["mullvad", "deconnecter"]: con = False
        e = dict(e, connecte=con, pays=pays if con else "", hote=(pays.lower() + "-got-wg-004") if con else "")
    print(json.dumps(e))
elif a[:1] == ["ip-publique"]:
    print('{"ip": "203.0.113.7"}')
'''
FAUX_INSTALLEUR = r'''#!/usr/bin/env python3
import json, os, sys
H = os.environ["HOME"]
open(H + "/appels", "a").write(json.dumps(["nc-assistant-install"] + sys.argv[1:]) + "\n")
open(H + "/ks.json", "w").write(json.dumps(dict(installe=True, voulu=True, actif=False, refus="", limites=["Limite un"])))
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
FAUX_MULLVAD = r'''#!/usr/bin/env python3
import os, sys, time
H = os.environ["HOME"]
open(H + "/appels-mullvad", "a").write(" ".join(sys.argv[1:]) + "\n")
if sys.argv[1:] == ["status", "listen"]:
    time.sleep(20)
'''
NOMS_VPN = ("VpnEtat", "VpnLigne", "VpnProtections", "VpnEntete", "VpnCarte", "VpnStat", "VpnBarre", "VpnPastille", "VpnFiltres",
            "VpnListe", "VpnRangee", "VpnCarteFournisseur", "VpnPied", "VpnDebit", "VpnCompteur")
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
        fichiers = sorted(f.stem for f in QML.glob("Vpn*.qml"))
        for attendu in ("Vpn", "VpnEtat", "VpnLigne", "VpnProtections", "VpnEntete", "VpnCarte", "VpnStat", "VpnBarre", "VpnPastille",
                        "VpnFiltres", "VpnListe", "VpnRangee", "VpnCarteFournisseur", "VpnPied", "VpnDebit", "VpnCompteur"):
            self.assertIn(attendu, fichiers)          # chaque composant dans son propre fichier
        for nom in fichiers:
            src = (QML / (nom + ".qml")).read_text()
            self.assertNotRegex(src, r"(?m)^\s*component ", nom)
            rep = [l for l in src.splitlines() if re.search(r"repeat:\s*true", l)]
            if nom == "VpnEtat":      # un seul Timer répétitif : l'état du kill switch, toutes les 10 s, panneau ouvert et écran allumé seulement
                self.assertEqual(len(rep), 1, rep)
                self.assertIn("interval: 10000", rep[0])
                self.assertIn("v.panneauOuvert", rep[0])
                self.assertIn("Etat.ecranVu", rep[0])
                self.assertIn("!v.masque", rep[0])
            elif nom == "VpnDebit":   # les débits : une fois par seconde, seulement si « actif » (fenêtre ouverte et écran allumé)
                self.assertEqual(len(rep), 1, rep)
                self.assertIn("interval: 1000", rep[0])
                self.assertIn("running: d.actif", rep[0])
            else:
                self.assertNotRegex(src, r"repeat:\s*true", nom + " : jamais de relevé toutes les N secondes")
        debit = (QML / "VpnDebit.qml").read_text()
        self.assertIn("model: d.actif ? d.interfaces : []", debit)       # pas de compteur fenêtre fermée ou écran éteint
        self.assertIn("actif: VpnEtat.panneauOuvert && Etat.ecranVu", self.vpn)
        self.assertIn('"/class/net/"', (QML / "VpnCompteur.qml").read_text())
        self.assertIn('NC_SYSFS', (QML / "VpnCompteur.qml").read_text())
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
        self.assertIn("VpnEtat.libelle", compact)
        self.assertIn("VpnEtat.demanderPanneau()", (QML / "Ile.qml").read_text())       # un clic sur l'indicateur ouvre le panneau complet
        self.assertIn("onOuvrirPanneau", self.shell)
        self.assertEqual(lua.count('SUPER .. " + ALT + code:55"'), 1)

    def test_aucune_ligne_de_shell_construite_avec_un_nom(self):
        self.assertEqual(self.etat.count('["sh", "-c"'), 1)      # le seul : l'enveloppe de zenity, texte fixe, fichier choisi jamais dedans
        self.assertNotIn("execDetached([\"sh\"", self.etat)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def lancer(self, corps, etats=None, reglages=None, delai=30, ks=None, sysfs=None, croissance=False):
        """etats : {0: état de départ, 1: état à la 2e lecture…} ; renvoie (journal de qs, appels de nc-vpn, appels de nmcli)."""
        with tempfile.TemporaryDirectory(prefix="nc-vpnqml-") as d:
            root = H.preparer(d, ("Couleurs", "Texte", "Ico", "BoutonReglages") + NOMS_VPN,
                              extra={"Vpn.qml": panneau_hors_fenetre(), "Partage.qml": FAUX_PARTAGE}, singletons=("VpnEtat", "Partage"))
            home = root / "home"
            (home / ".local/bin").mkdir(parents=True)
            for nom, texte, ou in (("nc-vpn", FAUX_NC_VPN, home / ".local/bin"), ("nc-assistant-install", FAUX_INSTALLEUR, home / ".local/bin"), ("nmcli", FAUX_NMCLI, root / "bin"),
                                   ("mullvad", FAUX_MULLVAD, root / "bin")):
                (ou / nom).write_text(texte)
                (ou / nom).chmod(0o755)
            H.faux(root, "notify-send")
            H.faux(root, "zenity", "echo /ailleurs/labo.ovpn")
            etats = etats or {0: etat_deux_tunnels()}
            if ks:
                (home / "ks.json").write_text(json.dumps(ks))
            (home / "etat.json").write_text(json.dumps(etats[0]))
            for k, v in etats.items():
                (home / ("etat-%d.json" % k)).write_text(json.dumps(v))
            entete = H.ENTETE + "import QtTest\n"
            reg = ("Reglages.valeurs = " + json.dumps(reglages) + "\n") if reglages else ""
            (root / "shell.qml").write_text(entete + "ShellRoot {\n id: racine\n property var fen: null\n property bool fermee: false\n property bool ksOuvert: false\n property int etape: 0\n"
                                            " property int ticks: 0\n" + H.OUTILS + OUTILS_VPN
                                            + " TestCase { id: t; name: \"Vpn\"; when: false }\n"
                                            + " Component.onCompleted: { " + reg + "}\n"
                                            + textwrap.dedent(corps) + "\n Timer { interval: 20000; running: true; onTriggered: { console.error(\"ECHEC délai\"); Qt.exit(3) } }\n}\n")
            plus = {}
            arret = threading.Event()
            if sysfs is not None:                # faux /sys/class/net : {interface: (rx, tx)} ; croissance : les compteurs montent sans cesse
                for iface, (rx, tx) in sysfs.items():
                    st = root / "sys/class/net" / iface / "statistics"
                    st.mkdir(parents=True)
                    (st / "rx_bytes").write_text(str(rx) + "\n")
                    (st / "tx_bytes").write_text(str(tx) + "\n")
                plus["NC_SYSFS"] = str(root / "sys")
                if croissance:
                    def monter():
                        n = 0
                        while not arret.wait(0.1):
                            n += 1
                            for iface, (rx, tx) in sysfs.items():
                                st = root / "sys/class/net" / iface / "statistics"
                                (st / "rx_bytes").write_text(str(rx + n * 100000) + "\n")
                                (st / "tx_bytes").write_text(str(tx + n * 20000) + "\n")
                    threading.Thread(target=monter, daemon=True).start()
            try:
                code, sortie = H.lancer(root, delai=delai, **plus)
            finally:
                arret.set()
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)
            lire = lambda n: [x for x in (home / n).read_text().splitlines()] if (home / n).exists() else []
            self.appels_mullvad = lire("appels-mullvad")
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
                    verifier(tous(corps, "nc-vpn-autre").length === 3, "les trois profils dans la liste : " + tous(corps, "nc-vpn-autre").length)
                    var tx = textes(corps)
                    verifier(tx.indexOf("Réseau privé") >= 0 && tx.indexOf("VPN · connexions et protection") >= 0, "titre et sous-titre : " + tx)
                    verifier(tx.indexOf("Connecté · 2 tunnels") >= 0, "titre de la carte : " + tx)
                    verifier(tx.indexOf("Maison") >= 0 && tx.indexOf("Bureau") >= 0 && tx.indexOf("Labo") >= 0, "noms : " + tx)
                    verifier(tx.indexOf("Fermer") >= 0 && trouver(corps, "nc-vpn-reglages").visible, "Fermer et le réglage")
                    verifier(trouver(corps, "nc-vpn-tout").visible, "Tout déconnecter")
                    verifier(trouver(corps, "nc-vpn-ip") === null || !trouver(corps, "nc-vpn-ip").visible, "pas de ligne d'IP par défaut")
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

    def test_clic_indicateur_et_raccourci_ouvrent_la_meme_fenetre(self):
        vpn = (QML / "Vpn.qml").read_text()
        shell = (QML / "shell.qml").read_text()
        self.assertEqual(len(re.findall(r"(?m)^\s*Vpn \{", shell)), 1, "une seule fenêtre VPN dans shell.qml")
        self.assertRegex(shell, r"function vpn\(\): void \{[^}]*racine\.vpnOuvert = !racine\.vpnOuvert")            # Super + Alt + V
        self.assertIn("function onOuvrirPanneau() { if (!racine.vpnOuvert)", shell)                         # clic sur l'indicateur
        self.assertIn("racine.vpnOuvert = true", shell)
        self.assertIn("VpnEtat.demanderPanneau()", (QML / "Ile.qml").read_text())
        self.assertIn('namespace: "nc-vpn"', vpn.replace("WlrLayershell.namespace: ", "namespace: "))
        compact = (QML / "Compact.qml").read_text()
        self.assertIn('nom: "shield_lock"', compact)         # notre glyphe, pas celui des clients
        self.assertIn('objectName: "nc-vpn-pill-glyphe"', compact)

    def test_ip_publique_demandee_a_l_ouverture_seulement_si_voulue_et_jamais_en_partage(self):
        _, appels, _ = self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var c = Qt.createComponent("Vpn.qml"); fen = c.createObject(racine); etape++; return }
                if (etape === 1) { if (VpnEtat.ip === "") return
                    verifier(VpnEtat.ip === "203.0.113.7", "IP lue : " + VpnEtat.ip)
                    verifier(textes(fen.contentItem).indexOf("203.0.113.7") >= 0, "IP affichée : " + textes(fen.contentItem))
                    verifier(textes(fen.contentItem).join("|").indexOf("IP via exemple.invalid") >= 0, "pied : IP via le service : " + textes(fen.contentItem))
                    Partage.silence = true; etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 3) return
                    verifier(VpnEtat.ip === "", "IP effacée en partage")
                    verifier(!trouver(fen.contentItem, "nc-vpn-ip").visible, "IP masquée en partage")
                    verifier(textes(fen.contentItem).join("|").indexOf("IP via") < 0, "pied sans le service en partage")
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
                    if (ticks === 8) verifier(VpnEtat.lu && VpnEtat.indNombre === 0 && !VpnEtat.indicateur, "départ : aucun tunnel, pas de bouclier")
                    if (ticks < 38) return
                    verifier(VpnEtat.indNombre === 2 && VpnEtat.indicateur, "l'événement de nmcli a relancé la lecture : " + VpnEtat.indNombre)
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', etats={0: zero, 1: un})
        self.assertEqual(nmcli, ["monitor"], "nmcli monitor lancé une seule fois")
        self.assertEqual([a for a in appels if a == ["indicateur", "--json"]], [["indicateur", "--json"]] * 2, "un relevé au départ, un seul après l'événement, aucun entre les deux")

    def test_libelle_fournisseur_pays_drapeau_plusieurs_tunnels_et_partage(self):
        c = [LIGNE_J(U2, "ProtonVPN FR#12", "vpn", True, "proton0"), LIGNE_J(U3, "Bureau", "vpn", True, "tun1"),
             LIGNE_J(U1, "Labo", "vpn", False, "")]
        c[0].update(fournisseur="Proton VPN", pays="FR")
        etat = dict(disponible=True, connexions=c, actives=c[:2])
        _, appels, nmcli = self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var d = VpnEtat.disponible; etape++; ticks = 0; return }
                if (etape === 1) { if (ticks < 8) return
                    verifier(VpnEtat.indicateur, "indicateur")
                    var attendu = "Proton VPN · " + String.fromCodePoint(0x1F1EB, 0x1F1F7) + " FR +1"
                    verifier(VpnEtat.libelle === attendu, "libellé : " + VpnEtat.libelle)
                    Partage.silence = true; etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 2) return
                    verifier(VpnEtat.libelle === "VPN", "partage : VPN seul : " + VpnEtat.libelle)
                    Partage.silence = false; VpnEtat.indPays = "fr"
                    etape++; ticks = 0; return }
                if (etape === 3) { if (ticks < 2) return
                    verifier(VpnEtat.drapeau === "", "un code pays mal formé n'a pas de drapeau")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', etats={0: etat})
        self.assertEqual(appels[0], ["indicateur", "--json"])
        self.assertFalse([a for a in appels if a[0] == "etat-json"], "panneau fermé : lecture légère seulement")

    def test_client_non_connecte_ne_donne_rien(self):
        c = [LIGNE_J(U1, "ProtonVPN FR#12", "vpn", False, ""), LIGNE_J(U2, "mullvad-de1", "wireguard", False, "")]
        c[0].update(fournisseur="Proton VPN", pays="FR")
        self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var d = VpnEtat.disponible; etape++; ticks = 0; return }
                if (etape === 1) { if (ticks < 8) return
                    verifier(VpnEtat.lu && !VpnEtat.indicateur && VpnEtat.indFournisseur === "", "rien d'affiché")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', etats={0: dict(disponible=True, connexions=c, actives=[])})

    def test_vpn_indicateur_non_pas_d_indicateur_ni_de_moniteur(self):
        _, appels, nmcli = self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var d = VpnEtat.disponible; etape++; ticks = 0; return }
                if (etape === 1) { if (ticks < 8) return
                    verifier(!VpnEtat.indicateur && !VpnEtat.veille, "VPN_INDICATEUR=non")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', reglages={"VPN_INDICATEUR": "non"})
        self.assertEqual(nmcli, [], "pas de moniteur")
        self.assertEqual(appels, [], "pas de lecture")

    def test_panneau_complet_protections_et_resume_masque_en_partage(self):
        c = [LIGNE_J(U2, "ProtonVPN FR#12", "vpn", True, "proton0"), LIGNE_J(U3, "Labo", "wireguard", True, "wg-labo")]
        c[0].update(fournisseur="Proton VPN", pays="FR")
        self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var k = Qt.createComponent("Vpn.qml"); fen = k.createObject(racine); etape++; return }
                if (etape === 1) { if (!VpnEtat.lu || ticks < 6) return
                    var corps = fen.contentItem
                    var tx = textes(corps)
                    var fl = String.fromCodePoint(0x1F1EB, 0x1F1F7)
                    verifier(trouver(corps, "nc-vpn-ks-pastille").visible, "pastille Kill switch")
                    verifier(!trouver(corps, "nc-vpn-protections").visible, "détail replié au départ")
                    verifier(trouver(corps, "nc-vpn-importer").visible && trouver(corps, "nc-vpn-actifs").visible, "fenêtre complète")
                    verifier(tx.indexOf("Connecté · " + fl + " FR · 2 tunnels") >= 0, "titre de la carte : " + tx)
                    verifier(tx.join("|").indexOf("Proton VPN · " + fl + " FR") >= 0, "ligne du tunnel : " + tx)
                    verifier(tx.indexOf("Importer un profil") >= 0 && tx.indexOf("Rechercher un pays, un serveur ou un profil…") >= 0, "boutons : " + tx)
                    verifier(tx.join("|").indexOf("Profils NetworkManager et clients installés · Débits mesurés sur le tunnel") >= 0, "pied : " + tx)
                    verifier(!tx.some(x => x.indexOf("IP via") >= 0), "pas d'IP, donc pas d'« IP via »")
                    Partage.silence = true; etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 2) return
                    var t2 = textes(fen.contentItem).join("|")
                    verifier(t2.indexOf("Proton VPN") < 0 && t2.indexOf("FR") < 0 && t2.indexOf("proton0") < 0, "fournisseur, pays et interface masqués : " + t2)
                    verifier(t2.indexOf("Connecté · 2 tunnels") >= 0, "titre sans pays en partage : " + t2)
                    verifier(!trouver(fen.contentItem, "nc-vpn-ks-pastille").visible, "pas de kill switch en partage")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', etats={0: dict(disponible=True, connexions=c, actives=c)})

    def test_carte_deux_tunnels_filtres_recherche_et_pastille_du_filtre(self):
        c = [LIGNE_J(U2, "ProtonVPN FR#12", "vpn", True, "proton0"), LIGNE_J(U3, "Labo", "wireguard", False, ""),
             LIGNE_J(U1, "Cyberghost DE", "vpn", False, "")]
        c[0].update(fournisseur="Proton VPN", pays="FR")
        c[2].update(fournisseur="CyberGhost", pays="DE")
        etat = dict(disponible=True, connexions=c, actives=c[:1], mullvad=False)
        self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var k = Qt.createComponent("Vpn.qml"); fen = k.createObject(racine); etape++; return }
                if (etape === 1) { if (!VpnEtat.lu || ticks < 6) return
                    var corps = fen.contentItem
                    verifier(trouver(corps, "nc-vpn-filtre-tous") && trouver(corps, "nc-vpn-filtre-proton") && trouver(corps, "nc-vpn-filtre-nord")
                             && trouver(corps, "nc-vpn-filtre-mullvad") && trouver(corps, "nc-vpn-filtre-perso"), "pastilles")
                    verifier(trouver(corps, "nc-vpn-filtre-cyberghost"), "CyberGhost détecté : sa pastille")
                    verifier(tous(corps, "nc-vpn-autre").length === 3, "Tous : trois profils")
                    t.mouseClick(trouver(corps, "nc-vpn-filtre-perso")); etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 2) return
                    var autres = tous(fen.contentItem, "nc-vpn-autre")
                    verifier(autres.length === 1 && textes(autres[0]).indexOf("Labo") >= 0, "Profils perso : Labo seulement : " + autres.length)
                    verifier(textes(autres[0]).join("|").indexOf("Profil · WireGuard") >= 0, "profil · protocole : " + textes(autres[0]))
                    t.mouseClick(trouver(fen.contentItem, "nc-vpn-filtre-cyberghost")); etape++; ticks = 0; return }
                if (etape === 3) { if (ticks < 2) return
                    var cg = tous(fen.contentItem, "nc-vpn-autre")
                    verifier(cg.length === 1 && textes(cg[0]).join("|").indexOf("Cyberghost DE") >= 0, "CyberGhost : son profil")
                    t.mouseClick(trouver(fen.contentItem, "nc-vpn-filtre-tous")); etape++; ticks = 0; return }
                if (etape === 4) { if (ticks < 2) return
                    var champ = trouver(fen.contentItem, "nc-vpn-recherche")
                    champ.forceActiveFocus(); champ.text = "lab"; etape++; ticks = 0; return }
                if (etape === 5) { if (ticks < 2) return
                    var r = tous(fen.contentItem, "nc-vpn-autre")
                    verifier(r.length === 1 && textes(r[0]).indexOf("Labo") >= 0, "recherche « lab » : Labo seul : " + r.length)
                    trouver(fen.contentItem, "nc-vpn-recherche").text = "zzzz"; etape++; ticks = 0; return }
                if (etape === 6) { if (ticks < 2) return
                    verifier(tous(fen.contentItem, "nc-vpn-autre").length === 0 && trouver(fen.contentItem, "nc-vpn-vide").visible, "aucun résultat")
                    trouver(fen.contentItem, "nc-vpn-recherche").text = "fr"; etape++; ticks = 0; return }
                if (etape === 7) { if (ticks < 2) return
                    var fr = tous(fen.contentItem, "nc-vpn-autre")
                    verifier(fr.length === 1 && textes(fr[0]).join("|").indexOf("ProtonVPN FR#12") >= 0, "recherche par code pays : " + fr.length)
                    verifier(textes(fr[0]).indexOf("Connecté") >= 0, "la ligne du tunnel monté est marquée Connecté")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', etats={0: etat})

    def test_fournisseurs_pas_prets_cartes_d_etat_sans_faux_bouton(self):
        etat = dict(disponible=True, connexions=[], actives=[], mullvad=False)
        self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var k = Qt.createComponent("Vpn.qml"); fen = k.createObject(racine); etape++; return }
                if (etape === 1) { if (!VpnEtat.lu || ticks < 6) return
                    var corps = fen.contentItem
                    var f = VpnEtat.fournisseurs
                    verifier(f.length === 3 && f[0].etat === "absent" && f[0].bientot && f[1].bientot && f[2].id === "mullvad" && f[2].etat === "absent", "modèle : " + JSON.stringify(f))
                    t.mouseClick(trouver(corps, "nc-vpn-filtre-proton")); etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 2) return
                    var corps2 = fen.contentItem
                    var carte = trouver(corps2, "nc-vpn-carte-fournisseur")
                    verifier(carte.visible, "carte d'état Proton")
                    var tx = textes(carte).join("|")
                    verifier(tx.indexOf("Proton VPN · bientôt") >= 0 && tx.indexOf("arrive bientôt") >= 0, "bientôt : " + tx)
                    verifier(tous(corps2, "nc-vpn-rangee-bouton").length === 0 && tous(corps2, "nc-vpn-pays").length === 0, "aucun bouton Connecter")
                    t.mouseClick(trouver(corps2, "nc-vpn-filtre-nord")); etape++; ticks = 0; return }
                if (etape === 3) { if (ticks < 2) return
                    verifier(textes(trouver(fen.contentItem, "nc-vpn-carte-fournisseur")).join("|").indexOf("NordVPN · bientôt") >= 0, "Nord bientôt")
                    t.mouseClick(trouver(fen.contentItem, "nc-vpn-filtre-mullvad")); etape++; ticks = 0; return }
                if (etape === 4) { if (ticks < 2) return
                    var tm = textes(trouver(fen.contentItem, "nc-vpn-carte-fournisseur")).join("|")
                    verifier(tm.indexOf("Mullvad · client absent") >= 0 && tm.indexOf("n'est pas installée") >= 0, "Mullvad absent : " + tm)
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', etats={0: etat})

    def test_mullvad_sans_compte_carte_d_etat_et_ecoute_unique(self):
        pays = [dict(cc="FR", nom="France"), dict(cc="SE", nom="Sweden")]
        sans = dict(disponible=True, connexions=[], actives=[], mullvad=True, mullvad_pays=pays,
                    mullvad_etat=dict(installe=True, connecte=False, pays="", hote="", compte=False))
        self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var k = Qt.createComponent("Vpn.qml"); fen = k.createObject(racine); etape++; return }
                if (etape === 1) { if (!VpnEtat.lu || ticks < 8) return
                    t.mouseClick(trouver(fen.contentItem, "nc-vpn-filtre-mullvad")); etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 2) return
                    var tm = textes(trouver(fen.contentItem, "nc-vpn-carte-fournisseur")).join("|")
                    verifier(tm.indexOf("Mullvad · installé, sans compte") >= 0 && tm.indexOf("ne lit jamais ton numéro de compte") >= 0, "sans compte : " + tm)
                    verifier(tous(fen.contentItem, "nc-vpn-pays").length === 0 && tous(fen.contentItem, "nc-vpn-rangee-bouton").length === 0, "pas de pays ni de bouton sans compte")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', etats={0: sans})
        self.assertEqual(self.appels_mullvad.count("status listen"), 1, "écoute lancée une fois, panneau ouvert : " + str(self.appels_mullvad))

    def test_mullvad_pret_pays_connecter_changer_deconnecter_et_masquage(self):
        pays = [dict(cc="FR", nom="France"), dict(cc="SE", nom="Sweden")]
        pret = dict(disponible=True, connexions=[], actives=[], mullvad=True, mullvad_pays=pays,
                    mullvad_etat=dict(installe=True, connecte=False, pays="", hote="", compte=True, dynamique=True))
        _, appels, _ = self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var k = Qt.createComponent("Vpn.qml"); fen = k.createObject(racine); etape++; return }
                if (etape === 1) { if (!VpnEtat.lu || ticks < 8) return
                    t.mouseClick(trouver(fen.contentItem, "nc-vpn-filtre-mullvad")); etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 3) return
                    var p = tous(fen.contentItem, "nc-vpn-pays")
                    verifier(p.length === 2, "prêt : deux pays : " + p.length)
                    verifier(textes(p[0]).join("|").indexOf("France") >= 0 && textes(p[1]).join("|").indexOf("Sweden") >= 0, "pays : " + textes(p[0]))
                    verifier(textes(p[1]).join("|").indexOf("Mullvad · WireGuard") >= 0, "fournisseur · protocole")
                    verifier(textes(p[1]).indexOf("Connecter") >= 0, "Connecter")
                    verifier(textes(fen.contentItem).indexOf("Déconnecté") >= 0, "carte déconnectée")
                    t.mouseClick(p[1]); etape++; ticks = 0; return }
                if (etape === 3) { if (ticks < 14) return
                    var p2 = tous(fen.contentItem, "nc-vpn-pays")
                    verifier(textes(p2[1]).indexOf("Connecté") >= 0 && textes(p2[0]).indexOf("Changer") >= 0, "pays actif Connecté, l'autre Changer : " + textes(p2[0]) + textes(p2[1]))
                    var tx = textes(fen.contentItem)
                    verifier(tx.indexOf("Connecté · " + String.fromCodePoint(0x1F1F8, 0x1F1EA) + " SE") >= 0, "carte : " + tx)
                    verifier(tx.join("|").indexOf("Mullvad · " + String.fromCodePoint(0x1F1F8, 0x1F1EA) + " SE") >= 0 && tx.join("|").indexOf("se-got-wg-004") >= 0, "tunnel Mullvad : " + tx)
                    t.mouseClick(p2[0]); etape++; ticks = 0; return }
                if (etape === 4) { if (ticks < 14) return
                    verifier(textes(fen.contentItem).indexOf("Connecté · " + String.fromCodePoint(0x1F1EB, 0x1F1F7) + " FR") >= 0, "changé pour la France : " + textes(fen.contentItem))
                    Partage.silence = true; etape++; ticks = 0; return }
                if (etape === 5) { if (ticks < 2) return
                    var t2 = textes(fen.contentItem).join("|")
                    verifier(t2.indexOf("fr-got-wg-004") < 0 && !t2.includes(String.fromCodePoint(0x1F1EB, 0x1F1F7) + " FR"), "relais et pays du tunnel masqués en partage : " + t2)
                    verifier(t2.indexOf("Tunnel 1") >= 0 && t2.indexOf("Changer") < 0, "tunnel anonyme, aucun pays marqué actif : " + t2)
                    Partage.silence = false; etape++; ticks = 0; return }
                if (etape === 6) { if (ticks < 3) return
                    t.mouseClick(tous(fen.contentItem, "nc-vpn-bouton").filter(b => b.visible)[0]); etape++; ticks = 0; return }       // Déconnecter Mullvad
                if (etape === 7) { if (ticks < 12) return
                    verifier(textes(fen.contentItem).indexOf("Déconnecté") >= 0, "déconnecté")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', etats={0: pret})
        self.assertEqual([a for a in appels if a[0] == "mullvad" and a[1] in ("pays", "connecter", "deconnecter")],
                         [["mullvad", "pays", "se"], ["mullvad", "connecter"], ["mullvad", "pays", "fr"], ["mullvad", "connecter"], ["mullvad", "deconnecter"]],
                         "choisir le pays puis connecter ; Changer idem ; Déconnecter")
        self.assertEqual(appels.count(["mullvad", "pays-json"]), 1, "liste des pays lue une fois")

    def test_nord_proton_branches_sur_fournisseurs_json_login_connecter_et_tout_couper(self):
        fl = [dict(id="nord", nom="NordVPN", etat="pret", message="", pays=[dict(code="fr", nom="France"), dict(code="de", nom="Germany")],
                   pays_actif="fr", connecte=True, peut_login=False),
              dict(id="proton", nom="Proton VPN", etat="sans_compte", message="Pas de compte Proton connecté.", pays=[], pays_actif="",
                   connecte=False, peut_login=True)]
        etat = dict(disponible=True, connexions=[], actives=[], fournisseurs=fl)
        _, appels, _ = self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var k = Qt.createComponent("Vpn.qml"); fen = k.createObject(racine); etape++; return }
                if (etape === 1) { if (!VpnEtat.lu || ticks < 8) return
                    var tx = textes(fen.contentItem)
                    verifier(tx.indexOf("Connecté · " + String.fromCodePoint(0x1F1EB, 0x1F1F7) + " FR") >= 0, "tunnel Nord : " + tx)
                    t.mouseClick(trouver(fen.contentItem, "nc-vpn-filtre-proton")); etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 2) return
                    var tp = textes(trouver(fen.contentItem, "nc-vpn-carte-fournisseur")).join("|")
                    verifier(tp.indexOf("Pas de compte Proton connecté.") >= 0 && tp.indexOf("bientôt") < 0, "message de nc-vpn : " + tp)
                    t.mouseClick(trouver(fen.contentItem, "nc-vpn-fournisseur-login")); etape++; ticks = 0; return }
                if (etape === 3) { if (ticks < 6) return
                    t.mouseClick(trouver(fen.contentItem, "nc-vpn-filtre-nord")); etape++; ticks = 0; return }
                if (etape === 4) { if (ticks < 2) return
                    var p = tous(fen.contentItem, "nc-vpn-pays")
                    verifier(p.length === 2 && textes(p[0]).indexOf("Connecté") >= 0 && textes(p[1]).indexOf("Changer") >= 0, "pays Nord : " + p.length)
                    t.mouseClick(p[1]); etape++; ticks = 0; return }
                if (etape === 5) { if (ticks < 6) return
                    t.mouseClick(trouver(fen.contentItem, "nc-vpn-tout")); etape++; ticks = 0; return }
                if (etape === 6) { if (ticks < 8) return; console.log("FINI"); Qt.exit(0) }
            } }
        ''', etats={0: etat})
        act = [a for a in appels if a[:1] == ["fournisseur"] or a[:1] == ["tout-deconnecter"]]
        self.assertEqual(act, [["fournisseur", "proton", "login"], ["fournisseur", "nord", "connecter", "DE"],
                               ["fournisseur", "nord", "deconnecter"]])

    def test_deux_tunnels_nm_et_mullvad_tout_deconnecter_arguments_exacts(self):
        c = [LIGNE_J(U2, "Labo", "wireguard", True, "wg-labo")]
        etat = dict(disponible=True, connexions=c, actives=c, mullvad=True, mullvad_pays=[],
                    mullvad_etat=dict(installe=True, connecte=True, pays="SE", hote="se-got-wg-004", compte=True))
        _, appels, _ = self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var k = Qt.createComponent("Vpn.qml"); fen = k.createObject(racine); etape++; return }
                if (etape === 1) { if (!VpnEtat.lu || ticks < 8) return
                    verifier(tous(fen.contentItem, "nc-vpn-actif").length === 2, "un profil de labo ET Mullvad en même temps")
                    verifier(textes(fen.contentItem).indexOf("Connecté · " + String.fromCodePoint(0x1F1F8, 0x1F1EA) + " SE · 2 tunnels") >= 0, "titre : " + textes(fen.contentItem))
                    t.mouseClick(trouver(fen.contentItem, "nc-vpn-tout")); etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 15) return
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', etats={0: etat})
        self.assertEqual([a for a in appels if a[0] in ("tout-deconnecter", "deconnecter") or a[:2] == ["mullvad", "deconnecter"]],
                         [["tout-deconnecter"], ["mullvad", "deconnecter"]])

    def test_debits_indisponibles_sans_sys_puis_calcules_sur_une_seconde(self):
        c = [LIGNE_J(U2, "Labo", "wireguard", True, "wg-labo")]
        etat = dict(disponible=True, connexions=c, actives=c)
        self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var k = Qt.createComponent("Vpn.qml"); fen = k.createObject(racine); etape++; return }
                if (etape === 1) { if (ticks < 45) return
                    var tx = textes(fen.contentItem)
                    verifier(tx.indexOf("Durée de connexion") >= 0 && tx.indexOf("Débit ↓") >= 0 && tx.indexOf("Débit ↑") >= 0, "mesures : " + tx)
                    verifier(tx.filter(x => x === "indisponible").length >= 3, "durée et deux débits indisponibles sans /sys ni horodatage : " + tx)
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', etats={0: etat}, sysfs={})
        self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var k = Qt.createComponent("Vpn.qml"); fen = k.createObject(racine); etape++; return }
                if (etape === 1) { if (ticks < 50) return
                    var tx = textes(fen.contentItem)
                    var d = tous(fen.contentItem, "nc-vpn-debit-bas")[0]
                    verifier(tx.some(x => /^[0-9]+([,.][0-9])? (Ko|Mo)\\/s$/.test(x)), "débits chiffrés (~1 Mo/s ↓, ~200 Ko/s ↑) : " + tx)
                    verifier(tx.some(x => /^2 min [0-9]{2} s$|^3 min [0-9]{2} s$/.test(x)), "durée de connexion (~2 min 10 s) : " + tx)
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', etats={0: dict(etat, connexions=[dict(c[0], depuis=int(time.time()) - 125)], actives=[dict(c[0], depuis=int(time.time()) - 125)])}, sysfs={"wg-labo": (1000, 500)}, croissance=True)

    def test_debits_seulement_fenetre_ouverte_et_ecran_allume(self):
        c = [LIGNE_J(U2, "Labo", "wireguard", True, "wg-labo")]
        etat = dict(disponible=True, connexions=c, actives=c)
        self.lancer('''
            property int memo: 0
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var k = Qt.createComponent("Vpn.qml"); fen = k.createObject(racine); etape++; return }
                if (etape === 1) { if (ticks < 15) return
                    var deb = trouver(fen.contentItem, "nc-vpn-debit")
                    verifier(deb.actif && deb.tics >= 1, "fenêtre ouverte et écran allumé : relevés en cours : " + deb.tics)
                    Etat.ecranVu = false; etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 3) return
                    var d2 = trouver(fen.contentItem, "nc-vpn-debit")
                    verifier(!d2.actif && d2.bas === -1 && d2.haut === -1, "écran éteint : arrêtés et remis à zéro")
                    memo = d2.tics; etape++; ticks = 0; return }
                if (etape === 3) { if (ticks < 25) return
                    verifier(trouver(fen.contentItem, "nc-vpn-debit").tics === memo, "écran éteint : aucun relevé en 2,5 s")
                    Etat.ecranVu = true; etape++; ticks = 0; return }
                if (etape === 4) { if (ticks < 15) return
                    verifier(trouver(fen.contentItem, "nc-vpn-debit").tics > memo, "écran rallumé : reprise")
                    fen.destroy(); etape++; ticks = 0; return }
                if (etape === 5) { if (ticks < 3) return
                    verifier(!VpnEtat.panneauOuvert, "fenêtre fermée : plus de panneau ouvert")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', etats={0: etat}, sysfs={"wg-labo": (1000, 500)})

    def test_kill_switch_limites_confirmation_activation_coupure_et_partage(self):
        _, appels, _ = self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var k = Qt.createComponent("Vpn.qml"); fen = k.createObject(racine); etape++; return }
                if (etape === 1) { if (!VpnEtat.lu || ticks < 6) return
                    if (!ksOuvert) { ksOuvert = true; t.mouseClick(trouver(fen.contentItem, "nc-vpn-ks-pastille")); ticks = 4; return }
                    var corps = fen.contentItem
                    verifier(trouver(corps, "nc-vpn-protections").visible, "section Protections")
                    var tx = textes(corps).join("|")
                    verifier(tx.indexOf("Bloquer tout hors du VPN") >= 0, "interrupteur : " + tx)
                    verifier(tx.indexOf("Limite un") >= 0 && tx.indexOf("Limite deux") >= 0, "limites montrées avant d'activer : " + tx)
                    verifier(!trouver(corps, "nc-vpn-ks-confirmation").visible, "pas de confirmation au départ")
                    t.mouseClick(trouver(corps, "nc-vpn-ks-bascule")); etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 2) return
                    var corps2 = fen.contentItem
                    verifier(trouver(corps2, "nc-vpn-ks-confirmation").visible, "confirmation demandée")
                    t.mouseClick(trouver(corps2, "nc-vpn-ks-annuler")); etape++; ticks = 0; return }
                if (etape === 3) { if (ticks < 2) return
                    var corps3 = fen.contentItem
                    verifier(!trouver(corps3, "nc-vpn-ks-confirmation").visible, "annulé : rien de caché")
                    t.mouseClick(trouver(corps3, "nc-vpn-ks-bascule")); etape++; ticks = 0; return }
                if (etape === 4) { if (ticks < 2) return
                    t.mouseClick(trouver(fen.contentItem, "nc-vpn-ks-confirmer")); etape++; ticks = 0; return }
                if (etape === 5) { if (ticks < 10) return
                    verifier(VpnEtat.ksActif === true, "actif relu après l'action")
                    verifier(textes(fen.contentItem).join("|").indexOf("Actif") >= 0, "état actif affiché")
                    verifier(textes(fen.contentItem).indexOf("Kill switch · actif") >= 0, "pastille active : " + textes(fen.contentItem))
                    Partage.silence = true; etape++; ticks = 0; return }
                if (etape === 6) { if (ticks < 2) return
                    verifier(!trouver(fen.contentItem, "nc-vpn-protections").visible, "rien pendant un partage d'écran")
                    VpnEtat.killswitchActiver(); VpnEtat.killswitchDesactiver()           // ignorés en partage
                    Partage.silence = false; etape++; ticks = 0; return }
                if (etape === 7) { if (ticks < 6) return
                    t.mouseClick(trouver(fen.contentItem, "nc-vpn-ks-bascule")); etape++; ticks = 0; return }       // coupure en un clic
                if (etape === 8) { if (ticks < 10) return
                    verifier(VpnEtat.ksActif === false, "coupé")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''')
        ks = [a for a in appels if a[:1] == ["killswitch"]]
        self.assertEqual([a[1] for a in ks if a[1] != "etat-json"], ["activer", "desactiver"])      # une activation après confirmation, une coupure
        self.assertNotIn(["killswitch", "activer"], appels[:appels.index(["killswitch", "activer"])])

    def test_kill_switch_refuse_ou_coupe_dans_les_reglages(self):
        _, appels, _ = self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var k = Qt.createComponent("Vpn.qml"); fen = k.createObject(racine); etape++; return }
                if (etape === 1) { if (!VpnEtat.lu || ticks < 6) return
                    if (!ksOuvert) { ksOuvert = true; t.mouseClick(trouver(fen.contentItem, "nc-vpn-ks-pastille")); ticks = 4; return }
                    var corps = fen.contentItem
                    var tx = textes(corps).join("|")
                    verifier(tx.indexOf("Refusé : Aucun tunnel monté") >= 0, "refus et raison : " + tx)
                    t.mouseClick(trouver(corps, "nc-vpn-ks-bascule")); etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 3) return
                    verifier(!trouver(fen.contentItem, "nc-vpn-ks-confirmation").visible, "refusé : pas de confirmation")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', ks=dict(installe=True, voulu=True, actif=False, refus="Aucun tunnel monté", limites=["L"]))
        self.assertFalse([a for a in appels if a[:2] in (["killswitch", "activer"], ["killswitch", "desactiver"])])

    def test_kill_switch_pas_installe_pas_de_couper_et_bouton_installer(self):
        _, appels, _ = self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var k = Qt.createComponent("Vpn.qml"); fen = k.createObject(racine); etape++; return }
                if (etape === 1) { if (!VpnEtat.lu || ticks < 6) return
                    if (!ksOuvert) { ksOuvert = true; t.mouseClick(trouver(fen.contentItem, "nc-vpn-ks-pastille")); ticks = 4; return }
                    var corps = fen.contentItem
                    var tx = textes(corps).join("|")
                    verifier(tx.indexOf("Pas installé : l'assistant se pose avec ton accord") >= 0, "pas installé affiché : " + tx)
                    verifier(tx.indexOf("Kill switch · pas installé") >= 0, "pastille : " + tx)
                    verifier(tx.indexOf("Inconnu") < 0 && tx.indexOf("Couper") < 0, "ni inconnu ni Couper : " + tx)
                    verifier(!trouver(corps, "nc-vpn-ks-bascule").visible, "pas de bouton Couper ni Activer")
                    var b = trouver(corps, "nc-vpn-ks-installer")
                    verifier(b.visible && tx.indexOf("Installer l'assistant") >= 0, "bouton Installer l'assistant : " + tx)
                    t.mouseClick(b); etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 10) return
                    var corps2 = fen.contentItem
                    verifier(VpnEtat.ksInstalle === true, "état relu après la fenêtre")
                    verifier(!trouver(corps2, "nc-vpn-ks-installer").visible, "plus de bouton Installer")
                    verifier(trouver(corps2, "nc-vpn-ks-bascule").visible, "l'interrupteur revient")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', ks=dict(installe=False, voulu=True, actif=None, refus="Pas installé", limites=["L"]))
        self.assertEqual([a for a in appels if a[:1] == ["nc-assistant-install"]], [["nc-assistant-install", "killswitch"]])
        i = appels.index(["nc-assistant-install", "killswitch"])
        self.assertIn(["killswitch", "etat-json"], appels[i + 1:], "relecture après la fin de la fenêtre")
        self.assertFalse([a for a in appels if a[:2] in (["killswitch", "activer"], ["killswitch", "desactiver"])])

    def test_kill_switch_etat_inconnu_propose_de_couper(self):
        _, appels, _ = self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var k = Qt.createComponent("Vpn.qml"); fen = k.createObject(racine); etape++; return }
                if (etape === 1) { if (!VpnEtat.lu || ticks < 6) return
                    if (!ksOuvert) { ksOuvert = true; t.mouseClick(trouver(fen.contentItem, "nc-vpn-ks-pastille")); ticks = 4; return }
                    var corps = fen.contentItem
                    var tx = textes(corps).join("|")
                    verifier(VpnEtat.ksActif === null, "état inconnu")
                    verifier(tx.indexOf("Kill switch · inconnu") >= 0, "pastille : " + tx)
                    verifier(tx.indexOf("Inconnu") >= 0, "affiché inconnu : " + tx)
                    verifier(tx.indexOf("Couper le kill switch") >= 0, "Couper proposé : " + tx)
                    t.mouseClick(trouver(corps, "nc-vpn-ks-bascule")); etape++; ticks = 0; return }
                if (etape === 2) { if (ticks < 6) return
                    verifier(!trouver(fen.contentItem, "nc-vpn-ks-confirmation").visible, "couper : pas de confirmation")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', ks=dict(installe=True, voulu=True, actif=None, refus="", limites=["L"]))
        self.assertIn(["killswitch", "desactiver"], appels)
        self.assertNotIn(["killswitch", "activer"], appels)

    def test_kill_switch_sources(self):
        src = (QML / "VpnProtections.qml").read_text()
        self.assertIn("!VpnEtat.masque", src)
        self.assertNotRegex(src, r"(?m)^\s*component ")
        self.assertIn("killswitchDesactiver()", src)
        etat = (QML / "VpnEtat.qml").read_text()
        self.assertIn('"nc-vpn", "killswitch", "etat-json"]', etat)
        self.assertIn("panneauOuvert && disponible && !masque", etat)
        self.assertIn("v.ksActif = null", etat)                       # JSON illisible : état inconnu

    def test_mullvad_sans_panneau_ni_tunnel_aucune_ecoute(self):
        etat = dict(disponible=True, connexions=[], actives=[], mullvad=True)
        self.lancer('''
            Timer { interval: 100; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) { var d = VpnEtat.disponible; etape++; ticks = 0; return }
                if (etape === 1) { if (ticks < 10) return
                    verifier(VpnEtat.mullvadInstalle, "installé")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', etats={0: etat})
        self.assertEqual(self.appels_mullvad, [], "ni panneau ouvert ni tunnel : pas de mullvad status listen")

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
        self.assertFalse([a for a in appels if a[0] not in ("etat-json", "indicateur", "fournisseurs-json")])

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
        self.assertEqual(appels, [["indicateur", "--json"]], "un seul relevé léger, au réveil, sans panneau")

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
