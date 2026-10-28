// L'IA du bureau peut-elle répondre maintenant ? (nc-ia disponible : code 0 si elle est permise et qu'une IA est joignable)
// Une seule question, posée par verifier() quand une page s'affiche (écran allumé par définition) : rien ne tourne
// tout seul. IA_MODE=non : jamais prête, tout de suite, sans lancer quoi que ce soit.
import QtQuick
import Quickshell.Io

Item {
    id: p
    visible: false; width: 0; height: 0
    property bool joignable: false
    readonly property bool prete: joignable && !Reglages.iaCoupee
    function verifier() {
        if (Reglages.iaCoupee) { joignable = false; return }
        if (!sonde.running) sonde.running = true
    }
    Process {
        id: sonde
        command: [Etat.bin + "nc-ia", "disponible"]
        onExited: code => p.joignable = code === 0
    }
}
