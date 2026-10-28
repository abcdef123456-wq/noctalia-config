// Un fond d'écran pour le jour, un pour la nuit (nc-reglages → Fonds d'écran, FONDS_JOUR_NUIT).
// Tout le travail est fait par nc-fond-jour-nuit (changement de fond comme partout : noctalia msg wallpaper-set, puis UN seul
// minuteur systemd posé jusqu'à la prochaine bascule). L'île ne fait que le lancer aux moments utiles, sans minuteur ni
// sondage : au démarrage, quand le réglage est allumé (« force ») ou coupé (« arreter »), et au réveil de l'écran ou au
// déverrouillage (rattrapage d'une bascule passée écran éteint, ou pendant une veille). Écran éteint : rien.
import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: fjn
    visible: false
    readonly property bool actif: Reglages.val("FONDS_JOUR_NUIT", "non") === "oui"
    property bool vu: false                  // le réglage a été allumé pendant cette vie de l'île
    property bool attente: false             // un lancement demandé pendant qu'un autre tournait
    property string argAttente: ""

    function lancer(arg) {
        if (lanceur.running) { attente = true; argAttente = arg; return }
        lanceur.command = [Etat.bin + "nc-fond-jour-nuit"].concat(arg !== "" ? [arg] : [])
        lanceur.running = true
    }
    Process {
        id: lanceur
        onRunningChanged: if (!running && fjn.attente) { fjn.attente = false; fjn.lancer(fjn.argAttente) }
    }
    onActifChanged: {
        if (actif) { vu = true; lancer("force") }
        else if (vu) { vu = false; lancer("arreter") }
    }
    Connections {
        target: Etat
        function onEcranVuChanged() { if (fjn.actif && Etat.ecranVu) fjn.lancer("") }
    }
    Component.onCompleted: if (actif) { vu = true; lancer("") }
}
