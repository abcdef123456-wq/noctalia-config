pragma Singleton
// Tes réglages (commande nc-reglages) : ~/.config/nc/reglages.conf, lignes CLE=valeur, relu dès qu'il change.
// val(CLE, défaut) : la valeur choisie, sinon le défaut.
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: r
    property var valeurs: ({})
    function val(cle, defaut) { return valeurs[cle] !== undefined && valeurs[cle] !== "" ? valeurs[cle] : defaut }

    FileView {
        path: Quickshell.env("HOME") + "/.config/nc/reglages.conf"
        watchChanges: true
        printErrors: false                       // pas de fichier : aucun réglage changé
        onFileChanged: reload()
        onLoaded: {
            var v = {}
            text().split("\n").forEach(l => {
                var m = l.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/)
                if (m) v[m[1]] = m[2].replace(/^"(.*)"$/, "$1")
            })
            r.valeurs = v
        }
        onLoadFailed: r.valeurs = {}
    }
}
