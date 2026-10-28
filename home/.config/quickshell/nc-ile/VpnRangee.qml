// Une ligne de la liste VPN (VpnListe.qml) : le nom du pays avec son drapeau, ou du profil ; à droite « fournisseur · protocole » en
// gris et un bouton « Connecter » (ou « Changer » quand un tunnel du même fournisseur est déjà monté). La ligne du pays déjà actif
// montre un point vert et « Connecté » à la place du bouton. Texte brut partout (Texte.qml).
import QtQuick

Rectangle {
    id: r
    property string nom: ""
    property string drapeau: ""
    property string detail: ""                    // « Mullvad · WireGuard »
    property bool actif: false
    property bool changer: false                  // « Changer » au lieu de « Connecter »
    property bool occupe: false
    signal clic()
    height: 46; radius: 15
    color: zone.containsMouse && !actif ? Qt.alpha(Couleurs.accent, 0.16) : Qt.alpha(Couleurs.carte, actif ? 0.8 : 0.5)
    border.width: actif ? 1 : 0; border.color: Qt.alpha(Couleurs.vert, 0.5)
    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
    opacity: occupe ? 0.6 : 1

    Rectangle {
        id: point
        x: 16; anchors.verticalCenter: parent.verticalCenter
        width: 9; height: 9; radius: 5
        color: r.actif ? Couleurs.vert : Qt.alpha(Couleurs.texteSec, 0.5)
    }
    Texte {
        id: nomTexte
        anchors.left: point.right; anchors.leftMargin: 12
        anchors.right: droite.left; anchors.rightMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        text: (r.drapeau !== "" ? r.drapeau + "  " : "") + r.nom
        font.pixelSize: 14; font.weight: Font.DemiBold
    }
    Row {
        id: droite
        anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
        spacing: 12
        Texte { anchors.verticalCenter: parent.verticalCenter; text: r.detail; secondaire: true; font.pixelSize: 12
                width: Math.min(implicitWidth, 220) }
        Rectangle {
            objectName: "nc-vpn-rangee-bouton"
            anchors.verticalCenter: parent.verticalCenter
            visible: !r.actif
            width: libelle.implicitWidth + 28; height: 30; radius: 15
            color: zone.containsMouse ? Qt.alpha(Couleurs.accent, 0.35) : Qt.alpha(Couleurs.gris3, 0.7)
            Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
            Texte { id: libelle; anchors.centerIn: parent; font.pixelSize: 12
                    text: r.occupe ? Reglages.t("En cours…", "Working…") : (r.changer ? Reglages.t("Changer", "Switch") : Reglages.t("Connecter", "Connect")) }
        }
        Texte { objectName: "nc-vpn-rangee-actif"; anchors.verticalCenter: parent.verticalCenter; visible: r.actif
                text: Reglages.t("Connecté", "Connected"); color: Couleurs.vert; font.pixelSize: 12; font.weight: Font.DemiBold }
    }
    MouseArea { id: zone; anchors.fill: parent; hoverEnabled: true; enabled: !r.actif && !r.occupe; onClicked: r.clic() }
}
