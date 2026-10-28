"""Résumé au réveil dans l'île (Resume.qml, PageResume.qml, Compact.qml, Ile.qml, réglage ILE_RESUME_REVEIL).

- Source : aucun minuteur qui tourne en continu, détection sur Etat.ecranVu, rien de lancé (ni nc-paquets, ni réseau),
  pas de composant neuf, textes venus de l'extérieur en texte brut (Texte.qml), réglage et README.
- Hors écran, avec le vrai qs (« qs -p », jamais « qs -c nc-ile ») : le vrai Resume.qml avec des Etat, Reglages, Partage et
  GoogleAgenda de remplacement. Cas : apparaît après 4 h d'absence, pas après 10 min, pas pendant un partage (reporté à la fin si
  c'est le matin), pas en jeu, réglage « non » = rien, lignes absentes sans données, titres et noms de paquets gardés tels quels,
  le clic ouvre la page, l'écran qui s'éteint le ferme, l'état est écrit.
HOME, XDG_* et TMPDIR sont ceux du dossier temporaire ; aucun chemin réel du HOME."""
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import tempfile
import textwrap
import time
import unittest
import warnings

from tests import _ile_hors_ecran as H

REPO = H.REPO
QML = H.QML


class Source(unittest.TestCase):
    def setUp(self):
        self.resume = (QML / "Resume.qml").read_text()
        self.code = re.sub(r"//.*", "", self.resume)
        self.page = re.sub(r"//.*", "", (QML / "PageResume.qml").read_text())

    def test_aucun_minuteur_continu_et_rien_de_lance(self):
        self.assertNotRegex(self.code, r"repeat:\s*true|running:\s*true|triggeredOnStart")
        # La pilule et l'attente des données : un minuteur court, seulement pendant le résumé
        self.assertIn("running: r.actif && !r.ouvert && Etat.ecranVu", self.code)
        # Les mises à jour sont lues, jamais comptées ; aucun appel réseau ni IA
        self.assertNotRegex(self.code, r"nc-paquets|nc-meteo|nc-ia|nc-jarvis|\bProcess\b|curl|wget")
        self.assertEqual(len(re.findall(r"execDetached", self.code)), 1)
        self.assertIn("function onEcranVuChanged()", self.code)
        self.assertNotRegex(self.page, r"\bProcess\b|repeat: true|execDetached")

    def test_partage_et_jeu(self):
        self.assertIn("if (Partage.silence) { enAttente = true; return }", self.code)
        self.assertIn("if (Partage.retient || Etat.jeu) return", self.code)
        self.assertIn("new Date().getHours() < 12", self.code)

    def test_textes_exterieurs_en_brut(self):
        # Titres d'événements et noms de paquets : Texte.qml (PlainText), jamais Text, RichText ni StyledText
        self.assertNotRegex(self.page, r"(?m)^\s*Text \{|RichText|StyledText|AutoText|textFormat")
        self.assertIn("text: parent.modelData.titre", self.page)
        self.assertIn("p.c.importants.join", self.page)
        self.assertIn("textFormat: Text.PlainText", (QML / "Texte.qml").read_text())

    def test_branche_comme_les_autres_activites(self):
        etat = (QML / "Etat.qml").read_text()
        compact = (QML / "Compact.qml").read_text()
        ile = (QML / "Ile.qml").read_text()
        self.assertIn('if (Resume.actif) a.push("resume")', etat)
        self.assertIn('Resume.actif ? "resume"', compact)
        self.assertIn("resume: resume })", compact)
        self.assertIn('resume: adaptee("resume", 170)', ile)
        self.assertIn("resume: pResume })", ile)
        self.assertIn("Component { id: pResume; PageResume {} }", ile)
        self.assertIn("Resume.ouvrir(fen.modelData.name)", ile)
        self.assertIn('resume: ["Résumé", "Summary"]', (QML / "NavigationIle.qml").read_text())

    def test_pas_de_composant_neuf(self):
        for nom in ("Resume.qml", "PageResume.qml", "Compact.qml", "Ile.qml", "Etat.qml"):
            self.assertEqual(len(re.findall(r"(?m)^\s*component ", (QML / nom).read_text())), 0 if nom != "Compact.qml" else 1, nom)

    def test_reglage_et_readme(self):
        with tempfile.TemporaryDirectory() as d:
            from unittest.mock import patch
            with patch.dict(os.environ, HOME=d), warnings.catch_warnings():
                warnings.simplefilter("ignore", ResourceWarning)
                reglages = runpy.run_path(str(REPO / "home/.local/bin/nc-reglages"))
        cle = reglages["PAR_CLE"]["ILE_RESUME_REVEIL"]
        self.assertEqual(cle.defaut, "oui")
        self.assertEqual(cle.section, "Île")
        self.assertIn("`ILE_RESUME_REVEIL`", (REPO / "README.md").read_text())


