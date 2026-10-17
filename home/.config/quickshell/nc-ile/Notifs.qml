pragma Singleton
// Notifications reçues par l'île (à la place de dunst et de celles de Noctalia) : chaque nouvelle notification sort de
// la pilule en bannière quelques secondes (comme sur iPhone), puis reste dans l'historique (page « Notifications »).
// Concentration : plus de bannières (sauf urgentes), l'historique se remplit quand même.
import QtQuick
import Quickshell
import Quickshell.Services.Notifications

Singleton {
    id: n

    // Plus récentes d'abord
    readonly property var liste: serveur.trackedNotifications.values.slice().reverse()
    property var banniere: null
    property var heures: ({})            // id -> heure d'arrivée (ms)
    property bool survol: false          // souris sur la bannière : elle reste

    PersistentProperties {
        id: garde
        reloadableId: "nc-ile-notifs"
        property bool concentration: false
    }
    property alias concentration: garde.concentration
    function basculerConcentration() { garde.concentration = !garde.concentration }

    // Ne pas déranger programmé (nc-reglages : NPD_NUIT, NPD_DEBUT, NPD_FIN) : la concentration s'active au début de la
    // plage et se coupe à la fin ; entre les deux, le bouton du centre de contrôle reste libre
    property bool dansPlage: false
    function minutes(h) { var p = String(h).split(":"); return (parseInt(p[0]) || 0) * 60 + (parseInt(p[1]) || 0) }
    function verifierPlage() {
        var d = new Date(), m = d.getHours() * 60 + d.getMinutes()
        var a = minutes(Reglages.val("NPD_DEBUT", "22:00")), b = minutes(Reglages.val("NPD_FIN", "07:00"))
        var dedans = Reglages.val("NPD_NUIT", "non") === "oui" && (a <= b ? (m >= a && m < b) : (m >= a || m < b))
        if (dedans !== dansPlage) { dansPlage = dedans; garde.concentration = dedans }
    }
    Timer { interval: 30000; repeat: true; running: true; triggeredOnStart: true; onTriggered: n.verifierPlage() }
    Connections { target: Reglages; function onValeursChanged() { n.verifierPlage() } }

    NotificationServer {
        id: serveur
        keepOnReload: true
        actionsSupported: true
        bodySupported: true
        bodyMarkupSupported: false
        imageSupported: true
        persistenceSupported: true
        onNotification: notif => {
            notif.tracked = true
            var h = Object.assign({}, n.heures); h[notif.id] = Date.now(); n.heures = h
            if (notif.lastGeneration) return                // gardée d'avant un rechargement de l'île : déjà vue
            if (n.concentration && notif.urgency !== NotificationUrgency.Critical) return
            // Rangée dans le centre sans bannière (indice « x-nc-discret » : la config affiche déjà une réaction
            // rapide dans la pilule, comme ⚡ Performance, que la bannière cachait)
            if (notif.hints && notif.hints["x-nc-discret"]) return
            // Bannières et leur durée : nc-reglages (ILE_BANNIERES, ILE_BANNIERE_DUREE en secondes)
            if (Reglages.val("ILE_BANNIERES", "oui") === "non" && notif.urgency !== NotificationUrgency.Critical) return
            n.banniere = notif
            fin.interval = notif.urgency === NotificationUrgency.Critical ? 12000
                         : Math.max(2, Math.min(30, parseFloat(Reglages.val("ILE_BANNIERE_DUREE", "5")) || 5)) * 1000
            fin.restart()
        }
    }
    Timer { id: fin; onTriggered: if (n.survol) restart(); else n.banniere = null }
    onSurvolChanged: if (!survol && banniere) fin.restart()

    // Une notification qui disparaît (fermée par l'appli ou par toi) quitte aussi la bannière
    Connections {
        target: n.banniere
        function onClosed() { n.banniere = null }
    }

    // Clic : action par défaut de l'appli (ouvrir le message…), sinon rien ; la notification est ensuite rangée
    function ouvrir(notif) {
        if (!notif) return
        var a = notif.actions.find(x => x.identifier === "default") || (notif.actions.length === 1 ? notif.actions[0] : null)
        if (a) a.invoke()
        if (banniere === notif) banniere = null
        if (!notif.resident) notif.dismiss()
    }
    // Boutons de la notification (Supprimer, Répondre…) : toutes les actions sauf celle du clic (« default »)
    function boutons(notif) { return notif ? notif.actions.filter(a => a.identifier !== "default") : [] }
    function agir(notif, action) {
        if (!notif || !action) return
        action.invoke()
        if (banniere === notif) banniere = null
        if (!notif.resident) notif.dismiss()
    }
    function fermer(notif) { if (banniere === notif) banniere = null; if (notif) notif.dismiss() }
    function toutEffacer() { banniere = null; var l = liste; for (var i = 0; i < l.length; i++) l[i].dismiss() }

    // Image de la notification : d'abord une vraie image de contenu (photo d'un contact, pochette), puis l'icône de
    // l'appli dans le thème (Terminal, Fichiers… dessinés par nc-icones), et seulement en dernier le fichier fourni par
    // l'appli (kitty envoie son propre logo, /usr/lib/kitty/logo/kitty.png, qui passait avant le thème)
    function icone(notif) {
        if (!notif) return ""
        var img = notif.image
        // Icône d'appli passée comme chemin (Quickshell la range en « image://icon//usr/… ») : pas une image de contenu
        // … sauf un fichier de ton dossier (capture d'écran…), affiché tel quel
        var fichierPerso = img.startsWith("image://icon//home/") || img.startsWith("image://icon//tmp/")
        var contenu = img !== "" && img !== notif.appIcon && (fichierPerso || (!img.startsWith("image://icon/")
                      && !img.startsWith("/usr/") && !img.startsWith("file:///usr/")))
        if (contenu) return img
        var nom = (notif.desktopEntry || notif.appName || "").toLowerCase()
        var duTheme = nom !== "" ? Quickshell.iconPath(nom, true) : ""
        if (duTheme) return duTheme
        if (notif.appIcon !== "") return notif.appIcon.indexOf("/") >= 0 ? notif.appIcon : Quickshell.iconPath(notif.appIcon, true)
        return img
    }
    // Nom affiché : les mêmes noms simples que dans le lanceur (nc-icones)
    function nomAppli(notif) {
        if (!notif) return ""
        var n = (notif.appName || "").toLowerCase()
        return ({ kitty: "Terminal", "org.gnome.nautilus": "Fichiers", nautilus: "Fichiers", dolphin: "Fichiers" })[n] || notif.appName
    }
    // « maintenant », « il y a 5 min », sinon l'heure
    function quand(notif, maintenant) {
        var t = heures[notif.id]
        if (!t) return ""
        var m = Math.floor((maintenant - t) / 60000)
        return m < 1 ? "maintenant" : (m < 60 ? "il y a " + m + " min" : Qt.formatTime(new Date(t), "hh:mm"))
    }
}
