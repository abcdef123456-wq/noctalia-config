// La ligne « Protections » de la fenêtre VPN : la pastille « Kill switch · actif / inactif / pas installé / inconnu » (l'état RÉEL lu par
// nc-vpn killswitch etat-json, VpnEtat.qml) avec sa courte explication ; un clic sur la pastille ouvre ou ferme le détail
// (VpnProtections.qml : limites, confirmation, « Installer l'assistant… ») ; à droite « Importer un profil » (un .ovpn ou un .conf).
// La pastille et l'explication disparaissent pendant un partage d'écran (comme VpnProtections).
import QtQuick

Item {
    id: b
    property bool detail: false
    signal basculerDetail()
    signal importer()
    height: 34

    readonly property bool montrer: VpnEtat.disponible && !VpnEtat.masque
    readonly property string etat: {
        if (!VpnEtat.ksLu) return ""
        if (!VpnEtat.ksInstalle) return Reglages.t("pas installé", "not installed")
        if (VpnEtat.ksActif === true) return Reglages.t("actif", "on")
        if (VpnEtat.ksActif === false) return Reglages.t("inactif", "off")
        return Reglages.t("inconnu", "unknown")
    }
    readonly property color couleurPoint: !VpnEtat.ksLu || !VpnEtat.ksInstalle ? Couleurs.gris5
                                          : (VpnEtat.ksActif === true ? Couleurs.vert : (VpnEtat.ksActif === false ? Couleurs.gris5 : Couleurs.orange))

    Texte { id: titre; visible: b.montrer; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
            text: Reglages.t("Protections", "Protections"); secondaire: true; font.pixelSize: 12 }
    VpnPastille {
        id: pastilleKs
        objectName: "nc-vpn-ks-pastille"
        visible: b.montrer
        anchors.left: titre.right; anchors.leftMargin: 12; anchors.verticalCenter: parent.verticalCenter
        texte: "Kill switch" + (b.etat !== "" ? " · " + b.etat : "")
        point: b.couleurPoint
        choisi: b.detail
        onClic: b.basculerDetail()
    }
    Texte {
        objectName: "nc-vpn-ks-explication"
        visible: b.montrer
        anchors.left: pastilleKs.right; anchors.leftMargin: 12; anchors.right: boutonImport.left; anchors.rightMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        text: Reglages.t("Bloque tout ce qui sort hors du VPN si le tunnel tombe.", "Blocks everything leaving outside the VPN if the tunnel drops.")
        secondaire: true; font.pixelSize: 12
    }
    Rectangle {
        id: boutonImport
        objectName: "nc-vpn-importer"
        visible: VpnEtat.disponible
        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
        width: importLibelle.implicitWidth + 44; height: 32; radius: 16
        color: zoneImport.containsMouse ? Qt.alpha(Couleurs.accent, 0.25) : Qt.alpha(Couleurs.carte, 0.6)
        border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.1)
        Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
        Accessible.role: Accessible.Button
        Accessible.name: importLibelle.text
        Row {
            anchors.centerIn: parent; spacing: 7
            Ico { anchors.verticalCenter: parent.verticalCenter; nom: "upload_file"; taille: 16; color: zoneImport.containsMouse ? Couleurs.accent : Couleurs.texteSec }
            Texte { id: importLibelle; anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Importer un profil", "Import a profile"); font.pixelSize: 12 }
        }
        MouseArea { id: zoneImport; anchors.fill: parent; hoverEnabled: true; onClicked: b.importer() }
    }
}
