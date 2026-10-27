"""Partage d'écran discret (Partage.qml, Notifs.qml, Compact.qml, PageNotifs.qml, réglage PARTAGE_DISCRET).

- Source : l'événement Hyprland « screencast » lu sur le canal de Quickshell (aucun processus de plus), l'ordre des modes de
  la pilule, le réglage de nc-reglages, la Concentration jamais assignée par Partage.qml, rien écrit sur le disque.
- Hors écran, avec le vrai qs sur un bus de session privé (dbus-run-session) et le vrai notify-send, comme test_notifs :
  les vrais Notifs.qml, Partage.qml et PageNotifs.qml reçoivent des événements « screencast » simulés (Partage.evenement,
  la fonction qu'appelle le signal rawEvent). Cas : bulle retenue dès le début, indicateur seulement après 1,5 s, urgentes
  retenues aussi, début-début-fin, fin sans début, capture courte (bulle montrée à la fin, sans message), compteur et
  notification de fin, Concentration intacte (active avant et après, inactive avant et après, changée pendant), réglage
  PARTAGE_DISCRET=non (rien ne change, même coupé en plein partage), page « Ton écran est partagé ».
- Le canal lui-même (Hyprland.rawEvent) est essayé avec un faux socket2 de Hyprland dans un dossier temporaire.
HOME et XDG_RUNTIME_DIR isolés, jamais les vrais ; aucune vraie notification, aucun vrai partage."""
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest

from tests import _isolation
from tests.test_notifs import Notifications

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
PROPRIETES = """property double marque: 0
                    function marquer() { marque = Date.now() }
                    function passe(ms) { return Date.now() - marque >= ms }
                    function attendu(texte) { return Notifs.liste.find(x => x.summary === texte) }"""

HORS_ECRAN = unittest.skipUnless(shutil.which("qs") and shutil.which("dbus-run-session") and _isolation.vrai("notify-send"),
                                 "Quickshell, dbus-run-session et notify-send requis")


