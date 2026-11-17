pragma Singleton
// État « Santé Garmin » pour le panneau Garmin.qml. Connecteur NON OFFICIEL (peut cesser de marcher si Garmin change son service).
// Tout vient de nc-garmin (etat-json, sync, widgets, demo, hydratation, installer, login, logout) en argv liste ; jamais un
// identifiant tapé à la main : les ids viennent du catalogue renvoyé par le moteur.
//   - lecture à l'ouverture du panneau et après chaque action ; AUCUNE minuterie, rien ne tourne panneau fermé ni si « actif » est faux ;
//   - file d'actions FIFO : jamais deux nc-garmin en même temps, l'état est relu quand la file est vide ;
//   - « Actualiser » = sync --force ; l'ouverture lance un sync simple (une fois, si le moteur est prêt) ;
//   - partage d'écran (Partage.silence) : le masquage se fait ICI, à un seul endroit. Le panneau, l'infobulle et le résumé ne lisent
//     que metriquesVisibles et resumeVisible (vides quand « masque » est vrai).
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: g

    readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
    signal ouvrirPanneau()
    function demanderPanneau() { ouvrirPanneau() }
    property bool panneauOuvert: false            // posé par Garmin.qml
    property bool lu: false
    property bool actif: false
    property bool installe: false
    property bool connecte: false
    property bool demo: false
    property bool pret: false
    property var widgetsActifs: []
    property var catalogue: []                    // [{id, nom, defaut, actif}]
    property var brut: ({})                       // les mesures telles que le moteur les donne : NE PAS lire hors de ce fichier
    readonly property string resume: pret && brut.body_battery !== undefined ? "Garmin · " + brut.body_battery + " %" + (brut.pas !== undefined ? " · " + brut.pas + Reglages.t(" pas", " steps") : "") : ""
    property string erreur: ""
    property bool occupe: agir.running
    property var suites: []                       // la file : [[argv…], …]
    property bool syncOuverture: false

    readonly property bool masque: Partage.silence
    readonly property var metriquesVisibles: masque ? ({}) : brut
    readonly property string resumeVisible: masque ? "" : resume

    function nomDe(id) {
        for (var i = 0; i < catalogue.length; i++) if (catalogue[i].id === id) return catalogue[i].nom
        return id
    }

    function relire() { if (!lire.running) lire.running = true }

    // Une action : lancée tout de suite si rien ne tourne, sinon mise en file
    function lancer(args) {
        if (agir.running) { g.suites = g.suites.concat([args]); return }
        erreur = ""
        agir.command = [bin + "nc-garmin"].concat(args)
        agir.running = true
    }
    function actualiser() { lancer(["sync", "--force"]) }
    function widget(action, id) { lancer(["widgets", action, id]) }
    function widgetsDefaut() { lancer(["widgets", "defaut"]) }
    function hydrater(ml) { lancer(["hydratation", ml]) }
    function demoBasculer() { lancer(["demo", "basculer"]) }
    function installer() { lancer(["installer"]) }
    function connecter() { lancer(["login"]) }
    function deconnecter() { lancer(["logout"]) }

    onPanneauOuvertChanged: {
        if (panneauOuvert) { syncOuverture = false; relire() }
    }

    function appliquer(txt) {
        var d
        try { d = JSON.parse(txt) } catch (e) { return }
        if (!d || d.erreur) { erreur = d && d.message ? String(d.message).slice(0, 240) : ""; return }
        actif = d.actif === true; installe = d.installe === true; connecte = d.connecte === true
        demo = d.demo === true; pret = d.pret === true
        widgetsActifs = d.widgets_actifs || []
        catalogue = d.widgets_catalogue || []
        brut = d.metriques || ({})
        lu = true
        // Un sync simple à l'ouverture, une seule fois, si le moteur est prêt (en démo il ne fait rien)
        if (panneauOuvert && actif && pret && !syncOuverture) { syncOuverture = true; lancer(["sync"]) }
    }

    Process {
        id: lire
        command: [g.bin + "nc-garmin", "etat-json"]
        stdout: StdioCollector { onStreamFinished: g.appliquer(text) }
    }
    Process {
        id: agir
        // nc-garmin dit ses erreurs en JSON sur stdout ({"erreur", "message"}) : seul le message traduit est montré
        stdout: StdioCollector { onStreamFinished: {
            var l = text.trim().split("\n"), d = null
            try { d = JSON.parse(l[l.length - 1]) } catch (e) {}
            if (d && d.erreur && d.message) g.erreur = String(d.message).slice(0, 240)
        } }
        onExited: code => {
            if (g.suites.length > 0) {
                var suivante = g.suites[0]
                g.suites = g.suites.slice(1)
                g.lancer(suivante)
                return
            }
            g.relire()
        }
    }
}
