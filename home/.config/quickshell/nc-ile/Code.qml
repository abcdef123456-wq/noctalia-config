// Espace de code (Super + X) : le sélecteur de projets de nc-code dans l'île, façon Raycast. Une carte de verre
// centrée (un peu au-dessus du milieu, comme Spotlight) : un champ de recherche floue, la liste des projets à gauche
// (le plus récent en tête ; pastille du langage, branche, date), l'aperçu du projet choisi à droite (branche, état,
// derniers commits, début du README en texte brut), une ligne d'actions rapides en bas.
// Clavier : flèches, Entrée ouvre (nc-code DOSSIER : Neovim, l'agent de l'IA, lazygit, terminal), Tab choisit l'agent,
// Alt + Entrée Neovim seul, Ctrl + Entrée ouvre même si un agent y travaille déjà, Échap ferme (ou revient des agents) ; Ctrl + E le dossier dans le gestionnaire de fichiers,
// Ctrl + Maj + C copie le chemin, Ctrl + G la page GitHub (https://github.com/… seulement, URL vérifiée ici aussi).
// Première ligne « + Nouveau projet » (Ctrl + N : taper le nom, nc-code --nouveau) ; Ctrl + L : cloner depuis GitHub
// (adresse ou propriétaire/dépôt, vide = tes dépôts ; nc-code --cloner ouvre une fenêtre kitty avec la progression).
// Tout vient de nc-code (--liste-json, --agents-json, --apercu-json : les fichiers de .git lus directement, bornés,
// jamais git : un dépôt trouvé sur le disque pourrait lui faire exécuter des commandes). Rien ne tourne fermé : la fenêtre n'existe
// qu'ouverte (shell.qml, LazyLoader) ; l'aperçu part 120 ms après le dernier déplacement, jamais un processus par pas.
// Les textes venus des dépôts (branche, message de commit, README) sont affichés en texte brut (Texte.qml).
// Un agent suivi par nc-claude qui travaille déjà dans le dossier d'un projet : badge sur sa ligne (« Claude travaille »,
// « t'attend »), et Entrée ramène à son terminal au lieu d'ouvrir un second espace (comparaison des chemins réels, en
// texte brut). Première ouverture (aucun projet jamais ouvert par nc-code) : une ligne d'aide discrète en bas.
// Verre : flou de Hyprland derrière (règle de calque nc-code, regles.lua), fond de la palette à 62 % (92 % sans flou).
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import Quickshell.Wayland

