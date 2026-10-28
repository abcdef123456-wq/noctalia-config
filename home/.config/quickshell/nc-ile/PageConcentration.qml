// Page « Concentration » : tes modes (Travail, Nuit, Jeu… ceux que tu crées), façon iOS. Un clic sur un mode l'active (il applique
// ses choix) ou le désactive (il remet ce qu'il avait changé) ; le curseur à droite ouvre ses réglages (EditeurMode.qml). Aucun mode
// n'existe au départ : trois propositions à créer d'un clic (Travail, Nuit, Jeu) et un champ pour le nom d'un mode à toi. Tout passe
// par Modes.qml puis nc-modes ; rien ne se lance sans clic. Les noms viennent d'un fichier : texte brut (Texte.qml), 24 signes au plus.
import QtQuick

Item {
    id: p
    property string ouvert: ""                  // mode dont l'éditeur est ouvert
    readonly property real hauteur: contenu.implicitHeight
    onHauteurChanged: Etat.annoncerHauteur("concentration", hauteur)
    Component.onCompleted: Etat.annoncerHauteur("concentration", hauteur)
    readonly property var exemples: [
        { id: "travail", nom: Reglages.t("Travail", "Work"), icone: "work" },
        { id: "nuit", nom: Reglages.t("Nuit", "Night"), icone: "bedtime" },
        { id: "jeu", nom: Reglages.t("Jeu", "Gaming"), icone: "sports_esports" }
    ]
    // Une proposition disparaît une fois créée (même nom)
    readonly property var propositions: exemples.filter(x => !Modes.modes.some(m => m.nom === x.nom))
    function creer() {
        var n = nouveau.text.trim()
        if (n === "") return
        Modes.creer(n, "")
        nouveau.text = ""
    }

    Flickable {
        anchors.fill: parent
        contentHeight: contenu.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Column {
            id: contenu
            width: parent.width
            spacing: 10

            Row {
                spacing: 10
                Ico { nom: "psychology"; taille: 24; color: Couleurs.accentClair; anchors.verticalCenter: parent.verticalCenter }
                Texte { text: Reglages.t("Concentration", "Focus"); font.pixelSize: 20; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
            }
            Texte {
                visible: !Modes.aModes
                width: parent.width; wrapMode: Text.WordWrap; secondaire: true; font.pixelSize: 12; elide: Text.ElideNone
                text: Reglages.t("Un mode règle d'un coup Ne pas déranger, le profil d'énergie, le fond du jour ou de la nuit et l'IA des notifications. Aucun n'existe : crée le tien.",
                                 "A mode sets Do Not Disturb, the power profile, the day or night wallpaper and the notification AI in one go. None exists yet: create yours.")
            }

            Repeater {
                model: Modes.modes
                Column {
                    id: ligne
                    required property var modelData
                    objectName: "ligneMode"
                    readonly property bool actif: Modes.actif === modelData.id
                    width: contenu.width; spacing: 8
                    Rectangle {
                        width: parent.width; height: 52; radius: 16
                        color: ligne.actif ? Couleurs.accent : (zone.containsMouse ? Couleurs.gris3 : Couleurs.gris2)
                        Behavior on color { ColorAnimation { duration: 160 } }
                        Ico { x: 14; anchors.verticalCenter: parent.verticalCenter; nom: ligne.modelData.icone; taille: 24
                              color: ligne.actif ? Couleurs.surCouleur : Couleurs.texte }
                        Texte { x: 48; width: parent.width - 48 - 56; anchors.verticalCenter: parent.verticalCenter
                                text: ligne.modelData.nom; font.pixelSize: 14; font.weight: Font.DemiBold
                                color: ligne.actif ? Couleurs.surCouleur : Couleurs.texte }
                        MouseArea {
                            id: zone
                            objectName: "activerMode"
                            anchors.fill: parent; anchors.rightMargin: 52; hoverEnabled: true
                            enabled: !Modes.occupe
                            cursorShape: Qt.PointingHandCursor
                            onClicked: Modes.basculer(ligne.modelData.id)
                            Accessible.role: Accessible.CheckBox
                            Accessible.name: ligne.modelData.nom
                            Accessible.checked: ligne.actif
                        }
                        Ico { anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter; nom: "tune"; taille: 20
                              color: ligne.actif ? Couleurs.surCouleur : Couleurs.texteSec }
                        MouseArea {
                            objectName: "editerMode"
                            anchors.right: parent.right; width: 52; height: parent.height
                            cursorShape: Qt.PointingHandCursor
                            onClicked: p.ouvert = (p.ouvert === ligne.modelData.id ? "" : ligne.modelData.id)
                            Accessible.role: Accessible.Button
                            Accessible.name: Reglages.t("Réglages du mode ", "Mode settings ") + ligne.modelData.nom
                        }
                    }
                    Loader {
                        width: parent.width
                        active: p.ouvert === ligne.modelData.id
                        visible: active
                        sourceComponent: EditeurMode { mode: ligne.modelData }
                    }
                }
            }

            Flow {
                visible: p.propositions.length > 0
                width: parent.width; spacing: 8
                Repeater {
                    model: p.propositions
                    BoutonEnergie {
                        required property var modelData
                        objectName: "creerExemple"
                        texte: modelData.nom; icone: modelData.icone
                        actif: !Modes.occupe && Modes.modes.length < 12
                        onClic: Modes.creer(modelData.nom, modelData.id)
                    }
                }
            }
            Row {
                spacing: 8
                Rectangle {
                    width: contenu.width - 8 - ajouter.implicitWidth; height: 34; radius: 17; color: Couleurs.gris2
                    border.width: 1; border.color: nouveau.activeFocus ? Couleurs.accent : "transparent"
                    TextInput {
                        id: nouveau
                        objectName: "nouveauMode"
                        anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 14
                        verticalAlignment: TextInput.AlignVCenter
                        clip: true; maximumLength: 24; selectByMouse: true
                        color: Couleurs.texte; selectionColor: Couleurs.accent; font.pixelSize: 13
                        onAccepted: p.creer()
                    }
                    Texte { anchors.fill: parent; anchors.leftMargin: 14; text: Reglages.t("Nom d'un nouveau mode", "New mode name")
                            visible: nouveau.text === "" && !nouveau.activeFocus; secondaire: true; font.pixelSize: 12 }
                }
                BoutonEnergie {
                    id: ajouter
                    objectName: "ajouterMode"
                    texte: Reglages.t("Créer", "Create"); icone: "add"
                    actif: !Modes.occupe && nouveau.text.trim() !== "" && Modes.modes.length < 12
                    onClic: p.creer()
                }
            }
            Texte {
                visible: Modes.message !== ""
                width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: 11; elide: Text.ElideNone; color: Couleurs.orange
                text: Modes.message
            }
            Texte {
                width: parent.width; wrapMode: Text.WordWrap; secondaire: true; font.pixelSize: 10; elide: Text.ElideNone
                text: Reglages.t("Désactiver un mode remet ce qu'il avait changé, sauf ce que tu as modifié toi-même depuis. Rien ne s'applique tout seul.",
                                 "Turning a mode off puts back what it changed, except what you changed yourself since. Nothing applies on its own.")
            }
        }
    }
}
