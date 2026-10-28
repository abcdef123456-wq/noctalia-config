pragma Singleton
// Ce que dit un texte copié, pour les actions rapides de la page Presse-papiers (PresseAction.qml) : une couleur
// (#rgb, #rrggbb, rgb(…)) et ses conversions, un lien http(s), un chemin, un calcul ou un nombre. Fonctions pures : rien n'est
// lancé ici, sauf la question « qalc est-il installé ? » (une seule fois, quand un calcul s'affiche).
// qalc n'est appelé que pour un calcul fait de chiffres et d'opérateurs seulement (aucune lettre : donc ni unité, ni devise,
// ni taux de change à aller chercher en ligne).
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: pa
    property int qalcDispo: -1             // -1 inconnu, 0 absent, 1 installé
    property bool demandeQalc: false
    Process {
        id: sonde
        command: ["sh", "-c", "command -v qalc >/dev/null 2>&1"]
        running: pa.demandeQalc && pa.qalcDispo < 0
        onExited: code => pa.qalcDispo = code === 0 ? 1 : 0
    }

    function deuxChiffres(n) { return Math.max(0, Math.min(255, n)) }
    function hex2(n) { var h = deuxChiffres(n).toString(16); return h.length < 2 ? "0" + h : h }
    // r, g, b (0 à 255) → { hex, rgb, hsl }
    function conversions(r, g, b) {
        var rr = r / 255, gg = g / 255, bb = b / 255
        var mx = Math.max(rr, gg, bb), mn = Math.min(rr, gg, bb), l = (mx + mn) / 2, h = 0, s = 0
        if (mx !== mn) {
            var d = mx - mn
            s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn)
            h = mx === rr ? (gg - bb) / d + (gg < bb ? 6 : 0) : (mx === gg ? (bb - rr) / d + 2 : (rr - gg) / d + 4)
            h *= 60
        }
        return { hex: "#" + hex2(r) + hex2(g) + hex2(b), rgb: "rgb(" + r + ", " + g + ", " + b + ")",
                 hsl: "hsl(" + Math.round(h) + ", " + Math.round(s * 100) + "%, " + Math.round(l * 100) + "%)" }
    }
    function couleur(t) {
        var m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(t)
        if (m) {
            var h = m[1].length === 3 ? m[1].replace(/./g, "$&$&") : m[1]
            return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
        }
        m = /^rgba?\(\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*(?:[,/]\s*[\d.]+%?\s*)?\)$/i.exec(t)
        if (m) {
            var v = [parseInt(m[1]), parseInt(m[2]), parseInt(m[3])]
            return v.every(x => x <= 255) ? v : null
        }
        return null
    }
    // Chemin absolu ou « ~/ » (jamais un nom relatif) : le ~ devient le dossier personnel
    function chemin(t, maison) {
        if (!/^(\/|~\/)[^\n\0]+$/.test(t) || t.length > 1024 || /^\/\/?$/.test(t)) return ""
        return t.charAt(0) === "~" ? String(maison || "") + t.slice(1) : t
    }
    // Un calcul : chiffres, opérateurs et parenthèses seulement, avec au moins un opérateur entre deux nombres ; pas une date
    function calcul(t) {
        if (t.length > 120 || !/^[0-9(.][0-9+\-*/^().%\s×÷]*$/.test(t)) return ""
        if (!/[0-9)]\s*[-+*/^×÷]\s*[0-9(.]/.test(t)) return ""
        if (/^\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}$/.test(t)) return ""
        var ouvertes = 0
        for (var i = 0; i < t.length; i++) { if (t[i] === "(") ouvertes++; else if (t[i] === ")" && --ouvertes < 0) return "" }
        return ouvertes === 0 ? t.replace(/×/g, "*").replace(/÷/g, "/") : ""
    }
    // null : rien à proposer ; sinon { genre: couleur|url|chemin|calcul|nombre, … }
    function detecter(texte, maison) {
        var t = String(texte || "").trim()
        if (t === "" || t.indexOf("\n") >= 0) return null
        if (/^https?:\/\/[^\s'"<>`\\]+$/i.test(t) && t.length <= 2000) return { genre: "url", url: t }
        if (t.length > 1024) return null
        var c = couleur(t)
        if (c) return Object.assign({ genre: "couleur", r: c[0], g: c[1], b: c[2] }, conversions(c[0], c[1], c[2]))
        var p = chemin(t, maison)
        if (p !== "") return { genre: "chemin", chemin: p }
        var e = calcul(t)
        if (e !== "") return { genre: "calcul", expr: e }
        if (/^\d{1,15}$/.test(t)) {
            var n = parseInt(t)
            return { genre: "nombre", n: n, hex: "0x" + n.toString(16), bin: "0b" + n.toString(2) }
        }
        return null
    }
    // Le dossier à ouvrir pour un fichier (un dossier s'ouvre lui-même : décidé par PresseAction)
    function dossierDe(p) { var i = p.lastIndexOf("/"); return i <= 0 ? "/" : p.slice(0, i) }
    // Sortie de qalc -t : une seule ligne courte, différente de la question ; sinon rien
    function resultat(sortie, expr) {
        var l = String(sortie || "").trim()
        if (l === "" || l.indexOf("\n") >= 0 || l.length > 60 || l.replace(/\s/g, "") === String(expr).replace(/\s/g, "")) return ""
        return l
    }
}
