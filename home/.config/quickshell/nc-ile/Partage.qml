pragma Singleton
// Partage d'écran discret : pendant qu'on partage son écran (Discord, Meet, Teams…), les bannières de notification ne
// s'affichent plus devant tout le monde ; elles restent dans l'historique (page Notifications).
// Détection sans sondage : l'événement Hyprland « screencast>>ÉTAT,TYPE » (ÉTAT 1 = début, 0 = fin ; TYPE 0 écran,
// 1 fenêtre, 2 zone), lu sur le canal que Quickshell écoute déjà (aucun processus de plus). Hyprland l'envoie pour
// toute capture par un client (portail xdg-desktop-portal-hyprland, grim, wf-recorder, OBS) : au premier cliché copié,
// puis à la fin de la session ou 0,5 s sans nouveau cliché. Chaque session envoie un début et une fin.
// Pas de requête « le partage est-il en cours ? » dans hyprctl : une île relancée en plein partage ne le sait pas
// avant le prochain début (rien n'est silencieux entre-temps).
//   silence    dès le premier début, sans délai : Notifs.qml garde les bulles (retenir) au lieu de les montrer
//   indicateur après 1,5 s de partage continu : « Partage » dans la pilule (Compact.qml), carte dans la page Notifications
//   fin        1 s de grâce après chaque fin (écran fixe : fin puis début au cliché suivant, sans bulle entre les deux), puis :
//              partage de 1,5 s ou plus : tout revient, puis une bulle courte « N reçues pendant le partage » (clic : page Notifications)
//              capture courte (moins de 1,5 s) : la dernière bulle retenue est montrée, sans message
// La Concentration de l'utilisateur n'est jamais touchée : ce silence est un état à part, que Notifs.montrer consulte.
// Le compteur reste en mémoire (un nombre), jamais écrit sur le disque.
// Réglage PARTAGE_DISCRET (nc-reglages) : non = rien de tout ça.
import QtQuick
import Quickshell
import Quickshell.Hyprland

Singleton {
    id: p

    readonly property bool reglage: Reglages.val("PARTAGE_DISCRET", "oui") !== "non"
    property int sessions: 0              // débuts moins fins : début, début, fin ne termine pas le partage
    property bool silence: false          // bulles retenues
    property bool indicateur: false       // partage continu depuis assez longtemps pour s'afficher
    property int compte: 0                // bulles retenues pendant ce partage
    property var retenue: null            // la dernière, pour une capture courte
    property var vues: ({})               // ids déjà comptés : une notification remplacée (replaces_id) ne compte qu'une fois
    property bool seuilEchu: false        // 1,5 s écoulées pendant une pause entre deux sessions : l'indicateur s'allume au début suivant
    property int delaiIndicateur: 1500    // ms ; contre le clignotement d'une simple capture d'écran
    property int delaiFin: 1000           // ms de grâce après toute fin : sur un écran fixe, Hyprland envoie fin (0,5 s sans cliché)
                                          // puis début au cliché suivant ; les bulles ne repartent pas entre les deux
    property int delaiFilet: 86400000     // 24 h : filet si une fin se perdait (ne tourne que pendant un partage). Hyprland n'envoie screencast
                                          // qu'au début et à la fin : un filet court coupait l'indicateur en plein partage long
    signal courteFinie(var notif)
    signal termine(int n)                 // vrai partage fini, n bulles retenues (n > 0)

    Connections {
        target: Hyprland
        function onRawEvent(event) { if (event.name === "screencast") p.evenement(event.data) }
    }

    function evenement(donnee) {
        if (!reglage) return
        if (silence) filet.restart()
        var etat = String(donnee).split(",")[0]
        if (etat === "1") debut()
        else if (etat === "0") fin()
    }
    function debut() {
        sessions++
        grace.stop()
        if (silence) {
            if (seuilEchu) { seuilEchu = false; indicateur = true }
            return
        }
        compte = 0
        retenue = null
        vues = ({})
        silence = true
        seuil.restart()
        filet.restart()
    }
    function fin() {
        if (sessions <= 0) return          // fin sans début (île relancée en plein partage) : ignorée
        sessions--
        if (sessions > 0) return
        grace.restart()          // toujours : terminer() distingue ensuite partage et capture courte
    }
    // Tout revient comme avant ; la Concentration n'a jamais bougé
    function terminer() {
        seuil.stop()
        grace.stop()
        filet.stop()
        var vrai = indicateur, n = compte, derniere = retenue
        sessions = 0
        silence = false
        indicateur = false
        compte = 0
        retenue = null
        vues = ({})
        seuilEchu = false
        if (vrai) { if (n > 0) termine(n) }
        else if (derniere) courteFinie(derniere)
    }
    // Appelée par Notifs.montrer à la place de la bulle
    function retenir(notif) {
        var id = notif && notif.id !== undefined ? String(notif.id) : ""
        if (id === "" || !vues[id]) {
            compte++
            if (id !== "") vues[id] = true
        }
        retenue = notif
    }
    // Texte de la notification de fin (le nombre seulement) ; Notifs.qml l'affiche en bulle courte
    function texteFin(n) {
        return n === 1 ? Reglages.t("1 notification reçue pendant le partage", "1 notification received while sharing")
                             : Reglages.t(n + " notifications reçues pendant le partage", n + " notifications received while sharing")
    }
    // Réglage coupé en plein partage : tout s'arrête sans message
    onReglageChanged: if (!reglage) { indicateur = false; compte = 0; retenue = null; terminer() }

    Timer { id: seuil; interval: p.delaiIndicateur; onTriggered: { if (p.sessions > 0) p.indicateur = true; else p.seuilEchu = true } }
    Timer { id: filet; interval: p.delaiFilet; onTriggered: { p.sessions = 0; p.terminer() } }
    Timer { id: grace; interval: p.delaiFin; onTriggered: p.terminer() }
}
