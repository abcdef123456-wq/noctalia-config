// Bannière d'une notification : l'île s'étire en bandeau sous la barre (comme sur iPhone).
// Icône ou image de l'appli, nom de l'appli et « maintenant », titre, deux lignes de texte.
// Clic : action de l'appli (ouvrir le message…) ; clic droit : fermer ; souris dessus : la bannière reste.
import QtQuick
import Quickshell.Widgets

Item {
    id: b
    // La dernière notification reste dessinée pendant que la bannière se referme
    property var vue: null
    readonly property var notif: Notifs.banniere
    onNotifChanged: if (notif) vue = notif

    ClippingRectangle {
        id: image
        anchors.left: parent.left; anchors.leftMargin: 16; anchors.verticalCenter: parent.verticalCenter
        width: 42; height: 42; radius: 11
        color: img.status === Image.Ready ? "transparent" : "#2c2c2e"
        Image {
            id: img
            anchors.fill: parent
            source: Notifs.icone(b.vue)
            sourceSize: Qt.size(84, 84)
            fillMode: Image.PreserveAspectCrop
        }
        Ico { anchors.centerIn: parent; nom: "notifications"; taille: 22; visible: img.status !== Image.Ready }
    }

    Column {
        anchors.left: image.right; anchors.leftMargin: 12
        anchors.right: parent.right; anchors.rightMargin: 18
        anchors.verticalCenter: parent.verticalCenter
        spacing: 1
        Item {
            width: parent.width; height: 16
            Texte { text: b.vue ? (b.vue.appName || "") : ""; secondaire: true; font.pixelSize: 12; width: parent.width - 90 }
            Texte {
                anchors.right: parent.right
                text: b.vue ? Notifs.quand(b.vue, Etat.maintenant.getTime()) : ""
                secondaire: true; font.pixelSize: 12
            }
        }
        Texte { width: parent.width; text: b.vue ? b.vue.summary : ""; font.pixelSize: 14; font.weight: Font.DemiBold }
        Texte {
            width: parent.width
            text: b.vue ? b.vue.body.replace(/<[^>]*>/g, "") : ""
            visible: text !== ""
            font.pixelSize: 13; color: "#d1d1d6"
            wrapMode: Text.Wrap; maximumLineCount: 2
        }
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onContainsMouseChanged: Notifs.survol = containsMouse
        onClicked: e => e.button === Qt.RightButton ? Notifs.fermer(b.vue) : Notifs.ouvrir(b.vue)
    }
}