class Source(unittest.TestCase):
    def setUp(self):
        self.partage = (QML / "Partage.qml").read_text()
        self.code = re.sub(r"//.*", "", self.partage)             # sans les commentaires
        self.notifs = (QML / "Notifs.qml").read_text()
        self.compact = (QML / "Compact.qml").read_text()
        self.reglages = (REPO / "home/.local/bin/nc-reglages").read_text()

    def test_evenement_sur_le_canal_de_quickshell(self):
        self.assertIn("import Quickshell.Hyprland", self.partage)
        self.assertRegex(self.partage, r'target: Hyprland\s+function onRawEvent\(event\) \{ if \(event\.name === "screencast"\)')
        # Aucun processus ni sondage de plus : ni Process, ni Timer qui se répète, ni hyprctl
        self.assertNotRegex(self.code, r"\bProcess\b|hyprctl|repeat: true|running: true")

    def test_delais(self):
        self.assertIn("property int delaiIndicateur: 1500", self.partage)

    def test_concentration_jamais_touchee(self):
        self.assertNotRegex(self.code, r"(?i)concentration\s*=[^=]|basculerConcentration|concentrationRegler")
        self.assertNotRegex(self.code, r"Notifs\.")           # Notifs consulte Partage, pas l'inverse

    def test_rien_sur_le_disque(self):
        self.assertNotRegex(self.code, r"Memo\.|FileView|PersistentProperties|writeFile|>>|tee ")

    def test_pas_de_composant_neuf(self):
        for nom in ("Partage.qml", "Notifs.qml", "Compact.qml", "PageNotifs.qml"):
            neufs = re.findall(r"(?m)^\s*component ", (QML / nom).read_text())
            self.assertEqual(len(neufs), 1 if nom == "Compact.qml" else 0, nom)      # Compact avait déjà son « Fondu »

    def test_notifs_consulte_partage_avant_la_bulle(self):
        m = re.search(r"function montrer\(notif\) \{\n(.*?)\n", self.notifs)
        self.assertIn("Partage.silence", m.group(1))

    def test_ordre_des_modes(self):
        m = re.search(r"readonly property string mode: (.*?)\n    readonly property real largeur", self.compact, re.S)
        ordre = m.group(1)
        self.assertLess(ordre.index("Etat.activiteType"), ordre.index('"video"'))
        self.assertLess(ordre.index('"video"'), ordre.index('"partage"'))
        for autre in ("AssistantEtat.activitePilule", '"telechargement"', '"claude"', '"musique"', '"minuteur"'):
            self.assertLess(ordre.index('"partage"'), ordre.index(autre), autre)
        self.assertIn("partage: partage", self.compact)
        self.assertIn("!Partage.indicateur", (QML / "Etat.qml").read_text())
        # Clic sur la bulle de fin : l'île déjà ouverte sur cet écran n'est pas basculée (basculer la fermerait)
        self.assertIn('Etat.ecranOuvert !== ecran) Etat.basculer(ecran, true)', (QML / "Notifs.qml").read_text())          # l'onde sonore s'arrête avec la pilule musique

    def test_reglage_oui_par_defaut_en_deux_langues(self):
        m = re.search(r'R\("PARTAGE_DISCRET", "Notifications", L\("([^"]+)", "([^"]+)"\), "ouinon", "oui",', self.reglages)
        self.assertTrue(m)
        self.assertEqual(m.group(1), "Partage d'écran discret")
        self.assertIn('Reglages.val("PARTAGE_DISCRET", "oui") !== "non"', self.partage)

    def test_ile_coupe_ses_animations_au_silence(self):
        ile = (QML / "Ile.qml").read_text()
        self.assertEqual(len(re.findall(r"enabled: !Notifs\.enPause && !Partage\.silence", ile)), 4)
        self.assertIn("garderBanniere.running && !Notifs.enPause && !Partage.silence", ile)
        self.assertNotRegex(ile, r"enabled: !Notifs\.enPause;")

    def test_textes_francais_et_anglais(self):
        for fr, en in (("1 notification reçue pendant le partage", "1 notification received while sharing"),
                       ("notifications reçues pendant le partage", "notifications received while sharing")):
            self.assertIn(fr, self.partage)
            self.assertIn(en, self.partage)
        self.assertIn('Reglages.t("Partage", "Sharing")', self.compact)
        # l'heure reste visible pendant le partage (le point du partage devant, comme l'iPhone)
        bloc = self.compact[self.compact.index('objectName: "nc-partage-pill"'):]
        self.assertIn("text: Etat.heure", bloc[:bloc.index("\n    }")])
        self.assertIn('Reglages.t("Ton écran est partagé", "Your screen is being shared")', (QML / "PageNotifs.qml").read_text())


class ReglageSeulementAvecLIle(unittest.TestCase):
    """Sans l'île Quickshell (bulles du démon de Noctalia), le réglage est caché : jamais l'impression d'être protégé."""

    def liste(self, avec_ile):
        with tempfile.TemporaryDirectory(prefix="nc-partage-reglage-") as d:
            conf = Path(d) / ".config"
            (conf / "nc").mkdir(parents=True)
            if avec_ile:
                (conf / "quickshell/nc-ile").mkdir(parents=True)
                (conf / "quickshell/nc-ile/shell.qml").write_text("")
            env = dict(os.environ, HOME=d, XDG_CONFIG_HOME=str(conf), NC_LANGUE="fr")
            r = subprocess.run([sys.executable, str(REPO / "home/.local/bin/nc-reglages"), "liste"], env=env, capture_output=True, text=True, timeout=60)
            return r.stdout

    def test_cache_sans_ile_visible_avec(self):
        self.assertNotIn("PARTAGE_DISCRET", self.liste(False))
        self.assertIn("PARTAGE_DISCRET", self.liste(True))

    def test_reglages_de_l_ile_aussi(self):
        """Ceux que le plugin Noctalia ne lit pas (pages, style, heure, bannières…) : cachés sans l'île Quickshell."""
        cles = ["ILE_HEURE", "ILE_DATE", "ILE_STYLE", "ILE_CONTOUR", "ILE_SURVOL", "ILE_BANNIERES", "ILE_METEO", "ILE_PRESSE", "PRESSE_DUREE",
                "ILE_ANIM_BATTERIE", "ILE_BANNIERE_DUREE", "ILE_TELECHARGEMENTS"] + ["ILE_PAGE_" + x.upper() for x in (
                    "musique", "claude", "minuteur", "charge", "jeu", "centre", "assistant", "notifications", "son", "reseau",
                    "bluetooth", "systeme", "calendrier", "meteo", "presse", "fenetres")]
        sans, avec = self.liste(False), self.liste(True)
        for c in cles:
            with self.subTest(cle=c):
                self.assertNotRegex(sans, r"\b%s\b" % c)
                self.assertRegex(avec, r"\b%s\b" % c)


