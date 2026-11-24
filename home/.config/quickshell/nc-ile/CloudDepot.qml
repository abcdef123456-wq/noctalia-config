import QtQuick

CloudCarte {
    id: depot
    objectName: "nc-cloud-depot-carte"
    required property var taille

    Texte { text: Reglages.t("Déposer des fichiers", "Upload files"); font.pixelSize: 17; font.weight: Font.DemiBold }
    CloudBouton {
        objectName: "nc-cloud-importer"
        width: parent.width; icone: "add"
        texte: CloudEtat.choixOuvert ? Reglages.t("Sélecteur ouvert…", "Picker open…") : Reglages.t("Importer des fichiers…", "Import files…")
        enabled: !CloudEtat.choixOuvert && !CloudEtat.deplacement
        onClic: if (enabled) CloudEtat.choisirFichiers()
    }
    Texte {
        objectName: "nc-cloud-choix-erreur"
        visible: CloudEtat.choixErreur !== ""
        width: parent.width; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 12
        text: CloudEtat.choixErreur
    }
    Rectangle {
        width: parent.width; height: Math.max(148, inviteDepot.implicitHeight + 24)
        radius: Couleurs.rayon(18, width, height)
        color: Qt.alpha(Couleurs.accent, zoneDepot.containsDrag ? 0.19 : 0.06)
        border.width: 1; border.color: Qt.alpha(Couleurs.accent, zoneDepot.containsDrag ? 0.75 : 0.25)
        opacity: zoneDepot.enabled ? 1 : 0.55
        Column {
            id: inviteDepot
            anchors.centerIn: parent; width: parent.width - 28; spacing: 9
            Ico { anchors.horizontalCenter: parent.horizontalCenter; nom: "cloud_upload"; taille: 34; color: Couleurs.accent }
            Texte {
                width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; font.weight: Font.DemiBold
                text: zoneDepot.containsDrag ? Reglages.t("Relâche tes fichiers ici", "Drop your files here")
                                            : Reglages.t("Glisse tes fichiers ici", "Drag your files here")
            }
            Texte {
                width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 11
                text: Reglages.t("Jusqu’à " + CloudEtat.maxFichiers + " fichiers · sources conservées",
                                 "Up to " + CloudEtat.maxFichiers + " files · originals kept")
            }
        }
        DropArea {
            id: zoneDepot
            objectName: "nc-cloud-depot-fichiers"
            anchors.fill: parent
            enabled: CloudEtat.actif && CloudEtat.associe && !CloudEtat.deplacement
            onEntered: drag => {
                if ((drag.supportedActions & Qt.CopyAction) && drag.hasUrls
                    && drag.urls.some(u => String(u).startsWith("file:///"))) drag.accept(Qt.CopyAction)
                else drag.accepted = false
            }
            onDropped: drop => {
                if ((drop.supportedActions & Qt.CopyAction) && drop.hasUrls && CloudEtat.recevoir(drop.urls))
                    drop.accept(Qt.CopyAction)
                else drop.accepted = false
            }
        }
    }
    Texte {
        width: parent.width; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 12
        text: Reglages.t("Choisis la destination dans « Mes fichiers », puis envoie ta sélection.",
                         "Choose a destination in “My files”, then upload your selection.")
    }

    Rectangle {
        objectName: "nc-cloud-recus"
        visible: CloudEtat.recus.length > 0
        width: parent.width; height: recus.implicitHeight + 20; radius: Couleurs.rayon(14, width, height)
        color: Couleurs.carte; border.width: 1; border.color: Couleurs.accent
        Column {
            id: recus
            x: 14; y: 10; width: parent.width - 28; spacing: 8
            Texte {
                objectName: "nc-cloud-recus-liste"
                width: parent.width; wrapMode: Text.Wrap
                text: Reglages.t(CloudEtat.recus.length + " fichier(s) reçu(s) :", CloudEtat.recus.length + " file(s) received:")
            }
            // Les chemins et diagnostics s'affichent en entier, même dans la demi-largeur.
            Repeater {
                model: CloudEtat.recus
                Column {
                    required property string modelData
                    required property int index
                    readonly property var ex: CloudEtat.examen[modelData]
                    width: recus.width; spacing: 2
                    Texte {
                        objectName: "nc-cloud-recu-" + index
                        width: parent.width; wrapMode: Text.WrapAnywhere; font.pixelSize: 12
                        text: CloudEtat.court(parent.modelData)
                        color: parent.ex && parent.ex.refus ? Couleurs.rouge : parent.ex && parent.ex.cache ? Couleurs.orange : Couleurs.texte
                    }
                    Texte {
                        objectName: "nc-cloud-recu-info-" + index
                        width: parent.width; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 12
                        text: !parent.ex ? "…" : parent.ex.refus ? Reglages.t("ne partira pas", "won't be sent")
                              : (parent.ex.cache ? Reglages.t("fichier caché · ", "hidden file · ") : "") + depot.taille(parent.ex.taille)
                    }
                }
            }
            Texte {
                visible: CloudEtat.recus.some(f => CloudEtat.examen[f] && CloudEtat.examen[f].refus)
                width: parent.width; wrapMode: Text.Wrap; color: Couleurs.rouge; font.pixelSize: 12
                text: CloudEtat.recus.map(f => CloudEtat.examen[f] && CloudEtat.examen[f].refus).filter(x => !!x).join(" ")
            }
            Texte {
                width: parent.width; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 12
                text: Reglages.t("Vers : ", "To: ") + CloudEtat.chemin[CloudEtat.chemin.length - 1].nom
                      + (CloudEtat.recusRefus !== "" ? " · " + CloudEtat.recusRefus : "")
            }
        }
    }
    CloudBouton {
        objectName: "nc-cloud-envoyer-ici"; width: parent.width; height: 38; principal: true; icone: "upload"
        texte: CloudEtat.recusCaches ? Reglages.t("Envoyer quand même", "Upload anyway") : Reglages.t("Envoyer ici", "Upload here")
        enabled: CloudEtat.examenPret && CloudEtat.aEnvoyer.length > 0
        onClic: if (enabled) CloudEtat.envoyerIci()
    }
    CloudBouton {
        objectName: "nc-cloud-recus-vider"; visible: CloudEtat.recus.length > 0
        texte: Reglages.t("Retirer", "Remove"); onClic: CloudEtat.viderRecus()
    }
    // Une note : un texte glissé sur l'île, en aperçu (texte brut), puis « Enregistrer la note » dans « Notes »
    Rectangle {
        objectName: "nc-cloud-note"
        visible: (CloudEtat.note !== "" || CloudEtat.noteRefus !== "" || CloudEtat.noteMessage !== "")
        width: parent.width; height: colNote.implicitHeight + 20; radius: Couleurs.rayon(14, width, height)
        color: Couleurs.carte; border.width: CloudEtat.note !== "" ? 1 : 0; border.color: Couleurs.accent
        Column {
            id: colNote
            x: 14; y: 10; width: parent.width - 28; spacing: 8
            Texte {
                visible: CloudEtat.note !== ""; width: parent.width; wrapMode: Text.Wrap
                text: Reglages.t("Note pour le dossier « Notes » :", "Note for the “Notes” folder:"); font.weight: Font.DemiBold
            }
            Texte {
                objectName: "nc-cloud-note-apercu"
                visible: CloudEtat.note !== ""
                width: parent.width; wrapMode: Text.Wrap; maximumLineCount: 5; elide: Text.ElideRight; secondaire: true
                text: CloudEtat.note.slice(0, 600)
            }
            Texte {
                objectName: "nc-cloud-note-message"
                visible: CloudEtat.noteRefus !== "" || CloudEtat.noteMessage !== ""
                width: parent.width; wrapMode: Text.Wrap; font.pixelSize: 12
                color: CloudEtat.noteRefus !== "" ? Couleurs.rouge : Couleurs.texteSec
                text: CloudEtat.noteRefus || CloudEtat.noteMessage
            }
            Flow {
                width: parent.width; spacing: 8
                CloudBouton { objectName: "nc-cloud-note-enregistrer"; visible: CloudEtat.note !== ""; principal: true
                              texte: CloudEtat.noteEnCours ? Reglages.t("Enregistrement…", "Saving…") : Reglages.t("Enregistrer la note", "Save note")
                              enabled: !CloudEtat.noteEnCours; onClic: if (enabled) CloudEtat.enregistrerNote() }
                CloudBouton { texte: CloudEtat.note !== "" ? Reglages.t("Retirer", "Remove") : Reglages.t("Fermer", "Close")
                              enabled: !CloudEtat.noteEnCours; onClic: CloudEtat.oublierNote() }
            }
        }
    }
}
