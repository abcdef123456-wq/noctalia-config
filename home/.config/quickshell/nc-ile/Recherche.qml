// Spotlight de l'île (Super + R) : la pilule s'étire en une longue capsule de recherche ; en tapant, quelques
// résultats compacts s'ajoutent dessous. ↑ ↓ pour choisir, Entrée pour lancer, Échap pour refermer.
// Appli déjà ouverte : Entrée amène sur sa fenêtre, Ctrl + Entrée en ouvre une nouvelle.
// On trouve : fenêtres ouvertes, applications (les plus utilisées d'abord), actions (verrouiller, mode jeu…), pages
// de l'île (son, Wi-Fi…), calculs et conversions (« 1,5 h en min », « 100 € en $ »), fichiers du dossier personnel.
// Préfixes : « g » Google, « yt » YouTube, « w » Wikipédia, « > » commande dans le terminal.
// Applications et fichiers : ~/.local/bin/nc-apps ; historique partagé avec le lanceur Noctalia (usage.json).
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Widgets
import Quickshell.Services.UPower

Item {
    id: r
    property bool actif: false
    readonly property int hauteurLigne: 46
    readonly property int hauteurVoulue: 56 + (resultats.length > 0 ? 6 + resultats.length * hauteurLigne + 8 : 0)

    property var applis: []
    property var fenetres: []
    property var usage: ({})
    property var fichiers: []
    property string calcul: ""
    property var resultats: []
    property int sel: 0
    readonly property string q: champ.text.trim()

    onActifChanged: {
        if (!actif) return
        champ.text = Etat.saisie; Etat.saisie = ""; sel = 0; fichiers = []; calcul = ""; entreeEnAttente = false
        lireApplis.running = true
        lireFenetres.running = true
        fichierUsage.reload()
        champ.forceActiveFocus()
        prendreClavier.essais = 0
        prendreClavier.restart()
    }
    // Curseur directement dans la barre : l'île ne reçoit le clavier de Hyprland qu'un instant après s'être ouverte,
    // la demande est donc répétée jusqu'à ce que la barre l'ait vraiment (1 s au plus)
    Timer {
        id: prendreClavier
        property int essais: 0
        interval: 60; repeat: true
        onTriggered: {
            if (!r.actif || champ.activeFocus || ++essais > 16) { stop(); return }
            champ.forceActiveFocus()
        }
    }

    Connections { target: Etat; function onValiderRecherche() { if (r.actif) r.valider(r.sel, false) } }

    // ── Sources ──
    Process {
        id: lireApplis
        command: [Etat.bin + "nc-apps", "list"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { r.applis = JSON.parse(text) } catch (e) {}
                r.chercher()
                // Entrée tapée avant que les applis soient chargées : validée maintenant, sur la liste complète
                if (r.entreeEnAttente) { r.entreeEnAttente = false; r.valider(r.sel, false) }
            }
        }
    }
    Process {
        id: lireFenetres
        command: ["hyprctl", "clients", "-j"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { r.fenetres = JSON.parse(text).filter(c => c.mapped && c.title !== "" && c.workspace && c.workspace.id > 0) } catch (e) {}
                r.chercher()
            }
        }
    }
    FileView {
        id: fichierUsage
        path: Quickshell.env("HOME") + "/.local/state/noctalia/plugins/data/nc/launcher/usage.json"
        printErrors: false
        onLoaded: { try { r.usage = JSON.parse(text()) } catch (e) { r.usage = ({}) } }
    }
    Process {
        id: lireFichiers
        property string pour: ""
        stdout: StdioCollector {
            onStreamFinished: {
                if (lireFichiers.pour !== r.q) return
                try { r.fichiers = JSON.parse(text).slice(0, 3) } catch (e) { r.fichiers = [] }
                r.chercher()
            }
        }
    }
    Process {
        id: calculer
        property string pour: ""
        stdout: StdioCollector {
            onStreamFinished: {
                if (calculer.pour !== r.q) return
                var t = text.trim().split("\n").pop()
                // Rien d'utile (texte non compris, même chose que la saisie) : pas de ligne de calcul
                r.calcul = t === "" || t === calculer.pour || /[A-Za-z]·|rem\(|^\(/.test(t) ? "" : t
                r.chercher()
            }
        }
    }
    // Fichiers et calcul : lancés un instant après la dernière touche
    Timer {
        id: attente
        interval: 120
        onTriggered: {
            var q = r.q
            if (q.length >= 3 && !/^(>|g |yt |w )/.test(q)) {
                lireFichiers.pour = q
                lireFichiers.command = [Etat.bin + "nc-apps", "files", q]
                lireFichiers.running = true
            }
            if (/\d/.test(q) && /[-+*/^%()√]|\s(en|to|in)\s|sqrt|sin|cos|log/.test(q)) {
                calculer.pour = q
                calculer.command = ["qalc", "-t", "-set", "mix 0", q.replace(/\s+en\s+/g, " to ")]
                calculer.running = true
            }
        }
    }

    // ── Actions et pages ──
    readonly property var actions: [
        { t: "Verrouiller", k: "verrouiller lock écran", g: "lock", f: () => Etat.faire(["noctalia", "msg", "session", "lock"]) },
        { t: "Mettre en veille", k: "veille suspend dormir", g: "bedtime", f: () => Etat.faire(["systemctl", "suspend"]) },
        { t: "Éteindre, redémarrer…", k: "éteindre redémarrer arrêt shutdown reboot quitter session", g: "power_settings_new", f: () => Etat.faire(["noctalia", "msg", "panel-toggle", "session-panel"]) },
        { t: "Mode jeu", k: "mode jeu game gaming", g: "sports_esports", f: () => Etat.faire(["hyprctl", "eval", "nc.mode_jeu()"]) },
        { t: "Économie d'énergie", k: "économie batterie eco énergie", g: "battery_saver", f: () => Etat.choisirProfil(PowerProfile.PowerSaver) },
        { t: "Équilibré", k: "équilibré énergie normal", g: "battery_full", f: () => Etat.choisirProfil(PowerProfile.Balanced) },
        { t: "Performance", k: "performance énergie puissance nvidia", g: "bolt", f: () => Etat.choisirProfil(PowerProfile.Performance) },
        { t: "Activer ou couper le Wi-Fi", k: "wifi wi-fi réseau internet", g: "wifi", f: () => Etat.faire(["noctalia", "msg", "wifi-toggle"]) },
        { t: "Activer ou couper le Bluetooth", k: "bluetooth", g: "bluetooth", f: () => Etat.faire(["noctalia", "msg", "bluetooth-toggle"]) },
        { t: "Concentration", k: "concentration ne pas déranger dnd notifications", g: "dark_mode", f: () => Notifs.basculerConcentration() },
        { t: "Nuit (tons chauds)", k: "nuit night lumière bleue", g: "wb_twilight", f: () => { Etat.nuit = !Etat.nuit; Etat.faire(["noctalia", "msg", "nightlight-force-toggle"]) } },
        { t: "Thème clair ou sombre", k: "thème clair sombre dark light", g: "contrast", f: () => Etat.faire(["noctalia", "msg", "theme-mode-toggle"]) },
        { t: "Rester éveillé", k: "rester éveillé café caféine veille", g: "coffee", f: () => Etat.basculerCafe() },
        { t: "Capture d'une zone", k: "capture écran screenshot", g: "screenshot_region", f: () => Quickshell.execDetached(["sh", "-c", "sleep 0.4; ~/.local/bin/nc-capture zone"]) },
        { t: "Presse-papiers", k: "presse-papiers clipboard copier coller", g: "content_paste", f: () => Quickshell.execDetached(["noctalia", "msg", "panel-toggle", "launcher", "/clipboard"]) },
        { t: "Fond d'écran suivant", k: "fond écran wallpaper suivant", g: "wallpaper", f: () => Etat.faire(["noctalia", "msg", "wallpaper-next"]) },
        { t: "Raccourcis clavier", k: "raccourcis clavier touches aide", g: "keyboard", f: () => Quickshell.execDetached([Etat.bin + "nc-shell-msg", "keys"]) }
    ]
    readonly property var pagesIle: [
        { t: "Son", k: "son volume audio sortie micro haut-parleurs casque", g: "volume_up", p: "son" },
        { t: "Wi-Fi", k: "wifi wi-fi réseau internet réseaux", g: "wifi", p: "reseau" },
        { t: "Bluetooth", k: "bluetooth appareils casque souris", g: "bluetooth", p: "bluetooth" },
        { t: "Notifications", k: "notifications messages", g: "notifications", p: "notifications" },
        { t: "Système", k: "système processeur mémoire batterie température disque énergie", g: "memory", p: "systeme" },
        { t: "Calendrier", k: "calendrier date agenda", g: "calendar_month", p: "calendrier" },
        { t: "Minuteur", k: "minuteur timer chrono", g: "timer", p: "minuteur" },
        { t: "Centre de contrôle", k: "centre contrôle réglages luminosité", g: "toggle_on", p: "centre" }
    ]

    // ── Recherche ──
    function sansAccents(s) { return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "") }
    // Score d'un nom : début 100, début d'un mot 80, dedans 55 (seulement si large), sinon 0.
    // Mots : séparés par espace, tiret, point, tiret bas (« org.gnome.Nautilus », « Wi-Fi »).
    function score(q, texte, large) {
        var t = sansAccents(texte)
        if (t === "" || q === "") return 0
        if (t.startsWith(q)) return 100
        var mots = t.split(/[\s._\-/]+/)
        for (var i = 0; i < mots.length; i++) if (mots[i].startsWith(q)) return 80
        return large && t.indexOf(q) >= 0 ? 55 : 0
    }
    // Icône d'un fichier selon son extension (icônes du thème NC)
    function iconeFichier(nom, dossier) {
        if (dossier) return "folder"
        var e = (nom.split(".").pop() || "").toLowerCase()
        var t = { mp4: "video-x-generic", mkv: "video-x-generic", webm: "video-x-generic", mov: "video-x-generic", avi: "video-x-generic",
                  mp3: "audio-x-generic", flac: "audio-x-generic", ogg: "audio-x-generic", wav: "audio-x-generic", m4a: "audio-x-generic",
                  png: "image-x-generic", jpg: "image-x-generic", jpeg: "image-x-generic", webp: "image-x-generic", gif: "image-x-generic", svg: "image-x-generic",
                  pdf: "application-pdf", zip: "package-x-generic", tar: "package-x-generic", gz: "package-x-generic", xz: "package-x-generic", "7z": "package-x-generic", rar: "package-x-generic",
                  py: "text-x-script", js: "text-x-script", ts: "text-x-script", sh: "text-x-script", c: "text-x-script", cpp: "text-x-script", h: "text-x-script",
                  rs: "text-x-script", go: "text-x-script", lua: "text-x-script", qml: "text-x-script", java: "text-x-script", css: "text-x-script",
                  json: "application-json", jsonl: "application-json", toml: "application-json", yaml: "application-json", yml: "application-json", xml: "application-json",
                  md: "text-markdown", html: "text-html", htm: "text-html", odt: "x-office-document", docx: "x-office-document", doc: "x-office-document",
                  ods: "x-office-spreadsheet", xlsx: "x-office-spreadsheet", csv: "x-office-spreadsheet", odp: "x-office-presentation", pptx: "x-office-presentation",
                  ttf: "font-x-generic", otf: "font-x-generic", iso: "application-x-cd-image" }[e]
        return t || "text-x-generic"
    }
    // Fenêtre déjà ouverte d'une appli (la plus récemment utilisée), sinon null
    function fenetreDe(ap) {
        var noms = [ap.wmclass, ap.id, ap.exe === "env" ? "" : ap.exe].filter(x => x).map(x => x.toLowerCase())
        var meilleure = null
        for (var i = 0; i < fenetres.length; i++) {
            var c = (fenetres[i].class || "").toLowerCase()
            if (noms.indexOf(c) >= 0 && (!meilleure || fenetres[i].focusHistoryID < meilleure.focusHistoryID)) meilleure = fenetres[i]
        }
        return meilleure
    }
    function allerA(adresse) { Etat.faire(["hyprctl", "eval", "hl.dispatch(hl.dsp.focus({ window = 'address:" + adresse + "' }))"]) }
    function poidsUsage(id) {
        var u = usage[id]
        if (!u) return 1
        var h = (Date.now() / 1000 - (u.t || 0)) / 3600
        return 1 + Math.min(1.2, (u.n || 0) / 15) * (h < 24 ? 1.4 : (h < 168 ? 1.1 : 0.8))
    }

    onQChanged: { sel = 0; fichiers = []; calcul = ""; attente.restart(); chercher() }

    function chercher() {
        var q = r.q, qa = sansAccents(q), out = []
        if (q === "") { resultats = []; return }

        // Préfixes : web et commande
        var web = [["g ", "Google", "https://www.google.com/search?q="], ["yt ", "YouTube", "https://www.youtube.com/results?search_query="],
                   ["w ", "Wikipédia", "https://fr.wikipedia.org/w/index.php?search="]]
        for (var w = 0; w < web.length; w++) {
            if (q.startsWith(web[w][0]) && q.length > web[w][0].length) {
                var terme = q.slice(web[w][0].length)
                var url = web[w][2] + encodeURIComponent(terme)
                resultats = [{ titre: terme, sous: "Rechercher sur " + web[w][1], glyphe: "travel_explore", f: () => Qt.openUrlExternally(url) }]
                return
            }
        }
        if (q.startsWith(">")) {
            var c = q.slice(1).trim()
            resultats = c === "" ? [] : [{ titre: c, sous: "Commande dans le terminal", glyphe: "terminal",
                                          f: () => Quickshell.execDetached(["kitty", "--hold", "sh", "-c", c]) }]
            return
        }

        // Calcul en tête
        if (calcul !== "") {
            var res = calcul
            out.push({ titre: "= " + res, sous: "Calcul · Entrée pour copier", glyphe: "calculate", s: 1000,
                       f: () => Quickshell.execDetached(["wl-copy", res.replace(/^≈?\s*/, "")]) })
        }
        // Applications : déjà ouverte → Entrée y va (Ctrl + Entrée : nouvelle fenêtre), sinon Entrée la lance
        var prises = {}
        for (var a = 0; a < applis.length; a++) {
            var ap = applis[a]
            var sa = Math.max(score(qa, ap.name, true), score(qa, ap.generic, false) - 20, score(qa, ap.id, false) - 15, score(qa, ap.keywords, false) - 30)
            if (sa > 0) {
                var id = ap.id, fen = fenetreDe(ap)
                var item = { titre: ap.name, icone: Quickshell.iconPath(ap.icon, true), glyphe: "apps", s: sa * poidsUsage(id) + (fen ? 15 : 0) }
                if (fen) {
                    var adresse = fen.address
                    prises[adresse] = true
                    item.sous = "Ouverte · bureau " + fen.workspace.name
                    item.aide = "↵ y aller · Ctrl ↵ nouvelle"
                    item.f = () => r.allerA(adresse)
                    item.nouveau = () => r.lancer(id)
                } else {
                    item.sous = ap.generic || "Application"
                    item.f = () => r.lancer(id)
                }
                out.push(item)
            }
        }
        // Fenêtres ouvertes (celles qui ne sont pas déjà proposées par leur appli)
        for (var i = 0; i < fenetres.length; i++) {
            var fe = fenetres[i]
            if (prises[fe.address]) continue
            var sf = Math.max(score(qa, fe.class, false), score(qa, fe.initialTitle, false), score(qa, fe.title, false) - 25)
            if (sf > 0) {
                var adr = fe.address
                out.push({ titre: fe.title, sous: "Fenêtre ouverte · bureau " + fe.workspace.name, icone: Quickshell.iconPath(fe.class, true) || Quickshell.iconPath(fe.class.toLowerCase(), true),
                           glyphe: "select_window", s: sf + 30, f: () => r.allerA(adr) })
            }
        }
        // Pages de l'île et actions
        for (var p = 0; p < pagesIle.length; p++) {
            var pg = pagesIle[p], sp = Math.max(score(qa, pg.t, true), score(qa, pg.k, false) - 15)
            if (sp > 0) { var nom = pg.p; out.push({ titre: pg.t, sous: "Dans l'île", glyphe: pg.g, s: sp - 5, page: nom }) }
        }
        for (var k = 0; k < actions.length; k++) {
            var ac = actions[k], sc = Math.max(score(qa, ac.t, true), score(qa, ac.k, false) - 15)
            if (sc > 0) out.push({ titre: ac.t, sous: "Action", glyphe: ac.g, s: sc - 8, f: ac.f })
        }
        // Fichiers
        for (var n = 0; n < fichiers.length; n++) {
            var fi = fichiers[n], chemin = fi.path
            out.push({ titre: fi.name, sous: (fi.dir ? "Dossier · " : "Fichier · ") + fi.parent,
                       icone: Quickshell.iconPath(iconeFichier(fi.name, fi.dir), true), glyphe: "description",
                       s: Math.min(70, Math.max(15, score(qa, fi.name, true) * 0.75)),   // jamais devant une appli qui commence par la saisie
                       f: () => Quickshell.execDetached([Etat.bin + "nc-apps", "open", chemin]) })
        }
        out.sort((x, y) => y.s - x.s)
        resultats = out.slice(0, 6)
        if (sel >= resultats.length) sel = Math.max(0, resultats.length - 1)
    }

    function lancer(id) {
        Quickshell.execDetached([Etat.bin + "nc-apps", "launch", id])
        // Suivre l'appli : sa fenêtre peut s'ouvrir sur un autre bureau (Discord réduit dans la zone de notification
        // ressort là où il était) ; dès qu'elle apparaît, on y va
        var ap = applis.find(x => x.id === id)
        if (ap) {
            suivi.noms = [ap.wmclass, ap.id, ap.exe === "env" ? "" : ap.exe].filter(x => x).map(x => x.toLowerCase())
            suivi.avant = fenetres.map(f => f.address)
            suivi.fin = Date.now() + 10000
            suivi.restart()
        }
        try {
            var u = Object.assign({}, usage)
            var e = u[id] || { n: 0 }
            u[id] = { n: (e.n || 0) + 1, t: Math.floor(Date.now() / 1000) }
            usage = u
            fichierUsage.setText(JSON.stringify(u))
        } catch (err) {}
    }
    Timer {
        id: suivi
        property var noms: []
        property var avant: []
        property real fin: 0
        interval: 400; repeat: true
        onTriggered: { if (Date.now() > fin) stop(); else if (!chercheFenetre.running) chercheFenetre.running = true }
    }
    Process {
        id: chercheFenetre
        command: ["hyprctl", "clients", "-j"]
        stdout: StdioCollector {
            onStreamFinished: {
                var l = []
                try { l = JSON.parse(text) } catch (e) { return }
                var f = l.find(c => c.mapped && suivi.noms.indexOf((c.class || "").toLowerCase()) >= 0 && suivi.avant.indexOf(c.address) < 0)
                if (f) { suivi.stop(); r.allerA(f.address) }
            }
        }
    }
    property bool entreeEnAttente: false
    function valider(i, nouveau) {
        // Applis pas encore chargées (on tape vite juste après Super + R) : on attend la liste avant de choisir
        if (lireApplis.running || applis.length === 0) { entreeEnAttente = true; return }
        var x = resultats[i]
        if (!x) return
        if (x.page) { Etat.recherche = false; Etat.aller(x.page); return }
        Etat.fermer()
        if (nouveau && x.nouveau) x.nouveau(); else x.f()
    }

    // ── Dessin ──
    // Barre de recherche
    Item {
        id: barre
        width: parent.width; height: 56
        Ico { id: loupe; x: 22; anchors.verticalCenter: parent.verticalCenter; nom: "search"; taille: 22; color: "#98989d" }
        TextInput {
            id: champ
            anchors.left: loupe.right; anchors.leftMargin: 12; anchors.right: parent.right; anchors.rightMargin: 22
            anchors.verticalCenter: parent.verticalCenter
            color: "white"; selectionColor: "#0a84ff"; selectedTextColor: "white"
            font.family: "Adwaita Sans"; font.pixelSize: 19
            clip: true
            cursorVisible: activeFocus
            Keys.onEscapePressed: Etat.fermer()
            Keys.onDownPressed: r.sel = Math.min(r.resultats.length - 1, r.sel + 1)
            Keys.onUpPressed: r.sel = Math.max(0, r.sel - 1)
            Keys.onTabPressed: r.sel = r.resultats.length > 0 ? (r.sel + 1) % r.resultats.length : 0
            Keys.onReturnPressed: e => r.valider(r.sel, (e.modifiers & Qt.ControlModifier) !== 0)
            Keys.onEnterPressed: e => r.valider(r.sel, (e.modifiers & Qt.ControlModifier) !== 0)
            Texte {
                visible: champ.text === ""
                anchors.verticalCenter: parent.verticalCenter
                text: "Rechercher"; secondaire: true; font.pixelSize: 19
            }
        }
    }

    // Résultats
    Column {
        id: liste
        anchors.top: barre.bottom; anchors.topMargin: 6
        x: 8; width: parent.width - 16
        Repeater {
            model: r.resultats
            Rectangle {
                id: ligne
                required property var modelData
                required property int index
                readonly property bool choisi: index === r.sel
                width: liste.width; height: r.hauteurLigne; radius: 14
                color: choisi ? "#2c2c2e" : "transparent"
                Item {
                    id: ic
                    x: 12; anchors.verticalCenter: parent.verticalCenter
                    width: 28; height: 28
                    Image {
                        id: img
                        anchors.fill: parent
                        source: ligne.modelData.icone || ""
                        sourceSize: Qt.size(56, 56)
                        visible: status === Image.Ready
                    }
                    Ico { anchors.centerIn: parent; nom: ligne.modelData.glyphe || "search"; taille: 22; color: "#d1d1d6"; visible: img.status !== Image.Ready }
                }
                Texte {
                    anchors.left: ic.right; anchors.leftMargin: 12; anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 12 - 28 - 12 - sous.width - 40
                    text: ligne.modelData.titre; font.pixelSize: 15; font.weight: ligne.choisi ? Font.DemiBold : Font.Normal
                }
                Texte {
                    id: sous
                    anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(implicitWidth, 320)
                    text: ligne.modelData.sous + (ligne.choisi ? "  ·  " + (ligne.modelData.aide || "↵") : ""); secondaire: true; font.pixelSize: 13
                    horizontalAlignment: Text.AlignRight
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true
                    onEntered: r.sel = ligne.index
                    onClicked: e => r.valider(ligne.index, (e.modifiers & Qt.ControlModifier) !== 0)
                }
            }
        }
    }
}
