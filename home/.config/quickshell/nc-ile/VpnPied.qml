// Le pied de la fenêtre VPN : une ligne discrète « Profils NetworkManager et clients installés · Débits mesurés sur le tunnel »,
// plus « · IP via SERVICE » seulement si l'IP publique est activée (VPN_IP_PUBLIQUE=oui avec un service https://) et hors partage
// d'écran. SERVICE est le nom d'hôte du service, jamais l'adresse complète. À droite, « Échap pour fermer ».
import QtQuick

Item {
    id: p
    height: 20
    readonly property string hote: {
        var u = String(Reglages.val("VPN_IP_SERVICE", ""))
        var m = /^https:\/\/([A-Za-z0-9.-]{1,80})(?:[:\/?#]|$)/.exec(u)
        return m ? m[1] : ""
    }
    readonly property bool ipActive: Reglages.val("VPN_IP_PUBLIQUE", "non") === "oui" && hote !== "" && !VpnEtat.masque

    Texte {
        objectName: "nc-vpn-pied"
        anchors.left: parent.left; anchors.right: echap.left; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
        text: Reglages.t("Profils NetworkManager et clients installés · Débits mesurés sur le tunnel", "NetworkManager profiles and installed clients · Speeds measured on the tunnel")
              + (p.ipActive ? " · " + Reglages.t("IP via ", "IP via ") + p.hote : "")
        secondaire: true; font.pixelSize: 11
    }
    Texte { id: echap; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            text: Reglages.t("Échap pour fermer", "Esc to close"); secondaire: true; font.pixelSize: 11 }
}
