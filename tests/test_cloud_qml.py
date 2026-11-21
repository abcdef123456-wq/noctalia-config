"""Panneau Cloud JARVIS de l'île (CloudEtat.qml, CloudPanneau.qml, CloudBouton.qml), C2b.
Sources : aucun component inline, aucun appel réseau depuis le QML (tout par nc-cloud --json), titre exact, entrée de la
recherche et IPC liées à CLOUD_JARVIS. Hors écran (vrai qs lancé par « qs -p », HOME et XDG_* isolés, faux nc-cloud qui
note ses arguments et joue des lignes JSON, vrais clics de souris par QtTest) : coupé ou non associé = aucun lancement ;
parcours, sélection d'un clic (la ligne ne bouge pas), double-clic (entrer, ouvrir), téléchargement avec « Remplacer » sur
un conflit, créer un fichier vide, renommer, déplacer ici, suppression jamais sans la question, un dossier seulement après
son aperçu (nouvel aperçu si le dossier a changé), chaque action seulement avec sa capacité. Sauté sans Quickshell."""
import json
import re
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from tests import _ile_hors_ecran as H

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
FICHIERS = ("CloudEtat.qml", "CloudPanneau.qml", "CloudBouton.qml")
PAGE_RACINE = {"evenement": "page", "parent": {"id": "root"}, "next_cursor": None,
               "entries": [{"id": "dddddddddddddddddddddddddddddddd", "name": "Photos", "kind": "directory", "revision": "r1", "parent": "root"},
                           {"id": "ffffffffffffffffffffffffffffffff", "name": "note.txt", "kind": "file", "size": 12, "revision": "r9", "parent": "root"}]}
ARBRE1, ARBRE2 = "a" * 64, "b" * 64
FAUX = r"""#!/bin/sh
# Faux nc-cloud : note ses arguments, joue une ligne JSON par commande (jamais de réseau)
echo "$*" >> "@ROOT@/journal"
[ "$1" = "--json" ] && shift
for dernier; do :; done      # l'id ou le dossier : toujours le dernier argument, après « -- »
case "$1" in
  etat) printf '%s\n' '{"evenement": "etat", "etat": {"used_bytes": 1048576, "quota_bytes": 21474836480}, "features": @FEAT@}' ;;
  lister) if [ "$dernier" = root ]; then cat "@ROOT@/racine.json"; else printf '%s\n' '{"evenement": "page", "entries": [], "next_cursor": null}'; fi ;;
  telecharger) case "$*" in *--remplacer*) printf '%s\n' '{"evenement": "resultat", "message": "Téléchargé."}' ;;
               *) printf '%s\n' '{"evenement": "erreur", "code": 6, "message": "note.txt existe déjà."}'; exit 6 ;; esac ;;
  supprimer) case "$*" in *--arbre=@ARBRE1@*) printf '%s\n' '{"evenement": "erreur", "code": 6, "erreur": "tree_changed", "message": "Le dossier a changé."}'; exit 6 ;; esac
             printf '%s\n' '{"evenement": "resultat", "message": "Supprimé."}' ;;
  apercu) n=$(cat "@ROOT@/apercus" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "@ROOT@/apercus"
          if [ "$n" = 1 ]; then t=@ARBRE1@; else t=@ARBRE2@; fi
          printf '{"evenement": "apercu", "entree": {"id": "%s"}, "files": 3, "directories": 2, "size": 2048, "tree_revision": "%s"}\n' "$dernier" "$t" ;;
  creer) printf '%s\n' '{"evenement": "resultat", "message": "Créé."}' ;;
  renommer) printf '%s\n' '{"evenement": "resultat", "message": "Renommé."}' ;;
  deplacer) printf '%s\n' '{"evenement": "resultat", "message": "Déplacé."}' ;;
  ouvrir) printf '%s\n' '{"evenement": "resultat", "message": "Ouvert : note.txt"}' ;;
  dossier) printf '%s\n' '{"evenement": "dossier", "message": "Dossier créé."}' ;;
esac
exit 0
"""
OUTILS = """
 function textes(item, l) { l = l || []; if (item.text !== undefined && item.visible && item.text !== "") l.push(String(item.text))
   for (var i = 0; i < item.children.length; i++) textes(item.children[i], l); return l }
 function vu(item, nom) { var x = trouver(item, nom); return x !== null && x.visible }
"""


