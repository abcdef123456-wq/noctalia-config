// Page « Presse-papiers » de l'île (Super + Maj + V) : les 12 derniers textes ou images copiés, le plus récent en
// haut ; un clic les recopie (Ctrl + V pour coller) ; « Effacer » vide l'historique. En mémoire seulement.
import QtQuick
import Quickshell.Widgets

Item {
    id: p
    function defiler(dy) { return defil.defiler(dy) }

    Item {
        id: tete
        width: parent.width; height: 34
        Texte { anchors.verticalCenter: parent.verticalCenter; leftPadding: 4; text: "Presse-papiers"; font.pixelSize: 20; font.weight: Font.Bold }
        Texte {
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            visible: Etat.presse.length > 0
            text: "Effacer"; color: ze.containsMouse ? Couleurs.accentClair : Couleurs.accent
            MouseArea { id: ze; anchors.fill: parent; anchors.margins: -6; hoverEnabled: true; onClicked: Etat.oublierPresse() }
        }
    }

    Defilement {
        id: defil
        anchors.top: tete.bottom; anchors.topMargin: 10; anchors.bottom: parent.bottom
        width: parent.width
        contentHeight: liste.implicitHeight

        Column {
            id: liste
            width: p.width; spacing: 6
            readonly property real voulue: 34 + 10 + implicitHeight
            onVoulueChanged: Etat.annoncerHauteur("presse", voulue)
            Component.onCompleted: Etat.annoncerHauteur("presse", voulue)

            Item {
                visible: Etat.presse.length === 0
                width: parent.width; height: 100
                Column {
                    anchors.centerIn: parent; spacing: 6
                    Ico { anchors.horizontalCenter: parent.horizontalCenter; nom: "content_paste"; taille: 30; color: Couleurs.gris4 }
                    Texte { anchors.horizontalCenter: parent.horizontalCenter; text: "Ce que tu copies apparaîtra ici"; secondaire: true }
                }
            }
            Repeater {
                model: Etat.presse
                Rectangle {
                    id: el
                    required property var modelData
                    required property int index
                    readonly property bool image: modelData.genre === "image"
                    width: liste.width; height: image ? 86 : Math.min(64, txt.implicitHeight + 20); radius: 14
                    color: zone.containsMouse ? Couleurs.carteSurvol : Couleurs.carte
                    property bool copie: false
                    Texte {
                        id: txt
                        visible: !el.image
                        x: 14; y: 10; width: parent.width - 60
                        text: el.image ? "" : el.modelData.texte.replace(/\s+/g, " ").trim()
                        wrapMode: Text.Wrap; maximumLineCount: 2; font.pixelSize: 13
                    }
                    ClippingRectangle {
                        visible: el.image
                        x: 10; y: 8; width: 110; height: 70; radius: 9; color: Couleurs.gris2
                        Image { anchors.fill: parent; source: el.image ? "file://" + el.modelData.chemin : ""; fillMode: Image.PreserveAspectCrop
                                asynchronous: true; sourceSize: Qt.size(220, 140) }
                    }
                    Texte { visible: el.image; x: 132; anchors.verticalCenter: parent.verticalCenter; text: "Image"; secondaire: true }
                    Ico {
                        anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
                        nom: el.copie ? "check" : (el.index === 0 ? "content_paste" : "content_copy"); taille: 17
                        color: el.copie ? Couleurs.vert : Couleurs.texteSec
                    }
                    Timer { id: fin; interval: 1200; onTriggered: el.copie = false }
                    MouseArea { id: zone; anchors.fill: parent; hoverEnabled: true; onClicked: { Etat.recopier(el.modelData); el.copie = true; fin.restart() } }
                }
            }
        }
    }
}