PanelWindow {
    id: code
    signal fermer()
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    // Calque Top, sous l'île ; Overlay seulement devant une fenêtre en plein écran (même règle que Fiche.qml)
    WlrLayershell.layer: Hyprland.activeToplevel && Hyprland.activeToplevel.lastIpcObject
                         && (Hyprland.activeToplevel.lastIpcObject.fullscreen || 0) > 0 ? WlrLayer.Overlay : WlrLayer.Top
    WlrLayershell.namespace: "nc-code"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    color: "transparent"

    readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
    readonly property real largeurEcran: code.screen ? code.screen.width : 1600
    readonly property real hauteurEcran: code.screen ? code.screen.height : 1000
    readonly property bool verre: Reglages.val("FENETRES_FLOU", "oui") !== "non" && !Reglages.sobre
    readonly property color texteSecondaire: Qt.tint(Couleurs.texteSec, Qt.alpha(Couleurs.texte, 0.35))
    readonly property int rayon: 20
    readonly property int largeurCarte: Math.min(980, Math.round(largeurEcran * 0.64))
    readonly property int hauteurCarte: Math.min(580, Math.round(hauteurEcran * 0.6))

    property var projets: []                        // nc-code --liste-json, le plus récent en tête
    property bool lus: false
    property var agents: []                         // nc-code --agents-json : [{prog, nom}]
    property string agentDefaut: ""
    property bool debutant: false                   // nc-code --agents-json : aucun projet jamais ouvert
    property string filtre: ""
    property int sel: 0                             // -1 = la ligne « + Nouveau projet » (Haut depuis le premier projet)
    property string mode: ""                        // "" = chercher un projet ; "choix" : Nouveau (projet vide ou GitHub) ; "nouveau" : taper le nom ; "cloner" : coller l'adresse
    property int selChoix: 0                        // la ligne du petit choix de « Nouveau »
    property bool choixAgent: false                 // Tab : la liste des agents à droite, à la place de l'aperçu
    property int selAgent: 0
    property var apercu: null                       // nc-code --apercu-json du dernier projet lu
    property bool entree: false
    property bool ressortEntree: true               // faux = le lanceur sort de la pilule (LanceurFondu.qml) : pas de ressort 0,94
    // Sortie de la pilule de l'île (ILE_LANCEUR_FONDU) : le clavier et le focus n'attendent rien, seul le fond grandit
    LanceurFondu {
        id: fondu
        ecran: code.screen ? code.screen.name : ""
        largeurEcran: code.largeurEcran
        onTermine: code.fermer()
    }
    Component.onCompleted: { if (fondu.demarrer()) ressortEntree = false; entree = true }

    // ── La recherche floue, comme dans nc-code : 0 = commence par, 1 + place = contient, 100 + place = les lettres
    // dans l'ordre ; -1 = ne correspond pas. Trié par score, puis par date (l'ordre de la liste) ──
    function correspond(f, t) {
        if (!f) return 0
        f = f.toLowerCase(); t = t.toLowerCase()
        if (t.startsWith(f)) return 0
        var i = t.indexOf(f)
        if (i >= 0) return 1 + i
        var pos = -1
        for (var k = 0; k < f.length; k++) { pos = t.indexOf(f[k], pos + 1); if (pos < 0) return -1 }
        return 100 + pos
    }
    readonly property var visibles: {
        var res = []
        projets.forEach((p, i) => { var s = correspond(filtre, p.nom + " " + p.court); if (s >= 0) res.push({ s: s, i: i, p: p }) })
        res.sort((a, b) => a.s - b.s || a.i - b.i)
        return res.map(x => x.p)
    }
    // Sans recherche, jamais un projet seulement « trouvé sur le disque » (jamais ouvert : une archive extraite) n'est
    // choisi d'avance : un Entrée par réflexe y lancerait lazygit, donc git, avec la config du dépôt
    function premierSur() {
        var v = visibles || []
        if (filtre !== "") return 0
        for (var k = 0; k < v.length; k++) if (!v[k].disque) return k
        return -1
    }
    function choisirPremier() { sel = premierSur() }
    onFiltreChanged: Qt.callLater(choisirPremier)          // après la mise à jour de visibles (pas de boucle de liaison)
    onProjetsChanged: Qt.callLater(choisirPremier)
    readonly property var projet: sel >= 0 && sel < visibles.length ? visibles[sel] : null
    readonly property var choixAgents: agents.concat([{ prog: "", nom: Reglages.t("Un terminal, sans agent", "A terminal, no agent") }])

    // ── nc-code : la liste et les agents à l'ouverture, l'aperçu du projet choisi ──
    Process {
        id: lecture
        running: true
        command: [code.bin + "nc-code", "--liste-json"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { var d = JSON.parse(text); code.projets = Array.isArray(d) ? d : [] } catch (e) { code.projets = [] }
                code.lus = true
            }
        }
    }
    Process {
        id: lectureAgents
        running: true
        command: [code.bin + "nc-code", "--agents-json"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var d = JSON.parse(text)
                    code.agents = d && Array.isArray(d.agents) ? d.agents.filter(a => a && typeof a.prog === "string" && a.prog !== "") : []
                    code.agentDefaut = d && typeof d.defaut === "string" ? d.defaut : ""
                    code.debutant = !!(d && d.debutant === true)
                } catch (e) { code.agents = [] }
            }
        }
    }
    Timer { id: attenteApercu; interval: 120; onTriggered: code.lireApercu() }
    onProjetChanged: if (projet) attenteApercu.restart()
    Process {
        id: lectureApercu
        stdout: StdioCollector {
            onStreamFinished: {
                try { var d = JSON.parse(text); if (d && typeof d.chemin === "string") code.apercu = d } catch (e) {}
                if (code.projet && (!code.apercu || code.apercu.chemin !== code.projet.chemin)) attenteApercu.restart()
            }
        }
    }
    function lireApercu() {
        if (!projet || lectureApercu.running) return
        if (apercu && apercu.chemin === projet.chemin) return
        lectureApercu.command = [bin + "nc-code", "--apercu-json", projet.chemin]
        lectureApercu.running = true
    }
    readonly property var apercuChoisi: apercu && projet && apercu.chemin === projet.chemin ? apercu : null

    // ── Les agents déjà au travail dans un projet (nc-claude : cwd_reel = le chemin réel de leur dossier) ──
    function cheminReel(s) {
        if (!s) return ""
        if (typeof s.cwd_reel === "string" && s.cwd_reel !== "") return s.cwd_reel
        var c = String(s.cwd || "")
        return c.indexOf("~/") === 0 ? Quickshell.env("HOME") + c.slice(1) : c
    }
    function agentOccupe(s) {
        if (!s || s.agent === "assistant") return false
        if (Agents.sessionActive(s)) return true
        return s.etat === "attente" && Etat.maintenant.getTime() / 1000 - (s.maj || 0) < 900
    }
    // chemin du projet → sa session la plus récente (Agents.sessions est trié par date)
    readonly property var agentsParChemin: {
        var res = {}
        var l = Agents.sessions || []
        for (var i = 0; i < l.length; i++) {
            var c = cheminReel(l[i])
            if (c !== "" && res[c] === undefined && agentOccupe(l[i])) res[c] = l[i]
        }
        return res
    }
    function sessionDe(p) { return p && p.chemin ? (agentsParChemin[p.chemin] || null) : null }
    function badgeDe(p) {
        var s = sessionDe(p)
        if (!s) return ""
        return s.etat === "travail" ? Agents.nom(s) + Reglages.t(" travaille", " is working") : Agents.nom(s) + Reglages.t(" t'attend", " is waiting")
    }
    function couleurBadge(p) { var s = sessionDe(p); return s ? Agents.couleurDe(s) : Couleurs.accent }
    readonly property var sessionProjet: sessionDe(projet)
    // Entrée : le terminal de l'agent qui y travaille déjà ; sinon un nouvel espace de code
    function entrer() {
        var s = sessionProjet
        if (s && Number(s.terminal) > 0) { Agents.allerTerminal(Number(s.terminal), Number(s.shell) || 0); quitter() }
        else ouvrir([])
    }

    // ── Les actions ──
    function quitter() { if (!fondu.fermer()) code.fermer() }
    // Ctrl + N (nouveau projet) et Ctrl + L (cloner depuis GitHub) : le champ sert à taper le nom ou l'adresse
    function demarrerMode(m) { mode = m; choixAgent = false; selChoix = 0; champ.text = ""; filtre = "" }
    function finirMode() { mode = ""; champ.text = "" }
    // Un choix du petit menu « Nouveau » (clavier ou clic) : 0 = projet vide (taper le nom), 1 = depuis GitHub
    function choisirNouveau(i) { demarrerMode(i === 1 ? "cloner" : "nouveau"); champ.forceActiveFocus() }
    function lancerSaisie() {
        var t = champ.text.trim()
        if (t.indexOf("-") === 0) return                                   // jamais une option pour nc-code
        if (mode === "nouveau") {
            if (t === "") return
            Quickshell.execDetached([bin + "nc-code", "--nouveau", t])      // en argv ; nc-code filtre le nom et refuse un nom pris
        } else if (mode === "cloner") {
            // Sans adresse : nc-code montre tes dépôts GitHub (si gh est connecté) dans une fenêtre kitty ; il revérifie tout
            Quickshell.execDetached([bin + "nc-code", "--cloner"].concat(t === "" ? [] : [t]))
        } else return
        quitter()
    }
    function ouvrir(options) {
        if (!projet) return
        Quickshell.execDetached([bin + "nc-code"].concat(options || []).concat([projet.chemin]))
        quitter()
    }
    // Seulement https://github.com/propriétaire/dépôt (nc-code l'a déjà vérifié ; revérifié ici avant d'ouvrir quoi que ce soit)
    function urlGitHub(u) {
        u = String(u || "")
        return /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(u) && !/\/\.\.?(\/|$)/.test(u) ? u : ""
    }
    readonly property string github: urlGitHub(projet ? projet.github : "")
    function ouvrirGitHub() {
        if (!github) return false
        Quickshell.execDetached(["xdg-open", github])                      // en argv, jamais une ligne de shell
        quitter()
        return true
    }
    function ouvrirDossier() { if (!projet) return; Quickshell.execDetached(["xdg-open", projet.chemin]); quitter() }
    function copierChemin() { if (!projet) return; Quickshell.execDetached(["wl-copy", "--", projet.chemin]); quitter() }
    // Une touche du champ de recherche : vrai si elle est prise ici (le reste va au texte)
    function touche(e) {
        var ctrl = (e.modifiers & Qt.ControlModifier) !== 0, maj = (e.modifiers & Qt.ShiftModifier) !== 0, alt = (e.modifiers & Qt.AltModifier) !== 0
        var n = choixAgent ? choixAgents.length : visibles.length
        // Les projets : de -1 (la ligne Nouveau) à la fin ; une page ne remonte pas jusqu'à Nouveau
        function bouger(d, page) {
            if (mode === "choix") selChoix = Math.max(0, Math.min(1, selChoix + d))
            else if (mode !== "") return
            else if (choixAgent) selAgent = Math.max(0, Math.min(n - 1, selAgent + d))
            else sel = Math.max(page && sel > 0 ? 0 : -1, Math.min(n - 1, sel + d))
        }
        if (e.key === Qt.Key_Escape) { if (mode !== "") finirMode(); else if (choixAgent) choixAgent = false; else quitter(); return true }
        if (ctrl && e.key === Qt.Key_N) { demarrerMode("choix"); return true }
        if (ctrl && e.key === Qt.Key_L) { demarrerMode("cloner"); return true }
        if (mode === "choix" && (e.key === Qt.Key_Return || e.key === Qt.Key_Enter)) { choisirNouveau(selChoix); return true }
        if (mode !== "" && (e.key === Qt.Key_Return || e.key === Qt.Key_Enter)) { lancerSaisie(); return true }
        if (e.key === Qt.Key_Down) { bouger(1); return true }
        if (e.key === Qt.Key_Up) { bouger(-1); return true }
        if (e.key === Qt.Key_PageDown) { bouger(5, true); return true }
        if (e.key === Qt.Key_PageUp) { bouger(-5, true); return true }
        if (e.key === Qt.Key_Tab || e.key === Qt.Key_Backtab) { if (projet && mode === "") { choixAgent = !choixAgent; selAgent = 0 } return true }
        if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter) {
            if (sel < 0 && !choixAgent) demarrerMode("choix")                   // la ligne « + Nouveau projet » est choisie
            else if (choixAgent) { var a = choixAgents[selAgent]; ouvrir(a && a.prog ? ["--agent", a.prog] : ["--sans-agent"]) }
            else if (alt) ouvrir(["--nvim"])
            else if (ctrl) ouvrir([])
            else entrer()
            return true
        }
        if (ctrl && e.key === Qt.Key_E) { ouvrirDossier(); return true }
        if (ctrl && maj && e.key === Qt.Key_C) { copierChemin(); return true }
        if (ctrl && e.key === Qt.Key_G) { ouvrirGitHub(); return true }
        return false
    }

    MouseArea { anchors.fill: parent; onClicked: code.quitter() }          // un clic à côté ferme

    // ── La carte de verre ──
    Item {
        id: carte
        x: Math.round((code.largeurEcran - width) / 2); y: Math.round((code.hauteurEcran - height) * 0.4)
        width: code.largeurCarte; height: code.hauteurCarte
        // Entrée : un petit ressort de 0,94 à 1 pendant le fondu de Hyprland ; direct en sobre
        scale: code.entree ? 1 : 0.94
        Behavior on scale { enabled: !Reglages.sobre && code.ressortEntree; SpringAnimation { spring: 4; damping: 0.32; epsilon: 0.001 } }
        // Contour aux couleurs de l'île (ILE_CONTOUR : dégradé de l'accent, discret, aucun)
        Rectangle {
            anchors.fill: fondVerre; anchors.margins: -1.5; radius: fondVerre.radius + 1.5
            visible: Couleurs.aContour
            opacity: fondu.actif ? Math.min(1, fondu.q) : 1
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[0] }
                GradientStop { position: 0.5; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[1] }
                GradientStop { position: 1; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[2] }
            }
        }
        Rectangle {
            id: fondVerre
            // Lanceur sorti de la pilule : du rectangle de la pilule (place, taille, rayon, couleur) à la carte
            x: fondu.actif ? fondu.mix(fondu.x0 - carte.x, 0) : 0
            y: fondu.actif ? fondu.mix(fondu.y0 - carte.y, 0) : 0
            width: fondu.actif ? fondu.mix(fondu.w0, carte.width) : carte.width
            height: fondu.actif ? fondu.mix(fondu.h0, carte.height) : carte.height
            radius: fondu.actif ? fondu.mix(fondu.r0, code.rayon) : code.rayon
            color: fondu.actif ? fondu.couleurVers(Qt.alpha(Couleurs.fond, code.verre ? 0.62 : 0.92))
                               : Qt.alpha(Couleurs.fond, code.verre ? 0.62 : 0.92)
            // Reflet du verre : un liseré clair en haut, qui s'efface vers les bords
            Rectangle {
                x: 28; width: parent.width - 56; height: 1; y: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: Qt.rgba(1, 1, 1, 0) }
                    GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.16) }
                    GradientStop { position: 1; color: Qt.rgba(1, 1, 1, 0) }
                }
            }
        }
        MouseArea { anchors.fill: parent }                                     // un clic dans la carte ne ferme pas

        // Le contenu apparaît quand le fond est presque grand ; le focus clavier ne dépend pas de son opacité
        Item {
            id: contenu
            anchors.fill: parent
            opacity: fondu.actif ? Math.max(0, Math.min(1, (fondu.q - 0.45) / 0.4)) : 1

        // ── Le champ de recherche ──
        Item {
            id: barre
            width: parent.width; height: 58
            Ico { id: loupe; x: 22; anchors.verticalCenter: parent.verticalCenter; nom: "terminal"; taille: 22; color: Couleurs.accent }
            TextInput {
                id: champ
                objectName: "nc-code-champ"
                anchors.left: loupe.right; anchors.leftMargin: 12; anchors.right: compteur.left; anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                color: Couleurs.texte; selectionColor: Couleurs.accent; selectedTextColor: Couleurs.surAccent
                font.family: "Adwaita Sans"; font.pixelSize: 18
                clip: true
                focus: true
                cursorVisible: activeFocus
                Component.onCompleted: forceActiveFocus()
                onTextChanged: code.filtre = code.mode === "" ? text : ""
                Keys.onPressed: e => { e.accepted = code.touche(e) }
                Texte {
                    visible: champ.text === ""
                    anchors.verticalCenter: parent.verticalCenter
                    text: code.mode === "choix" ? Reglages.t("Nouveau : choisis avec les flèches…", "New: pick with the arrows…")
                      : code.mode === "nouveau" ? Reglages.t("Nom du nouveau projet…", "New project name…")
                      : code.mode === "cloner" ? Reglages.t("Adresse GitHub (ou propriétaire/dépôt), vide = mes dépôts…", "GitHub address (or owner/repo), empty = my repos…")
                      : Reglages.t("Rechercher un projet…", "Search a project…")
                secondaire: true; font.pixelSize: 18
                }
            }
            Texte {
                id: compteur
                anchors.right: parent.right; anchors.rightMargin: 22; anchors.verticalCenter: parent.verticalCenter
                secondaire: true; font.pixelSize: 12
                text: !code.lus ? "…" : (code.filtre ? code.visibles.length + " / " : "") + code.projets.length + " "
                      + (code.projets.length > 1 ? Reglages.t("projets", "projects") : Reglages.t("projet", "project"))
            }
        }
        Rectangle { x: 16; y: barre.height; width: parent.width - 32; height: 1; color: Qt.alpha(Couleurs.texte, 0.08) }

        // ── Le corps : la liste à gauche, l'aperçu (ou les agents) à droite ──
        Item {
            id: corps
            y: barre.height + 1; width: parent.width; height: parent.height - y - pied.height
            // Première ligne : un nouveau projet (Ctrl + N), à cliquer ou au clavier
            Rectangle {
                id: nouveauLigne
                objectName: "nc-code-nouveau"
                z: 2                                                              // au-dessus de la liste : rien ne lui passe devant
                x: 8; y: 8; width: Math.round(parent.width * 0.46); height: 34; radius: 12
                // Choisie comme une ligne de la liste : Haut depuis le premier projet (sel = -1), le survol, ou son petit choix ouvert
                readonly property bool choisie: code.sel < 0 || code.mode === "choix" || code.mode === "nouveau" || code.mode === "cloner"
                color: zoneNouveau.containsMouse || choisie ? Qt.alpha(Couleurs.accent, 0.22) : Qt.alpha(Couleurs.carte, 0.45)
                Texte { x: 14; anchors.verticalCenter: parent.verticalCenter; text: "+  " + Reglages.t("Nouveau projet", "New project"); font.pixelSize: 13 }
                Texte { anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; text: "Ctrl N"; secondaire: true; font.pixelSize: 10 }
                MouseArea {
                    id: zoneNouveau
                    objectName: "nc-code-nouveau-zone"
                    anchors.fill: parent; hoverEnabled: true
                    onEntered: if (code.mode === "") code.sel = -1
                    onClicked: { code.demarrerMode("choix"); champ.forceActiveFocus() }
                }
            }
            ListView {
                id: liste
                objectName: "nc-code-liste"
                x: 8; y: 8 + nouveauLigne.height + 2; width: Math.round(parent.width * 0.46); height: parent.height - 16 - nouveauLigne.height - 2 - (aide.visible ? aide.height : 0)
                clip: true; spacing: 2
                boundsBehavior: Flickable.StopAtBounds
                model: code.visibles
                currentIndex: code.sel
                highlightFollowsCurrentItem: false
                onCurrentIndexChanged: if (currentIndex >= 0) positionViewAtIndex(currentIndex, ListView.Contain)
                delegate: CodeProjet {
                    width: liste.width
                    projet: modelData
                    actif: index === code.sel
                    onSurvol: code.sel = index
                    badge: code.badgeDe(modelData)
                    badgeCouleur: code.couleurBadge(modelData)
                    onOuvrir: code.entrer()
                }
                // La ligne choisie : un verre de l'accent qui glisse d'une ligne à l'autre avec un ressort
                Rectangle {
                    parent: liste.contentItem
                    z: -1
                    visible: liste.currentItem !== null
                    width: liste.width; height: liste.currentItem ? liste.currentItem.height : 0
                    y: liste.currentItem ? liste.currentItem.y : 0
                    radius: 12
                    color: Qt.alpha(Couleurs.accent, 0.22)
                    Behavior on y { enabled: !Reglages.sobre; SpringAnimation { spring: 5; damping: 0.4; epsilon: 0.5 } }
                }
            }
            // Première ouverture : une phrase pour se lancer (disparaît dès qu'un projet a été ouvert)
            Texte {
                id: aide
                objectName: "nc-code-aide"
                visible: code.debutant && code.mode === ""
                x: liste.x + 12; y: parent.height - height; width: liste.width - 24; height: 26     // bornée à la colonne de gauche (elide)
                secondaire: true; font.pixelSize: 11; elide: Text.ElideRight
                text: Reglages.t("Premier projet ? Choisis-en un, puis Entrée : Neovim, ton agent IA, lazygit et un terminal s'ouvrent.",
                                 "First project? Pick one, then Enter: Neovim, your AI agent, lazygit and a terminal open.")
            }
            Texte {
                visible: code.lus && code.visibles.length === 0
                x: 24; y: 24; width: liste.width - 32
                secondaire: true
                text: code.projets.length === 0 ? Reglages.t("Aucun dépôt git trouvé (cd dans un projet, puis nc-code .).", "No git repository found (cd into a project, then nc-code .).")
                                                : Reglages.t("Aucun projet ne correspond.", "No matching project.")
                wrapMode: Text.Wrap
            }
            Rectangle { id: separation; x: liste.x + liste.width + 8; y: 12; width: 1; height: parent.height - 24; color: Qt.alpha(Couleurs.texte, 0.08) }
            CodeApercu {
                objectName: "nc-code-apercu"
                x: separation.x + 17; y: 14; width: parent.width - x - 22; height: parent.height - 28
                visible: !code.choixAgent && code.mode === "" && code.projet !== null
                projet: code.projet
                apercu: code.apercuChoisi
            }
            // Nouveau (clic, Entrée sur la ligne, Ctrl + N) : « Projet vide » ou « Depuis GitHub »
            CodeChoixNouveau {
                objectName: "nc-code-choix"
                x: separation.x + 17; y: 14; width: parent.width - x - 22
                visible: code.mode === "choix"
                selection: code.selChoix
                onSurvol: i => code.selChoix = i
                onChoisir: i => code.choisirNouveau(i)
            }
            // Ligne « + Nouveau projet » choisie (Haut depuis le premier projet) : ce qu'Entrée va faire
            Texte {
                objectName: "nc-code-nouveau-aide"
                x: separation.x + 17; y: 14; width: parent.width - x - 22
                visible: code.mode === "" && !code.choixAgent && code.sel < 0
                secondaire: true; wrapMode: Text.Wrap
                text: Reglages.t("Entrée : un nouveau projet (vide, ou depuis GitHub). Bas revient à la liste.", "Enter: a new project (empty, or from GitHub). Down goes back to the list.")
            }
            // Ctrl + N / Ctrl + L : ce que fait la saisie
            Column {
                objectName: "nc-code-saisie"
                x: separation.x + 17; y: 14; width: parent.width - x - 22
                visible: code.mode === "nouveau" || code.mode === "cloner"
                spacing: 6
                Texte { width: parent.width; font.pixelSize: 17; font.weight: Font.Bold; height: 30
                        text: code.mode === "nouveau" ? Reglages.t("Nouveau projet", "New project") : Reglages.t("Cloner depuis GitHub", "Clone from GitHub") }
                Texte { width: parent.width; secondaire: true; font.pixelSize: 12; wrapMode: Text.Wrap
                        text: code.mode === "nouveau"
                              ? Reglages.t("Tape un nom (lettres, chiffres, - et _) puis Entrée : le dossier est créé avec un dépôt git et un README, puis ouvert. Un nom déjà pris est refusé. Modèles (vide, python, c, web) : nc-code --nouveau NOM --modele python.",
                                           "Type a name (letters, digits, - and _) then Enter: the folder is created with a repository and a README, then opened. A name already taken is refused. Templates: nc-code --nouveau NAME --modele python.")
                              : Reglages.t("Colle https://github.com/propriétaire/dépôt ou propriétaire/dépôt puis Entrée. Vide : la liste de tes dépôts (si gh est connecté). Rien n'est lancé si le dossier existe déjà. Échap revient.",
                                           "Paste https://github.com/owner/repo or owner/repo then Enter. Empty: your repositories (if gh is signed in). Nothing runs if the folder already exists. Esc goes back.") }
            }
            // Tab : quel agent ? (ceux de nc-ia qui sont installés, puis « un terminal, sans agent »)
            Column {
                objectName: "nc-code-agents"
                x: separation.x + 17; y: 14; width: parent.width - x - 22
                visible: code.choixAgent
                spacing: 4
                Texte { width: parent.width; text: Reglages.t("Quel agent ?", "Which agent?"); font.pixelSize: 17; font.weight: Font.Bold; height: 30 }
                Texte {
                    width: parent.width; height: 24; secondaire: true; font.pixelSize: 12
                    text: code.projet ? Reglages.t("Pour ", "For ") + code.projet.nom + Reglages.t(" · Entrée ouvre, Échap revient", " · Enter opens, Esc goes back") : ""
                }
                Repeater {
                    model: code.choixAgents
                    CodeAgent {
                        width: parent.width
                        agent: modelData
                        actif: index === code.selAgent
                        defaut: modelData.prog !== "" && modelData.prog === code.agentDefaut
                        onSurvol: code.selAgent = index
                        onChoisir: { code.selAgent = index; code.touche({ key: Qt.Key_Return, modifiers: 0 }) }
                    }
                }
            }
        }

        // ── Le pied : l'aide des touches à gauche, les actions rapides à droite ──
        Item {
            id: pied
            anchors.bottom: parent.bottom; width: parent.width; height: 48
            Rectangle { x: 16; y: 0; width: parent.width - 32; height: 1; color: Qt.alpha(Couleurs.texte, 0.08) }
            // Aides des touches à gauche : la largeur est bornée (pied moins les actions) ; quand elle manque, les aides les moins
            // utiles disparaissent une à une (« ouvrir quand même », puis « Alt ↵ », puis « Tab »), jamais coupées au milieu.
            // « ↵ ouvrir » et « Échap fermer » restent toujours. Si même ça ne tient pas, les actions de droite passent en icône seule.
            readonly property real largeurActionsPleine: {
                var l = [actFichiers, actCopier, actCloner, actGitHub], t = 0, n = 0
                for (var i = 0; i < l.length; i++) if (l[i].visible) { t += l[i].largeurPleine; n++ }
                return t + Math.max(0, n - 1) * 6
            }
            readonly property real aidesMini: aOuvrir.implicitWidth + aEchap.implicitWidth + 14
            readonly property bool actionsCompactes: width - 34 - largeurActionsPleine - 20 < aidesMini
            readonly property real placeAides: Math.max(0, width - 20 - actions.width - 14 - 20)
            function tient(l) { var t = 0; for (var i = 0; i < l.length; i++) t += l[i].implicitWidth; return t + (l.length - 1) * 14 <= placeAides }
            readonly property bool aideForce: tient([aOuvrir, aTab, aNvim, aForce, aEchap])
            readonly property bool aideNvim: aideForce || tient([aOuvrir, aTab, aNvim, aEchap])
            readonly property bool aideTab: aideNvim || tient([aOuvrir, aTab, aEchap])
            Row {
                id: aides
                objectName: "nc-code-aides"
                x: 20; width: pied.placeAides; height: parent.height; spacing: 14; clip: true
                CodeAide { id: aOuvrir; objectName: "nc-code-aide-ouvrir"; anchors.verticalCenter: parent.verticalCenter; touche: "↵"; libelle: Reglages.t("ouvrir", "open") }
                CodeAide { id: aTab; objectName: "nc-code-aide-tab"; anchors.verticalCenter: parent.verticalCenter; visible: pied.aideTab; touche: "Tab"; libelle: Reglages.t("agent", "agent") }
                CodeAide { id: aNvim; objectName: "nc-code-aide-nvim"; anchors.verticalCenter: parent.verticalCenter; visible: pied.aideNvim; touche: "Alt ↵"; libelle: "Neovim" }
                CodeAide { id: aForce; objectName: "nc-code-aide-force"; anchors.verticalCenter: parent.verticalCenter; visible: pied.aideForce; touche: "Ctrl ↵"; libelle: Reglages.t("ouvrir quand même", "open anyway") }
                CodeAide { id: aEchap; objectName: "nc-code-aide-echap"; anchors.verticalCenter: parent.verticalCenter; touche: Reglages.t("Échap", "Esc"); libelle: Reglages.t("fermer", "close") }
            }
            Row {
                id: actions
                objectName: "nc-code-actions"
                anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                CodeAction { id: actFichiers; objectName: "nc-code-fichiers"; compact: pied.actionsCompactes; glyphe: "folder_open"; libelle: Reglages.t("Fichiers", "Files"); touche: "Ctrl E"; onClic: code.ouvrirDossier() }
                CodeAction { id: actCopier; objectName: "nc-code-copier"; compact: pied.actionsCompactes; glyphe: "content_copy"; libelle: Reglages.t("Copier le chemin", "Copy path"); touche: "Ctrl ⇧ C"; onClic: code.copierChemin() }
                CodeAction { id: actCloner; objectName: "nc-code-cloner"; compact: pied.actionsCompactes; glyphe: "download"; libelle: Reglages.t("Cloner", "Clone"); touche: "Ctrl L"; onClic: { code.demarrerMode("cloner"); champ.forceActiveFocus() } }
                CodeAction { id: actGitHub; objectName: "nc-code-github"; compact: pied.actionsCompactes; visible: code.github !== ""; glyphe: "open_in_new"; libelle: "GitHub"; touche: "Ctrl G"; onClic: code.ouvrirGitHub() }
            }
        }
        }
    }
}
