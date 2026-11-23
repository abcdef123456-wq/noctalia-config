// Fenêtre « Cloud JARVIS » (IPC `cloud` de shell.qml, recherche de l'île, `nc-cloud fenetre`). Une VRAIE fenêtre
// (FloatingWindow), titre exact « Cloud JARVIS » dans les deux langues : les règles de Hyprland la reconnaissent à ce titre
// (regles.lua, automatismes.lua). Connexion et quota, puis les actions de la sélection et deux cartes :
// navigation à gauche, dépôt à droite. Un double-clic ouvre une entrée ; un glisser la déplace vers un dossier ou ↑.
// Les dépôts (dans la fenêtre, sur l'île ou via le portail) passent tous par l'examen avant confirmation.
// Les appels et la file des envois restent dans CloudEtat.qml ; fermer la fenêtre n'arrête pas les envois lancés.
import QtQuick
import QtQuick.Controls
import Quickshell

FloatingWindow {
    id: cloud
    signal fermer()
    title: Reglages.t("Cloud JARVIS", "Cloud JARVIS")   // le même nom dans les deux langues : la règle de Hyprland vise ce titre exact
    color: "transparent"
    implicitWidth: Math.min(900, Math.round(largeurEcran * 0.92))
    implicitHeight: Math.min(780, Math.round(hauteurEcran * 0.9), entete.y + entete.height + contenu.implicitHeight + 40)
    minimumSize: Qt.size(420, 260)
    onClosed: cloud.fermer()
    onVisibleChanged: if (!visible) cloud.fermer()

    readonly property real largeurEcran: cloud.screen ? cloud.screen.width : 1600
    readonly property real hauteurEcran: cloud.screen ? cloud.screen.height : 1000
    readonly property bool verre: Reglages.val("FENETRES_FLOU", "oui") !== "non" && !Reglages.sobre
    readonly property bool pret: CloudEtat.actif && CloudEtat.associe
    function finirGlisser() {
        if (apercuGlisser.Drag.active) apercuGlisser.Drag.cancel()
        apercuGlisser.Drag.active = false
        apercuGlisser.entree = null
    }
    Component.onCompleted: CloudEtat.panneauOuvert = true
    Component.onDestruction: CloudEtat.panneauOuvert = false

    function taille(n) {
        if (typeof n !== "number") return ""
        var u = ["o", "Kio", "Mio", "Gio", "Tio"], i = 0
        while (n >= 1024 && i < u.length - 1) { n /= 1024; i++ }
        return (i === 0 ? n : n.toFixed(1)) + " " + u[i]
    }

    Item {
        anchors.fill: parent
        focus: true
        Keys.onEscapePressed: if (!selection.annuler()) cloud.fermer()
        // Un seul fond, plein, sans arrondi ni contour : Hyprland dessine la bordure et découpe les coins
        Rectangle { anchors.fill: parent; color: Qt.alpha(Couleurs.fond, cloud.verre ? 0.62 : 0.92) }

        Item {
            id: entete
            objectName: "nc-cloud-entete"
            x: 22; y: 16; width: parent.width - 44; height: 42
            Rectangle {
                id: iconeTitre
                width: 42; height: 42; radius: Couleurs.rayon(14, width, height)
                color: Qt.alpha(Couleurs.accent, 0.16)
                Ico { anchors.centerIn: parent; nom: "cloud"; taille: 25; color: Couleurs.accent }
            }
            Texte {
                objectName: "nc-cloud-titre"
                anchors.left: iconeTitre.right; anchors.leftMargin: 10
                anchors.right: fermerBouton.left; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
                text: "Cloud JARVIS"; font.pixelSize: 22; font.weight: Font.Bold; elide: Text.ElideRight
            }
            CloudBouton {
                id: fermerBouton
                objectName: "nc-cloud-fermer"
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                texte: Reglages.t("Fermer", "Close"); onClic: cloud.fermer()
            }
        }

        // L'aperçu sous le pointeur pendant un glisser (Drag interne au panneau : rien ne sort de la fenêtre)
        // La page relue pendant un glisser (Actualiser, autre dossier) : le glisser est annulé
        Connections { target: CloudEtat; function onEntreesChanged() { cloud.finirGlisser() } }
        Rectangle {
            id: apercuGlisser
            objectName: "nc-cloud-fantome"
            property var entree: null
            z: 10
            visible: Drag.active
            width: Math.min(260, nomFantome.implicitWidth + 50); height: 34; radius: Couleurs.rayon(17, width, height)
            color: Couleurs.carteSurvol; border.width: 1; border.color: Couleurs.accent; opacity: 0.94
            Drag.keys: ["nc-cloud-entree"]
            Drag.hotSpot.x: 16; Drag.hotSpot.y: 17
            Ico { x: 12; anchors.verticalCenter: parent.verticalCenter; taille: 16
                  nom: apercuGlisser.entree && apercuGlisser.entree.kind === "file" ? "description" : "folder"; color: Couleurs.accent }
            Texte { id: nomFantome; x: 36; anchors.verticalCenter: parent.verticalCenter; width: Math.min(implicitWidth, 210)
                    elide: Text.ElideMiddle; text: apercuGlisser.entree ? apercuGlisser.entree.name : "" }
        }

        Flickable {
            id: defile
            anchors.top: entete.bottom; anchors.topMargin: 4
            anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
            contentWidth: width; contentHeight: contenu.implicitHeight + 36
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            flickableDirection: Flickable.VerticalFlick
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            Column {
                id: contenu
                objectName: "nc-cloud-contenu"
                x: 26; y: 18; width: defile.width - 52
                spacing: 14

                CloudConnexion { width: parent.width; pret: cloud.pret; taille: cloud.taille }
                Texte {
                    objectName: "nc-cloud-erreur"
                    visible: CloudEtat.erreur !== ""
                    width: parent.width; wrapMode: Text.WrapAnywhere; color: Couleurs.rouge; text: CloudEtat.erreur
                }
                Texte {
                    objectName: "nc-cloud-message"
                    visible: CloudEtat.message !== "" && CloudEtat.erreur === ""
                    width: parent.width; wrapMode: Text.WrapAnywhere; secondaire: true; text: CloudEtat.message
                }
                CloudSelection { id: selection; visible: cloud.pret; width: parent.width; taille: cloud.taille }

                // Juste après une suppression, la copie locale peut être remise pendant 20 s.
                Rectangle {
                    objectName: "nc-cloud-annulable"
                    visible: cloud.pret && CloudEtat.annulable !== null
                    width: parent.width; height: 40; radius: Couleurs.rayon(14, width, height); color: Couleurs.carte
                    Texte { anchors.left: parent.left; anchors.leftMargin: 14; anchors.right: annulerSuppression.left; anchors.rightMargin: 8
                            anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideMiddle
                            text: Reglages.t("Supprimé : ", "Deleted: ") + (CloudEtat.annulable ? CloudEtat.annulable.nom : "") }
                    CloudBouton { id: annulerSuppression; objectName: "nc-cloud-annuler-suppression"
                                  anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter
                                  texte: CloudEtat.annulable && !CloudEtat.annulable.remettable ? Reglages.t("Ouvrir le dossier", "Open the folder")
                                                                                                : Reglages.t("Annuler", "Undo")
                                  principal: true
                                  onClic: if (CloudEtat.annulable) {
                                      if (CloudEtat.annulable.remettable) CloudEtat.remettre(CloudEtat.annulable.copie, false)
                                      else CloudEtat.ouvrirCopie(CloudEtat.annulable.copie, CloudEtat.annulable.nom)
                                  } }
                }

                Flow {
                    id: zones
                    objectName: "nc-cloud-zones"
                    visible: cloud.pret
                    width: parent.width; spacing: 14
                    readonly property bool large: width >= 620
                    readonly property real largeurFichiers: large ? Math.round((width - spacing) * 0.55) : width
                    CloudFichiers {
                        width: zones.largeurFichiers; fantome: apercuGlisser; taille: cloud.taille
                        aRenommer: selection.renommage ? selection.nomIdentifiant : ""
                        onFinirGlisser: cloud.finirGlisser()
                    }
                    CloudDepot {
                        width: zones.large ? zones.width - zones.largeurFichiers - zones.spacing : zones.width
                        taille: cloud.taille
                    }
                }

                Column {
                    objectName: "nc-cloud-envois"
                    visible: cloud.pret && CloudEtat.envois.length > 0
                    width: parent.width; spacing: 6
                    Item {
                        width: parent.width; height: 30
                        Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Envois", "Uploads"); font.weight: Font.DemiBold }
                        Row {
                            anchors.right: parent.right; spacing: 8
                            CloudBouton { objectName: "nc-cloud-envois-annuler"; visible: CloudEtat.envoie; danger: true
                                          texte: Reglages.t("Annuler l'envoi", "Cancel upload"); onClic: CloudEtat.annulerEnvois() }
                            CloudBouton { objectName: "nc-cloud-effacer-termines"; texte: Reglages.t("Effacer les terminés", "Clear finished")
                                          enabled: CloudEtat.envois.some(e => CloudEtat.termines.indexOf(e.etat) >= 0)
                                          onClic: CloudEtat.effacerTermines() }
                        }
                    }
                    Repeater {
                        model: cloud.pret ? CloudEtat.envois : []
                        Rectangle {
                            id: envoi
                            required property var modelData
                            required property int index
                            objectName: "nc-cloud-envoi-" + index
                            width: parent.width; height: colEnvoi.implicitHeight + 16; radius: Couleurs.rayon(12, width, height); color: Couleurs.carte
                            readonly property real part: modelData.taille > 0 ? Math.min(1, modelData.envoye / modelData.taille) : 0
                            Column {
                                id: colEnvoi
                                x: 12; y: 8; width: parent.width - 24; spacing: 6
                                Item {
                                    width: parent.width; height: 20
                                    Texte { width: parent.width - etatEnvoi.implicitWidth - 12; elide: Text.ElideMiddle; text: envoi.modelData.nom }
                                    Texte {
                                        id: etatEnvoi
                                        objectName: "nc-cloud-envoi-etat-" + envoi.index
                                        anchors.right: parent.right; secondaire: true; font.pixelSize: 12
                                        text: ({ attente: Reglages.t("En attente", "Waiting"),
                                                 en_cours: Reglages.t("Envoi… ", "Uploading… ") + Math.round(envoi.part * 100) + " %",
                                                 publie: Reglages.t("Envoyé", "Uploaded"), conflit: Reglages.t("Ce nom existe déjà", "This name already exists"),
                                                 interrompu: Reglages.t("Interrompu", "Interrupted"), annule: Reglages.t("Annulé", "Cancelled"),
                                                 echec: Reglages.t("Échec", "Failed"), refuse: Reglages.t("Refusé", "Refused"),
                                                 inconnu: Reglages.t("À vérifier", "To check") })[envoi.modelData.etat] || ""
                                    }
                                }
                                Rectangle {
                                    visible: envoi.modelData.etat === "en_cours"
                                    width: parent.width; height: 4; radius: Couleurs.rayon(2, width, height); color: Couleurs.gris2
                                    Rectangle { width: parent.width * envoi.part; height: parent.height; radius: Couleurs.rayon(2, width, height); color: Couleurs.accent }
                                }
                                Texte {
                                    visible: ["echec", "refuse", "inconnu"].indexOf(envoi.modelData.etat) >= 0 && envoi.modelData.message !== ""
                                    width: parent.width; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 12; text: envoi.modelData.message
                                }
                                Flow {
                                    visible: envoi.modelData.etat === "conflit" || envoi.modelData.etat === "interrompu"
                                    width: parent.width; spacing: 8
                                    CloudBouton { visible: envoi.modelData.etat === "conflit"; objectName: "nc-cloud-garder-" + envoi.index
                                                  texte: Reglages.t("Conserver les deux", "Keep both"); onClic: CloudEtat.resoudre(envoi.index, "garder") }
                                    CloudBouton { visible: envoi.modelData.etat === "conflit" && !!(envoi.modelData.actuel && envoi.modelData.actuel.revision)
                                                  && envoi.modelData.actuel.kind !== "directory"
                                                  objectName: "nc-cloud-remplacer-envoi-" + envoi.index
                                                  texte: Reglages.t("Remplacer", "Replace"); onClic: CloudEtat.resoudre(envoi.index, "remplacer") }
                                    CloudBouton { visible: envoi.modelData.etat === "conflit"; objectName: "nc-cloud-annuler-envoi-" + envoi.index
                                                  texte: Reglages.t("Annuler", "Cancel"); onClic: CloudEtat.resoudre(envoi.index, "annuler") }
                                    CloudBouton { visible: envoi.modelData.etat === "interrompu"; principal: true; objectName: "nc-cloud-reprendre-" + envoi.index
                                                  texte: Reglages.t("Reprendre / vérifier", "Resume / check"); onClic: CloudEtat.reprendre(envoi.index) }
                                }
                            }
                        }
                    }
                }
                // Récents : les 5 derniers fichiers envoyés ou ouverts par CE PC (liste locale) ; un clic l'ouvre
                Column {
                    objectName: "nc-cloud-recents"
                    visible: cloud.pret && CloudEtat.recents.length > 0
                    width: parent.width; spacing: 6
                    Item {
                        width: parent.width; height: 26
                        Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Récents", "Recent"); secondaire: true; font.pixelSize: 12 }
                        CloudBouton { objectName: "nc-cloud-effacer-recents"; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                      texte: Reglages.t("Effacer les récents", "Clear recent"); enabled: !CloudEtat.occupe
                                      onClic: CloudEtat.effacerRecents() }
                    }
                    Flow {
                        width: parent.width; spacing: 6
                        Repeater {
                            model: CloudEtat.recents
                            CloudBouton {
                                required property var modelData
                                required property int index
                                objectName: "nc-cloud-recent-" + index
                                texte: modelData.nom.length > 32 ? modelData.nom.slice(0, 31) + "…" : modelData.nom
                                enabled: !CloudEtat.occupe
                                onClic: CloudEtat.ouvrirRecent(index)
                            }
                        }
                    }
                }

                // Corbeille locale : tant qu'une copie existe (24 h) ; « Remettre » la redépose au même endroit
                Column {
                    objectName: "nc-cloud-corbeille"
                    visible: cloud.pret && CloudEtat.corbeille.length > 0
                    width: parent.width; spacing: 6
                    Texte { text: Reglages.t("Corbeille locale", "Local trash"); secondaire: true; font.pixelSize: 12 }
                    Texte { width: parent.width; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 11
                            text: Reglages.t("Remis au même endroit, avec un nouvel identifiant : l'historique des versions est perdu.",
                                             "Put back in the same place, with a new identifier: the version history is lost.") }
                    Flow {
                        width: parent.width; spacing: 6
                        Repeater {
                            model: CloudEtat.corbeille
                            Row {
                                id: copieLigne
                                required property var modelData
                                readonly property string court: modelData.nom.length > 28 ? modelData.nom.slice(0, 27) + "…" : modelData.nom
                                spacing: 6
                                // Refusée : le fichier est toujours sur le serveur, la ligne est grisée
                                opacity: modelData.etat === "refuse" ? 0.55 : 1
                                Texte {
                                    visible: copieLigne.modelData.etat !== "supprime" || copieLigne.modelData.abimee
                                    objectName: "nc-cloud-etat-copie-" + copieLigne.modelData.copie
                                    anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.pixelSize: 11
                                    text: copieLigne.court + " : " + (copieLigne.modelData.abimee ? Reglages.t("copie abîmée", "damaged copy")
                                          : copieLigne.modelData.etat === "refuse" ? Reglages.t("non supprimé, le fichier est toujours sur le serveur",
                                                                                                  "not deleted, the file is still on the server")
                                          : Reglages.t("suppression non confirmée", "deletion not confirmed"))
                                }
                                CloudBouton {
                                    visible: copieLigne.modelData.remettable
                                    objectName: "nc-cloud-remettre-" + copieLigne.modelData.copie
                                    texte: Reglages.t("Remettre ", "Put back ") + copieLigne.court
                                    enabled: !CloudEtat.occupe
                                    onClic: CloudEtat.remettre(copieLigne.modelData.copie, false)
                                }
                                // Le dossier d'origine n'existe plus
                                CloudBouton {
                                    visible: copieLigne.modelData.remettable && CloudEtat.aRacine === copieLigne.modelData.copie
                                    objectName: "nc-cloud-remettre-racine-" + copieLigne.modelData.copie
                                    texte: Reglages.t("Remettre à la racine", "Put back at the root")
                                    enabled: !CloudEtat.occupe
                                    onClic: CloudEtat.remettre(copieLigne.modelData.copie, true)
                                }
                                // Un nom de fichier de secrets : pas de remise depuis l'île, la copie est montrée là où elle est
                                CloudBouton {
                                    visible: !copieLigne.modelData.remettable
                                    objectName: "nc-cloud-ouvrir-copie-" + copieLigne.modelData.copie
                                    texte: Reglages.t("Ouvrir le dossier de ", "Open the folder of ") + copieLigne.court
                                    onClic: CloudEtat.ouvrirCopie(copieLigne.modelData.copie, copieLigne.modelData.nom)
                                }
                            }
                        }
                    }
                }

                // Presse-papiers d'un PC à l'autre, à la demande : aperçu, puis confirmation ; un seul texte sur le cloud,
                // retiré quand un autre PC le prend
                Column {
                    objectName: "nc-cloud-presse"
                    visible: cloud.pret
                    width: parent.width; spacing: 6
                    Texte { text: Reglages.t("Presse-papiers", "Clipboard"); secondaire: true; font.pixelSize: 12 }
                    Row {
                        spacing: 6
                        CloudBouton { objectName: "nc-cloud-presse-envoyer"; texte: Reglages.t("Envoyer mon presse-papiers", "Send my clipboard")
                                      enabled: !CloudEtat.occupe && !CloudEtat.presseIndispo; onClic: CloudEtat.presseVoir() }
                        CloudBouton { objectName: "nc-cloud-presse-prendre"; texte: Reglages.t("Prendre celui du cloud", "Take the cloud's")
                                      enabled: !CloudEtat.occupe && !CloudEtat.presseIndispo; onClic: CloudEtat.presseVoirCloud() }
                    }
                    Rectangle {
                        objectName: "nc-cloud-presse-confirmation"
                        visible: CloudEtat.presse !== null
                        width: parent.width; radius: Couleurs.rayon(14, width, height); color: Couleurs.carte
                        height: presseColonne.implicitHeight + 20
                        Column {
                            id: presseColonne
                            x: 10; y: 10; width: parent.width - 20; spacing: 6
                            readonly property var p: CloudEtat.presse || ({ sens: "", caracteres: 0, lignes: 0, caches: 0, retires: 0, apercu: "" })
                            Texte {
                                objectName: "nc-cloud-presse-question"
                                width: parent.width; wrapMode: Text.Wrap; font.pixelSize: 12; font.weight: Font.DemiBold
                                readonly property string compte: presseColonne.p.caracteres + Reglages.t(" caractère(s), ", " character(s), ")
                                                                 + presseColonne.p.lignes + Reglages.t(" ligne(s)", " line(s)")
                                text: (presseColonne.p.sens === "envoi"
                                    ? Reglages.t("Envoyer ce texte au cloud (" + compte + ") ? Rien ne reconnaît un mot de passe : regarde l'aperçu.",
                                                 "Send this text to the cloud (" + compte + ")? Nothing can recognise a password: check the preview.")
                                    : Reglages.t("Copier ce texte dans le presse-papiers de ce PC (" + compte + ") ? Il sera retiré du cloud.",
                                                 "Copy this text to this PC's clipboard (" + compte + ")? It will be removed from the cloud."))
                                      + (presseColonne.p.sens === "prise" && presseColonne.p.lignes > 1
                                         ? Reglages.t(" Plusieurs lignes : collé dans un terminal, ce texte peut lancer des commandes.",
                                                      " Several lines: pasted into a terminal, this text can run commands.") : "")
                                      + (presseColonne.p.caches > 0
                                         ? Reglages.t(" " + presseColonne.p.caches + " caractère(s) au milieu ne sont pas montrés.",
                                                      " " + presseColonne.p.caches + " character(s) in the middle are not shown.") : "")
                                      + (presseColonne.p.retires > 0
                                         ? Reglages.t(" " + presseColonne.p.retires + " caractère(s) invisible(s) retiré(s).",
                                                      " " + presseColonne.p.retires + " invisible character(s) removed.") : "")
                            }
                            Texte { objectName: "nc-cloud-presse-apercu"; width: parent.width; wrapMode: Text.WrapAnywhere
                                    secondaire: true; font.pixelSize: 11; text: presseColonne.p.apercu }   // tout l'aperçu : rien de caché
                            Row {
                                spacing: 6
                                CloudBouton { objectName: "nc-cloud-presse-confirmer"; principal: true
                                              texte: presseColonne.p.sens === "envoi" ? Reglages.t("Envoyer", "Send") : Reglages.t("Copier ici", "Copy here")
                                              onClic: CloudEtat.presseConfirmer() }
                                CloudBouton { objectName: "nc-cloud-presse-annuler"; texte: Reglages.t("Annuler", "Cancel"); onClic: CloudEtat.presseAnnuler() }
                            }
                        }
                    }
                    Texte { objectName: "nc-cloud-presse-message"; visible: CloudEtat.presseMessage !== "" && CloudEtat.presse === null
                            width: parent.width; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 11; text: CloudEtat.presseMessage }
                }

            }
        }
    }
}
