// Spotlight de l'île (Super + R) : la pilule s'étire en une longue capsule de recherche ; en tapant, quelques
// résultats compacts s'ajoutent dessous. ↑ ↓ pour choisir, Entrée pour lancer, Échap pour refermer.
// Appli déjà ouverte : Entrée en ouvre une nouvelle fenêtre, Ctrl + Entrée amène sur celle qui est ouverte (inversé avec
// SPOTLIGHT_ENTREE=aller dans nc-reglages).
// On trouve : fenêtres ouvertes, applications (les plus utilisées d'abord), actions (verrouiller, mode jeu…), pages
// de l'île (son, Wi-Fi…), calculs et conversions (« 1,5 h en min », « 100 € en $ »), fichiers du dossier personnel.
// Préfixes : « g » Google, « yt » YouTube, « w » Wikipédia, « > » commande dans le terminal, « ? » question à une IA
// (réponse dans le Spotlight ; sa commande proposée se lance avec Entrée : nc-demander). Une saisie qui commence par
// un programme (htop, ping…) propose aussi de la lancer dans le terminal.
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
    readonly property int hauteurVoulue: 56 + (zoneReponse.visible ? zoneReponse.height + 10 : 0)
                                         + (resultats.length > 0 ? 6 + resultats.length * hauteurLigne + 8 : 0)

    // Question à une IA (« ? … ») : réponse, et la commande qu'elle propose
    property var execs: ({})                 // programmes du PATH (saisie qui commence par une commande)
    property string nomIA: ""
    property string questionPosee: ""
    property string reponse: ""
    property string commandeIA: ""
    readonly property bool reflechit: demandeur.running
    function demander(question) {
        if (question === "" || demandeur.running) return
        questionPosee = question; reponse = ""; commandeIA = ""
        demandeur.command = [Etat.bin + "nc-demander", "--flux", question]
        demandeur.running = true
        chercher()
    }
    // Dans le terminal, avec le PATH de l'utilisateur (l'île n'a que celui du système)
    function lancerCommande(c) { Quickshell.execDetached(["kitty", "--hold", "sh", "-c", "PATH=\"$HOME/.local/bin:$HOME/bin:$PATH\"; " + c]) }

    property var applis: []
    property var fenetres: []
    property var usage: ({})
    property var fichiers: []
    property string calcul: ""
    property var resultats: []
    property int sel: 0
    readonly property string q: champ.text.trim()

    // Chargée à la demande : déjà active à sa création (une seule initialisation, une fois tout créé) ; rouverte avant
    // d'être déchargée : réinitialisée au changement de « actif »
    property bool cree: false
    onActifChanged: if (actif && cree) demarrer()
    Component.onCompleted: { cree = true; if (actif) demarrer() }
    function demarrer() {
        champ.text = Etat.saisie; Etat.saisie = ""; sel = 0; fichiers = []; calcul = ""; entreeEnAttente = false
        lireApplis.running = true
        lireFenetres.running = true
        if (Object.keys(execs).length === 0) lireExecs.running = true
        if (nomIA === "") lireIA.running = true
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
        id: lireExecs
        command: ["sh", "-c", "IFS=:; for d in $HOME/.local/bin:$HOME/bin:$PATH; do ls -1 \"$d\" 2>/dev/null; done | sort -u"]
        stdout: StdioCollector { onStreamFinished: { var e = {}; text.split("\n").forEach(x => { if (x) e[x] = true }); r.execs = e } }
    }
    Process {
        id: lireIA
        command: [Etat.bin + "nc-demander", "--ia"]
        stdout: StdioCollector { onStreamFinished: r.nomIA = text.trim() || "-" }
    }
    // Réponse affichée pendant qu'elle s'écrit ; à la fin, la ligne « $ … » devient la commande à lancer
    property string brut: ""
    Process {
        id: demandeur
        onRunningChanged: {
            if (running) { r.brut = "" }
            else {
                var l = r.brut.trim().split("\n")
                var c = l.length && l[l.length - 1].trim().startsWith("$ ") ? l.pop().trim().slice(2).trim() : ""
                r.reponse = l.join("\n").trim() || Reglages.t("Pas de réponse.", "No answer.")
                r.commandeIA = c
            }
            r.chercher()
        }
        stdout: SplitParser {
            onRead: ligne => {
                try { r.brut += JSON.parse(ligne).t || "" } catch (e) { return }
                r.reponse = r.brut
            }
        }
    }
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
            if (q.length >= 3 && !/^(>|g |yt |w )/.test(q) && Reglages.val("SPOTLIGHT_FICHIERS", "oui") !== "non") {
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
        { t: Reglages.t("Verrouiller", "Lock"), k: "verrouiller lock écran screen", g: "lock", f: () => Etat.faire(["noctalia", "msg", "session", "lock"]) },
        { t: Reglages.t("Mettre en veille", "Sleep"), k: "veille suspend dormir sleep", g: "bedtime", f: () => Etat.faire(["systemctl", "suspend"]) },
        { t: Reglages.t("Éteindre, redémarrer…", "Shut Down, Restart…"), k: "éteindre redémarrer arrêt shutdown reboot quitter session shut power off restart log out logout", g: "power_settings_new", f: () => Etat.faire(["noctalia", "msg", "panel-toggle", "session"]) },
        { t: Reglages.t("Mode jeu", "Game Mode"), k: "mode jeu game gaming", g: "sports_esports", f: () => Etat.faire(["hyprctl", "eval", "nc.mode_jeu()"]) },
        { t: Reglages.t("Économie d'énergie", "Power Saver"), k: "économie batterie eco énergie power saver low battery energy", g: "battery_saver", f: () => Etat.choisirProfil(PowerProfile.PowerSaver) },
        { t: Reglages.t("Équilibré", "Balanced"), k: "équilibré énergie normal balanced power energy", g: "battery_full", f: () => Etat.choisirProfil(PowerProfile.Balanced) },
        { t: "Performance", k: "performance énergie puissance nvidia power energy", g: "bolt", f: () => Etat.choisirProfil(PowerProfile.Performance) },
        { t: Reglages.t("Activer ou couper le Wi-Fi", "Turn Wi-Fi On or Off"), k: "wifi wi-fi réseau internet network", g: "wifi", f: () => Etat.faire(["noctalia", "msg", "wifi-toggle"]) },
        { t: Reglages.t("Activer ou couper le Bluetooth", "Turn Bluetooth On or Off"), k: "bluetooth", g: "bluetooth", f: () => Etat.faire(["noctalia", "msg", "bluetooth-toggle"]) },
        { t: Reglages.t("Concentration", "Do Not Disturb"), k: "concentration ne pas déranger dnd notifications focus do not disturb", g: "dark_mode", f: () => Notifs.basculerConcentration() },
        { t: Reglages.t("Nuit (tons chauds)", "Night Light (Warm Tones)"), k: "nuit night lumière bleue blue light warm shift", g: "wb_twilight", f: () => { Etat.nuit = !Etat.nuit; Etat.faire(["noctalia", "msg", "nightlight-force-toggle"]) } },
        { t: Reglages.t("Thème clair ou sombre", "Light or Dark Theme"), k: "thème clair sombre dark light theme mode appearance", g: "contrast", f: () => Etat.faire(["noctalia", "msg", "theme-mode-toggle"]) },
        { t: Reglages.t("Rester éveillé", "Stay Awake"), k: "rester éveillé café caféine veille stay awake caffeine coffee", g: "coffee", f: () => Etat.basculerCafe() },
        { t: Reglages.t("Capture d'une zone", "Capture an Area"), k: "capture écran screenshot screen area region", g: "screenshot_region", f: () => Quickshell.execDetached(["sh", "-c", "sleep 0.4; ~/.local/bin/nc-capture zone"]) },
        { t: "Pomodoro", k: "pomodoro minuteur travail concentration pause tomate timer work focus break tomato", g: "psychology", f: () => { Etat.lancerPomodoro(); Etat.basculer(Etat.ecranOuvert, false) } },
        { t: Reglages.t("Copier le texte de l'écran", "Copy Text from Screen"), k: "texte ocr lire image copier capture extraire text copy read screen extract", g: "text_select_start", f: () => Quickshell.execDetached(["sh", "-c", "sleep 0.4; ~/.local/bin/nc-capture texte"]) },
        { t: Reglages.t("Presse-papiers", "Clipboard"), k: "presse-papiers clipboard copier coller copy paste history", g: "content_paste", f: () => Quickshell.execDetached(["noctalia", "msg", "panel-toggle", "launcher", "/clipboard"]) },
        { t: Reglages.t("Fond d'écran suivant", "Next Wallpaper"), k: "fond écran wallpaper suivant next background", g: "wallpaper", f: () => Etat.faire(["noctalia", "msg", "wallpaper-next"]) },
        { t: Reglages.t("Raccourcis clavier", "Keyboard Shortcuts"), k: "raccourcis clavier touches aide keyboard shortcuts keys help", g: "keyboard", f: () => Quickshell.execDetached([Etat.bin + "nc-shell-msg", "keys"]) }
    ]
    readonly property var pagesIle: [
        { t: "JARVIS", k: "jarvis assistant chat ia distant conversation question", g: "chat", p: "assistant" },
        { t: Reglages.t("Son", "Sound"), k: "son volume audio sortie micro haut-parleurs casque sound output speakers headphones microphone", g: "volume_up", p: "son" },
        { t: "Wi-Fi", k: "wifi wi-fi réseau internet réseaux network networks", g: "wifi", p: "reseau" },
        { t: "Bluetooth", k: "bluetooth appareils casque souris devices headphones mouse", g: "bluetooth", p: "bluetooth" },
        { t: "Notifications", k: "notifications messages", g: "notifications", p: "notifications" },
        { t: Reglages.t("Système", "System"), k: "système processeur mémoire batterie température disque énergie system cpu processor memory ram battery temperature disk power", g: "memory", p: "systeme" },
        { t: Reglages.t("Calendrier", "Calendar"), k: "calendrier date agenda calendar", g: "calendar_month", p: "calendrier" },
        { t: Reglages.t("Minuteur", "Timer"), k: "minuteur timer chrono stopwatch countdown", g: "timer", p: "minuteur" },
        { t: Reglages.t("Centre de contrôle", "Control Center"), k: "centre contrôle réglages luminosité control center settings brightness", g: "toggle_on", p: "centre" }
    ]

    // ── Recherche ──
    function sansAccents(s) { s = (s || "").toLowerCase(); try { return s.normalize("NFD").replace(/[̀-ͯ]/g, "") } catch (e) { return s } }
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
    // Aller sur une fenêtre ; réduite (Super + M), elle revient d'abord sur le bureau affiché (nc-fenetre)
    function allerA(adresse) { Etat.faire([Etat.bin + "nc-fenetre", "aller", adresse]) }
    function bureauNom(f) { return f.workspace.name === "special:reduites" ? Reglages.t("Réduite", "Minimized") : Reglages.t("Ouverte · bureau ", "Open · Desktop ") + f.workspace.name }
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
                   ["w ", Reglages.t("Wikipédia", "Wikipedia"), Reglages.t("https://fr.wikipedia.org/w/index.php?search=", "https://en.wikipedia.org/w/index.php?search=")]]
        for (var w = 0; w < web.length; w++) {
            if (q.startsWith(web[w][0]) && q.length > web[w][0].length) {
                var terme = q.slice(web[w][0].length)
                var url = web[w][2] + encodeURIComponent(terme)
                resultats = [{ titre: terme, sous: Reglages.t("Rechercher sur ", "Search ") + web[w][1], glyphe: "travel_explore", f: () => Qt.openUrlExternally(url) }]
                return
            }
        }
        if (q.startsWith("?")) {
            var question = q.slice(1).trim()
            if (r.reponse !== "" && question === r.questionPosee) {
                let cmdIA = r.commandeIA
                resultats = cmdIA === "" ? [] : [{ titre: cmdIA, sous: Reglages.t("Lancer dans le terminal", "Run in Terminal"), glyphe: "terminal", f: () => r.lancerCommande(cmdIA) }]
            } else {
                resultats = r.reflechit ? []
                          : nomIA === "-" ? [{ titre: Reglages.t("Aucune IA installée pour répondre", "No AI installed to answer"), sous: Reglages.t("Claude, opencode, Gemini ou Qwen", "Claude, opencode, Gemini or Qwen"), glyphe: "block", garder: true, f: () => {} }]
                          : [{ titre: question || Reglages.t("Pose ta question", "Ask your question"),
                               sous: r.reflechit ? (nomIA + Reglages.t(" réfléchit…", " is thinking…")) : Reglages.t("Demander à ", "Ask ") + (nomIA || Reglages.t("l'IA", "the AI")),
                               glyphe: "auto_awesome", garder: true, f: () => r.demander(question) }]
            }
            return
        }
        if (q.startsWith(">")) {
            var c = q.slice(1).trim()
            resultats = c === "" ? [] : [{ titre: c, sous: Reglages.t("Commande dans le terminal", "Command in Terminal"), glyphe: "terminal",
                                          f: () => r.lancerCommande(c) }]
            return
        }

        // Calcul en tête
        if (calcul !== "") {
            var res = calcul
            out.push({ titre: "= " + res, sous: Reglages.t("Calcul · Entrée pour copier", "Calculation · Enter to copy"), glyphe: "calculate", s: 1000,
                       f: () => Quickshell.execDetached(["wl-copy", res.replace(/^≈?\s*/, "")]) })
        }
        // Applications : déjà ouverte → Entrée en ouvre une nouvelle (Ctrl + Entrée : y aller), sinon Entrée la lance
        var prises = {}
        for (var a = 0; a < applis.length; a++) {
            var ap = applis[a]
            var sa = Math.max(score(qa, ap.name, true), score(qa, ap.generic, false) - 20, score(qa, ap.id, false) - 15, score(qa, ap.keywords, false) - 30)
            if (sa > 0) {
                let id = ap.id, fen = fenetreDe(ap)
                var item = { titre: ap.name, icone: Quickshell.iconPath(ap.icon, true), glyphe: "apps", s: sa * poidsUsage(id) + (fen ? 15 : 0) }
                if (fen) {
                    let adresse = fen.address
                    prises[adresse] = true
                    item.sous = bureauNom(fen)
                    if (Reglages.val("SPOTLIGHT_ENTREE", "nouvelle") === "aller") {
                        item.aide = Reglages.t("↵ y aller · Ctrl ↵ nouvelle", "↵ go to it · Ctrl ↵ new")
                        item.f = () => r.allerA(adresse)
                        item.nouveau = () => r.lancer(id)
                    } else {
                        item.aide = Reglages.t("↵ nouvelle · Ctrl ↵ y aller", "↵ new · Ctrl ↵ go to it")
                        item.f = () => r.lancer(id)
                        item.nouveau = () => r.allerA(adresse)
                    }
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
                let adr = fe.address
                out.push({ titre: fe.title, sous: fe.workspace.name === "special:reduites" ? Reglages.t("Fenêtre réduite · Entrée pour la ramener", "Minimized window · Enter to bring it back")
                                                                  : Reglages.t("Fenêtre ouverte · bureau ", "Open window · Desktop ") + fe.workspace.name,
                           icone: Quickshell.iconPath(fe.class, true) || Quickshell.iconPath(fe.class.toLowerCase(), true),
                           glyphe: "select_window", s: sf + 30, f: () => r.allerA(adr) })
            }
        }
        // Pages de l'île et actions
        for (var p = 0; p < pagesIle.length; p++) {
            var pg = pagesIle[p], sp = Math.max(score(qa, pg.t, true), score(qa, pg.k, false) - 15)
            if (sp > 0) { let nom = pg.p; out.push({ titre: pg.t, sous: Reglages.t("Dans l'île", "In the island"), glyphe: pg.g, s: sp - 5, page: nom }) }
        }
        for (var k = 0; k < actions.length; k++) {
            var ac = actions[k], sc = Math.max(score(qa, ac.t, true), score(qa, ac.k, false) - 15)
            if (sc > 0) out.push({ titre: ac.t, sous: "Action", glyphe: ac.g, s: sc - 8, f: ac.f })
        }
        // Fichiers
        for (var n = 0; n < fichiers.length; n++) {
            let fi = fichiers[n], chemin = fi.path
            out.push({ titre: fi.name, sous: (fi.dir ? Reglages.t("Dossier · ", "Folder · ") : Reglages.t("Fichier · ", "File · ")) + fi.parent,
                       icone: Quickshell.iconPath(iconeFichier(fi.name, fi.dir), true), glyphe: "description",
                       s: Math.min(70, Math.max(15, score(qa, fi.name, true) * 0.75)),   // jamais devant une appli qui commence par la saisie
                       f: () => Quickshell.execDetached([Etat.bin + "nc-apps", "open", chemin]) })
        }
        out.sort((x, y) => y.s - x.s)
        out = out.slice(0, 6)
        // Saisie qui commence par un programme (« htop », « ping google.fr ») : la lancer dans le terminal
        var prog = q.split(/\s+/)[0]
        if (execs[prog] && !q.startsWith("/")) {
            let commande = q
            out = out.slice(0, out.length && out[0].s >= 90 && q.indexOf(" ") < 0 ? 5 : 4)
            var lancerItem = { titre: commande, sous: Reglages.t("Lancer dans le terminal", "Run in Terminal"), glyphe: "terminal", aide: "↵", f: () => r.lancerCommande(commande) }
            // Avec des arguments, ou si rien ne lui correspond vraiment : en tête
            if (q.indexOf(" ") >= 0 || !out.length || out[0].s < 90) out.unshift(lancerItem); else out.push(lancerItem)
        }
        resultats = out
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
                if (f) { r.allerA(f.address); suivi.stop() }    // arrêter le suivi peut décharger le Spotlight : après
            }
        }
    }
    property bool entreeEnAttente: false
    // Encore du travail après la fermeture (suivre la fenêtre d'une appli lancée, Entrée en attente) : reste chargée
    readonly property bool occupe: suivi.running || entreeEnAttente
    function valider(i, nouveau) {
        // Applis pas encore chargées (on tape vite juste après Super + R) : on attend la liste avant de choisir
        if (lireApplis.running || applis.length === 0) { entreeEnAttente = true; return }
        var x = resultats[i]
        if (!x) return
        if (x.page) { Etat.recherche = false; Etat.aller(x.page); return }
        if (x.garder) { x.f(); return }        // question à l'IA : le Spotlight reste ouvert pour la réponse
        // Action d'abord : fermer l'île décharge le Spotlight tout de suite (ses fonctions n'existeraient plus)
        if (nouveau && x.nouveau) x.nouveau(); else x.f()
        Etat.fermer()
    }

    // ── Dessin ──
    // Barre de recherche
    Item {
        id: barre
        width: parent.width; height: 56
        Ico { id: loupe; x: 22; anchors.verticalCenter: parent.verticalCenter; nom: "search"; taille: 22; color: Couleurs.texteSec }
        TextInput {
            id: champ
            anchors.left: loupe.right; anchors.leftMargin: 12; anchors.right: parent.right; anchors.rightMargin: 22
            anchors.verticalCenter: parent.verticalCenter
            color: Couleurs.texte; selectionColor: Couleurs.accent; selectedTextColor: Couleurs.surAccent
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
                text: Reglages.t("Rechercher  ·  > commande  ·  ? question à l'IA", "Search  ·  > command  ·  ? ask the AI"); secondaire: true; font.pixelSize: 19
            }
        }
    }

    // Réponse de l'IA (« ? … »)
    Rectangle {
        id: zoneReponse
        visible: r.q.startsWith("?") && (r.reflechit || r.reponse !== "")
        readonly property bool attend: r.reflechit && r.reponse === ""
        anchors.top: barre.bottom; anchors.topMargin: 4
        x: 14; width: parent.width - 28; radius: 16; color: Couleurs.gris2
        height: Math.min(12 + enTete.height + (texteReponse.visible ? 6 + texteReponse.implicitHeight : 0) + 14, 320)
        clip: true
        Row {
            id: enTete
            x: 14; y: 12; spacing: 8
            Etincelle {
                anchors.verticalCenter: parent.verticalCenter; taille: 15; tourne: r.reflechit
                agent: ({ Claude: "claude", OpenCode: "opencode", Gemini: "gemini", Qwen: "qwen", Assistant: "assistant" })[r.nomIA] || "claude"
            }
            Texte { anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.pixelSize: 12
                    text: zoneReponse.attend ? r.nomIA + Reglages.t(" réfléchit…", " is thinking…") : r.nomIA }
        }
        Text {
            id: texteReponse
            anchors.top: enTete.bottom; anchors.topMargin: 6
            x: 14; width: parent.width - 28
            text: AssistantEtat.formater(r.reponse)
            visible: !zoneReponse.attend
            color: Couleurs.texte; font.family: "Adwaita Sans"; font.pixelSize: 14; wrapMode: Text.Wrap
            textFormat: Text.MarkdownText
        }
    }

    // Résultats
    Column {
        id: liste
        anchors.top: zoneReponse.visible ? zoneReponse.bottom : barre.bottom; anchors.topMargin: 6
        x: 8; width: parent.width - 16
        Repeater {
            model: r.resultats
            Rectangle {
                id: ligne
                required property var modelData
                required property int index
                readonly property bool choisi: index === r.sel
                width: liste.width; height: r.hauteurLigne; radius: 14
                color: choisi ? Couleurs.gris2 : "transparent"
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
                    Ico { anchors.centerIn: parent; nom: ligne.modelData.glyphe || "search"; taille: 22; color: Couleurs.texteDoux; visible: img.status !== Image.Ready }
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
