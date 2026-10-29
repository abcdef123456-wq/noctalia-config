// Fenêtre VPN « Réseau privé » (Super + Alt + V, un clic sur l'indicateur VPN de la pilule ou sur la pilule VPN de la barre : la MÊME
// fenêtre). Une VRAIE fenêtre (FloatingWindow), titre « VPN » (stable : les règles de Hyprland la reconnaissent à ce titre exact,
// regles.lua et automatismes.lua), sans focus clavier exclusif : elle apparaît dans l'aperçu des bureaux, Super + Q la ferme
// (signal closed → fermer → shell.qml désactive le LazyLoader ; l'île reste vivante). Une carte de verre, de haut en bas :
//   1. l'en-tête (VpnEntete.qml) : titre, sous-titre, « Fermer », ⚙ vers les réglages VPN ;
//   2. la carte principale (VpnCarte.qml) : état, un tunnel par ligne avec « Déconnecter », IP publique (si demandée), durée, débits,
//      et « Tout déconnecter » ;
//   3. la ligne « Protections » (VpnBarre.qml) : pastille Kill switch (clic : le détail VpnProtections.qml) et « Importer un profil » ;
//   4. les filtres et la recherche (VpnFiltres.qml) ;
//   5. la liste (VpnListe.qml) : pays de Mullvad, profils de NetworkManager, ou la carte d'état d'un fournisseur pas prêt ;
//   6. le pied (VpnPied.qml).
// Tout le contenu défile (Flickable) quand la fenêtre est basse. Tout vient de nc-vpn par VpnEtat.qml (mise à jour sur événements de NetworkManager, jamais en boucle). Rien n'existe fermé :
// la fenêtre n'est créée qu'ouverte (shell.qml, LazyLoader) ; les débits (VpnDebit.qml) ne sont relevés que fenêtre ouverte et
// écran allumé. Échap ferme. Noms en texte brut (Texte.qml) ; pendant un partage d'écran (Partage.qml) les noms, pays, serveurs,
// interfaces et IP sont masqués ou remplacés par « Tunnel N ».
// Verre : fenêtre transparente, flou de Hyprland derrière, fond de la palette à 62 % (92 % sans flou) ; bordure et coins : ceux de
// Hyprland seulement.
import QtQuick
import Quickshell

FloatingWindow {
    id: vpn
    signal fermer()
    title: Reglages.t("VPN", "VPN")                 // le même mot dans les deux langues : la règle de Hyprland vise ce titre exact
    color: "transparent"
    implicitWidth: vpn.largeurCarte
    implicitHeight: Math.min(Math.round(vpn.hauteurEcran * 0.9), contenu.implicitHeight + 48)
    minimumSize: Qt.size(420, 260)
    // Fermeture native (Super + Q, killactive) : la fenêtre n'est plus là, le LazyLoader de shell.qml se désactive
    onClosed: vpn.fermer()
    onVisibleChanged: if (!visible) vpn.fermer()

    readonly property real largeurEcran: vpn.screen ? vpn.screen.width : 1600
    readonly property real hauteurEcran: vpn.screen ? vpn.screen.height : 1000
    readonly property bool verre: Reglages.val("FENETRES_FLOU", "oui") !== "non" && !Reglages.sobre
    readonly property int largeurCarte: Math.min(880, Math.round(largeurEcran * 0.92))
    property bool ksDetail: false                 // le détail du kill switch (VpnProtections.qml) est déplié

    function quitter() { vpn.fermer() }
    function importer() { VpnEtat.choisirFichier(); quitter() }
    // Connexion au compte d'un fournisseur : un terminal ou une application s'ouvre PAR-DESSUS ; cette fenêtre garde tout le clavier
    // (fenêtre au premier plan) et avalerait ce qu'on y tape (nom de compte, mot de passe) : elle se ferme d'abord, comme pour l'import
    function connecterCompte(id) { VpnEtat.fournisseurLogin(id); quitter() }
    // Installer un client absent : le terminal (kitty) s'ouvre PAR-DESSUS, comme pour la connexion au compte, donc la fenêtre se ferme
    // d'abord (le mot de passe de sudo se tape dans le terminal) ; l'état est relu à la fermeture du terminal (VpnEtat.installerClient)
    function installerClient(id) { VpnEtat.installerClient(id); quitter() }
    Component.onCompleted: VpnEtat.panneauOuvert = true
    Component.onDestruction: VpnEtat.panneauOuvert = false

    Item {
        id: carte
        anchors.fill: parent
        Keys.onEscapePressed: vpn.quitter()                                // Échap, d'où que vienne le focus (champ de recherche compris)
        // Un seul fond, plein sur toute la surface, sans arrondi ni contour : c'est une vraie fenêtre, Hyprland dessine déjà
        // l'unique bordure et découpe les coins (general:border_size, decoration:rounding). Un contour ou un arrondi ici
        // ferait des coins doubles, comme dans les autres FloatingWindow (Parametres.qml, Jarvis.qml…), qui n'en ont pas
        Rectangle {
            id: fondVerre
            anchors.fill: parent
            color: Qt.alpha(Couleurs.fond, vpn.verre ? 0.62 : 0.92)
        }

        // Le focus clavier de départ (quand le champ de recherche ne l'a pas)
        Item { id: clavier; objectName: "nc-vpn-clavier"; anchors.fill: parent; focus: true }

        // Les débits : relevés une fois par seconde, fenêtre ouverte ET écran allumé seulement
        VpnDebit {
            id: debit
            objectName: "nc-vpn-debit"
            actif: VpnEtat.panneauOuvert && Etat.ecranVu
            interfaces: VpnEtat.tunnels.map(t => t.interface).filter(x => x !== "")
        }

        Flickable {
            id: defile
            objectName: "nc-vpn-defile"
            anchors.fill: parent; anchors.margins: 1
            contentWidth: width; contentHeight: contenu.implicitHeight + 48
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            flickableDirection: Flickable.VerticalFlick
        Column {
            id: contenu
            objectName: "nc-vpn-contenu"
            x: 26; y: 24; width: defile.width - 52
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
                onConnecterCompte: id => vpn.connecterCompte(id)
                onInstallerClient: id => vpn.installerClient(id)
                onOuvrirLien: lien => VpnEtat.ouvrirLien(lien)
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
        }
        Component.onCompleted: filtres.donnerFocus()
    }
}
