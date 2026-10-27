// Espace de code (Super + X) : le sélecteur de projets de nc-code dans l'île, façon Raycast. Une carte de verre
// centrée (un peu au-dessus du milieu, comme Spotlight) : un champ de recherche floue, la liste des projets à gauche
// (le plus récent en tête ; pastille du langage, branche, date), l'aperçu du projet choisi à droite (branche, état,
// derniers commits, début du README en texte brut), une ligne d'actions rapides en bas.
// Clavier : flèches, Entrée ouvre (nc-code DOSSIER : Neovim, l'agent de l'IA, lazygit, terminal), Tab choisit l'agent,
// Alt + Entrée Neovim seul, Échap ferme (ou revient des agents) ; Ctrl + E le dossier dans le gestionnaire de fichiers,
// Ctrl + Maj + C copie le chemin, Ctrl + G la page GitHub (https://github.com/… seulement, URL vérifiée ici aussi).
// Tout vient de nc-code (--liste-json, --agents-json, --apercu-json : les fichiers de .git lus directement, jamais git
// pour la liste ; pour l'aperçu, un git status borné, sans écriture). Rien ne tourne fermé : la fenêtre n'existe
// qu'ouverte (shell.qml, LazyLoader) ; l'aperçu part 120 ms après le dernier déplacement, jamais un processus par pas.
// Les textes venus des dépôts (branche, message de commit, README) sont affichés en texte brut (Texte.qml).
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
    property string filtre: ""
    property int sel: 0
    property bool choixAgent: false                 // Tab : la liste des agents à droite, à la place de l'aperçu
    property int selAgent: 0
    property var apercu: null                       // nc-code --apercu-json du dernier projet lu
    property bool entree: false
    Component.onCompleted: entree = true

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
    onFiltreChanged: sel = 0
    onProjetsChanged: sel = 0
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

    // ── Les actions ──
    function quitter() { code.fermer() }
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
        function bouger(d) { if (choixAgent) selAgent = Math.max(0, Math.min(n - 1, selAgent + d)); else sel = Math.max(0, Math.min(n - 1, sel + d)) }
        if (e.key === Qt.Key_Escape) { if (choixAgent) choixAgent = false; else quitter(); return true }
        if (e.key === Qt.Key_Down) { bouger(1); return true }
        if (e.key === Qt.Key_Up) { bouger(-1); return true }
        if (e.key === Qt.Key_PageDown) { bouger(5); return true }
        if (e.key === Qt.Key_PageUp) { bouger(-5); return true }
        if (e.key === Qt.Key_Tab || e.key === Qt.Key_Backtab) { if (projet) { choixAgent = !choixAgent; selAgent = 0 } return true }
        if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter) {
            if (choixAgent) { var a = choixAgents[selAgent]; ouvrir(a && a.prog ? ["--agent", a.prog] : ["--sans-agent"]) }
            else ouvrir(alt ? ["--nvim"] : [])
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
        Behavior on scale { enabled: !Reglages.sobre; SpringAnimation { spring: 4; damping: 0.32; epsilon: 0.001 } }
        // Contour aux couleurs de l'île (ILE_CONTOUR : dégradé de l'accent, discret, aucun)
        Rectangle {
            anchors.fill: fondVerre; anchors.margins: -1.5; radius: fondVerre.radius + 1.5
            visible: Couleurs.aContour
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[0] }
                GradientStop { position: 0.5; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[1] }
                GradientStop { position: 1; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[2] }
            }
        }
        Rectangle {
            id: fondVerre
            anchors.fill: parent; radius: code.rayon
            color: Qt.alpha(Couleurs.fond, code.verre ? 0.62 : 0.92)
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
                onTextChanged: code.filtre = text
                Keys.onPressed: e => { e.accepted = code.touche(e) }
                Texte {
                    visible: champ.text === ""
                    anchors.verticalCenter: parent.verticalCenter
                    text: Reglages.t("Rechercher un projet…", "Search a project…"); secondaire: true; font.pixelSize: 18
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
            ListView {
                id: liste
                objectName: "nc-code-liste"
                x: 8; y: 8; width: Math.round(parent.width * 0.46); height: parent.height - 16
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
                    onOuvrir: code.ouvrir([])
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
                visible: !code.choixAgent && code.projet !== null
                projet: code.projet
                apercu: code.apercuChoisi
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
            Row {
                x: 20; anchors.verticalCenter: parent.verticalCenter; spacing: 14
                Repeater {
                    model: [["↵", Reglages.t("ouvrir", "open")], ["Tab", Reglages.t("agent", "agent")], ["Alt ↵", "Neovim"], [Reglages.t("Échap", "Esc"), Reglages.t("fermer", "close")]]
                    Row {
                        spacing: 6
                        Rectangle {
                            width: libTouche.implicitWidth + 12; height: 20; radius: 6
                            color: Qt.alpha(Couleurs.carte, 0.7); border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.1)
                            Texte { id: libTouche; anchors.centerIn: parent; text: modelData[0]; font.pixelSize: 10; color: code.texteSecondaire }
                        }
                        Texte { height: 20; text: modelData[1]; font.pixelSize: 11; color: code.texteSecondaire }
                    }
                }
            }
            Row {
                anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                CodeAction { objectName: "nc-code-fichiers"; glyphe: "folder_open"; libelle: Reglages.t("Fichiers", "Files"); touche: "Ctrl E"; onClic: code.ouvrirDossier() }
                CodeAction { objectName: "nc-code-copier"; glyphe: "content_copy"; libelle: Reglages.t("Copier le chemin", "Copy path"); touche: "Ctrl ⇧ C"; onClic: code.copierChemin() }
                CodeAction { objectName: "nc-code-github"; visible: code.github !== ""; glyphe: "open_in_new"; libelle: "GitHub"; touche: "Ctrl G"; onClic: code.ouvrirGitHub() }
            }
        }
    }
}
