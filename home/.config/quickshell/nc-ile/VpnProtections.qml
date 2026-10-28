// Détail du kill switch de la fenêtre VPN (Vpn.qml), déplié par un clic sur la pastille « Kill switch » (VpnBarre.qml) : le kill switch, « Bloquer tout hors du VPN ». Réglage VPN_KILLSWITCH (non par
// défaut) ; tout passe par nc-vpn killswitch (VpnEtat.qml), qui appelle l'assistant root facultatif de l'installation. Les limites
// sont montrées en permanence, donc AVANT l'activation, et une confirmation explicite précède chaque activation. Désactiver
// reste possible en un clic, réglage coupé ou non. Rien du tout pendant un partage d'écran (VpnEtat.masque).
import QtQuick

Column {
    id: p
    property bool ouvert: true                    // déplié par la pastille de VpnBarre.qml
    visible: ouvert && VpnEtat.disponible && !VpnEtat.masque
    spacing: 6
    property bool confirmation: false
    readonly property bool pasInstalle: VpnEtat.ksLu && !VpnEtat.ksInstalle           // assistant ou règle sudo absents : ni Couper ni Activer
    readonly property bool actif: VpnEtat.ksActif === true
    readonly property bool inconnu: VpnEtat.ksInstalle && VpnEtat.ksActif === null     // l'assistant ne répond pas : on propose de couper
    readonly property bool coupable: actif || inconnu
    readonly property bool libre: VpnEtat.cible === ""
    // On ne propose d'activer que si le réglage est à oui, l'assistant est là et rien ne s'y oppose ; couper est toujours permis
    readonly property bool activable: VpnEtat.ksVoulu && VpnEtat.ksInstalle && VpnEtat.ksRefus === ""
    onVisibleChanged: if (!visible) confirmation = false
    onActifChanged: confirmation = false

    Texte { width: parent.width; font.pixelSize: 13; font.weight: Font.DemiBold; text: Reglages.t("Kill switch", "Kill switch") }
    Rectangle {
        objectName: "nc-vpn-ks-bascule"
        visible: !p.pasInstalle
        width: parent.width; height: 34; radius: 17
        color: zoneKs.containsMouse ? Qt.alpha(p.actif ? Couleurs.rouge : Couleurs.accent, 0.3) : Qt.alpha(Couleurs.gris3, 0.55)
        opacity: p.libre && (p.coupable || p.activable) ? 1 : 0.5
        Texte { anchors.centerIn: parent; font.pixelSize: 13; font.weight: Font.DemiBold
                text: p.inconnu ? Reglages.t("Couper le kill switch (état inconnu)", "Turn the kill switch off (unknown state)")
                                : (p.actif ? Reglages.t("Actif : ", "On: ") : "") + Reglages.t("Bloquer tout hors du VPN", "Block everything outside the VPN") }
        MouseArea {
            id: zoneKs
            anchors.fill: parent; hoverEnabled: true
            enabled: p.libre && (p.coupable || p.activable)
            onClicked: { if (p.coupable) VpnEtat.killswitchDesactiver(); else p.confirmation = !p.confirmation }
        }
    }
    Texte {
        objectName: "nc-vpn-ks-etat"
        width: parent.width; wrapMode: Text.Wrap; font.pixelSize: 12
        color: p.actif ? Couleurs.accent : (VpnEtat.ksRefus !== "" && VpnEtat.ksVoulu ? Couleurs.orange : Couleurs.texte)
        text: {
            if (p.pasInstalle) return Reglages.t("Pas installé : l'assistant se pose avec ton accord", "Not installed: the helper is set up with your consent")
            if (p.actif) return Reglages.t("Actif : rien ne sort hors du tunnel. Un clic sur l'interrupteur le coupe.",
                                           "On: nothing leaves outside the tunnel. One click on the switch turns it off.")
            if (p.inconnu) return Reglages.t("Inconnu : l'assistant ne répond pas. Un clic sur l'interrupteur tente de le couper.",
                                             "Unknown: the helper isn't answering. One click on the switch tries to turn it off.")
            if (!VpnEtat.ksVoulu) return Reglages.t("Inactif. Coupé dans les réglages (nc-reglages → Île → VPN : kill switch).",
                                                    "Off. Disabled in the settings (nc-settings → Island → VPN: kill switch).")
            if (VpnEtat.ksRefus !== "") return Reglages.t("Refusé : ", "Refused: ") + VpnEtat.ksRefus
            return Reglages.t("Inactif.", "Off.")
        }
    }
    // Pas installé : un seul bouton, qui ouvre une fenêtre de terminal pour l'étape kill switch d'install.sh (jamais en silence)
    Rectangle {
        objectName: "nc-vpn-ks-installer"
        visible: p.pasInstalle
        width: libelleInstaller.implicitWidth + 28; height: 30; radius: 15
        opacity: VpnEtat.installationEnCours ? 0.5 : 1
        color: zoneInstaller.containsMouse ? Qt.alpha(Couleurs.accent, 0.3) : Qt.alpha(Couleurs.gris3, 0.7)
        Texte { id: libelleInstaller; anchors.centerIn: parent; font.pixelSize: 12; font.weight: Font.DemiBold
                text: Reglages.t("Installer l'assistant…", "Install the helper…") }
        MouseArea { id: zoneInstaller; anchors.fill: parent; hoverEnabled: true; enabled: !VpnEtat.installationEnCours
                    onClicked: VpnEtat.installerAssistant() }
    }
    // Les limites, toujours visibles
    Column {
        objectName: "nc-vpn-ks-limites"
        width: parent.width; spacing: 2
        Repeater {
            model: VpnEtat.ksLimites
            Texte { width: p.width; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 11; text: "• " + modelData }
        }
    }
    // Confirmation explicite avant d'activer
    Column {
        objectName: "nc-vpn-ks-confirmation"
        visible: p.confirmation && !p.coupable
        width: parent.width; spacing: 6
        Texte { width: parent.width; wrapMode: Text.Wrap; font.pixelSize: 12
                text: Reglages.t("Bloquer toute sortie de l'ordinateur hors du VPN ? Si le tunnel tombe, plus rien ne sort. Les limites ci-dessus s'appliquent.",
                                 "Block everything leaving this computer outside the VPN? If the tunnel drops, nothing gets out. The limits above apply.") }
        Row {
            spacing: 8
            Rectangle {
                objectName: "nc-vpn-ks-confirmer"
                width: libelleOui.implicitWidth + 28; height: 30; radius: 15
                color: zoneOui.containsMouse ? Qt.alpha(Couleurs.rouge, 0.35) : Qt.alpha(Couleurs.gris3, 0.7)
                Texte { id: libelleOui; anchors.centerIn: parent; font.pixelSize: 12; text: Reglages.t("Oui, bloquer", "Yes, block") }
                MouseArea { id: zoneOui; anchors.fill: parent; hoverEnabled: true; enabled: p.libre
                            onClicked: { p.confirmation = false; VpnEtat.killswitchActiver() } }
            }
            Rectangle {
                objectName: "nc-vpn-ks-annuler"
                width: libelleNon.implicitWidth + 28; height: 30; radius: 15
                color: zoneNon.containsMouse ? Qt.alpha(Couleurs.accent, 0.25) : Qt.alpha(Couleurs.carte, 0.6)
                Texte { id: libelleNon; anchors.centerIn: parent; font.pixelSize: 12; text: Reglages.t("Annuler", "Cancel") }
                MouseArea { id: zoneNon; anchors.fill: parent; hoverEnabled: true; onClicked: p.confirmation = false }
            }
        }
    }
}
