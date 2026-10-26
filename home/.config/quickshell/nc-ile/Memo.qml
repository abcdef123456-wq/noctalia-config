pragma Singleton
// Ce que l'île garde d'une session à l'autre (nc-ile-memo : ~/.local/state/nc/ile/NOM.json, fichiers privés écrits
// d'un bloc). Memo.lire(nom, fonction) lit (null s'il n'y a rien) ; Memo.ecrire(nom, valeur) garde, les écritures
// passant une par une dans l'ordre. Rien du contenu n'est journalisé.
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: memo
    readonly property string bin: Quickshell.env("HOME") + "/.local/bin/nc-ile-memo"
    property var file: []                  // écritures en attente : { nom, json }
    property var lectures: []              // lectures en attente : { nom, cb }
    property int enAttente: file.length + lectures.length

    function ecrire(nom, valeur) {
        // Une seule écriture par nom en attente : la plus récente remplace l'ancienne
        file = file.filter(e => e.nom !== nom).concat([{ nom: nom, json: JSON.stringify(valeur === undefined ? null : valeur) }])
        suivant()
    }
    function lire(nom, cb) {
        lectures = lectures.concat([{ nom: nom, cb: cb }])
        suivant()
    }
    function oublier(nom) { Quickshell.execDetached([bin, "oublier", nom]) }

    property var courant: null
    function suivant() {
        if (courant || ecriture.running || lecture.running) return
        if (file.length) {
            courant = file[0]; file = file.slice(1)
            ecriture.command = [bin, "ecrire", courant.nom]
            ecriture.stdinEnabled = true
            ecriture.running = true
        } else if (lectures.length) {
            courant = lectures[0]; lectures = lectures.slice(1)
            lecture.command = [bin, "lire", courant.nom]
            lecture.running = true
        }
    }
    // Garde : si nc-ile-memo ne démarre pas ou ne finit jamais, courant resterait non nul et plus rien ne passerait.
    // Au bout de 10 s la commande est arrêtée, la lecture rend null et la file repart.
    Timer {
        interval: 10000
        running: memo.courant !== null
        onTriggered: {
            var c = memo.courant
            ecriture.running = false; lecture.running = false
            memo.courant = null
            if (c && c.cb) c.cb(null)
            memo.suivant()
        }
    }
    Process {
        id: ecriture
        onStarted: { write(memo.courant.json); stdinEnabled = false }
        stderr: StdioCollector { onStreamFinished: if (text.trim()) console.warn("nc-ile-memo : " + text.trim()) }
        onExited: { memo.courant = null; memo.suivant() }
    }
    Process {
        id: lecture
        onExited: memo.suivant()          // gardé : si le flux n'est pas encore fini, il rend la main et c'est le flux qui relance
        stdout: StdioCollector {
            onStreamFinished: {
                var v = null
                try { v = JSON.parse(text) } catch (_) { v = null }
                var cb = memo.courant ? memo.courant.cb : null
                memo.courant = null
                if (cb) cb(v)
                memo.suivant()
            }
        }
        stderr: StdioCollector {}
    }
}
