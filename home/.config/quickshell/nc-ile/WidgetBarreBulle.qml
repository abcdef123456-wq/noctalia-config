import QtQuick
import Quickshell

QtObject {
    id: info
    required property Item barre
    required property Item ancre
    property bool survol: false
    property string texte: ""
    readonly property bool active: survol && texte !== ""
    property bool ouverte: false
    onActiveChanged: {
        if (active) attente.restart()
        else { attente.stop(); ouverte = false }
    }
    property Timer attente: Timer { interval: 500; onTriggered: info.ouverte = true }
    property LazyLoader chargeur: LazyLoader {
        active: info.ouverte && info.ancre.visible
        WidgetBarrePopup {
            barre: info.barre
            ancre: info.ancre
            visible: true
            implicitWidth: Math.min(320, texteBulle.implicitWidth + 18)
            implicitHeight: texteBulle.contentHeight + 12
            Rectangle {
                anchors.fill: parent
                radius: Couleurs.rayon(8, width, height)
                color: Couleurs.carte
                border.color: Couleurs.gris3
                Text {
                    id: texteBulle
                    anchors.fill: parent
                    anchors.leftMargin: 9; anchors.rightMargin: 9
                    anchors.topMargin: 6; anchors.bottomMargin: 6
                    color: Couleurs.texte
                    text: info.texte
                    textFormat: Text.PlainText
                    font.family: info.barre.police
                    font.pixelSize: 12
                    wrapMode: Text.Wrap
                }
            }
        }
    }
}