def lire(nom):
    return (QML / nom).read_text()


def panneau_hors_fenetre():
    """CloudPanneau.qml dans une fenêtre ordinaire (la FloatingWindow de Quickshell n'existe pas hors écran), comme pour le VPN."""
    s = lire("CloudPanneau.qml")
    assert "FloatingWindow {" in s
    s = s.replace("FloatingWindow {", "Window {")
    for l in ("    implicitWidth: Math.min(680, Math.round(largeurEcran * 0.92))\n",
              "    implicitHeight: Math.min(Math.round(hauteurEcran * 0.85), contenu.implicitHeight + 48)\n",
              "    minimumSize: Qt.size(420, 260)\n", "    onClosed: cloud.fermer()\n"):
        assert l in s, l
        s = s.replace(l, "")
    s = s.replace("cloud.screen ? cloud.screen.width : 1600", "1600").replace("cloud.screen ? cloud.screen.height : 1000", "1000")
    return s.replace('    color: "transparent"\n', '    color: "transparent"; width: 700; height: 700; visible: true\n')


class Sources(unittest.TestCase):
    def test_aucun_component_inline_ni_reseau(self):
        for nom in FICHIERS:
            t = lire(nom)
            self.assertIsNone(re.search(r"^\s*component\s+\w+\s*:", t, re.M), nom)
            self.assertNotRegex(t, r"XMLHttpRequest|https?://|curl|wget", nom)
        self.assertIn('[bin + "nc-cloud", "--json"]', lire("CloudEtat.qml"))
        self.assertEqual(lire("CloudEtat.qml").count("proc.running = true"), 1)    # un seul point de lancement : la file

    def test_titre_exact_et_regles_hyprland(self):
        self.assertIn('title: Reglages.t("Cloud JARVIS", "Cloud JARVIS")', lire("CloudPanneau.qml"))
        regles = (REPO / "home/.config/hypr/nc/regles.lua").read_text()
        self.assertIn('title = "^(Cloud JARVIS)$" }, float = true', regles)
        self.assertIn("|Cloud JARVIS)$", regles)
        self.assertIn('local FENETRE_CLOUD = "Cloud JARVIS"', (REPO / "home/.config/hypr/nc/automatismes.lua").read_text())

    def test_ipc_et_recherche_liees_au_reglage(self):
        shell = lire("shell.qml")
        self.assertIn("function cloud(): void { racine.ouvrirCloud() }", shell)      # sans argument : ouvre, jamais ne referme
        m = re.search(r"function ouvrirCloud\(\) \{(.*?)\n    \}", shell, re.S)
        self.assertIsNotNone(m)
        self.assertIn("if (racine.cloudOuvert || !CloudEtat.actif) return", m.group(1) if m else "")
        self.assertIn("CloudPanneau {", shell)
        # L'écran est fixé à l'ouverture, jamais lié au moniteur actif en continu
        self.assertIn("            screen: racine.ecranCloud\n", shell)
        self.assertIn("racine.ecranCloud = Quickshell.screens.find(", m.group(1) if m else "")
        r = lire("Recherche.qml")
        self.assertIn("if (ac.cloud && !(CloudEtat.actif && CloudEtat.associe)) continue", r)
        self.assertIn('"ipc", "call", "ile", "cloud"', r)

    def test_actions_liees_aux_capacites(self):
        e = lire("CloudEtat.qml")
        self.assertIn("readonly property bool peutDeplacer: features.entry_move === true", e)
        self.assertIn("features.directory_delete === true && features.delete_preview === true", e)
        self.assertIn('if (!apercu || apercu.id !== e.id || !/^[0-9a-f]{64}$/.test(apercu.tree)) return', e)
        p = lire("CloudPanneau.qml")
        self.assertIn("suppression définitive, toutes ses versions", p)
        self.assertIn("onDoubleClicked: CloudEtat.ouvrirEntree(ligne.modelData)", p)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def lancer(self, corps, reglages=None, associe=True, suppression=True, features=None, page=None):
        with tempfile.TemporaryDirectory(prefix="nc-cloudqml-") as d:
            root = H.preparer(d, ("Couleurs", "Texte", "Ico", "BoutonReglages", "CloudBouton"),
                              extra={"CloudEtat.qml": lire("CloudEtat.qml"), "CloudPanneau.qml": panneau_hors_fenetre()},
                              singletons=("CloudEtat",))
            bin_ = root / "home/.local/bin"
            bin_.mkdir(parents=True)
            f = features if features is not None else {"file_delete": suppression, "entry_by_id": True}
            (bin_ / "nc-cloud").write_text(FAUX.replace("@ROOT@", str(root)).replace("@FEAT@", json.dumps(f))
                                           .replace("@ARBRE1@", ARBRE1).replace("@ARBRE2@", ARBRE2))
            (bin_ / "nc-cloud").chmod(0o755)
            H.faux(root, "nc-reglages")
            (root / "racine.json").write_text(json.dumps(page or PAGE_RACINE) + "\n")
            if associe:
                (root / "state/nc-cloud").mkdir(parents=True)
                (root / "state/nc-cloud/appareil.json").write_text('{"device_id": "d", "name": "pc"}')
            reg = ("Reglages.valeurs = " + json.dumps(reglages) + "\n") if reglages else ""
            (root / "shell.qml").write_text(
                H.ENTETE + "import QtTest\nShellRoot {\n id: racine\n property var fen: null\n property int etape: 0\n property int ticks: 0\n"
                + " TestCase { id: souris; name: \"Souris\"; when: false }\n" + H.OUTILS + OUTILS + " Component.onCompleted: { " + reg + "}\n" + textwrap.dedent(corps)
                + "\n Timer { interval: 15000; running: true; onTriggered: { console.error(\"ECHEC délai\"); Qt.exit(3) } }\n}\n")
            _, sortie = H.lancer(root, delai=40)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)
            return H.journal(root).splitlines()

    OUVRIR = '''
        function ouvrir() { var c = Qt.createComponent("CloudPanneau.qml"); verifier(c.status === Component.Ready, c.errorString())
                            fen = c.createObject(racine) }
    '''

    def test_coupe_rien_ne_tourne(self):
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                ticks++
                if (ticks < 8) return
                verifier(vu(fen.contentItem, "nc-cloud-coupe"), "message coupé")
                verifier(!vu(fen.contentItem, "nc-cloud-actualiser"), "pas d'Actualiser")
                CloudEtat.lancer(["etat"], "etat"); CloudEtat.actualiser()        // même appelé : rien ne part
                console.log("FINI"); Qt.exit(0)
            } }
        ''')
        self.assertEqual(j, [])

    def test_non_associe_rien_ne_tourne(self):
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                ticks++
                if (ticks < 8) return
                verifier(vu(fen.contentItem, "nc-cloud-non-associe"), "message non associé")
                verifier(!CloudEtat.associe, "non associé")
                CloudEtat.lancer(["etat"], "etat"); CloudEtat.creerDossier("x")
                console.log("FINI"); Qt.exit(0)
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"}, associe=False)
        self.assertEqual(j, [])

    def test_parcours_telechargement_remplacer_et_suppression(self):
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length) return
                var corps = fen.contentItem
                if (etape === 1) {
                    if (!CloudEtat.lu) return
                    verifier(CloudEtat.entrees.length === 2, "deux entrées")
                    verifier(textes(corps).indexOf("1.0 Mio sur 20.0 Gio") >= 0, "quota : " + textes(corps))
                    verifier(!vu(corps, "nc-cloud-actions-ffffffffffffffffffffffffffffffff") && !vu(corps, "nc-cloud-supprimer-ffffffffffffffffffffffffffffffff"), "aucune action avant le clic")
                    CloudEtat.choisir(CloudEtat.entrees[0])
                    verifier(!vu(corps, "nc-cloud-supprimer-dddddddddddddddddddddddddddddddd") && !vu(corps, "nc-cloud-telecharger-dddddddddddddddddddddddddddddddd"), "aucun Supprimer ni Télécharger pour un dossier sans directory_delete")
                    CloudEtat.choisir(CloudEtat.entrees[1])
                    verifier(vu(corps, "nc-cloud-supprimer-ffffffffffffffffffffffffffffffff"), "Supprimer pour un fichier")
                    CloudEtat.supprimer(CloudEtat.entrees[0])                  // un dossier : refusé sans lancement
                    CloudEtat.telecharger(CloudEtat.entrees[1], false); etape++; return }
                if (etape === 2) {
                    verifier(CloudEtat.aRemplacer === "ffffffffffffffffffffffffffffffff" && vu(corps, "nc-cloud-remplacer-ffffffffffffffffffffffffffffffff"), "Remplacer proposé")
                    verifier(CloudEtat.erreur.indexOf("existe déjà") >= 0, "erreur montrée")
                    CloudEtat.telecharger(CloudEtat.entrees[1], true); etape++; return }
                if (etape === 3) {
                    verifier(CloudEtat.message === "Téléchargé." && CloudEtat.aRemplacer === "", "téléchargé")
                    CloudEtat.choisir(CloudEtat.entrees[1]); trouver(corps, "nc-cloud-supprimer-ffffffffffffffffffffffffffffffff").clic(); etape++; return }
                if (etape === 4) {
                    verifier(vu(corps, "nc-cloud-question-ffffffffffffffffffffffffffffffff"), "question posée sur la ligne")
                    verifier(!vu(corps, "nc-cloud-supprimer-ffffffffffffffffffffffffffffffff"), "plus de Supprimer… pendant la question")
                    verifier(textes(corps).join("|").indexOf("suppression définitive, toutes ses versions") >= 0, "texte de la question")
                    trouver(corps, "nc-cloud-confirmer-ffffffffffffffffffffffffffffffff").clic(); etape++; return }
                if (etape === 5) { CloudEtat.aller(CloudEtat.entrees[0]); etape++; return }
                if (etape === 6) {
                    verifier(CloudEtat.dossier === "dddddddddddddddddddddddddddddddd" && CloudEtat.chemin.length === 2, "dans Photos")
                    verifier(vu(corps, "nc-cloud-vide"), "dossier vide")
                    CloudEtat.creerDossier("  Vacances  "); etape++; return }
                if (etape === 7) { CloudEtat.remonter(0); etape++; return }
                if (etape === 8) { verifier(CloudEtat.dossier === "root", "revenu à la racine"); console.log("FINI"); Qt.exit(0) }
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"})
        self.assertEqual(j, ["--json etat", "--json lister -- root", "--json telecharger --dossier=root -- ffffffffffffffffffffffffffffffff",
                             "--json telecharger --dossier=root --remplacer -- ffffffffffffffffffffffffffffffff", "--json supprimer --revision=r9 -- ffffffffffffffffffffffffffffffff",
                             "--json lister -- root", "--json lister -- dddddddddddddddddddddddddddddddd", "--json dossier -- dddddddddddddddddddddddddddddddd Vacances", "--json lister -- dddddddddddddddddddddddddddddddd",
                             "--json lister -- root"])

    def test_clic_choisit_sans_bouger_puis_double_clic(self):
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length || !CloudEtat.lu) return
                var corps = fen.contentItem
                if (etape === 1) {
                    var l = trouver(corps, "nc-cloud-entree-ffffffffffffffffffffffffffffffff"), nom = trouver(corps, "nc-cloud-nom-ffffffffffffffffffffffffffffffff")
                    var avant = nom.mapToItem(corps, 0, 0)
                    souris.mouseClick(l, 120, 18)
                    verifier(CloudEtat.selection === "ffffffffffffffffffffffffffffffff" && vu(corps, "nc-cloud-actions-ffffffffffffffffffffffffffffffff"), "un clic choisit et montre les actions")
                    var apres = nom.mapToItem(corps, 0, 0)
                    verifier(avant.x === apres.x && avant.y === apres.y, "le nom a bougé sous la souris : " + avant + " / " + apres)
                    var sous = l.childAt(120, 18)
                    verifier(sous !== null && sous.objectName !== "" ? sous.objectName.indexOf("nc-cloud-actions") < 0 : true, "une action sous le point cliqué")
                    verifier(!vu(corps, "nc-cloud-renommer-ffffffffffffffffffffffffffffffff") && !vu(corps, "nc-cloud-deplacer-ffffffffffffffffffffffffffffffff"), "ni Renommer ni Déplacer sans entry_move")
                    souris.mouseDoubleClickSequence(l, 120, 18); etape++; return }
                if (etape === 2) {
                    souris.mouseDoubleClickSequence(trouver(corps, "nc-cloud-entree-dddddddddddddddddddddddddddddddd"), 120, 18); etape++; return }
                if (etape === 3) {
                    verifier(CloudEtat.dossier === "dddddddddddddddddddddddddddddddd", "le double-clic n'est pas entré dans le dossier")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"})
        self.assertEqual(j, ["--json etat", "--json lister -- root", "--json ouvrir --dossier=root -- ffffffffffffffffffffffffffffffff", "--json lister -- dddddddddddddddddddddddddddddddd"])

    def test_creer_fichier_renommer_deplacer_ici(self):
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length || !CloudEtat.lu) return
                var corps = fen.contentItem
                if (etape === 1) {
                    trouver(corps, "nc-cloud-nom-dossier").text = "vide.txt"
                    trouver(corps, "nc-cloud-creer-fichier").clic(); etape++; return }
                if (etape === 2) {
                    CloudEtat.choisir(CloudEtat.entrees[1])
                    trouver(corps, "nc-cloud-renommer-ffffffffffffffffffffffffffffffff").clic()
                    verifier(vu(corps, "nc-cloud-nouveau-nom-ffffffffffffffffffffffffffffffff") && trouver(corps, "nc-cloud-nouveau-nom-ffffffffffffffffffffffffffffffff").text === "note.txt", "champ de renommage")
                    trouver(corps, "nc-cloud-nouveau-nom-ffffffffffffffffffffffffffffffff").text = "notes.md"
                    trouver(corps, "nc-cloud-valider-nom-ffffffffffffffffffffffffffffffff").clic(); etape++; return }
                if (etape === 3) {
                    CloudEtat.choisir(CloudEtat.entrees[1]); trouver(corps, "nc-cloud-deplacer-ffffffffffffffffffffffffffffffff").clic()
                    verifier(vu(corps, "nc-cloud-deplacement"), "bandeau du déplacement")
                    verifier(!trouver(corps, "nc-cloud-deplacer-ici").enabled, "Déplacer ici dans son propre dossier")
                    CloudEtat.aller(CloudEtat.entrees[0]); etape++; return }
                if (etape === 4) {
                    verifier(CloudEtat.dossier === "dddddddddddddddddddddddddddddddd" && trouver(corps, "nc-cloud-deplacer-ici").enabled, "Déplacer ici dans Photos")
                    trouver(corps, "nc-cloud-deplacer-ici").clic(); etape++; return }
                if (etape === 5) {
                    verifier(!CloudEtat.deplacement && !vu(corps, "nc-cloud-deplacement"), "bandeau fermé")
                    CloudEtat.remonter(0); etape++; return }
                if (etape === 6) {
                    CloudEtat.commencerDeplacement(CloudEtat.entrees[0]); CloudEtat.aller(CloudEtat.entrees[0])
                    verifier(CloudEtat.dossier === "root" && !CloudEtat.deplacementPossible, "un dossier dans lui-même")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"}, features={"entry_move": True})
        self.assertEqual(j, ["--json etat", "--json lister -- root", "--json creer -- root vide.txt", "--json lister -- root",
                             "--json renommer --revision=r9 -- ffffffffffffffffffffffffffffffff notes.md", "--json lister -- root", "--json lister -- dddddddddddddddddddddddddddddddd",
                             "--json deplacer --revision=r9 --vers=dddddddddddddddddddddddddddddddd -- ffffffffffffffffffffffffffffffff", "--json lister -- dddddddddddddddddddddddddddddddd", "--json lister -- root"])

    def test_dossier_apercu_question_puis_arbre_change(self):
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length || !CloudEtat.lu) return
                var corps = fen.contentItem
                if (etape === 1) {
                    CloudEtat.choisir(CloudEtat.entrees[0])
                    trouver(corps, "nc-cloud-supprimer-dddddddddddddddddddddddddddddddd").clic()
                    verifier(!trouver(corps, "nc-cloud-confirmer-dddddddddddddddddddddddddddddddd").enabled, "confirmer avant l'aperçu")
                    CloudEtat.supprimer(CloudEtat.entrees[0]); etape++; return }        // sans aperçu : refusé, rien ne part
                if (etape === 2) {
                    var ap = CloudEtat.apercu
                    CloudEtat.apercu = null
                    verifier(!trouver(corps, "nc-cloud-confirmer-dddddddddddddddddddddddddddddddd").enabled, "confirmer sans aperçu, rien en cours")
                    CloudEtat.apercu = ap
                    verifier(vu(corps, "nc-cloud-question-dddddddddddddddddddddddddddddddd"), "question")
                    var q = trouver(corps, "nc-cloud-question-dddddddddddddddddddddddddddddddd").text
                    verifier(q.indexOf("3 fichier(s), 2 dossier(s), 2.0 Kio") >= 0, "aperçu dans la question : " + q)
                    trouver(corps, "nc-cloud-confirmer-dddddddddddddddddddddddddddddddd").clic(); etape++; return }
                if (etape === 3) {
                    verifier(vu(corps, "nc-cloud-question-dddddddddddddddddddddddddddddddd") && CloudEtat.apercu && CloudEtat.apercu.tree === "@ARBRE2@", "nouvel aperçu, nouvelle question")
                    verifier(CloudEtat.erreur.indexOf("changé") >= 0, "le changement est dit")
                    trouver(corps, "nc-cloud-confirmer-dddddddddddddddddddddddddddddddd").clic(); etape++; return }
                if (etape === 4) { console.log("FINI"); Qt.exit(0) }
            } }
        '''.replace("@ARBRE2@", ARBRE2), reglages={"CLOUD_JARVIS": "oui"}, features={"directory_delete": True, "delete_preview": True})
        self.assertEqual(j, ["--json etat", "--json lister -- root", "--json apercu -- dddddddddddddddddddddddddddddddd",
                             "--json supprimer --revision=r1 --recursif --arbre=" + ARBRE1 + " -- dddddddddddddddddddddddddddddddd", "--json lister -- root", "--json apercu -- dddddddddddddddddddddddddddddddd",
                             "--json supprimer --revision=r1 --recursif --arbre=" + ARBRE2 + " -- dddddddddddddddddddddddddddddddd", "--json lister -- root"])

    def test_sans_aucune_capacite_ni_supprimer_ni_renommer_ni_deplacer(self):
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length || !CloudEtat.lu) return
                var corps = fen.contentItem
                for (var e of CloudEtat.entrees) {
                    CloudEtat.choisir(e)
                    for (var a of ["supprimer", "renommer", "deplacer"]) verifier(!vu(corps, "nc-cloud-" + a + "-" + e.id), a + " sans capacité")
                    verifier(vu(corps, "nc-cloud-ouvrir-" + e.id), "Ouvrir toujours")
                    CloudEtat.supprimer(e); CloudEtat.renommer(e, "x"); CloudEtat.commencerDeplacement(e); CloudEtat.demanderApercu(e)
                }
                verifier(!CloudEtat.deplacement, "déplacement sans capacité")
                console.log("FINI"); Qt.exit(0)
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"}, features={})
        self.assertEqual(j, ["--json etat", "--json lister -- root"])

    def test_nom_a_tiret_apres_double_tiret_et_ids_pieges_ecartes(self):
        """Un nom tapé « -x » n'est jamais lu comme une option ; un id du serveur hors de root ou 32 hex est écarté."""
        page = json.loads(json.dumps(PAGE_RACINE))
        page["entries"] += [{"id": i, "name": "piège", "kind": "file", "revision": "r", "parent": "root"}
                            for i in ("--remplacer", "-x", "../" + "a" * 32, "A" * 32, "a" * 33)]
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length || !CloudEtat.lu) return
                if (etape === 1) {
                    verifier(CloudEtat.entrees.length === 2, "ids piégés gardés : " + CloudEtat.entrees.length)
                    CloudEtat.creerDossier("-x"); etape++; return }
                console.log("FINI"); Qt.exit(0)
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"}, page=page)
        self.assertIn("--json dossier -- root -x", j)

    def test_sans_suppression_annoncee_aucun_bouton(self):
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || !CloudEtat.lu || CloudEtat.suites.length) return
                CloudEtat.choisir(CloudEtat.entrees[1])
                verifier(!vu(fen.contentItem, "nc-cloud-supprimer-ffffffffffffffffffffffffffffffff"), "pas de Supprimer sans file_delete")
                CloudEtat.supprimer(CloudEtat.entrees[1])
                ticks++
                if (ticks > 4) { console.log("FINI"); Qt.exit(0) }
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"}, suppression=False)
        self.assertNotIn("supprimer", " ".join(j))


if __name__ == "__main__":
    unittest.main()
