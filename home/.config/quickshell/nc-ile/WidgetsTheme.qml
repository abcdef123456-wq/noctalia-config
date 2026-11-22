// Widgets de bureau choisis par le thème (champ « widgets » du thème, écrit dans style.conf : WIDGETS_THEME=type:coin:taille,…).
// Créé par shell.qml ; ne montre rien si WIDGETS_BUREAU n'est pas « oui » ou si le thème n'a pas de widgets (alors Bureau.qml
// garde l'horloge et la date d'avant, à l'identique). Types : horloge-fine, horloge-mots, horloge-segments, calendrier,
// citation, musique, jauges. Coins : haut-gauche, haut-droite, bas-gauche, bas-droite, centre. Tailles : petit, moyen, grand.
// Énergie : aucune pendule à soi. Horloges, calendrier et citation suivent Etat.minute (une fois par minute) ; la citation
// relit son fichier une fois par jour ; les jauges sont les seules à avoir un minuteur (2 s), allumé seulement quand un
// widget « jauges » est vu (écran allumé, non verrouillé, widgets non cachés). Un seul échantillonnage pour tous les écrans.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

Scope {
    id: w
    readonly property bool actif: Reglages.val("WIDGETS_BUREAU", "non") === "oui"
    readonly property var liste: {
        if (!actif) return []
        var r = []
        var parts = String(Reglages.val("WIDGETS_THEME", "")).split(",")
        for (var i = 0; i < parts.length && r.length < 4; i++) {
            var p = parts[i].trim().split(":")
            if (p.length === 3) r.push({ type: p[0], coin: p[1], taille: p[2] })
        }
        return r
    }
    readonly property bool vu: Etat.ecranVu && !Etat.widgetsCaches
    readonly property bool aJauges: { for (var i = 0; i < liste.length; i++) if (liste[i].type === "jauges") return true; return false }
    readonly property bool aCitation: { for (var i = 0; i < liste.length; i++) if (liste[i].type === "citation") return true; return false }
    readonly property string dossier: (Quickshell.env("XDG_CONFIG_HOME") || (Quickshell.env("HOME") + "/.config")) + "/nc"

    // ── Citation du jour : ~/.config/nc/citations.txt, 4 Kio au plus, 200 caractères par ligne, une par jour ──
    property var citations: []
    readonly property int jour: Math.floor((Etat.minute.getTime() - Etat.minute.getTimezoneOffset() * 60000) / 86400000)
    readonly property string citation: citations.length > 0 ? citations[((jour % citations.length) + citations.length) % citations.length] : ""
    onJourChanged: if (aCitation && vu) fichierCitations.reload()
    FileView {
        id: fichierCitations
        path: w.aCitation ? w.dossier + "/citations.txt" : ""
        printErrors: false
        onLoaded: w.citations = text().slice(0, 4096).split("\n").map(l => l.trim().slice(0, 200)).filter(l => l !== "")
        onLoadFailed: w.citations = []
    }

    // ── Jauges : CPU (/proc/stat), RAM (/proc/meminfo), disque (df, toutes les 30 s) ──
    property real cpu: 0
    property real ram: 0
    property real disque: 0
    property var cpuAvant: null
    property int tic: 0
    function echantillon() {
        procStat.reload(); procMem.reload()
        if (tic++ % 15 === 0 && !dfProc.running) dfProc.running = true
    }
    onVuChanged: if (vu && aJauges) echantillon()
    readonly property var minuteur: echantillonneur
    Timer { id: echantillonneur; interval: 2000; repeat: true; running: w.vu && w.aJauges; onTriggered: w.echantillon() }
    FileView {
        id: procStat
        path: w.aJauges ? "/proc/stat" : ""
        printErrors: false
        onLoaded: {
            var m = text().split("\n")[0].trim().split(/\s+/).slice(1).map(Number)
            var total = m.reduce((a, b) => a + b, 0), repos = (m[3] || 0) + (m[4] || 0)
            if (w.cpuAvant && total > w.cpuAvant[0]) w.cpu = 1 - (repos - w.cpuAvant[1]) / (total - w.cpuAvant[0])
            w.cpuAvant = [total, repos]
        }
    }
    FileView {
        id: procMem
        path: w.aJauges ? "/proc/meminfo" : ""
        printErrors: false
        onLoaded: {
            var t = text(), a = /MemTotal:\s+(\d+)/.exec(t), b = /MemAvailable:\s+(\d+)/.exec(t)
            if (a && b && Number(a[1]) > 0) w.ram = 1 - Number(b[1]) / Number(a[1])
        }
    }
    Process {
        id: dfProc
        command: ["df", "-P", "/"]
        stdout: StdioCollector {
            onStreamFinished: { var m = /(\d+)%/.exec(text.split("\n")[1] || ""); if (m) w.disque = Number(m[1]) / 100 }
        }
    }
    function barre(v) {
        var n = Math.max(0, Math.min(10, Math.round(v * 10)))
        return "█".repeat(n) + "░".repeat(10 - n)
    }
    function pct(v) { return Math.round(Math.max(0, Math.min(1, v)) * 100) + "%" }

    // ── Contenu (lignes de texte) de chaque type ──
    readonly property var unites: ["", "une", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze"]
    readonly property var unitesEn: ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]
    function mots(d) {
        var h = d.getHours(), m = Math.floor(d.getMinutes() / 5) * 5
        var plus = m > 30, h2 = (h + (plus ? 1 : 0)) % 24, h12 = h2 % 12 === 0 ? 12 : h2 % 12
        if (Reglages.en) {
            var nom = unitesEn[h12]
            var t = { 0: "", 5: "five past", 10: "ten past", 15: "quarter past", 20: "twenty past", 25: "twenty-five past", 30: "half past",
                      35: "twenty-five to", 40: "twenty to", 45: "quarter to", 50: "ten to", 55: "five to" }
            return ["It's", m === 0 ? nom + " o'clock" : t[m] + " " + nom]
        }
        var heure = h2 === 0 ? "minuit" : (h2 === 12 ? "midi" : unites[h12] + (h12 === 1 ? " heure" : " heures"))
        var s = { 0: "", 5: " et cinq", 10: " et dix", 15: " et quart", 20: " et vingt", 25: " et vingt-cinq", 30: " et demie",
                  35: " moins vingt-cinq", 40: " moins vingt", 45: " moins le quart", 50: " moins dix", 55: " moins cinq" }
        return ["Il est", heure + s[m]]
    }
    function calendrier(d) {
        var an = d.getFullYear(), mo = d.getMonth()
        var premier = (new Date(an, mo, 1).getDay() + 6) % 7, nb = new Date(an, mo + 1, 0).getDate()
        var l = [Etat.mois[mo] + " " + an, Reglages.en ? "Mo Tu We Th Fr Sa Su" : "Lu Ma Me Je Ve Sa Di"], ligne = ""
        for (var i = 0; i < premier; i++) ligne += "    "
        for (var j = 1; j <= nb; j++) {
            ligne += (j === d.getDate() ? "[" + (j < 10 ? " " : "") + j + "]" : " " + (j < 10 ? " " : "") + j + " ")
            if ((premier + j) % 7 === 0) { l.push(ligne); ligne = "" }
        }
        if (ligne !== "") l.push(ligne)
        return l
    }
    function lignes(type) {
        var d = Etat.minute
        if (type === "horloge-fine") return [Qt.formatTime(d, Reglages.val("ILE_HEURE", "24") === "12" ? "h:mm AP" : "hh:mm")]
        if (type === "horloge-segments") return [Qt.formatTime(d, "hh") + " : " + Qt.formatTime(d, "mm")]
        if (type === "horloge-mots") return mots(d)
        if (type === "calendrier") return calendrier(d)
        if (type === "citation") return citation !== "" ? [citation] : []
        if (type === "musique") return Etat.aMusique ? (Etat.artiste !== "" ? [Etat.titre, Etat.artiste] : [Etat.titre]) : []
        if (type === "jauges") return ["CPU  " + barre(cpu) + " " + pct(cpu), "RAM  " + barre(ram) + " " + pct(ram), "DSK  " + barre(disque) + " " + pct(disque)]
        return []
    }
    readonly property var base: ({ "horloge-fine": 96, "horloge-segments": 80, "horloge-mots": 34, "calendrier": 17, "citation": 22, "musique": 20, "jauges": 16 })
    readonly property var echelle: ({ "petit": 0.6, "moyen": 1, "grand": 1.5 })

    readonly property var fenetres: fenetresV.instances
    Variants {
        id: fenetresV
        model: w.liste.length > 0 ? Quickshell.screens : []
        PanelWindow {
            required property var modelData
            screen: modelData
            anchors { top: true; bottom: true; left: true; right: true }
            margins { top: 96; left: 48; right: 48; bottom: 48 }
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Bottom
            WlrLayershell.namespace: "nc-bureau-theme"
            color: "transparent"
            mask: Region {}
            visible: w.vu
            Repeater {
                model: w.liste
                Column {
                    required property var modelData
                    readonly property var texte: w.lignes(modelData.type)
                    readonly property bool droite: modelData.coin.indexOf("droite") >= 0
                    readonly property bool bas: modelData.coin.indexOf("bas") >= 0
                    readonly property bool milieu: modelData.coin === "centre"
                    visible: texte.length > 0
                    spacing: 2
                    x: milieu ? (parent.width - width) / 2 : (droite ? parent.width - width : 0)
                    y: milieu ? (parent.height - height) / 2 : (bas ? parent.height - height : 0)
                    width: Math.min(implicitWidth, parent.width / 2)
                    Repeater {
                        model: parent.texte
                        Texte {
                            required property string modelData
                            required property int index
                            width: parent.width
                            horizontalAlignment: parent.droite ? Text.AlignRight : (parent.milieu ? Text.AlignHCenter : Text.AlignLeft)
                            text: modelData
                            font.pixelSize: Math.round((w.base[parent.modelData.type] || 20) * (w.echelle[parent.modelData.taille] || 1) * (index === 0 || parent.modelData.type === "calendrier" || parent.modelData.type === "jauges" ? 1 : 0.6))
                            font.weight: parent.modelData.type === "horloge-fine" ? Font.ExtraLight : (parent.modelData.type === "horloge-segments" ? Font.Bold : Font.Normal)
                            font.family: parent.modelData.type === "calendrier" || parent.modelData.type === "jauges" || parent.modelData.type === "horloge-segments" ? "monospace" : Couleurs.police
                            secondaire: index > 0 || parent.modelData.type === "citation"
                            wrapMode: parent.modelData.type === "citation" ? Text.WordWrap : Text.NoWrap
                            elide: parent.modelData.type === "citation" ? Text.ElideNone : Text.ElideRight
                            style: Text.Raised; styleColor: Qt.rgba(0, 0, 0, 0.35)
                        }
                    }
                }
            }
        }
    }
}
