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
  etat) printf '%s\n' '{"evenement": "etat", "etat": {"used_bytes": 1048576, "quota_bytes": 21474836480}, "features": @FEAT@, "fichiers": @FICHIERS@}' ;;
  lister) if [ "$dernier" = root ]; then cat "@ROOT@/racine.json"; elif [ -f "@ROOT@/sous.json" ]; then cat "@ROOT@/sous.json"
          else printf '%s\n' '{"evenement": "page", "entries": [], "next_cursor": null}'; fi ;;
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
  deposer) apres=0
           for a in "$@"; do
             if [ "$apres" = 0 ]; then [ "$a" = "--" ] && apres=1; continue; fi
             case "$a" in
               *lent*) printf '{"evenement": "progression", "fichier": "%s", "envoye": 5, "taille": 10}\n' "$a"; exec sleep 30 ;;
               *coupure*) printf '{"evenement": "progression", "fichier": "%s", "envoye": 5, "taille": 10}\n' "$a"
                          printf '[{"numero": 1, "cle": "CLEabcdefghijklmnop_-", "fichier": "%s", "nom": "coupure.txt", "taille": 10}]' "$a" > "@ROOT@/envois.json"
                          printf '%s\n' '{"evenement": "erreur", "code": 3, "message": "Hors ligne."}'; exit 3 ;;
               *resolu*) printf '{"evenement": "resultat", "fichier": "/autre%s", "etat": "publie", "message": "Envoyé."}\n' "$a"; exit 1 ;;
               *dossier-conflit*) printf '{"evenement": "conflit", "fichier": "%s", "actuel": {"id": "e", "kind": "directory", "revision": "rv7"}, "message": "Conflit."}\n' "$a"; exit 6 ;;
               *conflit*) case "$*" in
                            *--si-existe=*) printf '{"evenement": "resultat", "fichier": "%s", "etat": "publie", "message": "Envoyé."}\n' "$a" ;;
                            *) printf '{"evenement": "conflit", "fichier": "%s", "actuel": {"id": "e", "revision": "rv7"}, "message": "Conflit."}\n' "$a"; exit 6 ;;
                          esac ;;
               *) printf '{"evenement": "progression", "fichier": "%s", "envoye": 10, "taille": 10}\n' "$a"
                  printf '{"evenement": "resultat", "fichier": "%s", "etat": "publie", "message": "Envoyé."}\n' "$a" ;;
             esac
           done ;;
  examiner) apres=0; sep=""; printf '{"evenement": "examen", "fichiers": ['
            for a in "$@"; do
              if [ "$apres" = 0 ]; then [ "$a" = "--" ] && apres=1; continue; fi
              cache=false; refus=null
              case "$a" in */.*) cache=true ;; esac
              case "$a" in *.ssh*) cache=false; refus='"id : fichier protégé, non envoyé."' ;; esac
              printf '%s{"fichier": "%s", "taille": 3, "cache": %s, "refus": %s}' "$sep" "$a" "$cache" "$refus"; sep=", "
            done
            printf ']}\n' ;;
  reprendre) if [ "$2" = "--" ]; then printf '%s\n' '{"evenement": "resultat", "fichier": "/tmp/coupure.txt", "etat": "publie", "message": "Envoyé."}'
             else printf '{"evenement": "envois", "envois": %s}\n' "$(cat "@ROOT@/envois.json" 2>/dev/null || echo '[]')"
                  case "$(cat "@ROOT@/envois.json" 2>/dev/null)" in *longue*) exec sleep 30 ;; esac; fi ;;
  choisir) n=$(cat "@ROOT@/choix" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "@ROOT@/choix"
           case $n in
             1) printf '%s\n' '{"evenement": "choisis", "fichiers": ["file:///tmp/1", "file:///tmp/2", "file:///tmp/3", "file:///tmp/4", "file:///tmp/5", "file:///tmp/6", "file:///tmp/7", "file:///tmp/8", "file:///tmp/9"]}' ;;
             2) printf '%s\n' '{"evenement": "choisis", "fichiers": []}' ;;
             *) exec sleep 30 ;;
           esac ;;
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

    def test_pilule_indicateur_clic_survol_et_depot_sur_l_ile_fermee(self):
        compact, ile = lire("Compact.qml"), lire("Ile.qml")
        self.assertIn('objectName: "nc-cloud-pill"', compact)
        self.assertIn("visible: CloudEtat.actif && CloudEtat.associe", compact)
        self.assertIn('nom: CloudEtat.envoie ? "cloud_upload" : "cloud"', compact)          # activité discrète pendant un envoi
        self.assertIn("color: CloudEtat.envoie ? Couleurs.accentClair : Couleurs.texteSec", compact)
        self.assertIn("(compact.surCloud(e.x, e.y) ? CloudEtat.ouvrirPanneau()", ile)      # un clic ouvre le panneau
        self.assertIn("if (compact.surCloud(survol.point.position.x, survol.point.position.y)) { if (survol.hovered) restart(); return }", ile)
        m = re.search(r"DropArea \{\n\s*id: depotCloud(.*?)\n        \}\n", ile, re.S)
        self.assertIsNotNone(m)
        d = m.group(1) if m else ""
        self.assertIn("enabled: CloudEtat.actif && CloudEtat.associe && !fen.ouverte && !fen.banniere && !fen.enCarte", d)
        self.assertIn("drag.accept(Qt.CopyAction)", d)
        self.assertIn("drop.accept(Qt.CopyAction)", d)
        self.assertIn("if (CloudEtat.recevoir(drop.urls)) CloudEtat.ouvrirPanneau()", d)
        self.assertNotIn("envoyerIci", ile)                                                   # rien ne part avant le bouton
        self.assertIn("visible: depotCloud.containsDrag", ile)
        # La page JARVIS garde son propre dépôt (pièces jointes)
        self.assertIn("DropArea {", lire("Assistant.qml"))

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
    def lancer(self, corps, reglages=None, associe=True, suppression=True, features=None, page=None, notifier=False, sous=None, fichiers=False):
        with tempfile.TemporaryDirectory(prefix="nc-cloudqml-") as d:
            root = H.preparer(d, ("Couleurs", "Texte", "Ico", "BoutonReglages", "CloudBouton"),
                              extra={"CloudEtat.qml": lire("CloudEtat.qml"), "CloudPanneau.qml": panneau_hors_fenetre()},
                              singletons=("CloudEtat",))
            bin_ = root / "home/.local/bin"
            bin_.mkdir(parents=True)
            f = features if features is not None else {"file_delete": suppression, "entry_by_id": True}
            (bin_ / "nc-cloud").write_text(FAUX.replace("@ROOT@", str(root)).replace("@FEAT@", json.dumps(f))
                                           .replace("@ARBRE1@", ARBRE1).replace("@ARBRE2@", ARBRE2)
                                           .replace("@FICHIERS@", "true" if fichiers else "false"))
            (bin_ / "nc-cloud").chmod(0o755)
            H.faux(root, "nc-reglages")
            if notifier:
                H.faux(root, "notify-send")
            (root / "racine.json").write_text(json.dumps(page or PAGE_RACINE) + "\n")
            if sous:
                (root / "sous.json").write_text(json.dumps(sous) + "\n")
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
        self.assertEqual(j, ["--json etat", "--json lister -- root", "--json reprendre", "--json telecharger --dossier=root -- ffffffffffffffffffffffffffffffff",
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
        self.assertEqual(j, ["--json etat", "--json lister -- root", "--json reprendre", "--json ouvrir --dossier=root -- ffffffffffffffffffffffffffffffff", "--json lister -- dddddddddddddddddddddddddddddddd"])

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
        self.assertEqual(j, ["--json etat", "--json lister -- root", "--json reprendre", "--json creer -- root vide.txt", "--json lister -- root",
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
        self.assertEqual(j, ["--json etat", "--json lister -- root", "--json reprendre", "--json apercu -- dddddddddddddddddddddddddddddddd",
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
        self.assertEqual(j, ["--json etat", "--json lister -- root", "--json reprendre"])

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

    def test_recus_envoyer_ici_conflit_actualisation_et_effacer(self):
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length || !CloudEtat.lu || CloudEtat.envoie) return
                var corps = fen.contentItem
                if (etape === 1) {
                    verifier(!vu(corps, "nc-cloud-recus") && !vu(corps, "nc-cloud-envois"), "rien avant le dépôt")
                    verifier(CloudEtat.recevoir(["file:///tmp/a.txt", "file:///tmp/b%20conflit.txt", "https://x/y", "file://hote/z", "file:///tmp/a.txt"]), "reçus")
                    verifier(CloudEtat.recus.length === 2 && CloudEtat.recus[1] === "/tmp/b conflit.txt", "fichiers locaux seulement : " + CloudEtat.recus)
                    verifier(CloudEtat.recusRefus !== "" && vu(corps, "nc-cloud-recus"), "sélection montrée, écartés dits")
                    verifier(CloudEtat.envois.length === 0, "rien ne part avant Envoyer ici")
                    etape = 15; return }
                if (etape === 15) {
                    verifier(CloudEtat.examenPret && trouver(corps, "nc-cloud-envoyer-ici").enabled, "examen reçu")
                    verifier(trouver(corps, "nc-cloud-recu-1").text === "/tmp/b conflit.txt", "chemin complet : " + trouver(corps, "nc-cloud-recu-1").text)
                    verifier(trouver(corps, "nc-cloud-recu-info-0").text === "3 o", "taille : " + trouver(corps, "nc-cloud-recu-info-0").text)
                    verifier(trouver(corps, "nc-cloud-envoyer-ici").texte === "Envoyer ici", "pas de fichier caché")
                    trouver(corps, "nc-cloud-envoyer-ici").clic(); etape = 2; return }
                if (etape === 2) {
                    verifier(CloudEtat.recus.length === 0, "sélection vidée")
                    verifier(CloudEtat.envois[0].etat === "publie" && CloudEtat.envois[1].etat === "conflit", JSON.stringify(CloudEtat.envois))
                    verifier(vu(corps, "nc-cloud-garder-1") && vu(corps, "nc-cloud-remplacer-envoi-1") && vu(corps, "nc-cloud-annuler-envoi-1"), "choix du conflit")
                    verifier(!vu(corps, "nc-cloud-garder-0"), "pas de choix sans conflit")
                    trouver(corps, "nc-cloud-garder-1").clic(); etape++; return }
                if (etape === 3) {
                    verifier(CloudEtat.envois[1].etat === "publie", "conservé les deux")
                    verifier(trouver(corps, "nc-cloud-envoi-etat-1").text === "Envoyé", trouver(corps, "nc-cloud-envoi-etat-1").text)
                    CloudEtat.resoudre(0, "garder"); CloudEtat.resoudre(0, "remplacer"); CloudEtat.reprendre(0)   // ligne publiée : rien ne part
                    verifier(!CloudEtat.envoie, "aucun envoi relancé")
                    CloudEtat.envois = CloudEtat.envois.concat([{ fichier: "/tmp/x", nom: "x", dans: "root", etat: "interrompu", envoye: 0, taille: 0,
                                                                  message: "", actuel: null, fin: 0, vu: false }])
                    trouver(corps, "nc-cloud-effacer-termines").clic()
                    verifier(CloudEtat.envois.length === 1 && CloudEtat.envois[0].etat === "interrompu", "seuls les terminés partent")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"}, notifier=True)
        self.assertEqual([x for x in j if not x.startswith("notify-send")],
                         ["--json etat", "--json lister -- root", "--json reprendre",
                          "--json examiner -- /tmp/a.txt /tmp/b conflit.txt",
                          "--json deposer --dans=root -- /tmp/a.txt /tmp/b conflit.txt", "--json etat", "--json lister -- root",
                          "--json deposer --dans=root --si-existe=garder -- /tmp/b conflit.txt", "--json etat", "--json lister -- root"])
        notes = [x for x in j if x.startswith("notify-send")]
        self.assertEqual(len(notes), 2, j)                       # une notification à la fin de chaque envoi
        self.assertIn("1 fichier(s) envoyé(s)", notes[0])

    def test_adresses_non_normalisees_cache_protege_et_publie_sans_ligne(self):
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length || !CloudEtat.lu || CloudEtat.envoie) return
                var corps = fen.contentItem
                if (etape === 1) {
                    verifier(!CloudEtat.recevoir(["file:///home/user/.ssh/id_ed25519/", "file:///home/user/.ssh/id_ed25519/.",
                                                  "file:///home/user/a/../.ssh/id", "file:///home/user//a.txt", "file:///home/user/."]),
                             "formes non normalisées refusées")
                    verifier(CloudEtat.recus.length === 0, "rien reçu")
                    CloudEtat.recevoir(["file:///home/user/.notes/a.txt", "file:///home/user/.ssh/id", "file:///tmp/resolu.txt"])
                    etape++; return }
                if (etape === 2) {
                    verifier(trouver(corps, "nc-cloud-recu-info-0").text.indexOf("fichier caché") === 0, trouver(corps, "nc-cloud-recu-info-0").text)
                    verifier(trouver(corps, "nc-cloud-recu-info-1").text === "ne partira pas", "protégé")
                    verifier(trouver(corps, "nc-cloud-envoyer-ici").texte === "Envoyer quand même", "second regard")
                    trouver(corps, "nc-cloud-envoyer-ici").clic(); etape++; return }
                if (etape === 3) {
                    var r = CloudEtat.envois.find(e => e.fichier === "/tmp/resolu.txt")
                    verifier(r && r.etat === "inconnu", "publié sans ligne : jamais Échec (" + (r && r.etat) + ")")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"})
        self.assertIn("--json deposer --dans=root -- /home/user/.notes/a.txt /tmp/resolu.txt", j)       # le protégé ne part pas

    def test_annuler_pendant_une_reprise_et_pas_de_remplacer_pour_un_dossier(self):
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length || !CloudEtat.lu) return
                var corps = fen.contentItem
                if (etape === 1) { CloudEtat.recevoir(["file:///tmp/coupure-longue.txt", "file:///tmp/dossier-conflit"]); etape++; return }
                if (etape === 2) { CloudEtat.envoyerIci(); etape++; return }
                if (etape === 3 && !CloudEtat.envoie) {
                    verifier(CloudEtat.envois[0].etat === "interrompu", "interrompu : " + CloudEtat.envois[0].etat)
                    CloudEtat.recevoir(["file:///tmp/dossier-conflit"]); etape++; return }
                if (etape === 4) { CloudEtat.envoyerIci(); etape++; return }
                if (etape === 5 && !CloudEtat.envoie) {
                    var i = CloudEtat.envois.length - 1
                    verifier(CloudEtat.envois[i].etat === "conflit" && vu(corps, "nc-cloud-garder-" + i), "conflit")
                    verifier(!vu(corps, "nc-cloud-remplacer-envoi-" + i), "pas de Remplacer pour un dossier")
                    CloudEtat.resoudre(i, "remplacer")
                    verifier(CloudEtat.envois[i].etat === "conflit" && !CloudEtat.envoie, "remplacer refusé")
                    trouver(corps, "nc-cloud-reprendre-0").clic(); etape++; return }
                if (etape === 6 && CloudEtat.lotEnCours && CloudEtat.lotEnCours.suite) { CloudEtat.annulerEnvois(); etape++; return }
                if (etape === 7 && !CloudEtat.envoie) {
                    ticks++; if (ticks < 4) return
                    verifier(CloudEtat.envois[0].etat === "annule", "reprise annulée : " + CloudEtat.envois[0].etat)
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"})
        self.assertFalse([x for x in j if x.startswith("--json reprendre -- ")], j)          # la reprise annulée ne part pas

    def test_coupure_reprendre_fermer_puis_annuler(self):
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length || !CloudEtat.lu) return
                var corps = fen.contentItem
                if (etape === 1) { CloudEtat.recevoir(["file:///tmp/coupure.txt"]); etape = 10; return }
                if (etape === 10) { CloudEtat.envoyerIci(); etape = 2; return }
                if (etape === 2 && !CloudEtat.envoie) {
                    verifier(CloudEtat.envois[0].etat === "interrompu" && vu(corps, "nc-cloud-reprendre-0"), JSON.stringify(CloudEtat.envois))
                    trouver(corps, "nc-cloud-reprendre-0").clic(); etape++; return }
                if (etape === 3 && !CloudEtat.envoie) {
                    verifier(CloudEtat.envois[0].etat === "publie", "repris : " + CloudEtat.envois[0].etat)
                    CloudEtat.recevoir(["file:///tmp/lent.txt"]); etape = 30; return }
                if (etape === 30) { CloudEtat.envoyerIci(); etape = 4; return }
                if (etape === 4 && CloudEtat.envois[1].etat === "en_cours") {
                    verifier(vu(corps, "nc-cloud-envois-annuler"), "Annuler l'envoi montré")
                    CloudEtat.panneauOuvert = false; etape++; return }       // panneau fermé : l'envoi continue
                if (etape === 5) { ticks++; if (ticks < 4) return
                    verifier(CloudEtat.envoie && CloudEtat.envois[1].etat === "en_cours", "fermer n'arrête pas l'envoi")
                    CloudEtat.annulerEnvois(); etape++; return }
                if (etape === 6 && !CloudEtat.envoie) {
                    verifier(CloudEtat.envois[1].etat === "annule", "annulé : " + CloudEtat.envois[1].etat)
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"})
        self.assertEqual(j, ["--json etat", "--json lister -- root", "--json reprendre", "--json examiner -- /tmp/coupure.txt",
                             "--json deposer --dans=root -- /tmp/coupure.txt",
                             "--json reprendre", "--json reprendre -- CLEabcdefghijklmnop_-", "--json etat", "--json lister -- root",
                             "--json examiner -- /tmp/lent.txt", "--json deposer --dans=root -- /tmp/lent.txt"])

    def test_selecteur_huit_au_plus_annuler_garde_et_fermer_arrete(self):
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length || !CloudEtat.lu) return
                if (etape === 1) { trouver(fen.contentItem, "nc-cloud-importer").clic(); etape++; return }
                if (etape === 2 && !CloudEtat.choixOuvert) {
                    verifier(CloudEtat.recus.length === 8 && CloudEtat.recus[7] === "/tmp/8" && CloudEtat.recusRefus !== "", "8 au plus : " + CloudEtat.recus)
                    CloudEtat.choisirFichiers(); etape++; return }
                if (etape === 3 && !CloudEtat.choixOuvert) {
                    verifier(CloudEtat.recus.length === 8, "annuler garde la sélection")
                    CloudEtat.choisirFichiers(); etape++; return }
                if (etape === 4 && CloudEtat.choixOuvert) {
                    verifier(!trouver(fen.contentItem, "nc-cloud-importer").enabled, "un seul sélecteur à la fois")
                    CloudEtat.panneauOuvert = false; etape++; return }
                if (etape === 5) {
                    verifier(!CloudEtat.choixOuvert, "le sélecteur se ferme avec le panneau")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"})
        self.assertEqual(j.count("--json choisir"), 3, j)

    def test_glisser_sur_un_dossier_sur_soi_meme_puis_vers_le_parent(self):
        sous = {"evenement": "page", "parent": {"id": "dddddddddddddddddddddddddddddddd"}, "next_cursor": None,
                "entries": [{"id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "name": "photo.png", "kind": "file", "size": 3, "revision": "r5", "parent": "dddddddddddddddddddddddddddddddd"}]}
        j = self.lancer(self.OUVRIR + '''
            function glisser(de, vers, lacher) {
                souris.mousePress(de, 60, 20); souris.mouseMove(de, 70, 24); souris.mouseMove(de, 90, 30)
                souris.mouseMove(vers, 12, 12)
                if (lacher) souris.mouseRelease(vers, 12, 12)
            }
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length || !CloudEtat.lu) return
                var corps = fen.contentItem
                if (etape === 1) {
                    verifier(!vu(corps, "nc-cloud-parent"), "pas de ↑ à la racine")
                    glisser(trouver(corps, "nc-cloud-entree-ffffffffffffffffffffffffffffffff"), trouver(corps, "nc-cloud-entree-dddddddddddddddddddddddddddddddd"), false); etape++; return }
                if (etape === 2) {
                    verifier(vu(corps, "nc-cloud-fantome") && trouver(corps, "nc-cloud-fantome").entree.id === "ffffffffffffffffffffffffffffffff", "aperçu sous le pointeur")
                    verifier(trouver(corps, "nc-cloud-cible-dddddddddddddddddddddddddddddddd").containsDrag, "destination en surbrillance")
                    verifier(trouver(corps, "nc-cloud-entree-dddddddddddddddddddddddddddddddd").border.width === 2, "bordure de la destination")
                    souris.mouseRelease(trouver(corps, "nc-cloud-entree-dddddddddddddddddddddddddddddddd"), 12, 12); etape++; return }
                if (etape === 3) {
                    verifier(!vu(corps, "nc-cloud-fantome"), "aperçu retiré au lâcher")
                    glisser(trouver(corps, "nc-cloud-entree-dddddddddddddddddddddddddddddddd"), trouver(corps, "nc-cloud-entree-dddddddddddddddddddddddddddddddd"), false); etape++; return }
                if (etape === 4) {
                    verifier(!trouver(corps, "nc-cloud-cible-dddddddddddddddddddddddddddddddd").containsDrag, "pas de surbrillance sur soi-même")
                    souris.mouseRelease(trouver(corps, "nc-cloud-entree-dddddddddddddddddddddddddddddddd"), 12, 12)
                    glisser(trouver(corps, "nc-cloud-entree-dddddddddddddddddddddddddddddddd"), trouver(corps, "nc-cloud-entree-ffffffffffffffffffffffffffffffff"), false); etape = 40; return }
                if (etape === 40) {
                    verifier(!trouver(corps, "nc-cloud-cible-ffffffffffffffffffffffffffffffff").containsDrag, "pas de dépôt sur un fichier")
                    souris.mouseRelease(trouver(corps, "nc-cloud-entree-ffffffffffffffffffffffffffffffff"), 12, 12)
                    CloudEtat.deplacerVers(CloudEtat.entrees[1], "root")        // dans son propre dossier : rien
                    ticks++; if (ticks < 3) return
                    CloudEtat.aller(CloudEtat.entrees[0]); etape = 5; return }
                if (etape === 5) {
                    verifier(CloudEtat.dossier === "dddddddddddddddddddddddddddddddd" && vu(corps, "nc-cloud-parent"), "↑ dans Photos")
                    glisser(trouver(corps, "nc-cloud-entree-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), trouver(corps, "nc-cloud-parent"), false); etape++; return }
                if (etape === 6) {
                    verifier(trouver(corps, "nc-cloud-cible-parent").containsDrag && trouver(corps, "nc-cloud-parent").border.width === 2, "↑ en surbrillance")
                    souris.mouseRelease(trouver(corps, "nc-cloud-parent"), 12, 12); etape++; return }
                if (etape === 7) {
                    verifier(CloudEtat.dossier === "dddddddddddddddddddddddddddddddd", "on reste dans le dossier courant")
                    CloudEtat.deplacerVers({ id: "dddddddddddddddddddddddddddddddd", name: "Photos", kind: "directory", revision: "r1", parent: "root" }, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")   // dans le chemin
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"}, features={"entry_move": True, "file_delete": True}, sous=sous)
        self.assertEqual(j, ["--json etat", "--json lister -- root", "--json reprendre",
                             "--json deplacer --revision=r9 --vers=dddddddddddddddddddddddddddddddd -- ffffffffffffffffffffffffffffffff", "--json lister -- root",
                             "--json lister -- dddddddddddddddddddddddddddddddd", "--json deplacer --revision=r5 --vers=root -- aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "--json lister -- dddddddddddddddddddddddddddddddd"])

    def test_sans_glisser_sans_entry_move(self):
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length || !CloudEtat.lu) return
                var corps = fen.contentItem, de = trouver(corps, "nc-cloud-entree-ffffffffffffffffffffffffffffffff"), vers = trouver(corps, "nc-cloud-entree-dddddddddddddddddddddddddddddddd")
                if (etape === 1) { souris.mousePress(de, 60, 20); souris.mouseMove(de, 90, 30); souris.mouseMove(vers, 12, 12); etape++; return }
                verifier(!vu(corps, "nc-cloud-fantome"), "aucun glisser sans entry_move")
                souris.mouseRelease(vers, 12, 12)
                CloudEtat.deplacerVers(CloudEtat.entrees[1], "dddddddddddddddddddddddddddddddd")
                console.log("FINI"); Qt.exit(0)
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"})
        self.assertNotIn("deplacer", " ".join(j))

    def test_ouvrir_dans_fichiers_seulement_si_possible(self):
        for possible in (False, True):
            with self.subTest(possible=possible):
                j = self.lancer(self.OUVRIR + '''
                    Timer { interval: 80; running: true; repeat: true; onTriggered: {
                        if (etape === 0) { ouvrir(); etape++; return }
                        if (CloudEtat.occupe || CloudEtat.suites.length || !CloudEtat.lu) return
                        if (etape === 1) {
                            verifier(vu(fen.contentItem, "nc-cloud-fichiers") === CloudEtat.fichiersPossible, "bouton selon la présence de gi et WebDAV")
                            if (CloudEtat.fichiersPossible) trouver(fen.contentItem, "nc-cloud-fichiers").clic(); else CloudEtat.ouvrirFichiers()
                            etape++; return }
                        console.log("FINI"); Qt.exit(0)
                    } }
                ''', reglages={"CLOUD_JARVIS": "oui"}, fichiers=possible)
                self.assertEqual("--json fichiers" in j, possible, j)

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
