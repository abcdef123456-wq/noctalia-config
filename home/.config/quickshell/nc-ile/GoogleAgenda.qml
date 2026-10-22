pragma Singleton
// Google Agenda pour la page Calendrier, par JARVIS (nc-jarvis requete, op google.calendar : le gateway lit l'API avec
// le jeton Google déjà relié à JARVIS, jamais renvoyé ici). Un mois à la fois, gardé 5 minutes ; rien n'est demandé
// avant l'ouverture de la page. Cache : « AAAA-MM » → { t, events, calendars } ; erreur : message, par mois.
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: g
    readonly property int validite: 5 * 60 * 1000
    property var cache: ({})
    property string enCours: ""                 // mois en chargement
    property var erreurs: ({})                  // « AAAA-MM » → message
    property var attente: null                  // demande arrivée pendant un chargement
    property string sortie: ""

    function cle(d) { return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") }
    function iso(d) { return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0") }
    function frais(k) { var c = cache[k]; return !!c && Date.now() - c.t < validite }
    function erreur(k) { return erreurs[k] || "" }

    // Charge le mois de cette date (force : même si le cache est encore frais)
    function charger(d, force) {
        var k = cle(d)
        if (!force && frais(k)) return
        if (enCours === k) return
        if (enCours !== "") { attente = { d: d, force: force }; return }
        enCours = k
        var e = Object.assign({}, erreurs); delete e[k]; erreurs = e
        sortie = ""
        var debut = new Date(d.getFullYear(), d.getMonth(), 1), fin = new Date(d.getFullYear(), d.getMonth() + 1, 1)
        requete.corps = JSON.stringify({ op: "google.calendar", params: { from: iso(debut), to: iso(fin) }, confirmed: false })
        requete.stdinEnabled = true
        requete.running = true
        demarrage.restart()
    }
    function finir(texte) {
        var k = enCours, r = null
        try { r = JSON.parse(texte) } catch (_) {}
        if (r && r.ok === true && r.data && Array.isArray(r.data.events)) {
            let c = Object.assign({}, cache)
            c[k] = { t: Date.now(), events: r.data.events, calendars: r.data.calendars || [] }
            cache = c
        } else {
            let e = Object.assign({}, erreurs)
            e[k] = r && typeof (r.error || (r.data || {}).error) === "string" ? String(r.error || r.data.error).slice(0, 300)
                 : Reglages.t("JARVIS ne répond pas (nc-jarvis).", "JARVIS is not responding (nc-jarvis).")
            erreurs = e
        }
        enCours = ""
        if (attente) { let a = attente; attente = null; charger(a.d, a.force) }
    }
    Process {
        id: requete
        property string corps: ""
        command: [Quickshell.env("HOME") + "/.local/bin/nc-jarvis", "requete"]
        onStarted: { demarrage.stop(); write(corps + "\n"); stdinEnabled = false }
        stdout: StdioCollector { onStreamFinished: g.finir(text) }
        stderr: StdioCollector {}
    }
    Timer { id: demarrage; interval: 3000; onTriggered: if (g.enCours !== "" && !requete.running) g.finir("") }

    // Le prochain événement à partir de maintenant, dans les mois déjà chargés
    function prochain(maintenant) {
        var jour = iso(maintenant), instant = jour + "T" + Qt.formatTime(maintenant, "HH:mm")
        var cles = Object.keys(cache).sort()
        for (let i = 0; i < cles.length; i++) {
            if (cles[i] < jour.slice(0, 7)) continue
            let l = cache[cles[i]].events.slice().sort((a, b) => a.debut < b.debut ? -1 : (a.debut > b.debut ? 1 : 0))
            for (let j = 0; j < l.length; j++) {
                let e = l[j]
                if (e.journee ? (e.fin ? jour < e.fin : e.debut >= jour) : e.debut.slice(0, 16) >= instant) return e
            }
        }
        return null
    }
}
