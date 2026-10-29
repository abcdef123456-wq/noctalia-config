// L'en-tête de la fenêtre VPN : grand titre « Réseau privé », sous-titre « VPN · connexions et protection » ; à droite le bouton
// « Fermer » (Échap ferme aussi), le ⚙ (BoutonReglages) vers la section des réglages VPN (VPN_INDICATEUR, VPN_PILULE_BARRE, VPN_MASQUER_TRAY,
// VPN_BOUCLIER_WIFI, VPN_IP_PUBLIQUE, VPN_IP_SERVICE, VPN_KILLSWITCH) et, tant qu'il reste plusieurs indicateurs VPN, « Un seul indicateur » :
// nc-reglages vpn-un-indicateur (en argv) garde la pilule de la barre seule ; chaque réglage reste changeable un par un dans le ⚙.
import QtQuick
import Quickshell

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
    // Les 4 réglages d'affichage valent déjà « un seul indicateur » : le bouton n'a plus rien à faire, il disparaît
    readonly property bool unSeul: Reglages.val("VPN_PILULE_BARRE", "non") === "oui" && Reglages.val("VPN_MASQUER_TRAY", "non") === "oui"
                                   && Reglages.val("VPN_INDICATEUR", "oui") === "non" && Reglages.val("VPN_BOUCLIER_WIFI", "oui") === "non"
    Row {
        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
        spacing: 8
        Rectangle {
            objectName: "nc-vpn-un-indicateur"
            visible: !e.unSeul
            anchors.verticalCenter: parent.verticalCenter
            width: libelleUn.implicitWidth + 32; height: 30; radius: 15
            color: zoneUn.containsMouse ? Qt.alpha(Couleurs.accent, 0.25) : Qt.alpha(Couleurs.carte, 0.6)
            border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.1)
            Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
            Accessible.role: Accessible.Button
            Accessible.name: libelleUn.text
            Texte { id: libelleUn; anchors.centerIn: parent; text: Reglages.t("Un seul indicateur", "Single indicator"); font.pixelSize: 12 }
            MouseArea {
                id: zoneUn; anchors.fill: parent; hoverEnabled: true
                onClicked: Quickshell.execDetached([Quickshell.env("HOME") + "/.local/bin/nc-reglages", "vpn-un-indicateur"])
            }
        }
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
