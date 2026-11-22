// Widgets de bureau choisis par le thème (champ « widgets » du thème, écrit dans style.conf :
// WIDGETS_THEME=type:coin:taille[:style[:chiffres[:variante]]],…). Créé par shell.qml ; ne montre rien si WIDGETS_BUREAU n'est pas « oui » ou si le
// thème n'a pas de widgets (alors Bureau.qml garde l'horloge et la date d'avant, à l'identique).
// Types : horloge-fine, horloge-mots, horloge-segments, horloge-geante, calendrier, date, citation, musique, jauges, anneau,
// jauge-aiguille, meteo, accueil. Chiffres d'une horloge : un fichier Chiffres<Nom>.qml par style (CarteWidget.qml). Coins : haut-gauche, haut-droite, bas-gauche, bas-droite, centre. Tailles : petit, moyen, grand.
// Styles (CarteWidget.qml) : texte (sans carte, le défaut), carte, carte-ronde, brutal. 8 widgets au plus : ceux d'un même
// coin s'empilent (disposer), jamais l'un sur l'autre ni hors de l'écran.
// Énergie : aucune pendule à soi. Horloges, date, accueil, calendrier et citation suivent Etat.minute ; météo et musique,
// les signaux d'Etat (nc-meteo et MPRIS déjà lus par l'île) ; la citation relit son fichier une fois par jour. Jauges,
// anneau et jauge à aiguille : un relevé à chaque minute (Etat.minute, en même temps que l'heure : rien ne bouge entre
// deux), plus un seul minuteur de 2 s, une fois, quand l'un d'eux devient visible (le processeur se mesure entre deux
// relevés). Un seul échantillonnage pour tous les écrans. Ni animation ni flou.
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
        for (var i = 0; i < parts.length && r.length < 8; i++) {
            var p = parts[i].trim().split(":")
            if (p.length >= 3 && p.length <= 6)
                r.push({ type: p[0], coin: p[1], taille: p[2], style: ["carte", "carte-ronde", "brutal"].indexOf(p[3]) >= 0 ? p[3] : "texte",
                         chiffres: /^[a-z]+$/.test(p[4] || "") ? p[4] : "", variante: p[5] || "" })
        }
        return r
    }
    readonly property bool vu: Etat.ecranVu && !Etat.widgetsCaches
    readonly property bool aJauges: { for (var i = 0; i < liste.length; i++) if (["jauges", "anneau", "jauge-aiguille"].indexOf(liste[i].type) >= 0) return true; return false }
    readonly property bool aCitation: { for (var i = 0; i < liste.length; i++) if (liste[i].type === "citation") return true; return false }
    // Musique : seulement quand un titre JOUE (en pause ou sans titre, la carte n'est pas là : jamais de pochette vide)
    readonly property bool musique: Etat.aMusique && Etat.joue
    // WIDGETS_POLICE : une liste « A, B », la première installée (même règle qu'ILE_POLICE) ; vide ou aucune : celle de l'île.
    // Les petits textes (sous 30 px) prennent la suivante installée de la liste, s'il y en a une : une police à points
    // (Doto) pour l'heure, une police pleine pour les libellés (« Doto, JetBrains Mono »)
    readonly property var polices: {
        var installees = Qt.fontFamilies(), l = String(Reglages.val("WIDGETS_POLICE", "")).split(","), r = []
        for (var i = 0; i < l.length; i++) if (l[i].trim() !== "" && installees.indexOf(l[i].trim()) >= 0) r.push(l[i].trim())
        return r.length > 0 ? r : [Couleurs.police]
    }
    readonly property string police: polices[0]
    readonly property string policePetite: polices[Math.min(1, polices.length - 1)]
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

    // ── Jauges : CPU (/proc/stat), RAM (/proc/meminfo), disque (df, un relevé sur quinze) ──
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
    readonly property var minute: Etat.minute
    onMinuteChanged: if (vu && aJauges) echantillon()
    readonly property var minuteur: echantillonneur
    Timer { id: echantillonneur; interval: 2000; running: w.vu && w.aJauges; onTriggered: w.echantillon() }
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
        if (type === "horloge-mots") return mots(d)
        if (type === "calendrier") return calendrier(d)
        if (type === "citation") return citation !== "" ? [citation] : []
        if (type === "musique") return musique ? (Etat.artiste !== "" ? [Etat.titre, Etat.artiste] : [Etat.titre]) : []
        if (type === "jauges") return ["CPU  " + barre(cpu) + " " + pct(cpu), "RAM  " + barre(ram) + " " + pct(ram), "DSK  " + barre(disque) + " " + pct(disque)]
        return []
    }
    function heure(d) { return Qt.formatTime(d, Reglages.val("ILE_HEURE", "24") === "12" ? "h:mm" : "hh:mm") }
    function accueil(d) {
        var h = d.getHours()
        if (Reglages.en) return h >= 5 && h < 12 ? "Good morning" : (h >= 12 && h < 18 ? "Good afternoon" : "Good evening")
        return h >= 5 && h < 18 ? "Bonjour" : "Bonsoir"
    }
    function phraseMeteo(m) {
        var t = (m.temp !== undefined ? m.temp : "") + "°"
        return !Reglages.en && m.texte ? t + " et " + String(m.texte).toLowerCase() : t
    }

    // ── Lisibilité (WCAG) : luminance relative, contraste, mélange en sRGB (comme le dessin de Qt) ──
    function lum(c) {
        function f(x) { return x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4) }
        return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b)
    }
    function contraste(a, b) { var x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05) }
    function melange(a, b, f) { return Qt.rgba(a.r + (b.r - a.r) * f, a.g + (b.g - a.g) * f, a.b + (b.b - a.b) * f, 1) }
    // La couleur c, rapprochée du blanc ou du noir (le plus lointain du fond) jusqu'à 4,6:1 sur ce fond (4,5 et l'arrondi)
    function lisible(c, fond) {
        var cible = contraste(Qt.rgba(1, 1, 1, 1), fond) >= contraste(Qt.rgba(0, 0, 0, 1), fond) ? Qt.rgba(1, 1, 1, 1) : Qt.rgba(0, 0, 0, 1)
        for (var f = 0; f < 1; f += 0.05) { var m = melange(c, cible, f); if (contraste(m, fond) >= 4.6) return m }
        return cible
    }
    // Voile d'un widget sans carte : 0,55 au moins, plus opaque tant que le texte n'a pas 4,6:1 sur le pire fond d'écran
    function voile(texte, fond, pire) {
        for (var a = 0.55; a < 1; a += 0.05) if (contraste(texte, melange(fond, pire, 1 - a)) >= 4.6) return a
        return 1
    }

    readonly property var base: ({ "horloge-fine": 96, "horloge-segments": 80, "horloge-mots": 34, "calendrier": 17, "citation": 22, "musique": 20, "jauges": 16 })
    readonly property var echelle: ({ "petit": 0.6, "moyen": 1, "grand": 1.5 })

    // Place les widgets d'un écran (largeur l, hauteur h ; tailles[i] = [largeur, hauteur], 0 : rien à montrer). Par coin,
    // une colonne (comme une colonne de cartes) ; seules les cartes rondes qui se suivent se rangent côte à côte, tant
    // qu'elles tiennent dans la moitié de l'écran (tout l'écran au centre), à la taille de la plus grande. Les cartes seules
    // sur leur rangée prennent la largeur de la colonne (une colonne nette). Puis, dans l'ordre de la liste, un widget qui
    // sortirait de l'écran ou toucherait un widget déjà posé (un autre coin) n'est pas montré.
    // Rend, par widget, { x, y, l, h, v } (v : montré) ou undefined.
    function disposer(liste, tailles, l, h, ecart) {
        var places = [], poses = [], coins = ["haut-gauche", "haut-droite", "bas-gauche", "bas-droite", "centre"]
        for (var c = 0; c < coins.length; c++) {
            var ids = []
            for (var i = 0; i < liste.length; i++) if (liste[i].coin === coins[c] && tailles[i] && tailles[i][0] > 0) ids.push(i)
            if (ids.length === 0) continue
            var lignes = [], r = null, place = coins[c] === "centre" ? l : (l - ecart) / 2
            for (var n = 0; n < ids.length; n++) {
                var t = tailles[ids[n]], rond = liste[ids[n]].style === "carte-ronde"
                if (r && r.rond && rond && (r.ids.length + 1) * Math.max(r.h, t[1]) + r.ids.length * ecart <= place) {
                    r.ids.push(ids[n]); r.h = Math.max(r.h, t[1]); r.l = r.ids.length * r.h + (r.ids.length - 1) * ecart
                } else { r = { ids: [ids[n]], l: t[0], h: t[1], rond: rond }; lignes.push(r) }
            }
            var col = Math.max.apply(null, lignes.map(x => x.l))
            var total = lignes.reduce((s, x) => s + x.h, 0) + ecart * (lignes.length - 1)
            var centre = coins[c] === "centre", x0 = centre ? (l - col) / 2 : (coins[c].indexOf("droite") >= 0 ? l - col : 0)
            // trop haut : ce sont les derniers qui sortent (et ne sont pas montrés), jamais les premiers
            var y = Math.max(0, centre ? (h - total) / 2 : (coins[c].indexOf("bas") === 0 ? h - total : 0))
            for (var m = 0; m < lignes.length; m++) {
                var x = centre ? (l - lignes[m].l) / 2 : x0
                for (var q = 0; q < lignes[m].ids.length; q++) {
                    var j = lignes[m].ids[q], st = liste[j].style
                    var lj = lignes[m].rond ? lignes[m].h : (st === "carte" || st === "brutal" ? col : tailles[j][0])
                    places[j] = { x: Math.round(x), y: Math.round(y), l: lj, h: lignes[m].rond ? lignes[m].h : tailles[j][1] }
                    x += lj + ecart
                }
                y += lignes[m].h + ecart
            }
        }
        for (var k = 0; k < liste.length; k++) {
            var p = places[k]
            if (!p) continue
            p.v = p.x >= 0 && p.y >= 0 && p.x + p.l <= l && p.y + p.h <= h
            for (var z = 0; p.v && z < poses.length; z++) {
                var o = poses[z]
                if (p.x < o.x + o.l && o.x < p.x + p.l && p.y < o.y + o.h && o.y < p.y + p.h) p.v = false
            }
            if (p.v) poses.push(p)
        }
        return places
    }

    readonly property var fenetres: fenetresV.instances
    Variants {
        id: fenetresV
        model: w.liste.length > 0 ? Quickshell.screens : []
        PanelWindow {
            id: fen
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
            // Échelle de l'écran (1 : 1600 px de haut, marges comprises) et écart entre deux widgets
            readonly property real k: Math.max(0.5, Math.min(2, (height + 144) / 1600))
            readonly property int ecart: Math.round(24 * k)
            property var tailles: []
            function annoncer(i, l, h) { if (tailles[i] && tailles[i][0] === l && tailles[i][1] === h) return; var t = tailles.slice(); t[i] = [l, h]; tailles = t }
            readonly property var places: w.disposer(w.liste, tailles, width, height, ecart)
            Repeater {
                model: w.liste
                CarteWidget {
                    required property var modelData
                    required property int index
                    readonly property var place: fen.places[index]
                    objectName: "nc-widget-" + modelData.type
                    donnees: w
                    widget: modelData
                    k: fen.k
                    hauteurEcran: fen.height + 144
                    largeurMax: modelData.coin === "centre" ? fen.width : Math.floor((fen.width - fen.ecart) / 2)
                    x: place ? place.x : 0
                    y: place ? place.y : 0
                    width: place ? place.l : implicitWidth; height: place ? place.h : implicitHeight
                    visible: !!place && place.v
                    onImplicitWidthChanged: fen.annoncer(index, implicitWidth, implicitHeight)
                    onImplicitHeightChanged: fen.annoncer(index, implicitWidth, implicitHeight)
                    Component.onCompleted: fen.annoncer(index, implicitWidth, implicitHeight)
                }
            }
        }
    }
}
