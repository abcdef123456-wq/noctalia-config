import QtQuick

WidgetBarreLibelle {
    id: w
    readonly property var options: barre.definition
    readonly property string stat: options.stat || "cpu_usage"
    readonly property bool disque: stat.startsWith("disk_")
    readonly property bool reseau: stat === "net_rx" || stat === "net_tx"
    readonly property var mesure: (disque ? WidgetBarreSonde.disque : WidgetBarreSonde.valeurs)[stat]
    readonly property string trait: options.visualization || "gauge"
    readonly property bool dessiner: trait !== "none" && (options.peek !== true || !aGlyphe || revele)
    readonly property real proportion: Math.max(0, Math.min(1, !Number.isFinite(mesure) ? 0 :
        stat === "cpu_temp" ? mesure / 100 : stat === "disk_used" ? WidgetBarreSonde.disque.disk_used_pct / 100 :
        stat === "disk_free" ? WidgetBarreSonde.disque.disk_free_pct / 100 : reseau ? Math.log1p(mesure / 1024) / 12 : mesure / 100))
    readonly property color traitCouleur: proportion >= 0.9 && !reseau && stat !== "disk_free_pct" && stat !== "disk_free"
        ? barre.teinte(options.highlight_color || "error", barre.premierPlan) : barre.premierPlan
    property bool inscrit: false

    affiche: Number.isFinite(mesure) && largeurContenu > 0 && hauteurContenu > 0
    glyphe: stat === "cpu_temp" ? "thermostat" : stat === "ram_used" ? "memory_alt" : disque ? "hard_drive" :
        stat === "net_rx" ? "download" : stat === "net_tx" ? "upload" : "memory"
    encreGlyphe: traitCouleur
    libelle: [options.custom_label || "", options.show_value !== false ? valeur() : ""].filter(s => s !== "").join(" ")
    visuel: dessiner ? visuelMesure : null
    infobulle: {
        const ordre = [stat, "cpu_usage", "cpu_temp", "ram_used", "disk_used_pct"].filter((v, i, a) => a.indexOf(v) === i)
        return ordre.map(k => {
            const v = (k.startsWith("disk_") ? WidgetBarreSonde.disque : WidgetBarreSonde.valeurs)[k]
            if (!Number.isFinite(v)) return ""
            const nom = ({ cpu_usage: "CPU", cpu_temp: Reglages.t("Température", "Temperature"), ram_used: "RAM",
                net_rx: Reglages.t("Réception", "Download"), net_tx: Reglages.t("Envoi", "Upload") })[k] || Reglages.t("Disque", "Disk")
            return nom + " · " + format(k, v, true)
        }).filter(s => s).join("\n")
    }
    minimum: Number(options.label_min_width ?? 0)
    gauche: () => barre.page("systeme")
    function valeur() { return Number.isFinite(mesure) ? format(stat, mesure, options.label_show_units !== false) : "" }
    function format(cle, n, unites) {
        if (cle === "cpu_temp") return n + (unites ? "°C" : "")
        if (cle === "disk_used" || cle === "disk_free") return (n / 1073741824).toFixed(1) + (unites ? Reglages.t(" Gio", " GiB") : "")
        if (cle === "net_rx" || cle === "net_tx") {
            const m = options.network_speed_unit === "mb" || options.network_speed_unit !== "kb" && n >= 1e6
            const k = m || options.network_speed_unit === "kb" || n >= 1000
            const compact = options.network_speed_compact === true
            return (n / (m ? 1e6 : k ? 1e3 : 1)).toFixed(compact ? Number(options.network_speed_decimal_places ?? 1) : k ? 1 : 0)
                + (unites ? compact ? (m ? "M" : k ? "k" : "B") : m ? Reglages.t(" Mo/s", " MB/s") : k ? Reglages.t(" ko/s", " kB/s") : Reglages.t(" o/s", " B/s") : "")
        }
        return n + (unites ? "%" : "")
    }
    function abonnement(d) {
        WidgetBarreSonde.utilisateurs += d
        if (disque) WidgetBarreSonde.disques += d
        if (reseau) WidgetBarreSonde.reseaux += d
    }
    Component.onCompleted: { abonnement(1); inscrit = true }
    Component.onDestruction: if (inscrit) abonnement(-1)

    Component {
        id: visuelMesure
        Item {
            readonly property real t: w.barre.tailleIcone
            readonly property real largeurStat: !w.barre.vertical && w.trait === "graph" ? 31 : t
            implicitWidth: w.barre.vertical ? t : (w.aGlyphe ? t + 4 : 0) + largeurStat
            implicitHeight: w.barre.vertical ? (w.aGlyphe ? t + 2 : 0) + t : t
            Ico {
                visible: w.aGlyphe
                width: parent.t; height: width
                nom: w.glyphe; taille: width; color: w.encreGlyphe; plein: false
            }
            Canvas {
                id: mesure
                x: !w.barre.vertical && w.aGlyphe ? parent.t + 4 : 0
                y: w.barre.vertical && w.aGlyphe ? parent.t + 2 : 0
                width: parent.largeurStat; height: parent.t
                readonly property real fraction: w.proportion
                readonly property var serie: w.trait === "graph" ? WidgetBarreSonde.historique[w.stat] || [] : []
                readonly property color teinte: w.traitCouleur
                onFractionChanged: requestPaint()
                onTeinteChanged: requestPaint()
                onSerieChanged: requestPaint()
                onPaint: {
                    const c = getContext("2d"), x = width / 2, y = height / 2
                    c.clearRect(0, 0, width, height)
                    c.strokeStyle = teinte; c.lineWidth = 1.7; c.lineCap = "round"; c.lineJoin = "round"
                    if (w.trait === "graph") {
                        const max = w.reseau || w.disque && !w.stat.endsWith("_pct") ? Math.max(1, ...serie) : 100
                        c.beginPath()
                        if (serie.length < 2) { c.moveTo(1, height - 2); c.lineTo(width - 1, height - 2) }
                        else for (let i = 0; i < serie.length; i++) {
                            const px = 1 + (width - 2) * i / (serie.length - 1)
                            const py = height - 2 - (height - 4) * Math.min(1, serie[i] / max)
                            if (i === 0) c.moveTo(px, py); else c.lineTo(px, py)
                        }
                        c.stroke()
                    } else {
                        const rayon = Math.max(1, y - 2), debut = -Math.PI / 2
                        c.globalAlpha = 0.25; c.beginPath(); c.arc(x, y, rayon, 0, 2 * Math.PI); c.stroke()
                        c.globalAlpha = 1
                        if (fraction > 0) { c.beginPath(); c.arc(x, y, rayon, debut, debut + fraction * 2 * Math.PI); c.stroke() }
                    }
                }
            }
        }
    }
}
