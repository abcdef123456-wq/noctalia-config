// L'en-tête de la fenêtre VPN : grand titre « Réseau privé », sous-titre « VPN · connexions et protection » ; à droite le bouton
// « Fermer » (Échap ferme aussi) et le ⚙ (BoutonReglages) vers la section des réglages VPN (VPN_INDICATEUR, VPN_IP_PUBLIQUE,
// VPN_IP_SERVICE, VPN_KILLSWITCH).
import QtQuick

Item {
    id: e
    signal fermer()
    height: 52

    Column {
        anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
        spacing: 2
        Texte { objectName: "nc-vpn-titre"; text: Reglages.t("Réseau privé", "Private network"); font.pixelSize: 24; font.weight: Font.Bold }
        Texte { objectName: "nc-vpn-sous-titre"; text: Reglages.t("VPN · connexions et protection", "VPN · connections and protection")
                secondaire: true; font.pixelSize: 13 }
    }
    Row {
        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
        spacing: 8
        BoutonReglages {
            objectName: "nc-vpn-reglages"
            anchors.verticalCenter: parent.verticalCenter
            section: "Île"
            onOuvert: e.fermer()
        }
        Rectangle {
            objectName: "nc-vpn-fermer"
            anchors.verticalCenter: parent.verticalCenter
            width: libelleFermer.implicitWidth + 32; height: 30; radius: 15
            color: zoneFermer.containsMouse ? Qt.alpha(Couleurs.accent, 0.25) : Qt.alpha(Couleurs.carte, 0.6)
            border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.1)
            Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
            Accessible.role: Accessible.Button
            Accessible.name: libelleFermer.text
            Texte { id: libelleFermer; anchors.centerIn: parent; text: Reglages.t("Fermer", "Close"); font.pixelSize: 12 }
            MouseArea { id: zoneFermer; anchors.fill: parent; hoverEnabled: true; onClicked: e.fermer() }
        }
    }
}
