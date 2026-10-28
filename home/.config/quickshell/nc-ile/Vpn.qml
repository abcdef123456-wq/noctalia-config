// Fenêtre VPN « Réseau privé » (Super + Alt + V, ou un clic sur l'indicateur VPN de la pilule : la MÊME fenêtre). Une carte de verre
// centrée, de haut en bas :
//   1. l'en-tête (VpnEntete.qml) : titre, sous-titre, « Fermer », ⚙ vers les réglages VPN ;
//   2. la carte principale (VpnCarte.qml) : état, un tunnel par ligne avec « Déconnecter », IP publique (si demandée), durée, débits,
//      et « Tout déconnecter » ;
//   3. la ligne « Protections » (VpnBarre.qml) : pastille Kill switch (clic : le détail VpnProtections.qml) et « Importer un profil » ;
//   4. les filtres et la recherche (VpnFiltres.qml) ;
//   5. la liste (VpnListe.qml) : pays de Mullvad, profils de NetworkManager, ou la carte d'état d'un fournisseur pas prêt ;
//   6. le pied (VpnPied.qml).
// Tout vient de nc-vpn par VpnEtat.qml (mise à jour sur événements de NetworkManager, jamais en boucle). Rien n'existe fermé :
// la fenêtre n'est créée qu'ouverte (shell.qml, LazyLoader) ; les débits (VpnDebit.qml) ne sont relevés que fenêtre ouverte et
// écran allumé. Échap ferme. Noms en texte brut (Texte.qml) ; pendant un partage d'écran (Partage.qml) les noms, pays, serveurs,
// interfaces et IP sont masqués ou remplacés par « Tunnel N ».
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
    readonly property int rayon: 26
    readonly property int largeurCarte: Math.min(880, Math.round(largeurEcran * 0.92))
    property bool entree: false
    property bool ksDetail: false                 // le détail du kill switch (VpnProtections.qml) est déplié

    function quitter() { vpn.fermer() }
    function importer() { VpnEtat.choisirFichier(); quitter() }
    Component.onCompleted: { entree = true; VpnEtat.panneauOuvert = true }
    Component.onDestruction: VpnEtat.panneauOuvert = false

    MouseArea { anchors.fill: parent; onClicked: vpn.quitter() }          // un clic à côté ferme

    Item {
        id: carte
        x: Math.round((vpn.largeurEcran - width) / 2); y: Math.round((vpn.hauteurEcran - height) * 0.35)
        width: vpn.largeurCarte
        height: Math.min(Math.round(vpn.hauteurEcran * 0.94), contenu.implicitHeight + 48)
        scale: vpn.entree ? 1 : 0.94
        Behavior on scale { enabled: !Reglages.sobre; SpringAnimation { spring: 4; damping: 0.32; epsilon: 0.001 } }
        Keys.onEscapePressed: vpn.quitter()                                // Échap, d'où que vienne le focus (champ de recherche compris)
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
            border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.09)          // contour fin tout autour : la carte tient sans flou
            Rectangle {
                x: 32; width: parent.width - 64; height: 1; y: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: Qt.rgba(1, 1, 1, 0) }
                    GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.16) }
                    GradientStop { position: 1; color: Qt.rgba(1, 1, 1, 0) }
                }
            }
        }
        MouseArea { anchors.fill: parent }                                 // un clic dans la carte ne ferme pas

        // Le focus clavier de départ (quand le champ de recherche ne l'a pas)
        Item { id: clavier; objectName: "nc-vpn-clavier"; anchors.fill: parent; focus: true }

        // Les débits : relevés une fois par seconde, fenêtre ouverte ET écran allumé seulement
        VpnDebit {
            id: debit
            objectName: "nc-vpn-debit"
            actif: VpnEtat.panneauOuvert && Etat.ecranVu
            interfaces: VpnEtat.tunnels.map(t => t.interface).filter(x => x !== "")
        }

        Column {
            id: contenu
            objectName: "nc-vpn-contenu"
            x: 26; y: 24; width: parent.width - 52
            spacing: 14

            VpnEntete { width: parent.width; onFermer: vpn.quitter() }

            // ── NetworkManager absent ──
            Texte {
                objectName: "nc-vpn-indisponible"
                visible: VpnEtat.lu && !VpnEtat.disponible
                width: parent.width; wrapMode: Text.Wrap; secondaire: true
                text: Reglages.t("NetworkManager ne répond pas : les VPN ne peuvent pas être pilotés d'ici.",
                                 "NetworkManager is not responding: VPNs can't be controlled from here.")
            }

            VpnCarte {
                objectName: "nc-vpn-carte"
                width: parent.width
                debitBas: debit.bas; debitHaut: debit.haut; debitMesure: debit.mesure
            }

            VpnBarre {
                objectName: "nc-vpn-barre"
                width: parent.width
                detail: vpn.ksDetail
                onBasculerDetail: vpn.ksDetail = !vpn.ksDetail
                onImporter: vpn.importer()
            }
            // Le détail du kill switch : limites toujours visibles, confirmation avant d'activer
            Rectangle {
                visible: vpn.ksDetail && VpnEtat.disponible && !VpnEtat.masque
                width: parent.width; height: protections.height + 28; radius: 18
                color: Qt.alpha(Couleurs.carte, 0.5)
                border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.08)
                VpnProtections {
                    id: protections
                    objectName: "nc-vpn-protections"
                    x: 18; y: 14; width: parent.width - 36
                    ouvert: vpn.ksDetail
                }
            }

            VpnFiltres {
                id: filtres
                objectName: "nc-vpn-filtres-zone"
                width: parent.width
                visible: VpnEtat.lu
            }
            VpnListe {
                objectName: "nc-vpn-liste-zone"
                width: parent.width
                visible: VpnEtat.lu
                filtre: filtres.filtre
                recherche: filtres.recherche
                maxHauteur: Math.max(170, Math.min(340, Math.round(vpn.hauteurEcran * 0.3)))
            }

            // ── Le dernier message de nc-vpn (texte brut) ──
            Texte {
                objectName: "nc-vpn-erreur"
                visible: VpnEtat.erreur !== ""
                width: parent.width; wrapMode: Text.Wrap; color: Couleurs.orange; font.pixelSize: 12
                text: VpnEtat.erreur
            }

            VpnPied { width: parent.width }
        }
        Component.onCompleted: filtres.donnerFocus()
    }
}
