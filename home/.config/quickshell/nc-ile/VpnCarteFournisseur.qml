// La carte d'état d'un fournisseur qui n'est pas prêt, à la place de sa liste (VpnListe.qml) : « bientôt » (tant que nc-vpn ne
// répond pas), « client absent », « installé, pas de compte » (Proton : bouton « Se connecter au compte »), « se pilote dans son
// application » (Proton sans sa CLI : bouton « Ouvrir Proton VPN », qui lance l'application officielle, rien de caché) et
// « application ouverte » (Proton : la CLI ne tourne pas avec l'application, le message de nc-vpn dit de la fermer). Un message clair, jamais de faux bouton.
// Le modèle est un élément de VpnEtat.fournisseurs : {id, fournisseur, etat: absent | sans_compte | pilote_appli | pret, bientot, pays}.
import QtQuick

Rectangle {
    id: k
    property var modele: ({ fournisseur: "", etat: "absent", bientot: false, peutLogin: false, message: "" })
    readonly property string etatTexte: modele.bientot ? "bientot" : modele.etat
    readonly property string titre: {
        if (modele.bientot) return modele.fournisseur + " · " + Reglages.t("bientôt", "coming soon")
        if (modele.etat === "pilote_appli")
            return modele.fournisseur + " · " + (modele.probleme === "appli_ouverte" ? Reglages.t("application ouverte", "app is open")
                   : (modele.connecte === true ? Reglages.t("connecté", "connected") : Reglages.t("se pilote dans son application", "driven from its app")))
        if (modele.etat === "sans_compte") return modele.fournisseur + " · " + Reglages.t("installé, sans compte", "installed, no account")
        return modele.fournisseur + " · " + Reglages.t("client absent", "client not installed")
    }
    readonly property string message: {
        if (modele.etat === "pilote_appli" && modele.probleme === "appli_ouverte" && typeof modele.message === "string" && modele.message !== "")
            return modele.message                  // l'application est ouverte : la CLI ne peut pas piloter, nc-vpn dit de la fermer
        if (modele.etat === "pilote_appli" && modele.connecte === true)
            return Reglages.t("La connexion est active (voir en haut). Pour changer de pays ou te déconnecter, ouvre l'application " + modele.fournisseur + ".",
                              "The connection is active (see above). To switch country or disconnect, open the " + modele.fournisseur + " app.")
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
    color: Qt.alpha(Qt.tint(Couleurs.fond, Qt.alpha(Couleurs.texte, 0.08)), 0.85)       // un peu plus clair que la page, même sans flou
    border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.09)

    Row {
        id: contenu
        x: 20; y: 18; width: parent.width - 40; spacing: 14
        Ico {
            anchors.top: parent.top
            nom: k.etatTexte === "bientot" ? "schedule" : (k.etatTexte === "sans_compte" ? "person_off" : (k.etatTexte === "pilote_appli" ? "open_in_new" : "download"))
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
            Rectangle {
                objectName: "nc-vpn-fournisseur-ouvrir"
                visible: k.modele.peutLogin === true && k.modele.etat === "pilote_appli" && !k.modele.bientot
                width: libelleOuvrir.implicitWidth + 32; height: 32; radius: 16
                color: zoneOuvrir.containsMouse ? Qt.alpha(Couleurs.accent, 0.4) : Qt.alpha(Couleurs.accent, 0.25)
                opacity: VpnEtat.cible === "" ? 1 : 0.6
                Accessible.role: Accessible.Button
                Accessible.name: libelleOuvrir.text
                Texte { id: libelleOuvrir; anchors.centerIn: parent; text: Reglages.t("Ouvrir " + k.modele.fournisseur, "Open " + k.modele.fournisseur)
                        font.pixelSize: 12; font.weight: Font.DemiBold }
                MouseArea { id: zoneOuvrir; anchors.fill: parent; hoverEnabled: true; enabled: VpnEtat.cible === ""; onClicked: VpnEtat.fournisseurLogin(k.modele.id) }
            }
        }
    }
}
