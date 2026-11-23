import QtQuick

CloudCarte {
    id: selection
    objectName: "nc-cloud-selection"
    required property var taille
    readonly property var entree: !CloudEtat.deplacement && CloudEtat.selection !== ""
                                 ? CloudEtat.entrees.find(x => x.id === CloudEtat.selection) || null : null
    readonly property var entreeActive: entree || ({ id: "", name: "", kind: "" })
    readonly property bool fichier: entreeActive.kind === "file"
    readonly property bool apercuPret: !fichier && !!CloudEtat.apercu && CloudEtat.apercu.id === entreeActive.id
    property bool confirmer: false
    property bool renommage: false

    // Garder les lignes sous la souris au premier clic, même si les boutons passent sur deux rangées.
    height: Math.max(width < 650 ? 140 : 112, implicitHeight)
    onEntreeActiveChanged: if (!entree || (renommage && nomIdentifiant !== entree.id)
                                      || (confirmer && suppressionIdentifiant !== entree.id)) {
        confirmer = false
        renommage = false
    }
    property string nomIdentifiant: ""
    property string suppressionIdentifiant: ""

    function annuler() {
        if (confirmer) {
            confirmer = false
            CloudEtat.apercu = null
            if (CloudEtat.sansCopie === entreeActive.id) CloudEtat.sansCopie = ""
            return true
        }
        if (renommage) { renommage = false; return true }
        if (CloudEtat.deplacement) { CloudEtat.deplacement = null; return true }
        return false
    }

    Connections {
        target: CloudEtat
        function onRedemander(id) {
            // Après un échec de copie ou un arbre modifié, le serveur n'a rien supprimé : reprendre la question.
            if (!CloudEtat.entrees.some(e => e.id === id)) return
            CloudEtat.selection = id
            selection.suppressionIdentifiant = id
            selection.renommage = false
            selection.confirmer = true
        }
    }

    Texte {
        width: parent.width; height: 26; verticalAlignment: Text.AlignVCenter; elide: Text.ElideMiddle
        font.pixelSize: 16; font.weight: Font.DemiBold
        text: CloudEtat.deplacement ? Reglages.t("Déplacer « " + CloudEtat.deplacement.name + " »", "Move “" + CloudEtat.deplacement.name + "”")
              : selection.entree ? selection.entreeActive.name : Reglages.t("Sélectionne un fichier ou un dossier", "Select a file or folder")
    }
    Texte {
        visible: !selection.entree && !CloudEtat.deplacement
        width: parent.width; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 12
        text: Reglages.t("Un clic affiche les actions. Un double-clic ouvre le fichier ou le dossier.",
                         "Click to show actions. Double-click to open a file or folder.")
    }
    Column {
        objectName: "nc-cloud-deplacement"
        visible: !!CloudEtat.deplacement
        width: parent.width; spacing: 8
        Texte {
            width: parent.width; wrapMode: Text.Wrap
            text: Reglages.t("Va dans le dossier voulu, puis « Déplacer ici ».", "Go to the folder you want, then choose “Move here”.")
        }
        Flow {
            width: parent.width; spacing: 8
            CloudBouton { objectName: "nc-cloud-deplacer-ici"; principal: true; texte: Reglages.t("Déplacer ici", "Move here")
                          enabled: CloudEtat.deplacementPossible && !CloudEtat.occupe; onClic: CloudEtat.deplacerIci() }
            CloudBouton { objectName: "nc-cloud-deplacer-annuler"; texte: Reglages.t("Annuler", "Cancel"); onClic: selection.annuler() }
        }
    }
    Rectangle {
        visible: selection.renommage
        width: Math.min(parent.width, 320); height: 30; radius: Couleurs.rayon(15, width, height); color: Couleurs.gris2
        border.width: 1; border.color: Couleurs.accent
        TextInput {
            id: nouveauNom
            objectName: "nc-cloud-nouveau-nom-" + selection.entreeActive.id
            anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12
            verticalAlignment: TextInput.AlignVCenter; clip: true; selectByMouse: true; maximumLength: 240
            Accessible.name: Reglages.t("Nouveau nom", "New name")
            color: Couleurs.texte; selectionColor: Couleurs.accent; font.pixelSize: 12
            onAccepted: if (valider.enabled) valider.clic()
            Keys.onEscapePressed: selection.annuler()
        }
    }
    Texte {
        objectName: "nc-cloud-question-" + selection.entreeActive.id
        visible: selection.confirmer; width: parent.width; wrapMode: Text.WrapAnywhere
        color: Couleurs.rouge; font.pixelSize: 12; font.weight: Font.DemiBold
        text: selection.fichier && CloudEtat.sansCopie === selection.entreeActive.id
            ? Reglages.t("La copie sur ce PC a échoué. Supprimer « " + selection.entreeActive.name + " » quand même, sans copie ? C'est définitif.",
                         "The copy on this PC failed. Delete “" + selection.entreeActive.name + "” anyway, without a copy? It is permanent.")
              + (CloudEtat.raisonSansCopie !== "" ? " " + CloudEtat.raisonSansCopie : "")
            : selection.fichier && !CloudEtat.copiable(selection.entreeActive)
            ? Reglages.t("« " + selection.entreeActive.name + " » : trop gros pour une copie sur ce PC (plus de 500 Mio) : suppression définitive, toutes ses versions.",
                         "“" + selection.entreeActive.name + "”: too big for a copy on this PC (over 500 MiB): permanent deletion, all its versions.")
            : selection.fichier && selection.entreeActive.sensible === true
            ? Reglages.t("« " + selection.entreeActive.name + " » : supprimé du cloud avec toutes ses versions. Son nom ressemble à un fichier de secrets : il ne pourra pas être remis depuis l'île ; la copie restera 24 h dans ~/.cache/nc-cloud/corbeille.",
                         "“" + selection.entreeActive.name + "”: deleted from the cloud with all its versions. Its name looks like a secrets file: it cannot be put back from the island; the copy stays 24 h in ~/.cache/nc-cloud/corbeille.")
            : selection.fichier
            ? Reglages.t("« " + selection.entreeActive.name + " » : supprimé du cloud avec toutes ses versions. Une copie reste sur ce PC 24 h, pour le remettre.",
                         "“" + selection.entreeActive.name + "”: deleted from the cloud with all its versions. A copy stays on this PC for 24 h, to put it back.")
            : !selection.apercuPret ? Reglages.t("Calcul de ce que la suppression retirerait…", "Working out what the deletion would remove…")
            : Reglages.t("« " + selection.entreeActive.name + " » : " + CloudEtat.apercu.files + " fichier(s), " + CloudEtat.apercu.directories
                         + " dossier(s), " + selection.taille(CloudEtat.apercu.size) + " : suppression définitive, toutes les versions.",
                         "“" + selection.entreeActive.name + "”: " + CloudEtat.apercu.files + " file(s), " + CloudEtat.apercu.directories
                         + " folder(s), " + selection.taille(CloudEtat.apercu.size) + ": permanent deletion, all versions.")
    }
    Flow {
        id: actions
        objectName: "nc-cloud-actions-" + selection.entreeActive.id
        visible: !!selection.entree
        width: parent.width; spacing: 6
        readonly property bool libre: !selection.confirmer && !selection.renommage
        readonly property bool remplacer: selection.fichier && CloudEtat.aRemplacer === selection.entreeActive.id
        CloudBouton { visible: actions.libre; objectName: "nc-cloud-ouvrir-" + selection.entreeActive.id
                      icone: selection.fichier ? "open_in_new" : "folder_open"
                      texte: Reglages.t("Ouvrir", "Open"); enabled: !CloudEtat.occupe
                      onClic: CloudEtat.ouvrirEntree(selection.entree) }
        CloudBouton { visible: actions.libre && selection.fichier && !actions.remplacer
                      objectName: "nc-cloud-telecharger-" + selection.entreeActive.id
                      icone: "download"; texte: Reglages.t("Télécharger", "Download"); enabled: !CloudEtat.occupe
                      onClic: CloudEtat.telecharger(selection.entree, false) }
        CloudBouton { visible: actions.libre && actions.remplacer; objectName: "nc-cloud-remplacer-" + selection.entreeActive.id
                      icone: "download"; texte: Reglages.t("Remplacer", "Replace"); enabled: !CloudEtat.occupe
                      onClic: CloudEtat.telecharger(selection.entree, true) }
        CloudBouton { visible: actions.libre && CloudEtat.peutDeplacer
                      objectName: "nc-cloud-renommer-" + selection.entreeActive.id
                      icone: "edit"; texte: Reglages.t("Renommer", "Rename"); enabled: !CloudEtat.occupe
                      onClic: { selection.nomIdentifiant = selection.entreeActive.id; selection.renommage = true
                                nouveauNom.text = selection.entreeActive.name; nouveauNom.forceActiveFocus(); nouveauNom.selectAll() } }
        CloudBouton { visible: actions.libre && CloudEtat.peutDeplacer
                      objectName: "nc-cloud-deplacer-" + selection.entreeActive.id
                      icone: "drive_file_move"; texte: Reglages.t("Déplacer…", "Move…"); enabled: !CloudEtat.occupe
                      onClic: CloudEtat.commencerDeplacement(selection.entree) }
        CloudBouton { visible: actions.libre && CloudEtat.peutSupprimer(selection.entree)
                      objectName: "nc-cloud-supprimer-" + selection.entreeActive.id
                      icone: "delete"; texte: Reglages.t("Supprimer…", "Delete…"); enabled: !CloudEtat.occupe
                      onClic: { selection.suppressionIdentifiant = selection.entreeActive.id; selection.confirmer = true
                                if (!selection.fichier) CloudEtat.demanderApercu(selection.entree) } }
        CloudBouton { visible: selection.confirmer; danger: true
                      objectName: "nc-cloud-confirmer-" + selection.entreeActive.id
                      texte: selection.fichier && CloudEtat.copiable(selection.entree) && CloudEtat.sansCopie !== selection.entreeActive.id
                             ? Reglages.t("Supprimer", "Delete") : Reglages.t("Supprimer définitivement", "Delete permanently")
                      enabled: selection.confirmer && !CloudEtat.occupe && (selection.fichier || selection.apercuPret)
                      onClic: if (enabled) { selection.confirmer = false; CloudEtat.supprimer(selection.entree) } }
        CloudBouton { visible: selection.confirmer; objectName: "nc-cloud-annuler-" + selection.entreeActive.id
                      texte: Reglages.t("Annuler", "Cancel"); onClic: selection.annuler() }
        CloudBouton { id: valider; visible: selection.renommage; principal: true
                      objectName: "nc-cloud-valider-nom-" + selection.entreeActive.id
                      texte: Reglages.t("Renommer", "Rename")
                      enabled: selection.renommage && !CloudEtat.occupe && nouveauNom.text.trim() !== ""
                      onClic: if (enabled) { selection.renommage = false; CloudEtat.renommer(selection.entree, nouveauNom.text) } }
        CloudBouton { visible: selection.renommage; texte: Reglages.t("Annuler", "Cancel"); onClic: selection.annuler() }
    }
}
