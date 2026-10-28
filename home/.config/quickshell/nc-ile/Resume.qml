pragma Singleton
// Résumé au réveil (activité en direct « Bonjour » / « Bonsoir ») : quand tu reviens après une longue absence (écran vu et
// session déverrouillée pour la première fois depuis au moins 4 h), ou la première fois de la journée après 5 h du matin,
// la pilule montre une fois ce qui compte : la météo du jour, les prochains rendez-vous, les mises à jour du système et la
// batterie (sur batterie seulement). Pilule : « 12° · 3 rendez-vous · 5 mises à jour », ~8 s puis elle s'efface ; un clic
// ouvre la page Résumé (PageResume.qml) ; Échap ou un clic ailleurs la ferme.
// Rien de nouveau n'est demandé au réseau : la météo est celle que l'île a déjà (Etat.meteo, nc-meteo et son cache) ; les
// mises à jour sont LUES dans ~/.cache/nc/paquets.json (nc-paquets : jamais de compte lancé ici) ; l'agenda ne vient que de
// Google Agenda par JARVIS, s'il est déjà configuré (GOOGLE_INTEGRATION) et qu'il répond (4 s au plus) ; sinon la ligne n'existe pas.
// Aucune IA ici, et agenda coupé avec IA_MODE=non (il passe par JARVIS).
// Économie : aucun minuteur qui tourne en continu. La détection se fait sur le changement de Etat.ecranVu (écran éteint ou
// session verrouillée) : à la sortie on note l'heure, au retour on compare. Un seul minuteur court (8 s de la pilule, ou
// 4 s d'attente des données), et seulement pendant que le résumé se prépare ou s'affiche, écran vu.
// État gardé dans $XDG_STATE_HOME/nc/ile-resume (deux lignes : dernière sortie en secondes, dernier jour salué) ;
// écrit à chaque sortie d'écran et à chaque salutation, atomiquement.
// Partage d'écran (Partage.silence) : rien ; reporté à la fin du partage s'il est encore le matin (avant midi), sinon
// abandonné. Mode jeu, projection (Partage.retient) : rien, et le jour n'est pas noté.
// Réglage ILE_RESUME_REVEIL (nc-reglages → Île) : non = rien de tout ça.
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: r

    readonly property bool reglage: Reglages.val("ILE_RESUME_REVEIL", "oui") !== "non"
    property int absenceMini: 4 * 3600          // s d'écran non vu qui font une « longue absence »
    property int dureePilule: 8000              // ms
    property int attenteDonnees: 4000           // ms au plus pour la météo et l'agenda
    property real sortieLe: 0                   // s, dernière fois que l'écran a cessé d'être vu
    property string salueLe: ""                 // AAAA-MM-JJ, dernier jour où le résumé a été montré
    property bool lu: false                     // fichier d'état lu
    property bool demarre: false
    property bool prepare: false                // données en attente
    property bool enAttente: false              // reporté à la fin d'un partage d'écran
    property bool actif: false                  // pilule visible ou page ouverte
    property bool ouvert: false                 // la page est ouverte (le clic a eu lieu)
    property bool soir: false
    property var contenu: ({ meteo: null, evenements: [], nbEvenements: 0, maj: 0, importants: [], batterie: -1 })
    property bool paquetsPret: false
    property var paquets: null

    readonly property string fichierEtat: (Quickshell.env("XDG_STATE_HOME") || (Quickshell.env("HOME") + "/.local/state")) + "/nc/ile-resume"
    readonly property string fichierPaquets: (Quickshell.env("XDG_CACHE_HOME") || (Quickshell.env("HOME") + "/.cache")) + "/nc/paquets.json"
    readonly property bool agendaVoulu: Reglages.val("GOOGLE_INTEGRATION", "non") === "oui" && Reglages.val("GOOGLE_CALENDRIER", "oui") !== "non" && !Reglages.iaCoupee
    readonly property bool meteoVoulue: Reglages.val("ILE_METEO", "oui") !== "non"
    readonly property bool majVoulue: Reglages.val("MAJ_SYSTEME", "ile") !== "non"

    function jour(d) { return Qt.formatDate(d, "yyyy-MM-dd") }
    function nombre(x) { var n = parseInt(x); return isNaN(n) || n < 0 ? 0 : n }

    // ── État gardé ──
    FileView {
        path: r.fichierEtat; printErrors: false
        onLoaded: {
            var l = text().split("\n")
            r.sortieLe = parseFloat(l[0]) || 0
            r.salueLe = /^\d{4}-\d{2}-\d{2}$/.test((l[1] || "").trim()) ? l[1].trim() : ""
            r.lu = true; r.commencer()
        }
        onLoadFailed: { r.lu = true; r.commencer() }
    }
    function noter() {
        Quickshell.execDetached(["sh", "-c", "d=\"${XDG_STATE_HOME:-$HOME/.local/state}/nc\"; mkdir -p \"$d\" && printf '%s\\n%s\\n' \"$1\" \"$2\" > \"$d/.ile-resume.$$\" && mv -f \"$d/.ile-resume.$$\" \"$d/ile-resume\"",
                                 "sh", String(Math.floor(sortieLe)), salueLe])
    }

    // ── Détection : sur le changement de Etat.ecranVu seulement ──
    function commencer() { if (lu && Etat.pret && !demarre) { demarre = true; if (Etat.ecranVu) evaluer(false) } }
    Connections { target: Etat; function onPretChanged() { r.commencer() } }
    Connections {
        target: Etat
        function onEcranVuChanged() {
            if (!Etat.ecranVu) {
                r.annuler()
                r.sortieLe = Date.now() / 1000
                if (r.lu) r.noter()
                return
            }
            if (!r.lu) return
            var absence = r.sortieLe > 0 ? Date.now() / 1000 - r.sortieLe : 0
            r.evaluer(absence >= r.absenceMini)
        }
    }
    function evaluer(longue) {
        if (!reglage) return
        var d = new Date()
        if (!(longue || (salueLe !== jour(d) && d.getHours() >= 5))) return
        declencher()
    }
    function declencher() {
        if (actif || prepare || !Etat.ecranVu) return
        if (Partage.silence) { enAttente = true; return }
        if (Partage.retient || Etat.jeu) return
        prepare = true
        paquetsPret = !majVoulue
        if (majVoulue) lecturePaquets.reload()
        if (agendaVoulu) GoogleAgenda.charger(new Date(), false)
        attente.restart()
        pret()
    }
    function annuler() { prepare = false; attente.stop(); if (actif) fin() }
    // Début d'un partage : on cache et on reporte ; fin : on reprend s'il est encore le matin
    Connections {
        target: Partage
        function onSilenceChanged() {
            if (Partage.silence) {
                if (r.actif || r.prepare) { r.prepare = false; attente.stop(); if (r.actif) r.fin(); r.enAttente = true }
            } else if (r.enAttente) {
                r.enAttente = false
                if (r.reglage && new Date().getHours() < 12) r.declencher()
            }
        }
    }

    // ── Données déjà là ──
    FileView {
        id: lecturePaquets
        path: r.fichierPaquets; printErrors: false
        onLoaded: { try { r.paquets = JSON.parse(text()) } catch (e) { r.paquets = null } r.paquetsPret = true; r.pret() }
        onLoadFailed: { r.paquets = null; r.paquetsPret = true; r.pret() }
    }
    Connections { target: GoogleAgenda; function onEnCoursChanged() { r.pret() } }
    Connections { target: Etat; function onMeteoChanged() { r.pret() } }
    Timer { id: attente; interval: r.attenteDonnees; onTriggered: r.montrer() }
    function pret() {
        if (!prepare) return
        if (!paquetsPret) return
        if (agendaVoulu && GoogleAgenda.enCours !== "") return
        if (meteoVoulue && Etat.meteo.temp === undefined) return
        montrer()
    }

    function evenementsDuJour(d) {
        if (!agendaVoulu) return []
        var c = GoogleAgenda.cache[GoogleAgenda.cle(d)]
        if (!c || !Array.isArray(c.events)) return []
        var auj = jour(d), instant = auj + "T" + Qt.formatTime(d, "HH:mm")
        var l = c.events.filter(e => e && typeof e.debut === "string" && typeof e.titre === "string"
                                     && (e.journee ? (e.debut <= auj && (e.fin ? auj < e.fin : e.debut === auj))
                                                   : (e.debut.slice(0, 10) === auj && e.debut.slice(0, 16) >= instant)))
        l.sort((a, b) => a.debut < b.debut ? -1 : (a.debut > b.debut ? 1 : 0))
        return l.map(e => ({ titre: e.titre.slice(0, 120), journee: !!e.journee,
                             heure: e.journee ? "" : Qt.formatTime(new Date(parseInt(e.debut.slice(0, 4)), parseInt(e.debut.slice(5, 7)) - 1, parseInt(e.debut.slice(8, 10)),
                                                                           parseInt(e.debut.slice(11, 13)), parseInt(e.debut.slice(14, 16))),
                                                                   Reglages.val("ILE_HEURE", "24") === "12" ? "h:mm AP" : "hh:mm") }))
    }
    function construire(d) {
        var m = meteoVoulue && Etat.meteo.temp !== undefined && !Etat.meteo.perime
                ? { temp: Math.round(Number(Etat.meteo.temp)), texte: String(Etat.meteo.texte || ""), icone: String(Etat.meteo.icone || "cloud"),
                    min: Etat.meteo.min, max: Etat.meteo.max } : null
        if (m && isNaN(m.temp)) m = null
        var ev = evenementsDuJour(d)
        var p = majVoulue && paquets ? nombre(paquets.total) : 0
        var imp = []
        if (p > 0 && Array.isArray(paquets.paquets))
            imp = paquets.paquets.filter(x => x && x.important && typeof x.nom === "string").map(x => x.nom.slice(0, 60)).slice(0, 3)
        return { meteo: m, evenements: ev.slice(0, 4), nbEvenements: ev.length, maj: p, importants: imp,
                 batterie: Etat.aBatterie && !Etat.branche && Etat.pourcent > 0 ? Etat.pourcent : -1 }
    }
    function montrer() {
        attente.stop()
        if (!prepare) return
        prepare = false
        if (!Etat.ecranVu || Partage.silence || Partage.retient || Etat.jeu) return
        var d = new Date()
        var c = construire(d)
        salueLe = jour(d)
        noter()
        if (!c.meteo && c.nbEvenements === 0 && c.maj === 0 && c.batterie < 0) return      // rien à dire : pas de pilule vide
        contenu = c
        soir = d.getHours() >= 18 || d.getHours() < 5
        ouvert = false
        actif = true
    }
    function fin() { actif = false; ouvert = false }
    Timer { id: pilule; interval: r.dureePilule; running: r.actif && !r.ouvert && Etat.ecranVu; onTriggered: r.fin() }

    // Page ouverte : plus de minuteur ; refermée : le résumé est fini
    Connections {
        target: Etat
        function onEcranOuvertChanged() {
            if (!r.actif) return
            if (Etat.ecranOuvert !== "") r.ouvert = true
            else if (r.ouvert) r.fin()
        }
    }
    function ouvrir(ecran) { if (!actif) return; Etat.basculer(ecran, false); Etat.aller("resume") }

    // ── Textes de la pilule (des nombres seulement) ──
    function pluriel(n, fr1, frN, en1, enN) { return n + " " + (n === 1 ? Reglages.t(fr1, en1) : Reglages.t(frN, enN)) }
    readonly property string salut: soir ? Reglages.t("Bonsoir", "Good evening") : Reglages.t("Bonjour", "Good morning")
    readonly property string court: {
        var p = []
        var c = contenu
        if (c.meteo) p.push(c.meteo.temp + "°")
        if (c.nbEvenements > 0) p.push(pluriel(c.nbEvenements, "rendez-vous", "rendez-vous", "event", "events"))
        if (c.maj > 0) p.push(pluriel(c.maj, "mise à jour", "mises à jour", "update", "updates"))
        if (p.length === 0 && c.batterie >= 0) p.push(Reglages.t("Batterie ", "Battery ") + c.batterie + " %")
        return p.length ? p.join(" · ") : salut
    }
}
