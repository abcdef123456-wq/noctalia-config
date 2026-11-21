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
  etat) n=$(cat "@ROOT@/etats" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "@ROOT@/etats"
        if [ -f "@ROOT@/etat-echec-apres" ] && [ "$n" -gt "$(cat "@ROOT@/etat-echec-apres")" ]; then
          printf '%s\n' '{"evenement": "erreur", "code": 3, "message": "Hors ligne."}'; exit 3; fi
        printf '%s\n' '{"evenement": "etat", "etat": {"used_bytes": 1048576, "quota_bytes": 21474836480}, "features": @FEAT@, "fichiers": @FICHIERS@}' ;;
  lister) if [ "$dernier" = root ]; then cat "@ROOT@/racine.json"; elif [ -f "@ROOT@/sous.json" ]; then cat "@ROOT@/sous.json"
          else printf '%s\n' '{"evenement": "page", "entries": [], "next_cursor": null}'; fi ;;
  telecharger) case "$*" in *--remplacer*) printf '%s\n' '{"evenement": "resultat", "message": "Téléchargé."}' ;;
               *) printf '%s\n' '{"evenement": "erreur", "code": 6, "message": "note.txt existe déjà."}'; exit 6 ;; esac ;;
  supprimer) case "$*" in *--arbre=@ARBRE1@*) printf '%s\n' '{"evenement": "erreur", "code": 6, "erreur": "tree_changed", "message": "Le dossier a changé."}'; exit 6 ;; esac
             case "$*" in *--copie*) m=$(cat "@ROOT@/mode-copie" 2>/dev/null)
               if [ "$m" = echec ]; then echo ok > "@ROOT@/mode-copie"
                 printf '%s\n' '{"evenement": "erreur", "code": 12, "erreur": "copie", "message": "Copie locale impossible."}'; exit 12; fi
               if [ "$m" = ok ]; then printf '%s\n' '[{"copie": "cccccccccccccccccccccccccccccccc", "nom": "note.txt", "taille": 12, "date": 1, "remettable": true, "etat": "supprime"}, {"copie": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", "nom": "cle.pem", "taille": 3, "date": 1, "remettable": false, "etat": "supprime"}, {"copie": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "nom": "vieux.txt", "taille": 1, "date": 1, "remettable": false, "etat": "refuse"}, {"copie": "../x", "nom": "y"}]' > "@ROOT@/corbeille.json"
                 printf '{"evenement": "resultat", "etat": "supprime", "copie": "cccccccccccccccccccccccccccccccc", "copie_etat": "%s", "nom": "note.txt", "message": "Fichier supprimé. Une copie reste sur ce PC 24 h."}\n' "$(cat "@ROOT@/copie-etat" 2>/dev/null || echo supprime)"; exit 0; fi ;;
             esac
             printf '%s\n' '{"evenement": "resultat", "message": "Supprimé."}' ;;
  corbeille) case "$*" in *--racine*) ;; *--remettre=*) if [ -f "@ROOT@/parent-absent" ]; then rm -f "@ROOT@/parent-absent"
                 printf '%s\n' '{"evenement": "erreur", "code": 1, "erreur": "parent_absent", "message": "Le dossier d origine n existe plus."}'; exit 1; fi ;; esac
             case "$*" in *--remettre=*) rm -f "@ROOT@/corbeille.json"; printf '%s\n' '{"evenement": "resultat", "etat": "publie", "message": "Envoyé."}'; exit 0 ;; esac
             printf '{"evenement": "corbeille", "copies": %s}\n' "$(cat "@ROOT@/corbeille.json" 2>/dev/null || echo '[]')" ;;
  apercu) n=$(cat "@ROOT@/apercus" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "@ROOT@/apercus"
          if [ "$n" = 1 ]; then t=@ARBRE1@; else t=@ARBRE2@; fi
          printf '{"evenement": "apercu", "entree": {"id": "%s"}, "files": 3, "directories": 2, "size": 2048, "tree_revision": "%s"}\n' "$dernier" "$t" ;;
  creer) printf '%s\n' '{"evenement": "resultat", "message": "Créé."}' ;;
  renommer) printf '%s\n' '{"evenement": "resultat", "message": "Renommé."}' ;;
  deplacer) printf '%s\n' '{"evenement": "resultat", "message": "Déplacé."}' ;;
  ouvrir) printf '%s\n' '{"evenement": "resultat", "message": "Ouvert : note.txt"}' ;;
  dossier) printf '%s\n' '{"evenement": "dossier", "message": "Dossier créé."}' ;;
  recents) case "$*" in *--effacer*) rm -f "@ROOT@/recents.json" ;; esac
           printf '{"evenement": "recents", "recents": %s}\n' "$(cat "@ROOT@/recents.json" 2>/dev/null || echo '[]')" ;;
  note) cat > "@ROOT@/note-entree"
        printf '%s\n' '{"evenement": "note", "nom": "Idee 2026-11-21 08h15.txt", "message": "Note enregistrée dans Notes : Idee 2026-11-21 08h15.txt."}' ;;
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
        self.assertIn("if (fichiers ? CloudEtat.recevoir(drop.urls) : CloudEtat.recevoirTexte(drop.text)) CloudEtat.ouvrirPanneau()", d)
        self.assertIn('drop.urls.some(u => String(u).startsWith("file:///"))', d)          # une adresse de fichier : dépôt normal
        self.assertNotIn("enregistrerNote", ile)                                              # rien ne part avant le bouton
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
    def lancer(self, corps, reglages=None, associe=True, suppression=True, features=None, page=None, notifier=False, sous=None, fichiers=False, recents=None, voir_recents=False,
               etat_echec_apres=None, mode_copie=None, parent_absent=False, copie_etat=None):
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
            H.faux(root, "xdg-open")                       # « Ouvrir le dossier » : jamais le vrai
            if notifier:
                H.faux(root, "notify-send")
            (root / "racine.json").write_text(json.dumps(page or PAGE_RACINE) + "\n")
            if sous:
                (root / "sous.json").write_text(json.dumps(sous) + "\n")
            if recents is not None:
                (root / "recents.json").write_text(json.dumps(recents))
            if mode_copie:
                (root / "mode-copie").write_text(mode_copie)
            if parent_absent:
                (root / "parent-absent").write_text("1")
            if copie_etat:
                (root / "copie-etat").write_text(copie_etat)
            if etat_echec_apres is not None:
                (root / "etat-echec-apres").write_text(str(etat_echec_apres))
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
            n = Path(root) / "note-entree"
            self.note_recue = n.read_text(encoding="utf-8") if n.exists() else None
            # La relecture locale des récents (à chaque ouverture, envoi, ouverture de fichier) n'est montrée qu'à qui la demande
            return [x for x in H.journal(root).splitlines() if voir_recents or x not in ("--json recents", "--json corbeille")]

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
                    verifier(textes(corps).join("|").indexOf("Une copie reste sur ce PC 24 h") >= 0, "texte de la question")
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
                             "--json telecharger --dossier=root --remplacer -- ffffffffffffffffffffffffffffffff", "--json supprimer --revision=r9 --dossier=root --copie -- ffffffffffffffffffffffffffffffff",
                             "--json lister -- root", "--json lister -- dddddddddddddddddddddddddddddddd", "--json dossier -- dddddddddddddddddddddddddddddddd Vacances", "--json lister -- dddddddddddddddddddddddddddddddd",
                             "--json lister -- root"])

    def test_corbeille_suppression_non_confirmee_pas_d_annuler(self):
        F = "f" * 32
        self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length) return
                var corps = fen.contentItem
                if (etape === 1) { if (!CloudEtat.lu) return
                    CloudEtat.choisir(CloudEtat.entrees[1]); trouver(corps, "nc-cloud-supprimer-@F@").clic(); etape++; return }
                if (etape === 2) { trouver(corps, "nc-cloud-confirmer-@F@").clic(); etape++; return }
                if (etape === 3) {
                    verifier(CloudEtat.message.indexOf("Une copie reste") >= 0, "résultat reçu : " + CloudEtat.message)
                    verifier(CloudEtat.annulable === null && !vu(corps, "nc-cloud-annulable"), "pas d'Annuler sans suppression confirmée")
                    console.log("FINI"); Qt.exit(0) }
            } }
        '''.replace("@F@", F), reglages={"CLOUD_JARVIS": "oui"}, mode_copie="ok", copie_etat="doute")

    def test_corbeille_copie_ratee_sans_copie_puis_annuler(self):
        F = "f" * 32
        j = self.lancer(self.OUVRIR + '''
            property var gardees: []
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length) return
                var corps = fen.contentItem, F = "@F@"
                function question() { return trouver(corps, "nc-cloud-question-" + F).text }
                function confirmer() { return trouver(corps, "nc-cloud-confirmer-" + F) }
                if (etape === 1) {
                    if (!CloudEtat.lu) return
                    verifier(!CloudEtat.copiable({ kind: "file", size: 524288001 }) && CloudEtat.copiable({ kind: "file", size: 524288000 })
                             && !CloudEtat.copiable({ kind: "directory", size: 1 }), "copiable : 500 Mio, fichiers seulement")
                    verifier(!vu(corps, "nc-cloud-corbeille") && !vu(corps, "nc-cloud-annulable"), "rien sans copie")
                    // Plus de 500 Mio : la question le dit AVANT, définitive
                    racine.gardees = CloudEtat.entrees
                    CloudEtat.entrees = [CloudEtat.entrees[0], Object.assign({}, CloudEtat.entrees[1], { size: 524288001 })]
                    CloudEtat.choisir(CloudEtat.entrees[1]); trouver(corps, "nc-cloud-supprimer-" + F).clic(); etape = 10; return }
                if (etape === 10) {
                    verifier(question().indexOf("trop gros pour une copie") >= 0 && confirmer().texte === "Supprimer définitivement", "gros : " + question())
                    trouver(corps, "nc-cloud-annuler-" + F).clic()
                    CloudEtat.entrees = [racine.gardees[0], Object.assign({}, racine.gardees[1], { sensible: true })]
                    CloudEtat.choisir(CloudEtat.entrees[1]); trouver(corps, "nc-cloud-supprimer-" + F).clic(); etape = 11; return }
                if (etape === 11) {   // nom de fichier de secrets : dit AVANT, avec où restera la copie
                    verifier(question().indexOf("ne pourra pas être remis depuis l'île") >= 0 && question().indexOf("~/.cache/nc-cloud/corbeille") >= 0,
                             "sensible : " + question())
                    trouver(corps, "nc-cloud-annuler-" + F).clic()
                    CloudEtat.entrees = racine.gardees
                    CloudEtat.choisir(CloudEtat.entrees[1]); trouver(corps, "nc-cloud-supprimer-" + F).clic(); etape = 2; return }
                if (etape === 2) {
                    verifier(question().indexOf("Une copie reste sur ce PC 24 h") >= 0 && confirmer().texte === "Supprimer", "avec copie : " + question())
                    confirmer().clic(); etape++; return }
                if (etape === 3) {   // copie ratée : rien n'est supprimé, la question revient, « sans copie », définitive
                    verifier(question().indexOf("La copie sur ce PC a échoué") >= 0 && confirmer().texte === "Supprimer définitivement", "sans copie : " + question())
                    confirmer().clic(); etape++; return }
                if (etape === 4) {
                    verifier(CloudEtat.sansCopie === "" && !vu(corps, "nc-cloud-annulable"), "supprimé sans copie : rien à annuler")
                    CloudEtat.choisir(CloudEtat.entrees[1]); trouver(corps, "nc-cloud-supprimer-" + F).clic(); etape++; return }
                if (etape === 5) {
                    verifier(question().indexOf("Une copie reste") >= 0, "la question suivante reprend la copie")
                    confirmer().clic(); etape++; return }
                if (etape === 6) {
                    verifier(vu(corps, "nc-cloud-annulable") && CloudEtat.annulable.nom === "note.txt" && CloudEtat.annulable.remettable, "Supprimé · Annuler")
                    verifier(vu(corps, "nc-cloud-corbeille") && CloudEtat.corbeille.length === 3 && vu(corps, "nc-cloud-remettre-@C@"), "corbeille : trois copies sûres")
                    // Refusée : grisée, son état dit, pas de « Remettre » (le fichier est toujours sur le serveur)
                    verifier(!vu(corps, "nc-cloud-remettre-@A@") && vu(corps, "nc-cloud-ouvrir-copie-@A@")
                             && vu(corps, "nc-cloud-etat-copie-@A@") && trouver(corps, "nc-cloud-etat-copie-@A@").parent.opacity < 1
                             && trouver(corps, "nc-cloud-etat-copie-@C@").parent.opacity === 1
                             && trouver(corps, "nc-cloud-etat-copie-@A@").text.indexOf("toujours sur le serveur") >= 0
                             && !vu(corps, "nc-cloud-etat-copie-@C@"), "copie refusée")
                    // Un nom de fichier de secrets : pas de « Remettre », son dossier à ouvrir
                    verifier(!vu(corps, "nc-cloud-remettre-@E@") && vu(corps, "nc-cloud-ouvrir-copie-@E@") && !vu(corps, "nc-cloud-ouvrir-copie-@C@"), "copie non remettable")
                    // Le dossier montre « contenu » : le nom d'origine est dit
                    trouver(corps, "nc-cloud-ouvrir-copie-@E@").clic()
                    verifier(CloudEtat.message.indexOf("« contenu »") >= 0 && CloudEtat.message.indexOf(CloudEtat.corbeille.find(x => x.copie === "@E@").nom) >= 0,
                             "nom d'origine : " + CloudEtat.message)
                    // Le dossier d'origine a disparu : « Remettre à la racine »
                    trouver(corps, "nc-cloud-remettre-@C@").clic(); etape = 20; return }
                if (etape === 20) {
                    verifier(CloudEtat.aRacine === "@C@" && vu(corps, "nc-cloud-remettre-racine-@C@"), "Remettre à la racine proposé")
                    trouver(corps, "nc-cloud-remettre-racine-@C@").clic(); etape = 21; return }
                if (etape === 21) {
                    verifier(CloudEtat.aRacine === "" && CloudEtat.corbeille.length === 0, "remis à la racine")
                    // Une nouvelle suppression, pour « Annuler » du bandeau
                    CloudEtat.choisir(CloudEtat.entrees[1]); trouver(corps, "nc-cloud-supprimer-" + F).clic(); confirmer().clic(); etape = 22; return }
                if (etape === 22) {
                    verifier(CloudEtat.dureeAnnuler === 20000, "20 s")
                    trouver(corps, "nc-cloud-annuler-suppression").clic(); etape = 7; return }
                if (etape === 7) {
                    verifier(CloudEtat.annulable === null && CloudEtat.corbeille.length === 0 && !vu(corps, "nc-cloud-corbeille"), "remis : corbeille vide")
                    // Sans clic, le bandeau part seul (durée raccourcie pour le test)
                    CloudEtat.dureeAnnuler = 300
                    CloudEtat.choisir(CloudEtat.entrees[1]); trouver(corps, "nc-cloud-supprimer-" + F).clic(); confirmer().clic(); etape++; return }
                if (etape === 8) { if (CloudEtat.annulable === null) return; etape++; return }
                if (etape === 9) {
                    ticks++; if (CloudEtat.annulable !== null && ticks < 40) return
                    verifier(CloudEtat.annulable === null && !vu(corps, "nc-cloud-annulable"), "bandeau parti seul")
                    console.log("FINI"); Qt.exit(0) }
            } }
        '''.replace("@F@", F).replace("@C@", "c" * 32).replace("@E@", "e" * 32).replace("@A@", "a" * 32), reglages={"CLOUD_JARVIS": "oui"},
           mode_copie="echec", parent_absent=True)
        ouvert = [x for x in j if x.startswith("xdg-open ")]               # le dossier de la copie, en argv, une seule fois
        self.assertEqual(len(ouvert), 1, j)
        self.assertTrue(ouvert[0].endswith("/nc-cloud/corbeille/" + "e" * 32), ouvert)
        j = [x for x in j if not x.startswith("xdg-open ")]
        self.assertEqual(j[3:], [f"--json supprimer --revision=r9 --dossier=root --copie -- {F}", f"--json supprimer --revision=r9 --dossier=root -- {F}",
                                 "--json lister -- root", f"--json supprimer --revision=r9 --dossier=root --copie -- {F}", "--json lister -- root",
                                 "--json corbeille --remettre=" + "c" * 32, "--json corbeille --remettre=" + "c" * 32 + " --racine",
                                 "--json lister -- root", f"--json supprimer --revision=r9 --dossier=root --copie -- {F}", "--json lister -- root",
                                 "--json corbeille --remettre=" + "c" * 32, "--json lister -- root",
                                 f"--json supprimer --revision=r9 --dossier=root --copie -- {F}", "--json lister -- root"])

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

    def test_en_tete_a_420_px_sans_chevauchement(self):
        self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length || !CloudEtat.lu) return
                var corps = fen.contentItem
                var t = trouver(corps, "nc-cloud-titre"), b = trouver(corps, "nc-cloud-boutons-entete")
                function separes() {
                    var a = t.mapToItem(corps, 0, 0), c = b.mapToItem(corps, 0, 0)
                    return a.x + t.implicitWidth <= c.x || a.y + t.height <= c.y
                }
                if (etape === 1) {
                    verifier(vu(corps, "nc-cloud-fichiers"), "4 boutons")
                    verifier(separes() && !trouver(corps, "nc-cloud-entete").serre, "700 px : une ligne")
                    fen.width = 420; etape++; return }
                if (etape === 2) {
                    verifier(separes(), "420 px : titre et boutons séparés")
                    verifier(trouver(corps, "nc-cloud-entete").serre, "420 px : deux lignes")
                    var c = b.mapToItem(corps, 0, 0)
                    verifier(c.x >= 0 && c.x + b.width <= fen.width, "boutons dans la fenêtre")
                    verifier(b.y + b.height <= trouver(corps, "nc-cloud-entete").height, "l'en-tête grandit : rien ne déborde dessous")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"}, fichiers=True)

    def test_texte_glisse_devient_une_note_par_l_entree_standard(self):
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length || !CloudEtat.lu) return
                var corps = fen.contentItem
                if (etape === 1) {
                    verifier(!vu(corps, "nc-cloud-note"), "rien avant le dépôt")
                    verifier(!CloudEtat.recevoirTexte("   "), "texte vide ignoré")
                    verifier(CloudEtat.recevoirTexte("x".repeat(65537)) && CloudEtat.note === "" && vu(corps, "nc-cloud-note-message"), "trop long : refusé")
                    verifier(!vu(corps, "nc-cloud-note-enregistrer"), "pas de bouton pour un refus")
                    verifier(CloudEtat.recevoirTexte("é".repeat(32769)) && CloudEtat.note === "", "64 Kio comptés en octets UTF-8")
                    verifier(CloudEtat.recevoirTexte("Idée secrète\\nmot-de-passe-7Qz"), "texte reçu")
                    etape++; return }
                if (etape === 2) {
                    verifier(trouver(corps, "nc-cloud-note-apercu").text === "Idée secrète\\nmot-de-passe-7Qz", "aperçu")
                    trouver(corps, "nc-cloud-note-enregistrer").clic(); etape++; return }
                if (etape === 3 && !CloudEtat.noteEnCours) {
                    ticks++; if (ticks < 3) return
                    verifier(CloudEtat.note === "" && trouver(corps, "nc-cloud-note-message").text.indexOf("Note enregistrée") === 0, "message")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"})
        self.assertIn("--json note", j)
        self.assertFalse([x for x in j if "secrète" in x or "7Qz" in x], j)                       # jamais dans argv
        self.assertEqual(self.note_recue, "Idée secrète\nmot-de-passe-7Qz")

    def test_recents_ouvrir_effacer_et_ids_surs(self):
        r = [{"id": "a" * 32, "nom": "Rapport final.pdf", "dossier": "d" * 32},
             {"id": "--json", "nom": "piège", "dossier": "root"},                    # id hostile : écarté
             {"id": "b" * 32, "nom": "x", "dossier": "../.."},                        # dossier hostile : écarté
             {"id": "c" * 32, "nom": "<b>gras</b>" + "n" * 60, "dossier": "root"}]
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length || !CloudEtat.lu) return
                var corps = fen.contentItem
                if (etape === 1) {
                    verifier(vu(corps, "nc-cloud-recents") && CloudEtat.recents.length === 2, "deux récents sûrs : " + CloudEtat.recents.length)
                    verifier(trouver(corps, "nc-cloud-recent-0").texte === "Rapport final.pdf", "nom")
                    verifier(trouver(corps, "nc-cloud-recent-1").texte.length === 32, "nom long coupé")
                    trouver(corps, "nc-cloud-recent-0").clic(); etape++; return }
                if (etape === 2) { trouver(corps, "nc-cloud-effacer-recents").clic(); etape++; return }
                if (etape === 3) {
                    verifier(CloudEtat.recents.length === 0 && !vu(corps, "nc-cloud-recents"), "effacés : bande cachée")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"}, recents=r, voir_recents=True)
        self.assertEqual(j[:4], ["--json etat", "--json lister -- root", "--json reprendre", "--json recents"])
        i = j.index("--json ouvrir --dossier=" + "d" * 32 + " -- " + "a" * 32)
        self.assertEqual(j[i + 1], "--json recents")                                   # relue après l'ouverture
        self.assertIn("--json recents --effacer", j)
        self.assertFalse([x for x in j if "piège" in x or "--json ouvrir --dossier=../" in x])

    def test_quota_pour_le_centre_une_fois_par_10_minutes_et_hors_ligne(self):
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (!CloudEtat.associe) return
                if (etape === 0) { CloudEtat.lireQuota(); CloudEtat.lireQuota(); etape++; return }
                if (etape === 1) {
                    if (CloudEtat.quotaTexte === "") return
                    verifier(CloudEtat.quotaTexte === "1 Mo sur 20 Go" && !CloudEtat.quotaVieux, "quota : " + CloudEtat.quotaTexte)
                    CloudEtat.lireQuota()                                     // moins de 10 minutes : rien n'est relu
                    etape = 10; return }
                if (etape === 10) {
                    ticks++; if (ticks < 4) return
                    verifier(!CloudEtat.quotaVieux, "relu avant 10 minutes (le serveur, coupé, aurait échoué)")
                    // 10 minutes plus tard, et le serveur injoignable : la dernière valeur reste, marquée vieille
                    CloudEtat.quotaEssai = Date.now() - 600001; CloudEtat.lireQuota()
                    etape = 2; return }
                if (etape === 2 && CloudEtat.quotaVieux) {
                    verifier(CloudEtat.quotaTexte === "1 Mo sur 20 Go", "dernière valeur gardée")
                    CloudEtat.noterQuota({ used_bytes: 2 * 1048576, quota_bytes: 21474836480 })     // le panneau relit l'état
                    verifier(!CloudEtat.quotaVieux && CloudEtat.quotaTexte === "2 Mo sur 20 Go", "de nouveau à jour")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"}, voir_recents=True, etat_echec_apres=1)
        self.assertEqual(j.count("--json etat"), 2, j)

    def test_recents_eteints_sans_cloud(self):
        j = self.lancer(self.OUVRIR + '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                ticks++; if (ticks < 5) return
                verifier(!vu(fen.contentItem, "nc-cloud-recents"), "rien sans le cloud")
                console.log("FINI"); Qt.exit(0)
            } }
        ''', reglages={"CLOUD_JARVIS": "non"}, recents=[{"id": "a" * 32, "nom": "x", "dossier": "root"}], voir_recents=True)
        self.assertEqual(j, [])

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

    def test_glisser_sans_relacher_ou_page_relue_ne_deplace_rien(self):
        j = self.lancer(self.OUVRIR + '''
            readonly property string f: "nc-cloud-entree-ffffffffffffffffffffffffffffffff"
            readonly property string d: "nc-cloud-entree-dddddddddddddddddddddddddddddddd"
            function glisser(de, vers) {
                souris.mousePress(de, 60, 20); souris.mouseMove(de, 70, 24); souris.mouseMove(de, 90, 30); souris.mouseMove(vers, 12, 12)
            }
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                if (CloudEtat.occupe || CloudEtat.suites.length || !CloudEtat.lu) return
                var corps = fen.contentItem
                if (etape === 1) { glisser(trouver(corps, f), trouver(corps, d)); etape++; return }
                if (etape === 2) {
                    verifier(trouver(corps, "nc-cloud-cible-dddddddddddddddddddddddddddddddd").containsDrag, "au-dessus de Photos")
                    var z = trouver(corps, "nc-cloud-zone-ffffffffffffffffffffffffffffffff")
                    z.visible = false
                    z.visible = true                          // saisie perdue, sans relâchement
                    verifier(!vu(corps, "nc-cloud-fantome"), "glisser annulé")
                    souris.mouseRelease(trouver(corps, d), 12, 12); etape++; return }
                if (etape === 3) { glisser(trouver(corps, f), trouver(corps, d)); etape++; return }
                if (etape === 4) {
                    verifier(vu(corps, "nc-cloud-fantome"), "second glisser")
                    CloudEtat.actualiser()                                          // la page est relue pendant le glisser
                    verifier(!vu(corps, "nc-cloud-fantome") && trouver(corps, "nc-cloud-fantome").entree === null, "annulé à la relecture")
                    etape++; return }
                if (etape === 5) {
                    ticks++; if (ticks < 3) return
                    souris.mouseRelease(trouver(corps, d), 12, 12)
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''', reglages={"CLOUD_JARVIS": "oui"}, features={"entry_move": True, "file_delete": True})
        self.assertFalse([x for x in j if "deplacer" in x], j)

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
