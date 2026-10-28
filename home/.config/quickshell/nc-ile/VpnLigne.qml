// Une ligne du panneau VPN (Vpn.qml) : le nom de la connexion en texte brut, son type et son interface, et un bouton.
// Tunnel monté : un point vert et « Déconnecter ». Tunnel coupé : un clic sur la ligne connecte.
import QtQuick

Rectangle {
    id: ligne
    property string nom: ""
    property string detail: ""
    property bool monte: false
    property bool occupe: false                   // une action est en cours sur cette ligne
    signal clic()                                 // ligne cliquée (connecter) ou bouton (déconnecter)
    height: 44; radius: 14
    color: zone.containsMouse ? Qt.alpha(Couleurs.accent, 0.2) : Qt.alpha(Couleurs.carte, 0.55)
    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
    opacity: occupe ? 0.6 : 1

    Rectangle {
        id: point
        x: 14; anchors.verticalCenter: parent.verticalCenter
        width: 9; height: 9; radius: 5
        color: ligne.monte ? Couleurs.vert : Couleurs.gris4
    }
    Column {
        anchors.left: point.right; anchors.leftMargin: 12
        anchors.right: bouton.visible ? bouton.left : parent.right; anchors.rightMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        spacing: 1
        Texte { width: parent.width; text: ligne.nom; font.pixelSize: 13; font.weight: Font.DemiBold }
        Texte { width: parent.width; text: ligne.occupe ? Reglages.t("En cours…", "Working…") : ligne.detail; secondaire: true; font.pixelSize: 11
                visible: text !== "" }
    }
    MouseArea { id: zone; anchors.fill: parent; hoverEnabled: true; enabled: !ligne.monte && !ligne.occupe; onClicked: ligne.clic() }
    Rectangle {
        id: bouton
        objectName: "nc-vpn-bouton"
        visible: ligne.monte
        anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
        width: libelle.implicitWidth + 24; height: 28; radius: 14
        color: zoneBouton.containsMouse ? Qt.alpha(Couleurs.rouge, 0.3) : Qt.alpha(Couleurs.gris3, 0.7)
        Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
        Texte { id: libelle; anchors.centerIn: parent; text: Reglages.t("Déconnecter", "Disconnect"); font.pixelSize: 12 }
        MouseArea { id: zoneBouton; anchors.fill: parent; hoverEnabled: true; enabled: !ligne.occupe; onClicked: ligne.clic() }
    }
}
