// Panneau VPN (Super + Alt + V) : les tunnels VPN et WireGuard que NetworkManager connaît, pilotés depuis l'île. Une carte de
// verre centrée : en haut les tunnels montés (tous, plusieurs à la fois), chacun avec « Déconnecter », et « Tout déconnecter » ;
// dessous les autres connexions (un clic connecte) ; en bas « Importer… » (un .ovpn ou un .conf, par le sélecteur de zenity).
// Tout vient de nc-vpn par VpnEtat.qml (mise à jour sur événements de NetworkManager, jamais en boucle). Rien n'existe fermé :
// la fenêtre n'est créée qu'ouverte (shell.qml, LazyLoader). Échap ferme. Noms de connexions en texte brut (Texte.qml) ; pendant
// un partage d'écran (Partage.qml) les noms, interfaces et IP sont remplacés par « Tunnel N ».
// Verre : flou de Hyprland derrière (règle de calque nc-vpn, regles.lua), fond de la palette à 62 % (92 % sans flou).
import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland

PanelWindow {
    id: vpn
    signal fermer()
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: Hyprland.activeToplevel && Hyprland.activeToplevel.lastIpcObject
                         && (Hyprland.activeToplevel.lastIpcObject.fullscreen || 0) > 0 ? WlrLayer.Overlay : WlrLayer.Top
    WlrLayershell.namespace: "nc-vpn"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    color: "transparent"

    readonly property real largeurEcran: vpn.screen ? vpn.screen.width : 1600
    readonly property real hauteurEcran: vpn.screen ? vpn.screen.height : 1000
    readonly property bool verre: Reglages.val("FENETRES_FLOU", "oui") !== "non" && !Reglages.sobre
    readonly property int rayon: 22
    readonly property int largeurCarte: Math.min(460, Math.round(largeurEcran * 0.9))
    readonly property var autres: VpnEtat.connexions.filter(c => !c.active)
    property bool entree: false

    function quitter() { vpn.fermer() }
    function nomDe(c, i) { return VpnEtat.masque ? Reglages.t("Tunnel ", "Tunnel ") + (i + 1) : c.nom }
    function typeDe(c) { return c.type === "wireguard" ? "WireGuard" : "VPN" }
    function detailDe(c) {
        if (VpnEtat.masque) return typeDe(c)
        return typeDe(c) + (c.active && c.interface ? " · " + c.interface : "")
    }
    function importer() { VpnEtat.choisirFichier(); quitter() }
    Component.onCompleted: { entree = true; VpnEtat.panneauOuvert = true }
    Component.onDestruction: VpnEtat.panneauOuvert = false

    MouseArea { anchors.fill: parent; onClicked: vpn.quitter() }          // un clic à côté ferme

    Item {
        id: carte
        x: Math.round((vpn.largeurEcran - width) / 2); y: Math.round((vpn.hauteurEcran - height) * 0.35)
        width: vpn.largeurCarte
        height: Math.min(Math.round(vpn.hauteurEcran * 0.85), contenu.implicitHeight + 36)
        scale: vpn.entree ? 1 : 0.94
        Behavior on scale { enabled: !Reglages.sobre; SpringAnimation { spring: 4; damping: 0.32; epsilon: 0.001 } }
        Rectangle {
            anchors.fill: fondVerre; anchors.margins: -1.5; radius: fondVerre.radius + 1.5
            visible: Couleurs.aContour
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[0] }
                GradientStop { position: 0.5; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[1] }
                GradientStop { position: 1; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[2] }
            }
        }
        Rectangle {
            id: fondVerre
            anchors.fill: parent; radius: vpn.rayon
            color: Qt.alpha(Couleurs.fond, vpn.verre ? 0.62 : 0.92)
            Rectangle {
                x: 28; width: parent.width - 56; height: 1; y: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: Qt.rgba(1, 1, 1, 0) }
                    GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.16) }
                    GradientStop { position: 1; color: Qt.rgba(1, 1, 1, 0) }
                }
            }
        }
        MouseArea { anchors.fill: parent }                                 // un clic dans la carte ne ferme pas

        // Échap ferme ; le focus clavier reste sur cet élément
        Item {
            id: clavier
            objectName: "nc-vpn-clavier"
            anchors.fill: parent
            focus: true
            Keys.onEscapePressed: vpn.quitter()
        }

        Column {
            id: contenu
            objectName: "nc-vpn-contenu"
            x: 18; y: 18; width: parent.width - 36
            spacing: 10

            // ── Titre ──
            Row {
                spacing: 10; height: 28
                Ico { anchors.verticalCenter: parent.verticalCenter; nom: "shield"; taille: 22; color: VpnEtat.actif ? Couleurs.vert : Couleurs.accent }
                Texte { anchors.verticalCenter: parent.verticalCenter; text: "VPN"; font.pixelSize: 18; font.weight: Font.Bold }
            }

            // ── NetworkManager absent ──
            Texte {
                objectName: "nc-vpn-indisponible"
                visible: VpnEtat.lu && !VpnEtat.disponible
                width: parent.width; wrapMode: Text.Wrap; secondaire: true
                text: Reglages.t("NetworkManager ne répond pas : les VPN ne peuvent pas être pilotés d'ici.",
                                 "NetworkManager isn't responding: VPNs can't be controlled from here.")
            }

            // ── Les tunnels montés ──
            Column {
                objectName: "nc-vpn-actifs"
                visible: VpnEtat.disponible
                width: parent.width; spacing: 6
                Texte {
                    width: parent.width; secondaire: true; font.pixelSize: 12
                    text: VpnEtat.actives.length === 0 ? Reglages.t("Aucun tunnel connecté", "No tunnel connected")
                          : (VpnEtat.actives.length > 1 ? Reglages.t("Connectés", "Connected") : Reglages.t("Connecté", "Connected"))
                }
                Repeater {
                    model: VpnEtat.actives
                    VpnLigne {
                        objectName: "nc-vpn-actif"
                        width: parent.width
                        nom: vpn.nomDe(modelData, index)
                        detail: vpn.detailDe(modelData)
                        monte: true
                        occupe: VpnEtat.cible === modelData.uuid || VpnEtat.cible === "tout"
                        onClic: VpnEtat.deconnecter(modelData.uuid)
                    }
                }
                // IP publique : seulement si tu l'as demandée dans les réglages ; masquée en partage
                Texte {
                    objectName: "nc-vpn-ip"
                    visible: VpnEtat.ip !== "" && !VpnEtat.masque
                    width: parent.width; secondaire: true; font.pixelSize: 12
                    text: Reglages.t("IP publique : ", "Public IP: ") + VpnEtat.ip
                }
                Rectangle {
                    objectName: "nc-vpn-tout"
                    visible: VpnEtat.actives.length > 0
                    width: parent.width; height: 34; radius: 17
                    color: zoneTout.containsMouse ? Qt.alpha(Couleurs.rouge, 0.3) : Qt.alpha(Couleurs.gris3, 0.55)
                    opacity: VpnEtat.cible !== "" ? 0.6 : 1
                    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
                    Texte { anchors.centerIn: parent; text: Reglages.t("Tout déconnecter", "Disconnect all"); font.pixelSize: 13; font.weight: Font.DemiBold }
                    MouseArea { id: zoneTout; anchors.fill: parent; hoverEnabled: true; enabled: VpnEtat.cible === ""; onClicked: VpnEtat.toutDeconnecter() }
                }
            }

            // ── Les autres connexions : un clic connecte ──
            Column {
                objectName: "nc-vpn-autres"
                visible: VpnEtat.disponible && vpn.autres.length > 0
                width: parent.width; spacing: 6
                Texte { width: parent.width; secondaire: true; font.pixelSize: 12; text: Reglages.t("Autres connexions", "Other connections") }
                Repeater {
                    model: vpn.autres
                    VpnLigne {
                        objectName: "nc-vpn-autre"
                        width: parent.width
                        nom: vpn.nomDe(modelData, VpnEtat.actives.length + index)
                        detail: vpn.detailDe(modelData)
                        occupe: VpnEtat.cible === modelData.uuid
                        onClic: VpnEtat.connecter(modelData.uuid)
                    }
                }
            }
            Texte {
                objectName: "nc-vpn-vide"
                visible: VpnEtat.disponible && VpnEtat.connexions.length === 0
                width: parent.width; wrapMode: Text.Wrap; secondaire: true
                text: Reglages.t("Aucune connexion VPN ou WireGuard. Importe un fichier .ovpn ou .conf.",
                                 "No VPN or WireGuard connection. Import an .ovpn or .conf file.")
            }

            // ── Le dernier message de nc-vpn (texte brut) ──
            Texte {
                objectName: "nc-vpn-erreur"
                visible: VpnEtat.erreur !== ""
                width: parent.width; wrapMode: Text.Wrap; color: Couleurs.orange; font.pixelSize: 12
                text: VpnEtat.erreur
            }

            // ── Pied : importer, Échap ──
            Item {
                width: parent.width; height: 32
                visible: VpnEtat.disponible
                Rectangle {
                    objectName: "nc-vpn-importer"
                    anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                    width: importLibelle.implicitWidth + 40; height: 30; radius: 15
                    color: zoneImport.containsMouse ? Qt.alpha(Couleurs.accent, 0.25) : Qt.alpha(Couleurs.carte, 0.6)
                    border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.1)
                    Row {
                        anchors.centerIn: parent; spacing: 7
                        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "upload_file"; taille: 16; color: zoneImport.containsMouse ? Couleurs.accent : Couleurs.texteSec }
                        Texte { id: importLibelle; anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Importer…", "Import…"); font.pixelSize: 12 }
                    }
                    MouseArea { id: zoneImport; anchors.fill: parent; hoverEnabled: true; onClicked: vpn.importer() }
                }
                Texte {
                    anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                    text: Reglages.t("Échap pour fermer", "Esc to close"); secondaire: true; font.pixelSize: 11
                }
            }
        }
    }
}
