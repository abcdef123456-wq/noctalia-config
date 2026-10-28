pragma Singleton
// Notifications reçues par l'île (à la place de dunst et de celles de Noctalia) : chaque nouvelle notification sort de
// la pilule en bannière quelques secondes (comme sur iPhone), puis reste dans l'historique (page « Notifications »).
// Concentration : plus de bannières (sauf urgentes), l'historique se remplit quand même.
// Écran partagé, mode jeu ou projection (Partage.qml) : plus de bannières du tout, urgentes comprises, sans toucher à la Concentration.
// Lu / non lu (ouverte, répondue ou marquée), report (15 min, 1 h, demain : la notification revient en bannière à
// l'heure dite, même après un redémarrage de l'île), applis masquées (1 h ou toujours : ni bannière ni carte), réponse
// rapide quand l'appli le permet (sendInlineReply). Tout ça est gardé par Memo « notifs ».
import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Services.Notifications

Singleton {
    id: n

    // Plus récentes d'abord, sans les reportées ni les applis masquées, avec les reportées revenues à l'heure (synthétiques)
    readonly property var brutes: serveur.trackedNotifications.values.slice().reverse()
    readonly property var liste: brutes.filter(x => !reports[x.id] && !appliMasquee(x)).concat(revenues)
                                       .sort((a, b) => (heures[b.id] || 0) - (heures[a.id] || 0))
    readonly property int nonLues: liste.filter(x => !lus[x.id]).length
    property var banniere: null
    property var heures: ({})            // id -> heure d'arrivée (ms)
    property bool survol: false          // souris sur la bannière : elle reste
    property var lus: ({})               // id -> true
    property var reports: ({})           // id -> heure de retour (ms) ; la notification est gardée, cachée en attendant
    property var masques: ({})           // appli (nom en minuscules) -> heure de fin (ms), -1 : toujours
    property var attentes: []            // reportées à garder d'une session à l'autre : { id, app, summary, body, image, urgency, due }
    property var revenues: []            // reportées revenues après un redémarrage : objets synthétiques { id, synthetique: true, … }
    property bool pret: false

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
    Timer { interval: 30000; repeat: true; running: true; triggeredOnStart: true; onTriggered: { n.verifierPlage(); n.verifierReports() } }
    Connections { target: Reglages; function onValeursChanged() { n.verifierPlage() } }

    // ── Gardé d'une session à l'autre ──
    Component.onCompleted: Memo.lire("notifs", v => {
        if (v) {
            if (v.masques && typeof v.masques === "object") masques = v.masques
            if (v.lus && typeof v.lus === "object") lus = v.lus
            if (v.heures && typeof v.heures === "object") heures = Object.assign({}, v.heures, heures)
            if (Array.isArray(v.attentes)) attentes = v.attentes.filter(a => a && typeof a.summary === "string" && a.due > 0)
        }
        pret = true
        verifierReports()
    })
    function garder() {
        if (!pret) return
        var ids = {}
        serveur.trackedNotifications.values.forEach(x => ids[x.id] = true)     // la liste du serveur, à jour, pas sa copie liée
        var l = {}, h = {}
        for (let k in lus) if (ids[k]) l[k] = true
        for (let k2 in heures) if (ids[k2]) h[k2] = heures[k2]
        Memo.ecrire("notifs", { masques: masques, lus: l, heures: h, attentes: attentes })
    }

    NotificationServer {
        id: serveur
        keepOnReload: true
        actionsSupported: true
        bodySupported: true
        bodyMarkupSupported: false
        imageSupported: true
        persistenceSupported: true
        inlineReplySupported: true
        onNotification: notif => {
            notif.tracked = true
            var h = Object.assign({}, n.heures); h[notif.id] = Date.now(); n.heures = h
            if (notif.lastGeneration) return                // gardée d'avant un rechargement de l'île : déjà vue
            n.garder()
            if (n.appliMasquee(notif)) return               // appli masquée : ni bannière, ni carte
            if (n.concentration && notif.urgency !== NotificationUrgency.Critical) return
            // Rangée dans le centre sans bannière (indice « x-nc-discret » : la config affiche déjà une réaction
            // rapide dans la pilule, comme ⚡ Performance, que la bannière cachait)
            if (notif.hints && notif.hints["x-nc-discret"]) return
            // Bannières et leur durée : nc-reglages (ILE_BANNIERES, ILE_BANNIERE_DUREE en secondes)
            if (Reglages.val("ILE_BANNIERES", "oui") === "non" && notif.urgency !== NotificationUrgency.Critical) return
            n.montrer(notif)
        }
    }
    // Une notification retirée (par toi ou par l'appli) : son état lu et son heure ne sont plus gardés
    Connections { target: serveur.trackedNotifications; function onValuesChanged() { n.garder() } }
    // Bannières en pause (nc-session, le temps de capturer l'aperçu d'une session : ipc « bannieresPause ») : celle qui
    // est affichée se cache aussitôt, sans animation (Ile.qml), et la plus récente attend la reprise. Reprise
    // automatique au bout de 3 s au plus, si la reprise ne vient pas (nc-session arrêté en pleine capture).
    property bool enPause: false
    property var enAttente: null
    function pauseBannieres(oui) {
        if (oui) {
            if (!enPause) enPause = true                  // d'abord : Ile.qml coupe ses animations avant que la bannière parte
            if (banniere) { enAttente = banniere; banniere = null }
            reprise.restart()
            return
        }
        reprise.stop()
        if (!enPause) return
        enPause = false
        var a = enAttente
        enAttente = null
        if (a && encoreLa(a)) montrer(a)
    }
    // Partage d'écran (Partage.qml) : au début, la bulle affichée et celle qui attendait la reprise disparaissent aussitôt ; à la
    // fin d'une capture courte, la bulle retenue est montrée (si elle est encore là et que la Concentration ne la cache pas).
    // Le réglage Concentration n'est jamais touché.
    Connections {
        target: Partage
        function onRetientChanged() {
            if (!Partage.retient) return
            if (n.enAttente) { Partage.retenir(n.enAttente); n.enAttente = null }
            n.banniere = null
        }
        // Vrai partage fini : une bulle courte avec le nombre seulement ; un clic ouvre la page Notifications
        function onTermine(nombre) {
            if (!n.concentration) n.annonce(Partage.texteFin(nombre))
        }
        // Fin du mode jeu ou de la projection (Ne pas déranger automatique) : le même groupe, avec le nombre seulement
        function onTermineAuto(nombre, raison) {
            if (!n.concentration) n.annonce(Partage.texteFinAuto(nombre, raison))
        }
        function onCourteFinie(notif) {
            if (n.encoreLa(notif) && (!n.concentration || notif.urgency === NotificationUrgency.Critical)) n.montrer(notif)
        }
    }
    function annonce(texte) {
        var id = "p" + Date.now()
        var h = Object.assign({}, heures); h[id] = Date.now(); heures = h
        montrer({ id: id, synthetique: true, page: "notifications", appName: Reglages.t("Île", "Island"), summary: texte, body: "",
                  image: "", appIcon: "", desktopEntry: "", urgency: NotificationUrgency.Normal, actions: [], resident: true,
                  hasInlineReply: false, hints: {} })
    }
    // Toujours là : ni fermée (par toi ou par l'appli), ni reportée, ni son appli masquée entre-temps
    function encoreLa(notif) {
        if (notif.synthetique) return revenues.indexOf(notif) >= 0
        return serveur.trackedNotifications.values.indexOf(notif) >= 0 && !reports[notif.id] && !appliMasquee(notif)
    }
    Timer { id: reprise; interval: 3000; onTriggered: n.pauseBannieres(false) }

    function montrer(notif) {
        if (Partage.retient) { Partage.retenir(notif); return }     // écran partagé, jeu ou projection : gardée dans l'historique, pas de bulle
        if (enPause) { enAttente = notif; return }
        banniere = notif
        fin.prolonge = false
        fin.interval = Math.max(3000, Math.min(5000, Math.round((parseFloat(Reglages.val("ILE_BANNIERE_DUREE", "4")) || 4) * 1000)))
        fin.restart()
        plafond.restart()
    }
    Timer {
        id: fin
        property bool prolonge: false
        onTriggered: {
            if (n.survol && !prolonge) {
                prolonge = true
                interval = 1500
                restart()
            } else {
                prolonge = false
                n.survol = false
                n.banniere = null
            }
        }
    }
    // Plafond strict : 5 secondes maximum pour faire disparaître le popup sans jamais rester coincé
    Timer {
        id: plafond
        interval: 5000
        onTriggered: {
            n.survol = false
            fin.prolonge = false
            n.banniere = null
        }
    }
    onSurvolChanged: if (!survol && banniere) fin.restart()
    onBanniereChanged: if (!banniere) { fin.stop(); plafond.stop(); n.survol = false }

    // Une notification qui disparaît (fermée par l'appli ou par toi) quitte aussi la bannière
    Connections {
        target: n.banniere && !n.banniere.synthetique ? n.banniere : null
        function onClosed() { fin.stop(); plafond.stop(); n.survol = false; n.banniere = null }
    }

    // ── Lu / non lu ──
    function lire(notif) {
        if (!notif || lus[notif.id]) return
        var l = Object.assign({}, lus); l[notif.id] = true; lus = l
        garder()
    }
    function toutLire() {
        var l = Object.assign({}, lus)
        liste.forEach(x => l[x.id] = true)
        lus = l
        garder()
    }

    // Clic : action par défaut de l'appli (ouvrir le message…), sinon rien ; la notification est ensuite rangée
    function ouvrir(notif) {
        if (!notif) return
        if (notif.page) {                                // bulle de l'île (fin de partage) : ouvre la page, rien d'autre
            banniere = null
            var ecran = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : (Quickshell.screens.length ? Quickshell.screens[0].name : "")
            if (ecran === "" || Etat.ecranOuvert !== ecran) Etat.basculer(ecran, true)   // déjà ouverte sur cet écran : basculer la fermerait
            Etat.aller(notif.page)
            return
        }
        lire(notif)
        var a = notif.actions.find(x => x.identifier === "default") || (notif.actions.length === 1 ? notif.actions[0] : null)
        if (a) a.invoke()
        if (banniere === notif) banniere = null
        if (notif.synthetique) retirerRevenue(notif)
        else if (!notif.resident) notif.dismiss()
    }
    // Boutons de la notification (Supprimer, Répondre…) : toutes les actions sauf celle du clic (« default »)
    function boutons(notif) { return notif ? notif.actions.filter(a => a.identifier !== "default") : [] }
    function agir(notif, action) {
        if (!notif || !action) return
        lire(notif)
        action.invoke()
        if (banniere === notif) banniere = null
        if (!notif.resident) notif.dismiss()
    }
    // Réponse rapide (appli qui le permet : hasInlineReply), sinon l'appli est ouverte
    function repondre(notif, texte) {
        if (!notif) return false
        if (notif.hasInlineReply && texte && texte.trim()) {
            lire(notif)
            notif.sendInlineReply(texte.trim())
            if (banniere === notif) banniere = null
            if (!notif.resident) notif.dismiss()
            return true
        }
        ouvrir(notif)
        return false
    }
    function fermer(notif) {
        if (banniere === notif) banniere = null
        if (!notif) return
        if (notif.synthetique) retirerRevenue(notif)
        else notif.dismiss()
    }
    function toutEffacer() {
        banniere = null
        var l = liste
        for (let i = 0; i < l.length; i++) { if (l[i].synthetique) retirerRevenue(l[i]); else l[i].dismiss() }
    }

    // ── Reporter : 15 min, 1 h, demain (à 9 h) ──
    function reporter(notif, quand) {
        if (!notif) return
        var due = Date.now() + (quand === "15m" ? 15 * 60000 : quand === "1h" ? 3600000 : 0)
        if (quand === "demain") { let d = new Date(); d.setDate(d.getDate() + 1); d.setHours(9, 0, 0, 0); due = d.getTime() }
        if (banniere === notif) banniere = null
        if (notif.synthetique) retirerRevenue(notif)
        var r = Object.assign({}, reports); r[notif.id] = due; reports = r
        attentes = attentes.filter(a => a.id !== String(notif.id)).concat([{ id: String(notif.id), app: notif.appName || "", summary: notif.summary || "",
            body: (notif.body || "").slice(0, 2000), image: icone(notif), urgency: notif.urgency === NotificationUrgency.Critical ? 2 : 1, due: due }])
        garder()
    }
    function verifierReports() {
        var maintenant = Date.now(), r = Object.assign({}, reports), change = false
        for (let k in r) if (r[k] <= maintenant) { delete r[k]; change = true }
        if (change) reports = r
        var dues = attentes.filter(a => a.due <= maintenant)
        if (!dues.length) return
        attentes = attentes.filter(a => a.due > maintenant)
        dues.forEach(a => {
            var reelle = brutes.find(x => String(x.id) === a.id)
            var objet = reelle || { id: "r" + a.id, synthetique: true, appName: a.app, summary: a.summary, body: a.body, image: a.image,
                                     appIcon: "", desktopEntry: "", urgency: a.urgency === 2 ? NotificationUrgency.Critical : NotificationUrgency.Normal,
                                     actions: [], resident: true, hasInlineReply: false, hints: {} }
            var h = Object.assign({}, heures); h[objet.id] = maintenant; heures = h
            if (!reelle) revenues = revenues.concat([objet])
            var l = Object.assign({}, lus); delete l[objet.id]; lus = l
            if (!concentration || objet.urgency === NotificationUrgency.Critical) montrer(objet)
        })
        garder()
    }
    function retirerRevenue(objet) { revenues = revenues.filter(x => x !== objet) }

    // ── Masquer une appli : 1 h ou toujours ──
    function cleAppli(notif) { return String(notif && (notif.desktopEntry || notif.appName) || "").toLowerCase() }
    function appliMasquee(notif) {
        var fin = masques[cleAppli(notif)]
        return fin !== undefined && (fin < 0 || fin > Date.now())
    }
    function masquerAppli(notif, duree) {
        var m = Object.assign({}, masques); m[cleAppli(notif)] = duree === "toujours" ? -1 : Date.now() + 3600000; masques = m
        if (banniere && cleAppli(banniere) === cleAppli(notif)) banniere = null
        garder()
    }
    function demasquerAppli(cle) { var m = Object.assign({}, masques); delete m[cle]; masques = m; garder() }
    readonly property var applisMasquees: Object.keys(masques).filter(k => masques[k] < 0 || masques[k] > Date.now())

    // ── Groupes par appli, plus récente d'abord dans chaque groupe ──
    function groupes(l) {
        var res = [], par = {}
        l.forEach(x => {
            var cle = cleAppli(x)
            if (!par[cle]) { par[cle] = { cle: cle, nom: nomAppli(x), notifs: [], nonLues: 0 }; res.push(par[cle]) }
            par[cle].notifs.push(x)
            if (!lus[x.id]) par[cle].nonLues++
        })
        return res
    }
    function correspond(x, recherche, filtre) {
        if (filtre === "nonlues" && lus[x.id]) return false
        if (filtre === "urgentes" && x.urgency !== NotificationUrgency.Critical) return false
        if (!recherche) return true
        var r = recherche.toLowerCase()
        return (x.summary || "").toLowerCase().indexOf(r) >= 0 || (x.body || "").toLowerCase().indexOf(r) >= 0 || nomAppli(x).toLowerCase().indexOf(r) >= 0
    }

    // Image de la notification : d'abord une vraie image de contenu (photo d'un contact, pochette), puis l'icône de
    // l'appli dans le thème (Terminal, Fichiers… dessinés par nc-icones), et seulement en dernier le fichier fourni par
    // l'appli (kitty envoie son propre logo, /usr/lib/kitty/logo/kitty.png, qui passait avant le thème)
    function icone(notif) {
        if (!notif) return ""
        var img = notif.image || ""
        // Icône d'appli passée comme chemin (Quickshell la range en « image://icon//usr/… ») : pas une image de contenu
        // … sauf un fichier de ton dossier (capture d'écran…), affiché tel quel
        var fichierPerso = img.startsWith("image://icon//home/") || img.startsWith("image://icon//tmp/")
        var contenu = img !== "" && img !== notif.appIcon && (fichierPerso || (!img.startsWith("image://icon/")
                      && !img.startsWith("/usr/") && !img.startsWith("file:///usr/")))
        if (contenu && !Reglages.imagesLegeres) return img          // pas d'image de contenu en Économie (ECO_IMAGES)
        var nom = (notif.desktopEntry || notif.appName || "").toLowerCase()
        var duTheme = nom !== "" ? Quickshell.iconPath(nom, true) : ""
        if (duTheme) return duTheme
        if (notif.appIcon) return notif.appIcon.indexOf("/") >= 0 ? notif.appIcon : Quickshell.iconPath(notif.appIcon, true)
        return img
    }
    // Nom affiché : les mêmes noms simples que dans le lanceur (nc-icones)
    function nomAppli(notif) {
        if (!notif) return ""
        var nom = (notif.appName || "").toLowerCase()
        var f = Reglages.t("Fichiers", "Files")
        return ({ kitty: "Terminal", "org.gnome.nautilus": f, nautilus: f, dolphin: f })[nom] || notif.appName || Reglages.t("Application", "Application")
    }
    // « maintenant », « il y a 5 min », sinon l'heure
    function quand(notif, maintenant) {
        var t = heures[notif.id]
        if (!t) return ""
        var m = Math.floor((maintenant - t) / 60000)
        return m < 1 ? Reglages.t("maintenant", "now") : (m < 60 ? Reglages.t("il y a " + m + " min", m + " min ago") : Qt.formatTime(new Date(t), "hh:mm"))
    }
}