@HORS_ECRAN
class Logique(unittest.TestCase):
    def executer(self, scenario, apres=None):
        return Notifications.executer(self, scenario, proprietes=PROPRIETES, apres=apres)

    def test_partage_long_bulles_retenues_indicateur_et_notification_de_fin(self):
        memo = self.executer('''
                if (etape === 0) {
                    if (!Notifs.pret) return
                    verifier(Partage.delaiIndicateur === 1500 && Partage.delaiFin === 1000, "délais par défaut")
                    Partage.evenement("0,0")                                  // fin sans début : ignorée
                    verifier(Partage.sessions === 0 && !Partage.silence, "fin sans début")
                    notifier("Chat", "avant", "", "normal"); etape++; return }
                // Avant le partage : la bulle s'affiche ; au début, elle disparaît tout de suite
                if (etape === 1) {
                    if (Notifs.liste.length < 1 || Notifs.banniere === null) return
                    verifier(Notifs.banniere.summary === "avant", "bulle avant le partage")
                    creer()
                    verifier(!trouver(page, "nc-notifs-partage").visible, "carte « partagé » avant le partage")
                    Partage.evenement("1,0"); marquer()
                    verifier(Partage.silence && !Partage.indicateur, "silence dès le début, indicateur pas encore")
                    verifier(Notifs.banniere === null, "la bulle affichée n'a pas disparu au début")
                    verifier(trouver(page, "nc-notifs-partage").visible, "carte « Ton écran est partagé » absente")
                    notifier("Chat", "secret", "code 123456", "normal"); etape++; return }
                // Une notification pendant le partage : dans l'historique, pas en bulle
                if (etape === 2) {
                    if (Notifs.liste.length < 2) return
                    verifier(Notifs.banniere === null, "bulle montrée pendant le partage")
                    verifier(Partage.compte === 1, "compte : " + Partage.compte)
                    if (!passe(1300)) verifier(!Partage.indicateur, "indicateur avant 1,5 s")
                    notifier("Banque", "urgente", "", "critical"); etape++; return }
                // Même une urgente reste retenue ; l'indicateur arrive après 1,5 s (pas avant)
                if (etape === 3) {
                    if (Notifs.liste.length < 3) return
                    verifier(Notifs.banniere === null, "urgente montrée pendant le partage")
                    verifier(Partage.compte === 2, "compte : " + Partage.compte)
                    verifier(attendu("secret") !== undefined && attendu("urgente") !== undefined, "historique incomplet")
                    if (!Partage.indicateur) return
                    verifier(Date.now() - marque >= 1450, "indicateur trop tôt : " + (Date.now() - marque))
                    // Début, début, fin : le partage continue
                    Partage.evenement("1,1"); verifier(Partage.sessions === 2, "deux sessions")
                    Partage.evenement("0,1")
                    verifier(Partage.sessions === 1 && Partage.silence && Partage.indicateur, "début, début, fin termine le partage")
                    verifier(Notifs.concentration === false, "Concentration touchée")
                    Partage.evenement("0,0"); marquer()
                    verifier(Partage.silence, "retour immédiat des bulles (pas de grâce)")
                    etape++; return }
                if (etape === 4) {
                    if (Partage.silence) return
                    verifier(passe(900), "grâce trop courte")
                    verifier(!Partage.indicateur && Partage.compte === 0 && Partage.sessions === 0, "état non remis à zéro")
                    verifier(Notifs.concentration === false, "Concentration touchée à la fin")
                    verifier(!trouver(page, "nc-notifs-partage").visible, "carte encore là")
                    etape++; return }
                // Une bulle de fin, avec le nombre seulement ; hors de l'historique ; un clic ouvre la page Notifications
                if (etape === 5) {
                    if (Notifs.banniere === null) return
                    verifier(Notifs.banniere.summary === "2 notifications received while sharing", "bulle de fin : " + Notifs.banniere.summary)
                    verifier(Notifs.banniere.body === "", "contenu dans la bulle de fin")
                    verifier(Notifs.liste.length === 3, "la bulle de fin est dans l'historique")
                    Notifs.ouvrir(Notifs.banniere)
                    verifier(Notifs.banniere === null && Etat.ouvert === "btruenotifications", "clic : page Notifications : " + Etat.ouvert)
                    Qt.quit() }
        ''')
        # Le compteur ne touche jamais le disque : seulement les clés habituelles de Memo, aucun nombre de partage
        self.assertIsNotNone(memo)
        self.assertEqual(set(memo), {"masques", "lus", "heures", "attentes"})
        self.assertNotIn("partage", json.dumps(memo).lower())

    def test_capture_courte_la_bulle_retenue_est_montree_a_la_fin(self):
        self.executer('''
                if (etape === 0) {
                    if (!Notifs.pret) return
                    Partage.delaiIndicateur = 5000
                    Partage.evenement("1,2")
                    verifier(Partage.silence && !Partage.indicateur, "silence dès le début")
                    notifier("Capture", "photo", "", "normal"); etape++; return }
                if (etape === 1) {
                    if (Notifs.liste.length < 1) return
                    verifier(Notifs.banniere === null, "bulle pendant la capture")
                    verifier(Partage.compte === 1, "retenue comptée")
                    Partage.evenement("0,2"); marquer()
                    verifier(Partage.silence && Notifs.banniere === null, "bulle montrée avant la fin de la grâce")
                    etape++; return }
                if (etape === 2) {
                    if (Partage.silence) return
                    verifier(passe(900) && !Partage.indicateur, "capture courte : bulle trop tôt")
                    verifier(Notifs.banniere !== null && Notifs.banniere.summary === "photo", "bulle retenue pas montrée à la fin")
                    marquer(); etape++; return }
                if (etape === 3) {
                    if (!passe(1200)) return
                    verifier(Notifs.liste.length === 1, "message de fin après une capture courte")
                    verifier(Partage.compte === 0 && Partage.retenue === null, "compteur pas remis à zéro")
                    Qt.quit() }
        ''')

    def test_ecran_fixe_fin_puis_debut_aucune_bulle_entre_les_deux(self):
        """Hyprland envoie fin après 0,5 s sans cliché puis début au suivant : rien ne s'affiche entre les deux, même si
        la pastille ne s'est jamais allumée ; 1,5 s écoulées pendant la pause allument l'indicateur au début suivant."""
        self.executer('''
                if (etape === 0) {
                    if (!Notifs.pret) return
                    Partage.evenement("1,0"); marquer()
                    notifier("Chat", "secret", "code", "normal"); etape++; return }
                if (etape === 1) {
                    if (Notifs.liste.length < 1) return
                    verifier(Notifs.banniere === null, "bulle après le début")
                    if (!passe(700)) return
                    Partage.evenement("0,0")                          // fin à 0,7 s : la bulle ne doit pas sortir
                    verifier(Notifs.banniere === null && Partage.silence, "bulle montrée à la fin, pendant la pause")
                    etape++; return }
                if (etape === 2) {
                    verifier(Notifs.banniere === null && Partage.silence, "bulle montrée entre la fin et le début")
                    if (!passe(1550)) return
                    verifier(Partage.sessions === 0 && !Partage.indicateur, "indicateur allumé pendant la pause")
                    Partage.evenement("1,0")                          // le cliché suivant, à 1,6 s : le seuil est échu
                    verifier(Partage.indicateur && Partage.silence && Notifs.banniere === null, "seuil échu pendant la pause pas appliqué")
                    verifier(Partage.compte === 1, "compte : " + Partage.compte)
                    Partage.evenement("0,0"); etape++; return }
                if (etape === 3) {
                    if (Partage.silence) return
                    marquer(); etape++; return }
                if (etape === 4) {
                    if (Notifs.banniere === null) return
                    verifier(Notifs.banniere.summary === "1 notification received while sharing", "fin : " + Notifs.banniere.summary)
                    Qt.quit() }
        ''')

    def test_rafale_de_captures_aucune_bulle_entre_deux(self):
        self.executer('''
                if (etape === 0) {
                    if (!Notifs.pret) return
                    // Grâce de 3 s (1 s en vrai) : les captures sont à 400 ms l'une de l'autre, une machine chargée
                    // (suite complète) peut retarder la minuterie du test de plus d'une seconde
                    Partage.delaiFin = 3000
                    Partage.evenement("1,2"); notifier("Chat", "un", "", "normal"); marquer(); etape++; return }
                if (etape === 1) {
                    if (Notifs.liste.length < 1) return
                    Partage.evenement("0,2"); marquer(); etape++; return }
                // 2e capture 400 ms plus tard, 3e encore 400 ms plus tard : jamais de bulle entre elles
                if (etape === 2) {
                    verifier(Notifs.banniere === null, "bulle entre deux captures")
                    if (!passe(400)) return
                    Partage.evenement("1,2"); notifier("Chat", "deux", "", "normal"); marquer(); etape++; return }
                if (etape === 3) {
                    verifier(Notifs.banniere === null, "bulle pendant la 2e capture")
                    if (Notifs.liste.length < 2 || !passe(400)) return
                    Partage.evenement("0,2"); marquer(); etape++; return }
                if (etape === 4) {
                    verifier(Notifs.banniere === null, "bulle entre la 2e et la 3e capture")
                    if (!passe(400)) return
                    Partage.evenement("1,2"); Partage.evenement("0,2"); marquer(); etape++; return }
                if (etape === 5) {
                    if (Partage.silence) { verifier(Notifs.banniere === null, "bulle pendant la grâce"); return }
                    verifier(Notifs.banniere !== null && Notifs.banniere.summary === "deux", "la dernière bulle retenue est montrée")
                    Qt.quit() }
        ''')

    def test_notification_remplacee_comptee_une_fois_et_filet(self):
        self.executer('''
                if (etape === 0) {
                    if (!Notifs.pret) return
                    Partage.delaiFilet = 500; Partage.delaiIndicateur = 100
                    Partage.evenement("1,0"); notifier("Chat", "a", "", "normal"); etape++; return }
                if (etape === 1) {
                    if (Notifs.liste.length < 1) return
                    Partage.retenir(Notifs.liste[0]); Partage.retenir(Notifs.liste[0])      // remplacée : même id
                    verifier(Partage.compte === 1, "remplacée comptée plusieurs fois : " + Partage.compte)
                    marquer(); etape++; return }
                // Filet : une fin perdue ne garde pas le silence pour toujours (remis à zéro à chaque événement)
                if (etape === 2) {
                    if (!passe(300)) return
                    verifier(Partage.silence, "filet trop tôt"); Partage.evenement("1,0"); marquer(); etape++; return }
                if (etape === 3) {
                    if (!passe(300)) return
                    verifier(Partage.silence, "filet pas remis à zéro par l'événement"); etape++; return }
                if (etape === 4) {
                    if (Partage.silence) return
                    verifier(Partage.sessions === 0 && !Partage.indicateur, "filet : état pas remis à zéro")
                    Qt.quit() }
        ''')

    def test_concentration_jamais_touchee(self):
        self.executer('''
                if (etape === 0) {
                    if (!Notifs.pret) return
                    Partage.delaiIndicateur = 300; Partage.delaiFin = 200
                    // a : active avant, active après ; une notification reçue pendant (déjà sans bulle) n'est pas comptée
                    Notifs.concentration = true
                    Partage.evenement("1,0"); notifier("Chat", "muette", "", "normal"); etape++; return }
                if (etape === 1) {
                    if (!Partage.indicateur || Notifs.liste.length < 1) return
                    verifier(Partage.compte === 0, "notification déjà muette comptée : " + Partage.compte)
                    Partage.evenement("0,0"); etape++; return }
                if (etape === 2) {
                    if (Partage.silence) return
                    verifier(Notifs.concentration === true, "a : Concentration coupée à la fin")
                    // b : inactive avant, l'utilisateur l'active pendant → laissée active
                    Notifs.concentration = false
                    Partage.evenement("1,0"); etape++; return }
                if (etape === 3) {
                    if (!Partage.indicateur) return
                    Notifs.concentration = true
                    Partage.evenement("0,0"); etape++; return }
                if (etape === 4) {
                    if (Partage.silence) return
                    verifier(Notifs.concentration === true, "b : Concentration changée pendant, écrasée à la fin")
                    // c : active avant, l'utilisateur la coupe pendant → laissée coupée
                    Partage.evenement("1,0"); etape++; return }
                if (etape === 5) {
                    if (!Partage.indicateur) return
                    Notifs.concentration = false
                    Partage.evenement("0,0"); etape++; return }
                if (etape === 6) {
                    if (Partage.silence) return
                    verifier(Notifs.concentration === false, "c : Concentration changée pendant, écrasée à la fin")
                    // d : inactive avant, inactive après (capture courte puis partage)
                    Partage.delaiIndicateur = 5000
                    Partage.evenement("1,0"); Partage.evenement("0,0")
                    verifier(Notifs.concentration === false, "d : Concentration touchée par une capture")
                    marquer(); etape++; return }
                // La notification reçue sous Concentration n'a donné aucun message de fin
                if (etape === 7) {
                    if (!passe(900)) return
                    verifier(Notifs.liste.length === 1, "message de fin sans bulle retenue : " + Notifs.liste.length)
                    verifier(Notifs.concentration === false, "d : Concentration touchée")
                    Qt.quit() }
        ''')

    def test_reglage_non_rien_ne_change(self):
        self.executer('''
                if (etape === 0) {
                    if (!Notifs.pret) return
                    Reglages.valeurs = ({ PARTAGE_DISCRET: "non" })
                    Partage.evenement("1,0")
                    verifier(!Partage.silence && Partage.sessions === 0 && !Partage.indicateur, "réglage non : partage pris en compte")
                    notifier("Chat", "visible", "", "normal"); etape++; return }
                if (etape === 1) {
                    if (Notifs.liste.length < 1) return
                    verifier(Notifs.banniere !== null && Notifs.banniere.summary === "visible", "réglage non : bulle retenue")
                    verifier(Partage.compte === 0, "réglage non : compté")
                    // Coupé en plein partage : le silence s'arrête aussitôt, sans message
                    Reglages.valeurs = ({})
                    Partage.delaiIndicateur = 200
                    Partage.evenement("1,0")
                    verifier(Partage.silence, "réglage oui : pas de silence")
                    Reglages.valeurs = ({ PARTAGE_DISCRET: "non" })
                    verifier(!Partage.silence && !Partage.indicateur && Partage.sessions === 0, "réglage coupé en plein partage")
                    Partage.evenement("0,0")
                    marquer(); etape++; return }
                if (etape === 2) {
                    if (!passe(900)) return
                    verifier(Notifs.liste.length === 1, "message de fin malgré le réglage non")
                    verifier(Notifs.concentration === false, "Concentration touchée")
                    Qt.quit() }
        ''')


