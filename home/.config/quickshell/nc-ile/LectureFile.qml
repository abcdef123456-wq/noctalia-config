// Lecture d'une commande (nc-ile-etat…) avec file d'attente : une demande faite pendant une lecture en cours n'est pas
// perdue, elle est rejouée dès que la lecture finit (une seule en attente, quel que soit le nombre de demandes).
import QtQuick
import Quickshell
import Quickshell.Io

Scope {
    id: l
    property var commande: []
    property bool actif: true
    property bool enAttente: false
    readonly property bool enCours: p.running
    signal lu(string texte)

    function demander() {
        if (!actif || commande.length === 0) return
        if (p.running) enAttente = true
        else p.running = true
    }
    Process {
        id: p
        command: l.commande
        stdout: StdioCollector { onStreamFinished: l.lu(this.text) }
        onRunningChanged: if (!running && l.enAttente) { l.enAttente = false; l.demander() }
    }
}
