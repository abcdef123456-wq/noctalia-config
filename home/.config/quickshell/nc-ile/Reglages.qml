pragma Singleton
// Tes réglages (commande nc-reglages) : ~/.config/nc/reglages.conf, lignes CLE=valeur, relu dès qu'il change.
// Le style du bureau (style Apple…) donne ses propres valeurs dans ~/.config/nc/style.conf ; tes réglages passent devant.
// val(CLE, défaut) : la valeur choisie, sinon celle du style, sinon le défaut.
// Langue (réglage LANGUE : auto, fr, en ; auto = celle du système) : Reglages.t("texte français", "English text"),
// dates et heures avec Reglages.locale.
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
    readonly property bool en: {
        var l = Quickshell.env("NC_LANGUE") || ""
        if (l !== "fr" && l !== "en") l = val("LANGUE", "auto")
        if (l !== "fr" && l !== "en") l = (Quickshell.env("LC_ALL") || Quickshell.env("LC_MESSAGES") || Quickshell.env("LANG") || "fr").startsWith("fr") ? "fr" : "en"
        return l === "en"
    }
    function t(fr, en) { return r.en ? en : fr }
    readonly property var locale: Qt.locale(en ? "en_US" : "fr_FR")
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