def _faux_hyprland(dossier, lignes, pret, fini):
    """Un faux Hyprland : socket2 envoie les lignes puis se tait ; socket répond « [] » aux requêtes."""
    chemins = []
    for nom in (".socket2.sock", ".socket.sock"):
        s = socket.socket(socket.AF_UNIX)
        s.bind(str(dossier / nom))
        s.listen(8)
        chemins.append(s)
    flux, requetes = chemins

    def serveur_requetes():
        while not fini.is_set():
            try:
                c, _ = requetes.accept()
            except OSError:
                return
            try:
                c.settimeout(1)
                c.recv(4096)
                c.sendall(b"[]")
            except OSError:
                pass
            c.close()

    def serveur_flux():
        try:
            c, _ = flux.accept()
        except OSError:
            return
        pret.set()
        for ligne in lignes:
            if fini.wait(timeout=ligne[0]):
                break
            c.sendall(ligne[1].encode())
        fini.wait(timeout=10)
        c.close()

    threading.Thread(target=serveur_requetes, daemon=True).start()
    threading.Thread(target=serveur_flux, daemon=True).start()
    return chemins


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class CanalHyprland(unittest.TestCase):
    """Le vrai signal Hyprland.rawEvent de Quickshell, nourri par un faux socket2 : « screencast>>1,0 » puis « 0,0 »."""

    def test_rawEvent_screencast(self):
        with tempfile.TemporaryDirectory(prefix="nc-partage-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            signature = "faux_0_1"
            hypr = root / "run/hypr" / signature
            hypr.mkdir(parents=True, mode=0o700)
            pret, fini = threading.Event(), threading.Event()
            # La fin arrive 3 s après le début : bien au-delà du seuil de 1,5 s de la pastille (1,5 s pile faisait une course)
            socks = _faux_hyprland(hypr, [(1.0, "screencast>>1,0\nscreencastv2>>1,0,DP-1\n"), (3.0, "screencast>>0,0\n")], pret, fini)
            self.addCleanup(lambda: [s.close() for s in socks])
            self.addCleanup(fini.set)
            for nom in ("Partage.qml",):
                shutil.copy2(QML / nom, root / nom)
            (root / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function t(fr,en){return fr} function val(k,d){return d}}')
            (root / "qmldir").write_text("singleton Partage 1.0 Partage.qml\nsingleton Reglages 1.0 Reglages.qml\n")
            (root / "shell.qml").write_text(textwrap.dedent('''\
                import QtQuick
                import Quickshell
                ShellRoot {
                    property int etape: 0
                    property double marque: 0
                    function verifier(ok, message) { if (!ok) { console.error(message); Qt.exit(2) } }
                    Timer { interval: 100; running: true; repeat: true; onTriggered: {
                        if (etape === 0) { Partage.delaiFin = 100; marque = Date.now(); etape++ }
                        else if (etape === 1) {
                            if (!Partage.silence) return
                            verifier(Partage.sessions === 1, "une seule session (screencastv2 ignoré) : " + Partage.sessions)
                            etape++ }
                        else if (etape === 2) {
                            if (!Partage.indicateur) return
                            etape++ }
                        else if (etape === 3) {
                            if (Partage.silence) return
                            console.log("CANAL-OK"); Qt.quit() } } }
                    Timer { interval: 9000; running: true; onTriggered: { console.error("délai dépassé"); Qt.exit(9) } }
                }'''))
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       XDG_RUNTIME_DIR=str(root / "run"), XDG_CACHE_HOME=str(root / "cache"),
                       HYPRLAND_INSTANCE_SIGNATURE=signature)
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env, capture_output=True, text=True, timeout=20)
            sortie = r.stdout + r.stderr
            for erreur in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type"):
                self.assertNotIn(erreur, sortie)
            self.assertIn("CANAL-OK", sortie, sortie)


if __name__ == "__main__":
    unittest.main()
