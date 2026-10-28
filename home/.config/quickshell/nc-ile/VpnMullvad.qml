// Section « Mullvad » du panneau VPN (Vpn.qml) : l'application officielle Mullvad (commande `mullvad`), dont le tunnel est hors de
// NetworkManager. Visible seulement si la commande existe. Connecter, déconnecter et choisir le pays (deux lettres minuscules,
// validées ici et par nc-vpn) passent par nc-vpn (VpnEtat.qml), jamais par un shell. Le numéro de compte n'est jamais lu ni
// montré : seulement « connecté au compte » ou non. Pendant un partage d'écran, ni pays ni relais.
import QtQuick

Column {
    id: m
    visible: VpnEtat.mullvadInstalle
    spacing: 6
    readonly property var e: VpnEtat.mullvad
    readonly property bool libre: VpnEtat.cible === ""
    function drapeau(cc) {
        return /^[A-Z]{2}$/.test(cc) ? String.fromCodePoint(0x1F1E6 + cc.charCodeAt(0) - 65, 0x1F1E6 + cc.charCodeAt(1) - 65) : ""
    }

    Texte { width: parent.width; secondaire: true; font.pixelSize: 12; text: Reglages.t("Mullvad (application)", "Mullvad (app)") }
    Texte {
        objectName: "nc-mullvad-etat"
        width: parent.width; wrapMode: Text.Wrap; font.pixelSize: 13
        text: {
            var t = m.e.connecte ? Reglages.t("Connecté", "Connected") : Reglages.t("Déconnecté", "Disconnected")
            if (m.e.connecte && !VpnEtat.masque && m.e.pays !== "") t += " · " + m.drapeau(m.e.pays) + " " + m.e.pays
            if (m.e.connecte && !VpnEtat.masque && m.e.hote !== "") t += " · " + m.e.hote
            return t
        }
    }
    Texte {
        objectName: "nc-mullvad-compte"
        visible: m.e.compte !== null
        width: parent.width; secondaire: true; font.pixelSize: 11
        text: m.e.compte === true ? Reglages.t("Connecté au compte", "Logged in to an account")
                                  : Reglages.t("Pas connecté au compte : ouvre l'application Mullvad", "Not logged in: open the Mullvad app")
    }
    Row {
        spacing: 8
        Rectangle {
            objectName: "nc-mullvad-bascule"
            width: libelle.implicitWidth + 28; height: 30; radius: 15
            color: zoneBascule.containsMouse ? Qt.alpha(m.e.connecte ? Couleurs.rouge : Couleurs.accent, 0.3) : Qt.alpha(Couleurs.gris3, 0.7)
            opacity: m.libre ? 1 : 0.6
            Texte { id: libelle; anchors.centerIn: parent; font.pixelSize: 12
                    text: m.e.connecte ? Reglages.t("Déconnecter", "Disconnect") : Reglages.t("Connecter", "Connect") }
            MouseArea { id: zoneBascule; anchors.fill: parent; hoverEnabled: true; enabled: m.libre
                        onClicked: m.e.connecte ? VpnEtat.mullvadDeconnecter() : VpnEtat.mullvadConnecter() }
        }
        Rectangle {
            width: 54; height: 30; radius: 15
            color: Qt.alpha(Couleurs.carte, 0.6); border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.1)
            TextInput {
                id: champ
                objectName: "nc-mullvad-pays"
                anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12
                verticalAlignment: TextInput.AlignVCenter
                maximumLength: 2; color: Couleurs.texte; font.pixelSize: 13
                inputMethodHints: Qt.ImhLowercaseOnly | Qt.ImhNoPredictiveText
                validator: RegularExpressionValidator { regularExpression: /^[a-z]{0,2}$/ }
                Keys.onReturnPressed: m.choisir()
            }
            Texte { visible: champ.text === ""; anchors.centerIn: parent; text: "fr"; secondaire: true; font.pixelSize: 12 }
        }
        Rectangle {
            objectName: "nc-mullvad-choisir"
            width: libelleChoix.implicitWidth + 28; height: 30; radius: 15
            color: zoneChoix.containsMouse ? Qt.alpha(Couleurs.accent, 0.25) : Qt.alpha(Couleurs.carte, 0.6)
            opacity: m.libre && /^[a-z]{2}$/.test(champ.text) ? 1 : 0.5
            Texte { id: libelleChoix; anchors.centerIn: parent; font.pixelSize: 12; text: Reglages.t("Choisir le pays", "Set country") }
            MouseArea { id: zoneChoix; anchors.fill: parent; hoverEnabled: true; onClicked: m.choisir() }
        }
    }
    function choisir() { if (libre && /^[a-z]{2}$/.test(champ.text)) VpnEtat.mullvadPays(champ.text) }
}
