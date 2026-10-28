// La carte d'état d'un fournisseur qui n'est pas prêt, à la place de sa liste (VpnListe.qml) : « bientôt » (Proton, Nord : leurs
// adaptateurs arrivent plus tard), « client absent », « installé, pas de compte ». Un message clair, jamais de faux bouton.
// Le modèle est un élément de VpnEtat.fournisseurs : {id, fournisseur, etat: absent | sans_compte | pret, bientot, pays}.
import QtQuick

Rectangle {
    id: k
    property var modele: ({ fournisseur: "", etat: "absent", bientot: false, peutLogin: false, message: "" })
    readonly property string etatTexte: modele.bientot ? "bientot" : modele.etat
    readonly property string titre: {
        if (modele.bientot) return modele.fournisseur + " · " + Reglages.t("bientôt", "coming soon")
        if (modele.etat === "sans_compte") return modele.fournisseur + " · " + Reglages.t("installé, sans compte", "installed, no account")
        return modele.fournisseur + " · " + Reglages.t("client absent", "client not installed")
    }
    readonly property string message: {
        if (!modele.bientot && typeof modele.message === "string" && modele.message !== "") return modele.message      // le message de nc-vpn, en texte brut
        if (modele.bientot)
            return Reglages.t("La gestion de " + modele.fournisseur + " depuis cette fenêtre arrive bientôt. En attendant, importe un profil WireGuard ou OpenVPN fourni par le service (« Importer un profil ») : il apparaît dans « Profils perso ».",
                              "Managing " + modele.fournisseur + " from this window is coming soon. Meanwhile, bring in a WireGuard or OpenVPN profile from the service (\"Import a profile\"): it shows up in \"My profiles\".")
        if (modele.etat === "sans_compte")
            return Reglages.t("L'application " + modele.fournisseur + " est installée mais pas connectée à un compte. Ouvre-la et connecte ton compte ; l'île ne lit jamais ton numéro de compte.",
                              "The " + modele.fournisseur + " app is installed but not logged in. Open it and log in; the island never reads your account number.")
        return Reglages.t("L'application " + modele.fournisseur + " n'est pas installée. Installe-la avec le gestionnaire de paquets de ta distribution, puis rouvre cette fenêtre.",
                          "The " + modele.fournisseur + " app is not installed. Install it with your distribution's package manager, then reopen this window.")
    }
    height: contenu.implicitHeight + 36; radius: 18
    color: Qt.alpha(Couleurs.carte, 0.5)
    border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.08)

    Row {
        id: contenu
        x: 20; y: 18; width: parent.width - 40; spacing: 14
        Ico {
            anchors.top: parent.top
            nom: k.etatTexte === "bientot" ? "schedule" : (k.etatTexte === "sans_compte" ? "person_off" : "download")
            taille: 26; color: Couleurs.texteSec
        }
        Column {
            width: parent.width - 40; spacing: 4
            Texte { objectName: "nc-vpn-fournisseur-titre"; width: parent.width; text: k.titre; font.pixelSize: 15; font.weight: Font.DemiBold }
            Rectangle {
                objectName: "nc-vpn-fournisseur-login"
                visible: k.modele.peutLogin === true && k.modele.etat === "sans_compte" && !k.modele.bientot
                width: libelleLogin.implicitWidth + 32; height: 32; radius: 16
                color: zoneLogin.containsMouse ? Qt.alpha(Couleurs.accent, 0.4) : Qt.alpha(Couleurs.accent, 0.25)
                opacity: VpnEtat.cible === "" ? 1 : 0.6
                Texte { id: libelleLogin; anchors.centerIn: parent; text: Reglages.t("Se connecter au compte", "Log in to the account"); font.pixelSize: 12; font.weight: Font.DemiBold }
                MouseArea { id: zoneLogin; anchors.fill: parent; hoverEnabled: true; enabled: VpnEtat.cible === ""; onClicked: VpnEtat.fournisseurLogin(k.modele.id) }
            }
            Texte { objectName: "nc-vpn-fournisseur-message"; width: parent.width; text: k.message; wrapMode: Text.Wrap; elide: Text.ElideNone
                    secondaire: true; font.pixelSize: 12 }
        }
    }
}
