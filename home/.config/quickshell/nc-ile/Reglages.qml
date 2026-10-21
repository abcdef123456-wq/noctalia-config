pragma Singleton
// Tes réglages (commande nc-reglages) : ~/.config/nc/reglages.conf, lignes CLE=valeur, relu dès qu'il change.
// Le style du bureau (style Apple…) donne ses propres valeurs dans ~/.config/nc/style.conf ; tes réglages passent devant.
// val(CLE, défaut) : la valeur choisie, sinon celle du style, sinon le défaut.
// Langue (réglage LANGUE : auto, fr, en ; auto = celle du système) : Reglages.t("texte français", "English text"),
// dates et heures avec Reglages.locale.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.UPower

Singleton {
    id: r
    property var valeurs: ({})
    property var style: ({})
    function val(cle, defaut) {
        if (valeurs[cle] !== undefined && valeurs[cle] !== "") return valeurs[cle]
        if (style[cle] !== undefined && style[cle] !== "") return style[cle]
        return defaut
    }
    // IA du bureau coupée (nc-reglages → Intelligence artificielle → Aucune) : plus de pages JARVIS ni Agents, plus d'IA
    // dans le Spotlight ; les réponses de la config (sans IA) restent
    // En profil Économie sur batterie, seule l'IA d'arrière-plan se met en pause (IA_ECONOMIE, nc-ia --fond) : rien dans
    // l'île ne tourne tout seul, tout ce qu'on y lance reste disponible
    readonly property bool iaCoupee: val("IA_MODE", "auto") === "non"
    function pageActive(nom) { return !(iaCoupee && (nom === "claude" || nom === "assistant")) && val("ILE_PAGE_" + nom.toUpperCase(), "oui") !== "non" }
    function filtrerPages(pages) { return pages.filter(nom => pageActive(nom)) }
    readonly property bool en: {
        var l = Quickshell.env("NC_LANGUE") || ""
        if (l !== "fr" && l !== "en") l = val("LANGUE", "auto")
        if (l !== "fr" && l !== "en") l = (Quickshell.env("LC_ALL") || Quickshell.env("LC_MESSAGES") || Quickshell.env("LANG") || "fr").startsWith("fr") ? "fr" : "en"
        return l === "en"
    }
    function t(fr, en) { return r.en ? en : fr }
    // Économie (profil d'énergie, quel que soit le service : power-profiles-daemon, tuned-ppd, tlp-pd) : l'île coupe ses
    // animations et l'analyse du son (ECO_EFFETS, comme Hyprland et Noctalia) et ses images décoratives (ECO_IMAGES :
    // pochettes, images des notifications, fond flouté de la vue des fenêtres, icônes des logiciels à installer).
    // « Effets visuels : aucun » coupe les animations dans tous les profils.
    readonly property bool economie: PowerProfiles.profile === PowerProfile.PowerSaver
    readonly property bool sobre: val("EFFETS", "tous") === "aucun" || (economie && val("ECO_EFFETS", "oui") !== "non")
    readonly property bool imagesLegeres: economie && val("ECO_IMAGES", "oui") !== "non"
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
