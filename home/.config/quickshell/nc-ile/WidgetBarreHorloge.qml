import QtQuick

WidgetBarreLibelle {
    id: horloge
    readonly property var options: barre.definition
    readonly property string format: (barre.vertical ? options.vertical_format : "") || options.format
                                     || (barre.type === "date" ? "{:%a %d %b}" : "{:%H:%M}")
    readonly property date instant: /%-?[STX]/.test(format + (options.tooltip_format || "")) ? Etat.maintenant : Etat.minute
    libelle: barre.vertical && !options.vertical_format ? formater(format).replace(/:/g, "\n") : formater(format)
    infobulle: options.tooltip_format ? formater(options.tooltip_format) : Etat.dateLongue + " · " + Etat.heure
    gauche: () => barre.page("calendrier")
    maximum: barre.vertical ? 38 : 360

    function formater(motif) {
        const traduire = s => s.replace(/%(-?)([a-zA-Z%])/g, (original, sansZero, c) => {
            const t = champ(c, original)
            return sansZero ? t.replace(/^[ 0](?=\d)/, "") : t
        })
        return motif.includes("{:") ? motif.replace(/\{:([^{}]+)\}/g, (_, s) => traduire(s)) : traduire(motif)
    }

    function champ(c, original) {
        const d = instant, locale = Reglages.locale
        const pad = (valeur, taille = 2) => String(valeur).padStart(taille, "0")
        switch (c) {
        case "a": return d.toLocaleDateString(locale, "ddd")
        case "A": return d.toLocaleDateString(locale, "dddd")
        case "b": return d.toLocaleDateString(locale, "MMM")
        case "B": return d.toLocaleDateString(locale, "MMMM")
        case "d": return pad(d.getDate())
        case "e": return String(d.getDate()).padStart(2, " ")
        case "H": return pad(d.getHours())
        case "I": return pad(d.getHours() % 12 || 12)
        case "M": return pad(d.getMinutes())
        case "S": return pad(d.getSeconds())
        case "p": return d.toLocaleTimeString(locale, "AP")
        case "y": return pad(d.getFullYear() % 100)
        case "Y": return String(d.getFullYear())
        case "m": return pad(d.getMonth() + 1)
        case "j": return pad(Math.round((Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) - Date.UTC(d.getFullYear(), 0, 1)) / 86400000) + 1, 3)
        case "u": return String(d.getDay() || 7)
        case "w": return String(d.getDay())
        case "R": return Qt.formatTime(d, "hh:mm")
        case "T": return Qt.formatTime(d, "hh:mm:ss")
        case "D": return Qt.formatDate(d, "MM/dd/yy")
        case "F": return Qt.formatDate(d, "yyyy-MM-dd")
        case "x": return d.toLocaleDateString(locale, Locale.ShortFormat)
        case "X": return d.toLocaleTimeString(locale, Locale.ShortFormat)
        case "%": return "%"
        default: return original
        }
    }
}
