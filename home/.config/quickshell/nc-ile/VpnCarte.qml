// La carte principale de la fenêtre VPN : un point d'état (vert connecté, gris déconnecté), le titre « Connecté · 🇫🇷 FR · 2 tunnels »
// ou « Déconnecté », une ligne par tunnel RÉELLEMENT monté (NetworkManager et application Mullvad, plusieurs à la fois) avec son
// bouton « Déconnecter », puis les mesures : IP publique (la ligne n'existe que si VPN_IP_PUBLIQUE=oui), durée de connexion, débits
// ↓ ↑. Une valeur absente s'écrit « indisponible ». « Tout déconnecter » (couleur d'alerte) est dans la ligne du titre, à droite ;
// les lignes de tunnel prennent toute la largeur. Pendant un partage d'écran
// (VpnEtat.masque) : noms « Tunnel N », ni pays, ni serveur, ni interface, ni IP.
import QtQuick

Rectangle {
    id: c
    property real debitBas: -1                    // octets/s reçus (VpnDebit.qml), -1 = indisponible
    property real debitHaut: -1
    property bool debitMesure: false              // assez de relevés pour dire « indisponible » au lieu de « … »

    readonly property var tunnels: VpnEtat.tunnels
    readonly property bool monte: tunnels.length > 0
    readonly property bool libre: VpnEtat.cible === ""
    readonly property bool ipLigne: Reglages.val("VPN_IP_PUBLIQUE", "non") === "oui" && !VpnEtat.masque
    readonly property string indispo: Reglages.t("indisponible", "unavailable")

    radius: 22
    height: contenu.implicitHeight + 36
    color: Qt.alpha(Qt.tint(Couleurs.fond, Qt.alpha(Couleurs.texte, 0.08)), 0.85)       // un peu plus clair que la page, même sans flou
    border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.09)

    function titre() {
        if (!monte) return Reglages.t("Déconnecté", "Disconnected")
        var t = Reglages.t("Connecté", "Connected")
        if (!VpnEtat.masque) {
            for (var i = 0; i < tunnels.length; i++)
                if (tunnels[i].pays !== "") { t += " · " + VpnEtat.drapeauDe(tunnels[i].pays) + " " + tunnels[i].pays; break }
        }
        if (tunnels.length > 1) t += " · " + tunnels.length + " " + Reglages.t("tunnels", "tunnels")
        return t
    }
    function nomDe(t, i) {
        if (VpnEtat.masque) return Reglages.t("Tunnel ", "Tunnel ") + (i + 1)
        var n = t.fournisseur !== "" ? t.fournisseur : t.nom
        if (t.pays !== "") n += " · " + VpnEtat.drapeauDe(t.pays) + " " + t.pays
        return n
    }
    function detailDe(t) {
        var etat = Reglages.t("Actif", "Active")
        if (VpnEtat.masque) return etat
        var parts = []
        if (t.serveur !== "" && t.serveur !== t.fournisseur && (t.fournisseur !== "" || t.mullvad)) parts.push(t.serveur)
        parts.push(etat)
        return parts.join(" · ")
    }
    function unite(octets) {
        var u = ["o/s", "Ko/s", "Mo/s", "Go/s"], i = 0, x = octets
        while (x >= 1000 && i < u.length - 1) { x /= 1000; i++ }
        var txt = (i === 0 ? Math.round(x) : (x < 10 ? x.toFixed(1) : Math.round(x))).toString()
        return (Reglages.en ? txt : txt.replace(".", ",")) + " " + u[i]
    }
    function formaterDebit(v) { return v >= 0 ? unite(v) : (debitMesure ? indispo : "…") }
    function duree() {
        var depuis = 0
        for (var i = 0; i < tunnels.length; i++)
            if (tunnels[i].depuis > 0 && (depuis === 0 || tunnels[i].depuis < depuis)) depuis = tunnels[i].depuis
        if (depuis <= 0 || VpnEtat.maintenant <= depuis) return indispo
        var s = Math.floor(VpnEtat.maintenant - depuis)
        var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60
        if (h > 0) return h + " h " + (m < 10 ? "0" : "") + m + " min"
        if (m > 0) return m + " min " + (r < 10 ? "0" : "") + r + " s"
        return r + " s"
    }
    function deconnecter(t) { if (t.externe) VpnEtat.fournisseurDeconnecter(t.externe); else if (t.mullvad) VpnEtat.mullvadDeconnecter(); else VpnEtat.deconnecter(t.uuid) }

    Column {
        id: contenu
        x: 20; y: 18
        width: parent.width - 40
        spacing: 10

        Item {
            id: ligneTitre
            width: parent.width; height: 38
            Row {
                anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                width: parent.width - (boutonTout.visible ? boutonTout.width + 16 : 0)
                spacing: 10
                Rectangle {
                    objectName: "nc-vpn-point"
                    anchors.verticalCenter: parent.verticalCenter
                    width: 12; height: 12; radius: 6
                    color: c.monte ? Couleurs.vert : Couleurs.gris4
                }
                Texte { objectName: "nc-vpn-titre-etat"; anchors.verticalCenter: parent.verticalCenter; text: c.titre(); font.pixelSize: 18; font.weight: Font.Bold
                        width: Math.min(implicitWidth, parent.width - 22) }
            }
            Rectangle {
                id: boutonTout
                objectName: "nc-vpn-tout"
                visible: c.monte
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                width: libelleTout.implicitWidth + 36; height: 38; radius: 19
                color: zoneTout.containsMouse ? Qt.alpha(Couleurs.rouge, 0.34) : Qt.alpha(Couleurs.rouge, 0.18)
                border.width: 1; border.color: Qt.alpha(Couleurs.rouge, 0.45)
                opacity: c.libre ? 1 : 0.6
                Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
                Accessible.role: Accessible.Button
                Accessible.name: libelleTout.text
                Texte { id: libelleTout; anchors.centerIn: parent; text: Reglages.t("Tout déconnecter", "Disconnect all"); color: Couleurs.rouge
                        font.pixelSize: 13; font.weight: Font.DemiBold }
                MouseArea { id: zoneTout; anchors.fill: parent; hoverEnabled: true; enabled: c.libre; onClicked: VpnEtat.toutDeconnecter() }
            }
        }
        Texte {
            objectName: "nc-vpn-aucun"
            visible: !c.monte
            width: parent.width; secondaire: true; font.pixelSize: 12
            text: Reglages.t("Aucun tunnel actif : choisis un pays ou un profil dans la liste.", "No active tunnel: pick a country or a profile from the list.")
        }
        Column {
            objectName: "nc-vpn-actifs"
            visible: c.monte
            width: parent.width; spacing: 6
            Repeater {
                model: c.tunnels
                VpnLigne {
                    objectName: "nc-vpn-actif"
                    width: parent.width
                    nom: c.nomDe(modelData, index)
                    detail: c.detailDe(modelData)
                    monte: true
                    occupe: VpnEtat.cible === modelData.id || VpnEtat.cible === "tout" || (modelData.externe && VpnEtat.cible === "ext:" + modelData.externe) || (modelData.mullvad && VpnEtat.cible === "mullvad")
                    onClic: c.deconnecter(modelData)
                }
            }
        }
        Flow {
            objectName: "nc-vpn-mesures"
            visible: c.monte
            width: parent.width; spacing: 28
            VpnStat { objectName: "nc-vpn-ip"; visible: c.ipLigne; titre: Reglages.t("IP publique", "Public IP")
                      valeur: VpnEtat.ip !== "" ? VpnEtat.ip : c.indispo }
            VpnStat { objectName: "nc-vpn-duree"; titre: Reglages.t("Durée de connexion", "Connected for"); valeur: c.duree() }
            VpnStat { objectName: "nc-vpn-debit-bas"; titre: Reglages.t("Débit ↓", "Download ↓"); valeur: c.formaterDebit(c.debitBas) }
            VpnStat { objectName: "nc-vpn-debit-haut"; titre: Reglages.t("Débit ↑", "Upload ↑"); valeur: c.formaterDebit(c.debitHaut) }
        }
    }
}