ETAT = """
  property bool pret: true
  property var meteo: %s
  property bool aBatterie: %s
  property bool branche: %s
  property int pourcent: %d
  property string ecranOuvert: ""
  property date maintenant: new Date()
  property var appels: []
  function basculer(e, c) { appels = appels.concat(["basculer:" + e]); ecranOuvert = e }
  function aller(n) { appels = appels.concat(["aller:" + n]) }
  function fermer() { ecranOuvert = "" }
"""
PARTAGE = "pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false; property bool auto: false; readonly property bool retient: silence || auto }\n"
AGENDA = """pragma Singleton
import QtQuick
QtObject {
    property var cache: ({})
    property string enCours: ""
    property int appels: 0
    function cle(d) { return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") }
    function charger(d, force) { appels++; var c = {}; c[cle(d)] = { t: Date.now(), events: %s, calendars: [] }; cache = c }
}
"""
METEO = {"temp": 12, "texte": "Ciel dégagé", "icone": "wb_sunny", "min": 8, "max": 15}


def aujourdhui(decalage=0):
    return time.strftime("%Y-%m-%d", time.localtime(time.time() + decalage * 86400))


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def lancer(self, corps, valeurs=None, meteo=METEO, paquets=None, batterie=None, sortie_il_y_a=None, jour=None,
               agenda=None, ia_coupee=False, delai=40):
        """Lance le vrai Resume.qml ; rend (journal de qs, dossier d'état lu après la fin)."""
        with tempfile.TemporaryDirectory(prefix="nc-resume-") as d:
            root = H.preparer(d, ("Resume", "Couleurs"), etat=ETAT % ("(" + json.dumps(meteo) + ")" if meteo else "({})", "true" if batterie else "false",
                                                                       "false" if batterie else "true", batterie or 0),
                              extra={"Partage.qml": PARTAGE, "GoogleAgenda.qml": AGENDA % json.dumps(agenda or [])},
                              singletons=("Resume", "Partage", "GoogleAgenda"))
            reglages = (root / "Reglages.qml").read_text()
            reglages = reglages.replace("property var valeurs: ({})", "property var valeurs: (" + json.dumps(valeurs or {}) + ")")
            reglages = reglages.replace("iaCoupee: true", "iaCoupee: " + ("true" if ia_coupee else "false"))
            (root / "Reglages.qml").write_text(reglages)
            if paquets is not None:
                (root / "cache/nc").mkdir(parents=True)
                (root / "cache/nc/paquets.json").write_text(json.dumps(paquets))
            if sortie_il_y_a is not None or jour is not None:
                (root / "state/nc").mkdir(parents=True)
                (root / "state/nc/ile-resume").write_text("%d\n%s\n" % (time.time() - (sortie_il_y_a or 0), jour or aujourdhui()))
            (root / "shell.qml").write_text(H.ENTETE + "ShellRoot {\n" + H.OUTILS + textwrap.dedent(corps) + "\n}\n")
            code, sortie = H.lancer(root, delai=delai)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)
            etat = root / "state/nc/ile-resume"
            return sortie, (etat.read_text() if etat.exists() else "")

    # Cadre commun : le code de chaque étape tourne à la seconde donnée (après 0,6 s de démarrage) ; FINI après la dernière
    def pas(self, avant, apres=None, attente=1.2, suite=()):
        avant = "Resume.attenteDonnees = 400; " + avant
        etapes = [(0.0, avant), (attente, apres or "")] + list(suite)
        corps = "".join("if (t === %d) { %s }\n" % (2 + round(s / 0.3), code) for s, code in etapes)
        dernier = 2 + round(max(s for s, _ in etapes) / 0.3) + 1
        return """
            property int t: 0
            Timer { interval: 300; running: true; repeat: true; property int essais: 0; onTriggered: { if (!Resume.demarre && ++essais < 40) return; parent.t++
                var t = parent.t
                %s
                if (t === %d) { console.log("FINI"); Qt.exit(0) } } }
        """ % (corps, dernier)

    ABSENCE = "Etat.ecranVu = false; Resume.sortieLe = Date.now() / 1000 - 5 * 3600; Etat.ecranVu = true;"
    PAQUETS = {"total": 5, "paquets": [{"nom": "linux", "important": True}, {"nom": "<b>gras</b>", "important": True}, {"nom": "vim"}]}

    def test_apparait_apres_4_h_d_absence(self):
        sortie, etat = self.lancer(self.pas(self.ABSENCE, '''
            verifier(Resume.actif, "pas de résumé après 5 h")
            verifier(Resume.court === "12° · 5 mises à jour", "pilule : " + Resume.court)
            verifier(Resume.contenu.importants[0] === "linux" && Resume.contenu.importants[1] === "<b>gras</b>", "importants : " + Resume.contenu.importants)
            verifier(Resume.contenu.meteo.temp === 12 && Resume.contenu.batterie === -1, "contenu")
            verifier(Resume.salut === "Bonjour" || Resume.salut === "Bonsoir", "salut")
        '''), paquets=self.PAQUETS, jour=aujourdhui(), sortie_il_y_a=60)
        # L'état est écrit : sortie notée, jour salué
        self.assertRegex(etat, r"^\d+\n%s\n$" % aujourdhui())

    def test_pas_apres_10_minutes(self):
        self.lancer(self.pas("Etat.ecranVu = false; Resume.sortieLe = Date.now() / 1000 - 600; Etat.ecranVu = true;",
                             'verifier(!Resume.actif && !Resume.prepare, "résumé après 10 min")'),
                    paquets=self.PAQUETS, jour=aujourdhui())

    def test_disparait_seul_puis_clic_et_fermeture(self):
        self.lancer(self.pas("Resume.dureePilule = 700; " + self.ABSENCE, 'verifier(!Resume.actif, "pilule jamais effacée")',
                             suite=[(1.5, "Resume.dureePilule = 60000; " + self.ABSENCE),
                                    (2.7, 'verifier(Resume.actif, "pas revenu"); Resume.ouvrir("DP-1")'),
                                    (3.0, 'verifier(Resume.ouvert && Etat.appels.join() === "basculer:DP-1,aller:resume", "clic : " + Etat.appels + Resume.ouvert); Resume.dureePilule = 1'),
                                    (4.5, 'verifier(Resume.actif, "effacée page ouverte"); Etat.fermer()'),
                                    (5.1, 'verifier(!Resume.actif, "page fermée, résumé fini")')]),
                    paquets=self.PAQUETS, jour=aujourdhui(), sortie_il_y_a=60, delai=60)

    def test_pas_pendant_un_partage_puis_reporte_le_matin(self):
        self.lancer(self.pas("Partage.silence = true; " + self.ABSENCE, 'verifier(!Resume.actif && Resume.enAttente, "montré pendant un partage"); Partage.silence = false',
                             suite=[(2.7, 'verifier(Resume.actif === (new Date().getHours() < 12), "reprise : " + Resume.actif + " " + new Date().getHours())')]),
                    paquets=self.PAQUETS, jour=aujourdhui(), sortie_il_y_a=60)

    def test_partage_commence_pendant_la_pilule(self):
        self.lancer(self.pas(self.ABSENCE, 'verifier(Resume.actif, "pas là"); Partage.silence = true; verifier(!Resume.actif && Resume.enAttente, "pilule gardée pendant le partage")'),
                    paquets=self.PAQUETS, jour=aujourdhui(), sortie_il_y_a=60)

    def test_pas_en_mode_jeu_ni_projection(self):
        self.lancer(self.pas("Etat.jeu = true; " + self.ABSENCE, 'verifier(!Resume.actif && !Resume.prepare, "résumé en jeu"); Etat.jeu = false; Partage.auto = true; ' + self.ABSENCE,
                             suite=[(2.7, 'verifier(!Resume.actif && !Resume.prepare, "résumé en projection")')]),
                    paquets=self.PAQUETS, jour=aujourdhui(), sortie_il_y_a=60)

    def test_reglage_non_rien(self):
        sortie, etat = self.lancer(self.pas(self.ABSENCE, 'verifier(!Resume.actif && !Resume.prepare, "résumé malgré ILE_RESUME_REVEIL=non")'),
                                   valeurs={"ILE_RESUME_REVEIL": "non"}, paquets=self.PAQUETS, jour=aujourdhui(), sortie_il_y_a=60)

    def test_ecran_qui_s_eteint_ferme(self):
        self.lancer(self.pas(self.ABSENCE, 'verifier(Resume.actif, "pas là"); Etat.ecranVu = false; verifier(!Resume.actif, "écran éteint, résumé encore là")'),
                    paquets=self.PAQUETS, jour=aujourdhui(), sortie_il_y_a=60)

    @unittest.skipIf(time.localtime().tm_hour < 5, "avant 5 h le résumé du jour n'existe pas")
    def test_premiere_fois_du_jour_au_demarrage(self):
        # Pas de longue absence : le jour n'a pas encore été salué, il est plus de 5 h
        self.lancer(self.pas("", 'verifier(Resume.actif, "pas de résumé la première fois du jour")'), paquets=self.PAQUETS, jour="2000-01-01", sortie_il_y_a=60)

    def test_pas_deux_fois_le_meme_jour(self):
        self.lancer(self.pas("", 'verifier(!Resume.actif, "résumé alors que le jour est déjà salué")'), paquets=self.PAQUETS, jour=aujourdhui(), sortie_il_y_a=60)

    def test_lignes_absentes_sans_donnees(self):
        sortie, etat = self.lancer(self.pas(self.ABSENCE, 'verifier(!Resume.actif, "pilule vide")'), meteo=None, paquets=None, jour=aujourdhui(), sortie_il_y_a=60)
        # Rien à dire : le jour est quand même noté, mais rien n'a été montré
        self.assertIn(aujourdhui(), etat)
        # Les mises à jour seules : pas de météo, pas d'agenda
        self.lancer(self.pas(self.ABSENCE, '''
            verifier(Resume.actif && Resume.court === "5 mises à jour", "mises à jour seules : " + Resume.court)
            verifier(Resume.contenu.meteo === null && Resume.contenu.nbEvenements === 0, "lignes en trop")
        '''), meteo=None, paquets=self.PAQUETS, jour=aujourdhui(), sortie_il_y_a=60)
        # Météo coupée (ILE_METEO=non) et mises à jour coupées (MAJ_SYSTEME=non) : rien malgré les données
        self.lancer(self.pas(self.ABSENCE, 'verifier(!Resume.actif, "données malgré les réglages")'),
                    valeurs={"ILE_METEO": "non", "MAJ_SYSTEME": "non"}, paquets=self.PAQUETS, jour=aujourdhui(), sortie_il_y_a=60)
        # Fichier de paquets abîmé : pas d'erreur, la ligne n'existe pas
        self.lancer(self.pas(self.ABSENCE, 'verifier(Resume.actif && Resume.court === "12°", "paquets abîmés : " + Resume.court)'),
                    paquets="pas du json", jour=aujourdhui(), sortie_il_y_a=60)

    def test_batterie_seulement_sur_batterie(self):
        self.lancer(self.pas(self.ABSENCE, 'verifier(Resume.actif && Resume.contenu.batterie === 83, "batterie : " + Resume.contenu.batterie)'),
                    meteo=None, paquets={"total": 0, "paquets": []}, batterie=83, jour=aujourdhui(), sortie_il_y_a=60)
        self.lancer(self.pas(self.ABSENCE, 'verifier(Resume.contenu.batterie === -1, "batterie sur secteur")'), paquets=self.PAQUETS, jour=aujourdhui(), sortie_il_y_a=60)

    def test_agenda_seulement_s_il_est_configure(self):
        evenements = [{"debut": aujourdhui(), "fin": aujourdhui(1), "journee": True, "titre": "<b>Anniversaire</b>"},
                      {"debut": aujourdhui(-1) + "T10:00", "fin": aujourdhui(-1) + "T11:00", "journee": False, "titre": "Hier"},
                      {"debut": aujourdhui(1) + "T10:00", "fin": aujourdhui(1) + "T11:00", "journee": False, "titre": "Demain"}]
        google = {"GOOGLE_INTEGRATION": "oui"}
        self.lancer(self.pas(self.ABSENCE, '''
            verifier(Resume.actif && Resume.contenu.nbEvenements === 1, "événements du jour : " + JSON.stringify(Resume.contenu.evenements))
            verifier(Resume.contenu.evenements[0].titre === "<b>Anniversaire</b>" && Resume.contenu.evenements[0].journee, "titre gardé tel quel")
            verifier(Resume.court === "12° · 1 rendez-vous · 5 mises à jour", "pilule : " + Resume.court)
            verifier(GoogleAgenda.appels === 1, "agenda demandé " + GoogleAgenda.appels + " fois")
        '''), valeurs=google, paquets=self.PAQUETS, agenda=evenements, jour=aujourdhui(), sortie_il_y_a=60)
        # Non configuré, ou IA coupée : aucune demande, aucune ligne
        for valeurs, ia in (({}, False), (google, True), ({"GOOGLE_INTEGRATION": "oui", "GOOGLE_CALENDRIER": "non"}, False)):
            self.lancer(self.pas(self.ABSENCE, '''
                verifier(Resume.actif && Resume.contenu.nbEvenements === 0 && GoogleAgenda.appels === 0, "agenda demandé : " + GoogleAgenda.appels)
            '''), valeurs=valeurs, ia_coupee=ia, paquets=self.PAQUETS, agenda=evenements, jour=aujourdhui(), sortie_il_y_a=60)
        # Configuré mais qui ne répond pas (rien dans le cache) : la ligne n'existe pas, sans erreur
        self.lancer(self.pas(self.ABSENCE, 'verifier(Resume.actif && Resume.contenu.nbEvenements === 0, "agenda muet")'),
                    valeurs=google, paquets=self.PAQUETS, agenda=[], jour=aujourdhui(), sortie_il_y_a=60)


if __name__ == "__main__":
    unittest.main()
