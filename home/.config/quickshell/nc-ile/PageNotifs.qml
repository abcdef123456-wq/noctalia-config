// Page « Notifications » de l'île : l'historique en cartes, comme le centre de notifications de l'iPhone.
// Clic sur une carte : action de l'appli ; croix (au survol) ou clic droit : la retirer ; « Tout effacer ».
import QtQuick
import Quickshell.Widgets

Item {
    id: p
    function defiler(dy) { return defil.defiler(dy) }

    Item {
        id: tete
        width: parent.width; height: 34
        Texte { anchors.verticalCenter: parent.verticalCenter; leftPadding: 4; text: "Notifications"; font.pixelSize: 20; font.weight: Font.Bold }
        Texte {
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            visible: Notifs.liste.length > 0
            text: Reglages.t("Tout effacer", "Clear All"); color: ze.containsMouse ? Couleurs.accentClair : Couleurs.accent
            MouseArea { id: ze; anchors.fill: parent; anchors.margins: -6; hoverEnabled: true; onClicked: Notifs.toutEffacer() }
        }
    }

    Defilement {
        id: defil
        anchors.top: tete.bottom; anchors.topMargin: 10; anchors.bottom: parent.bottom
        width: parent.width
        contentHeight: liste.implicitHeight

        Column {
            id: liste
            width: p.width; spacing: 8
            readonly property real voulue: 34 + 10 + implicitHeight
            onVoulueChanged: Etat.annoncerHauteur("notifications", voulue)
            Component.onCompleted: Etat.annoncerHauteur("notifications", voulue)

            Item {
                visible: Notifs.liste.length === 0
                width: parent.width; height: 110
                Column {
                    anchors.centerIn: parent; spacing: 6
                    Ico { anchors.horizontalCenter: parent.horizontalCenter; nom: Notifs.concentration ? "dark_mode" : "notifications"; taille: 30; color: Couleurs.gris4 }
                    Texte {
                        anchors.horizontalCenter: parent.horizontalCenter; secondaire: true
                        text: Notifs.concentration ? Reglages.t("Concentration activée", "Focus is on") : Reglages.t("Aucune notification", "No Notifications")
                    }
                }
            }

            Repeater {
                model: Notifs.liste
                Rectangle {
                    id: carte
                    required property var modelData
                    width: liste.width
                    height: contenu.implicitHeight + 24
                    radius: 18
                    color: zc.containsMouse ? Couleurs.gris2 : Couleurs.carte
                    Behavior on color { ColorAnimation { duration: 120 } }
                    scale: zc.pressed ? 0.98 : 1
                    Behavior on scale { SpringAnimation { spring: 6; damping: 0.45 } }

                    MouseArea {
                        id: zc
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        onClicked: e => {
                            if (e.button === Qt.RightButton) { Notifs.fermer(carte.modelData); return }
                            Notifs.ouvrir(carte.modelData); Etat.fermer()
                        }
                    }

                    ClippingRectangle {
                        id: ic
                        x: 12; y: 12; width: 34; height: 34; radius: 9
                        color: im.status === Image.Ready ? "transparent" : Couleurs.gris2
                        Image { id: im; anchors.fill: parent; source: Notifs.icone(carte.modelData); sourceSize: Qt.size(68, 68); fillMode: Image.PreserveAspectCrop }
                        Ico { anchors.centerIn: parent; nom: "notifications"; taille: 18; visible: im.status !== Image.Ready }
                    }
                    Column {
                        id: contenu
                        anchors.left: ic.right; anchors.leftMargin: 10; anchors.right: parent.right; anchors.rightMargin: 14
                        y: 12; spacing: 1
                        Item {
                            width: parent.width; height: 16
                            Texte { text: Notifs.nomAppli(carte.modelData); secondaire: true; font.pixelSize: 12; width: parent.width - 100 }
                            Texte {
                                anchors.right: parent.right
                                visible: !zc.containsMouse
                                text: Notifs.quand(carte.modelData, Etat.maintenant.getTime())
                                secondaire: true; font.pixelSize: 12
                            }
                        }
                        Texte { width: parent.width; text: carte.modelData.summary; font.pixelSize: 14; font.weight: Font.DemiBold }
                        Texte {
                            width: parent.width
                            text: carte.modelData.body.replace(/<[^>]*>/g, "")
                            visible: text !== ""
                            font.pixelSize: 13; color: Couleurs.texteDoux
                            wrapMode: Text.Wrap; maximumLineCount: 3
                        }
                        Row {
                            visible: Notifs.boutons(carte.modelData).length > 0
                            topPadding: 8; spacing: 8
                            Repeater {
                                model: Notifs.boutons(carte.modelData)
                                Rectangle {
                                    required property var modelData
                                    width: lbc.implicitWidth + 24; height: 28; radius: 14
                                    color: zbc.pressed ? Couleurs.gris4 : Couleurs.gris3
                                    Texte { id: lbc; anchors.centerIn: parent; text: parent.modelData.text; font.pixelSize: 13; font.weight: Font.DemiBold }
                                    MouseArea { id: zbc; anchors.fill: parent; onClicked: Notifs.agir(carte.modelData, parent.modelData) }
                                }
                            }
                        }
                    }
                    // Croix pour retirer la carte (au survol)
                    Rectangle {
                        anchors.right: parent.right; anchors.rightMargin: 10; y: 9
                        width: 22; height: 22; radius: 11
                        color: zx.containsMouse ? Couleurs.gris4 : Couleurs.gris3
                        visible: zc.containsMouse || zx.containsMouse
                        Ico { anchors.centerIn: parent; nom: "close"; taille: 14; color: Couleurs.texteDoux }
                        MouseArea { id: zx; anchors.fill: parent; hoverEnabled: true; onClicked: Notifs.fermer(carte.modelData) }
                    }
                }
            }
        }
    }
}
