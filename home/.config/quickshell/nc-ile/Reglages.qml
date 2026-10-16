pragma Singleton
// Tes réglages (commande nc-reglages) : ~/.config/nc/reglages.conf, lignes CLE=valeur, relu dès qu'il change.
// Le style du bureau (style Apple…) donne ses propres valeurs dans ~/.config/nc/style.conf ; tes réglages passent devant.
// val(CLE, défaut) : la valeur choisie, sinon celle du style, sinon le défaut.
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: r
    property var valeurs: ({})
    property var style: ({})
    function val(cle, defaut) {
        if (valeurs[cle] !== undefined && valeurs[cle] !== "") return valeurs[cle]
        if (style[cle] !== undefined && style[cle] !== "") return style[cle]
        return defaut
    }
    function lire(texte) {
        var v = {}
        texte.split("\n").forEach(l => {
            var m = l.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/)
            if (m) v[m[1]] = m[2].replace(/^"(.*)"$/, "$1")
        })
        return v
    }

    FileView {
        path: Quickshell.env("HOME") + "/.config/nc/reglages.conf"
        watchChanges: true
        printErrors: false                       // pas de fichier : aucun réglage changé
        onFileChanged: reload()
        onLoaded: r.valeurs = r.lire(text())
        onLoadFailed: r.valeurs = {}
    }
    FileView {
        path: Quickshell.env("HOME") + "/.config/nc/style.conf"
        watchChanges: true
        printErrors: false                       // pas de fichier : style de la config
        onFileChanged: reload()
        onLoaded: r.style = r.lire(text())
        onLoadFailed: r.style = {}
    }
}
