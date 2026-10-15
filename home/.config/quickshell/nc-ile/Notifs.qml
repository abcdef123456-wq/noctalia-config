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
            if (n.concentration && notif.urgency !== NotificationUrgency.Critical) return
            n.banniere = notif
            fin.interval = notif.urgency === NotificationUrgency.Critical ? 12000 : 5500
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
    function fermer(notif) { if (banniere === notif) banniere = null; if (notif) notif.dismiss() }
    function toutEffacer() { banniere = null; var l = liste; for (var i = 0; i < l.length; i++) l[i].dismiss() }

    function icone(notif) {
        if (!notif) return ""
        if (notif.image !== "") return notif.image
        if (notif.appIcon !== "") return notif.appIcon.indexOf("/") >= 0 ? notif.appIcon : Quickshell.iconPath(notif.appIcon, true)
        return Quickshell.iconPath((notif.desktopEntry || notif.appName || "").toLowerCase(), true)
    }
    // « maintenant », « il y a 5 min », sinon l'heure
    function quand(notif, maintenant) {
        var t = heures[notif.id]
        if (!t) return ""
        var m = Math.floor((maintenant - t) / 60000)
        return m < 1 ? "maintenant" : (m < 60 ? "il y a " + m + " min" : Qt.formatTime(new Date(t), "hh:mm"))
    }
}
