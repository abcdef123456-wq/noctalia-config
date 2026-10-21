// Fenêtre des réglages (Super + Alt + , ; nc-reglages fenetre ; appli « Réglages du bureau ») : tous les réglages de
// nc-reglages, en graphique, avec une recherche. Même catalogue et mêmes règles que l'écran du terminal : la fenêtre
// lit « nc-reglages catalogue » (JSON) et change une valeur par « nc-reglages set », qui applique aussitôt
// (Hyprland, Noctalia, île, veille, terminal…). Une fenêtre classique de Hyprland (règle nc-reglages-fenetre).
// Sections en pastilles ; une recherche (Ctrl + F) cherche dans toutes les sections, sans accent ni majuscule ;
// bascule oui/non, pastilles de choix, curseur pour les nombres, champ pour le texte ; ↺ remet la valeur de la config.
// Au clavier : ↑ ↓ choisir, ← → changer la valeur, Entrée ou Espace basculer (ou saisir un texte), r valeur de la
// config, Tab et Maj + Tab changer de section, une lettre lance la recherche, Échap vide la recherche puis ferme.
// Tout en haut de la liste, ↑ monte sur la rangée des onglets : ← → y changent d'onglet, ↓ redescend dans la liste,
// ↑ encore va à la recherche (dont ↓ ramène aux onglets).
// Même cadrage que le cockpit : nc/automatismes.lua la place à l'ouverture.
// Section Raccourcis : tous les raccourcis clavier (ceux de la config et les tiens), cherchables par nom ou par touches ;
// Entrée sur l'un d'eux attend la nouvelle combinaison (Hyprland coupe ses raccourcis le temps de la taper, comme dans
// le terminal), Suppr le désactive (ou retire l'un des tiens), r le remet comme dans la config.
// Échap avec l'île ouverte ferme l'île, pas la fenêtre (ileOuverte et fermerIle, branchés par shell.qml).
import QtQuick
import Quickshell
import Quickshell.Io

FloatingWindow {
    id: fen
    title: "Réglages du bureau"
    visible: false
    implicitWidth: 1040; implicitHeight: 740; minimumSize: Qt.size(720, 480)
    color: Couleurs.fond
    readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
    property var catalogue: []
    property string section: ""
    property string recherche: ""
    property string message: ""
    property bool erreur: false
    property var file: []                           // écritures en attente : des commandes nc-reglages, une par une
    property var capture: null                      // le raccourci dont on attend les nouvelles touches
    property string captureMessage: ""
    property bool ileOuverte: false                 // l'île est ouverte (shell.qml) : Échap la ferme d'abord
    signal fermerIle()
    property bool relire: false                     // une relecture demandée pendant qu'une autre tournait
    readonly property bool enCours: lecture.running || ecriture.running || relire || file.length > 0
    readonly property var sections: { var s = []; catalogue.forEach(r => { if (s.indexOf(r.sectionNom) < 0) s.push(r.sectionNom) }); return s }
    // Recherche : chaque mot doit se trouver (dans le nom, l'aide, la clé, la section ou la valeur) ; espaces et « + »
    // séparent les mots, donc « super a », « super+a » et « Super + A » trouvent le même raccourci
    readonly property var visibles: {
        var mots = normaliser(recherche).split(/[\s+]+/).filter(m => m !== "")
        if (mots.length) return catalogue.filter(r => {
            var t = normaliser(r.nom + " " + r.aide + " " + r.cle + " " + r.sectionNom + " " + r.affiche)
            return mots.every(m => t.indexOf(m) >= 0)
        })
        return catalogue.filter(r => r.sectionNom === section)
    }
    // Sans accent ni majuscule ; sans String.normalize (moteur JavaScript d'un Qt ancien), seulement sans majuscule
    function normaliser(t) { var s = String(t).toLowerCase(); try { return s.normalize("NFD").replace(/[̀-ͯ]/g, "") } catch (e) { return s } }
    function afficher(nom) { surEcran(nom); visible = true; charger(); liste.forceActiveFocus() }
    function surEcran(nom) {
        var ecrans = Quickshell.screens
        for (var i = 0; i < ecrans.length; i++) if (ecrans[i].name === nom) { screen = ecrans[i]; return }
    }
    onClosed: close()
    function close() { visible = false }
    // Relecture du catalogue ; si une lecture tourne déjà (lancée avant la dernière écriture), une autre suit
    function charger() { if (lecture.running) relire = true; else lecture.running = true }
    // Une valeur : nc-reglages set (ou reset pour revenir à la config) ; les demandes se suivent une par une
    function commande(args) { file.push([bin + "nc-reglages"].concat(args)); file = file; suivant() }
    function regler(cle, valeur) { commande(["set", cle, String(valeur)]) }
    function remettre(cle) { commande(["reset", cle]) }
    function suivant() {
        if (ecriture.running || !file.length) return
        ecriture.command = file.shift(); file = file
        ecriture.running = true
    }
    // Un raccourci : changer (touches), desactiver, reactiver, origine, retirer — nc-reglages raccourci JSON
    function raccourci(r, action, touches) {
        commande(["raccourci", JSON.stringify({action: action, ids: r.ids, origs: r.origs, nom: r.nom, mien: r.mien, touches: touches || ""})])
    }
    // r ou ↺ : la valeur de la config (réglage), ou le raccourci d'origine / réactivé
    function remettreLigne(r) {
        if (!r || !r.modifie) return
        if (r.genre !== "raccourci") remettre(r.cle)
        else if (r.desactive) raccourci(r, "reactiver")
        else if (r.mien === "") raccourci(r, "origine")
    }
    // Suppr : désactiver un raccourci de la config, retirer l'un des tiens
    function supprimerLigne(r) {
        if (!r || r.genre !== "raccourci") return
        if (r.mien !== "") raccourci(r, "retirer")
        else if (!r.desactive) raccourci(r, "desactiver")
    }
    // Capture des nouvelles touches d'un raccourci : Hyprland en mode « nc-capture » (sans raccourcis, 20 s au plus)
    function capturer(r) {
        if (!r || !r.modifiable) return
        capture = r; captureMessage = ""
        Quickshell.execDetached([bin + "nc-reglages", "capture"])
        zoneCapture.forceActiveFocus()
    }
    function finCapture(touches) {
        var r = capture
        capture = null
        Quickshell.execDetached([bin + "nc-reglages", "capture", "fin"])
        liste.forceActiveFocus()
        if (r && touches) raccourci(r, "changer", touches)
    }
    // Une touche du clavier -> « Super+Maj+T » (noms de nc-raccourci) ; "" pour un modificateur seul ; "annuler" pour Échap
    function combinaison(event) {
        var k = event.key
        if ([Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_Super_L, Qt.Key_Super_R, Qt.Key_AltGr, Qt.Key_CapsLock].indexOf(k) >= 0) return ""
        var mods = []
        if (event.modifiers & Qt.MetaModifier) mods.push("Super")
        if (event.modifiers & Qt.ControlModifier) mods.push("Ctrl")
        if (event.modifiers & Qt.AltModifier) mods.push("Alt")
        if (event.modifiers & Qt.ShiftModifier) mods.push("Maj")
        if (k === Qt.Key_Escape && !mods.length) return "annuler"
        var t = "", sc = event.nativeScanCode
        var noms = {}
        noms[Qt.Key_Return] = "Entrée"; noms[Qt.Key_Enter] = "Entrée"; noms[Qt.Key_Space] = "Espace"; noms[Qt.Key_Tab] = "Tab"
        noms[Qt.Key_Escape] = "Échap"; noms[Qt.Key_Print] = "Impr"; noms[Qt.Key_Delete] = "Suppr"
        noms[Qt.Key_Left] = "gauche"; noms[Qt.Key_Right] = "droite"; noms[Qt.Key_Up] = "haut"; noms[Qt.Key_Down] = "bas"
        if (sc >= 10 && sc <= 19) t = String((sc - 9) % 10)           // rangée des chiffres, quelle que soit la disposition
        else if (k >= Qt.Key_A && k <= Qt.Key_Z) t = String.fromCharCode(k)
        else if (k >= Qt.Key_0 && k <= Qt.Key_9) t = String.fromCharCode(k)
        else if (k >= Qt.Key_F1 && k <= Qt.Key_F12) t = "F" + (k - Qt.Key_F1 + 1)
        else t = noms[k] || ""
        if (!t) return "?"
        if (!mods.length && !/^F\d+$/.test(t)) return "?"
        return mods.concat([t]).join("+")
    }
    function reglage(cle) { for (var i = 0; i < catalogue.length; i++) if (catalogue[i].cle === cle) return catalogue[i]; return null }
    function borner(r, v) { v = Math.round(v / r.pas) * r.pas; return Math.max(r.mini, Math.min(r.maxi, v)) }
    // ← → : la valeur d'après (d = 1) ou d'avant (d = -1), selon le genre du réglage
    function changer(r, d) {
        if (!r || r.genre === "raccourci") return
        if (r.genre === "ouinon") regler(r.cle, r.valeur === "oui" ? "non" : "oui")
        else if (r.genre === "choix" || r.genre === "hz") {
            var c = r.choix, i = 0
            for (var k = 0; k < c.length; k++) if (c[k][0] === r.valeur) i = k
            if (c.length) regler(r.cle, c[(i + d + c.length) % c.length][0])
        } else if (r.genre === "entier") regler(r.cle, borner(r, Number(r.valeur) + d * r.pas))
    }
    // Entrée ou Espace : bascule, choix suivant, ou saisie du texte
    function basculer(r) {
        if (!r) return
        if (r.genre === "raccourci") { if (r.desactive) raccourci(r, "reactiver"); else capturer(r); return }
        if (r.genre === "texte" || r.genre === "dossier") { if (liste.currentItem) liste.currentItem.editer() }
        else changer(r, 1)
    }
    function sectionSuivante(d) {
        if (!sections.length) return
        champRecherche.text = ""; recherche = ""
        section = sections[(Math.max(0, sections.indexOf(section)) + d + sections.length) % sections.length]
        liste.currentIndex = liste.count ? 0 : -1
    }
    // Le caractère d'une touche lettre ou chiffre (le texte de l'événement, sinon le code de la touche), ou ""
    function lettre(event) {
        // Une lettre (toute écriture : elle a une majuscule) ou un chiffre ; sans regex Unicode (Qt 6.8 de Debian 13)
        var c = event.text || ""
        if (c.length === 1 && (c.toLowerCase() !== c.toUpperCase() || (c >= "0" && c <= "9"))) return c
        if ((event.key >= Qt.Key_A && event.key <= Qt.Key_Z) || (event.key >= Qt.Key_0 && event.key <= Qt.Key_9)) return String.fromCharCode(event.key).toLowerCase()
        return ""
    }
    readonly property var courant: liste.currentIndex >= 0 && liste.currentIndex < visibles.length ? visibles[liste.currentIndex] : null

    Process {
        id: lecture
        command: [fen.bin + "nc-reglages", "catalogue"]
        onRunningChanged: if (!running && fen.relire) Qt.callLater(() => { fen.relire = false; lecture.running = true })
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var d = JSON.parse(text)
                    if (!Array.isArray(d)) throw new Error("catalogue")
                    fen.catalogue = d
                    if (!fen.section || fen.sections.indexOf(fen.section) < 0) fen.section = fen.sections.length ? fen.sections[0] : ""
                    fen.erreur = false
                } catch (e) {
                    fen.message = Reglages.t("Réglages illisibles : lance nc-reglages dans un terminal.", "Settings unreadable: run nc-settings in a terminal.")
                    fen.erreur = true
                }
            }
        }
        stderr: StdioCollector {}
    }
    Process {
        id: ecriture
        stdout: StdioCollector { onStreamFinished: { fen.message = text.trim().split("\n").pop() || ""; fen.erreur = false } }
        stderr: StdioCollector { onStreamFinished: if (text.trim()) { fen.message = text.trim().split("\n").pop(); fen.erreur = true } }
        onExited: (code, status) => { if (code !== 0 && !fen.erreur) { fen.message = Reglages.t("Valeur refusée.", "Value rejected."); fen.erreur = true }; fen.charger(); fen.suivant() }
    }
    Timer { id: effaceMessage; interval: 6000; running: fen.message !== "" && !fen.erreur; onTriggered: fen.message = "" }

    Shortcut {
        sequence: "Escape"; enabled: !fen.capture
        onActivated: { if (fen.ileOuverte) fen.fermerIle(); else if (fen.recherche !== "") { fen.recherche = ""; champRecherche.text = "" } else fen.close() }
    }
    Shortcut { sequences: ["Ctrl+F", "Ctrl+K"]; enabled: !fen.capture; onActivated: { champRecherche.forceActiveFocus(); champRecherche.selectAll() } }
    onVisibleChanged: if (!visible && capture) finCapture("")

    component Pastille: Rectangle {
        id: pastille
        property string texte: ""
        property bool actif: false
        property bool petit: false
        property bool clavier: false                 // l'onglet choisi quand la rangée a le focus du clavier
        signal clic()
        width: etiquette.implicitWidth + (petit ? 22 : 30); height: petit ? 30 : 36; radius: height / 2
        color: clavier ? Couleurs.gris5 : (actif ? Couleurs.gris4 : (zp.containsMouse ? Couleurs.gris3 : Couleurs.gris2))
        border.width: clavier ? 2.5 : (actif ? 1.5 : 0); border.color: Couleurs.accent
        scale: clavier ? 1.06 : 1
        Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        Behavior on color { ColorAnimation { duration: 120 } }
        Texte { id: etiquette; anchors.centerIn: parent; text: pastille.texte; font.pixelSize: petit ? 12 : 13; font.weight: Font.DemiBold
                color: pastille.actif ? Couleurs.texte : Couleurs.texteSec }
        MouseArea { id: zp; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pastille.clic() }
    }

    Item {
        id: tout                                     // tout le contenu (une capture hors écran en prend l'image)
        objectName: "nc-reglages-tout"
        anchors.fill: parent
        Rectangle { anchors.fill: parent; color: Couleurs.fond }

        // ── En-tête : titre, recherche, fermer ──
        Row {
            id: entete
            x: 22; y: 18; height: 40; spacing: 12
            Ico { anchors.verticalCenter: parent.verticalCenter; nom: "tune"; taille: 24; color: Couleurs.accent }
            Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Réglages", "Settings"); font.pixelSize: 18; font.weight: Font.Bold; font.letterSpacing: 1 }
            Texte { anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.pixelSize: 12
                    text: fen.catalogue.length ? fen.catalogue.length + Reglages.t(" réglages", " settings") : "" }
        }
        Rectangle {
            id: champ
            anchors.horizontalCenter: parent.horizontalCenter; y: 18; width: Math.min(440, tout.width - 460); height: 40; radius: 20
            color: Couleurs.gris2; border.width: 1; border.color: champRecherche.activeFocus ? Couleurs.accent : "transparent"
            Ico { x: 14; anchors.verticalCenter: parent.verticalCenter; nom: "search"; taille: 18; color: Couleurs.texteSec }
            TextInput {
                id: champRecherche
                objectName: "nc-reglages-recherche"
                anchors.fill: parent; anchors.leftMargin: 40; anchors.rightMargin: 36
                verticalAlignment: TextInput.AlignVCenter; clip: true; selectByMouse: true
                color: Couleurs.texte; selectionColor: Couleurs.accent; font.pixelSize: 13
                onTextChanged: { fen.recherche = text; liste.currentIndex = liste.count ? 0 : -1 }
                Keys.onDownPressed: { if (fen.recherche.trim()) liste.forceActiveFocus(); else rangee.forceActiveFocus() }
                Keys.onReturnPressed: liste.forceActiveFocus()
                Keys.onTabPressed: fen.sectionSuivante(1)
                Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; visible: !champRecherche.text; color: Couleurs.texteSec; font: champRecherche.font
                       text: Reglages.t("Chercher un réglage (Ctrl + F)…", "Search a setting (Ctrl + F)…") }
            }
            AssistantCommande { anchors.right: parent.right; anchors.rightMargin: 5; anchors.verticalCenter: parent.verticalCenter; rond: true; width: 30; height: 30
                                icone: "close"; visible: champRecherche.text !== ""; aide: Reglages.t("Effacer", "Clear"); onClic: { champRecherche.text = ""; champRecherche.forceActiveFocus() } }
        }
        Row {
            anchors.right: parent.right; anchors.rightMargin: 14; y: 18; height: 40; spacing: 8
            AssistantCommande { anchors.verticalCenter: parent.verticalCenter; rond: true; width: 34; height: 34; icone: "refresh"; aide: Reglages.t("Relire", "Reload"); enabled: !fen.enCours; onClic: fen.charger() }
            AssistantCommande { anchors.verticalCenter: parent.verticalCenter; rond: true; width: 34; height: 34; icone: "keyboard"; aide: Reglages.t("Raccourcis clavier (terminal)", "Keyboard shortcuts (terminal)")
                                onClic: Quickshell.execDetached(["kitty", "--class", "nc-reglages", "-e", fen.bin + "nc-reglages", "raccourcis"]) }
            AssistantCommande { anchors.verticalCenter: parent.verticalCenter; rond: true; width: 34; height: 34; icone: "close"; aide: Reglages.t("Fermer (Échap)", "Close (Esc)"); onClic: fen.close() }
        }

        // ── Sections en pastilles (grisées pendant une recherche, qui couvre tout) ──
        Flow {
            id: rangee
            objectName: "nc-reglages-sections"
            x: 22; y: entete.y + entete.height + 14; width: tout.width - 44; spacing: 8
            opacity: fen.recherche.trim() && !activeFocus ? 0.45 : 1
            // Au clavier : ← → changent d'onglet (et effacent une recherche), ↓ Entrée Espace descendent dans la liste,
            // ↑ va à la recherche, une lettre la commence
            Keys.onPressed: event => {
                event.accepted = true
                if (event.key === Qt.Key_Right || event.key === Qt.Key_Tab) fen.sectionSuivante(1)
                else if (event.key === Qt.Key_Left || event.key === Qt.Key_Backtab) fen.sectionSuivante(-1)
                else if (event.key === Qt.Key_Home) { if (fen.sections.length) { fen.sectionSuivante(0); fen.section = fen.sections[0] } }
                else if (event.key === Qt.Key_End) { if (fen.sections.length) { fen.sectionSuivante(0); fen.section = fen.sections[fen.sections.length - 1] } }
                else if (event.key === Qt.Key_Down || event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) {
                    liste.currentIndex = liste.count ? 0 : -1; liste.forceActiveFocus()
                }
                else if (event.key === Qt.Key_Up) champRecherche.forceActiveFocus()
                else if (!(event.modifiers & (Qt.ControlModifier | Qt.AltModifier)) && fen.lettre(event) !== "") {
                    champRecherche.text = fen.lettre(event); champRecherche.forceActiveFocus(); champRecherche.cursorPosition = 1
                }
                else event.accepted = false
            }
            Repeater {
                model: fen.sections
                Pastille { required property string modelData; texte: modelData; actif: !fen.recherche.trim() && fen.section === modelData
                           clavier: rangee.activeFocus && fen.section === modelData
                           onClic: { fen.section = modelData; champRecherche.text = ""; fen.recherche = "" } }
            }
        }

        // ── Les réglages ──
        ListView {
            id: liste
            objectName: "nc-reglages-liste"
            x: 22; y: rangee.y + rangee.height + 14; width: tout.width - 44; height: pied.y - y - 10
            clip: true; spacing: 8; model: fen.visibles
            boundsBehavior: Flickable.StopAtBounds
            focus: true
            currentIndex: 0
            highlightMoveDuration: 80
            onCountChanged: if (currentIndex < 0 && count) currentIndex = 0
            onCurrentIndexChanged: if (currentIndex >= 0) positionViewAtIndex(currentIndex, ListView.Contain)
            Keys.onPressed: event => {
                var r = fen.courant
                event.accepted = true
                if (event.key === Qt.Key_Down) { if (currentIndex < count - 1) currentIndex++ }
                else if (event.key === Qt.Key_Up) { if (currentIndex > 0) currentIndex--; else if (fen.recherche.trim()) champRecherche.forceActiveFocus(); else rangee.forceActiveFocus() }
                else if (event.key === Qt.Key_Right || event.key === Qt.Key_Plus) fen.changer(r, 1)
                else if (event.key === Qt.Key_Left || event.key === Qt.Key_Minus) fen.changer(r, -1)
                else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) fen.basculer(r)
                else if (event.key === Qt.Key_Tab) fen.sectionSuivante(1)
                else if (event.key === Qt.Key_Backtab) fen.sectionSuivante(-1)
                else if (event.key === Qt.Key_Home) currentIndex = count ? 0 : -1
                else if (event.key === Qt.Key_End) currentIndex = count - 1
                else if (event.key === Qt.Key_PageDown) currentIndex = Math.min(count - 1, currentIndex + 8)
                else if (event.key === Qt.Key_PageUp) currentIndex = Math.max(0, currentIndex - 8)
                else if (event.key === Qt.Key_R && !(event.modifiers & Qt.ControlModifier)) fen.remettreLigne(r)
                else if (event.key === Qt.Key_Delete || event.key === Qt.Key_Backspace) { if (r && r.genre === "raccourci") fen.supprimerLigne(r); else fen.remettreLigne(r) }
                else if (!(event.modifiers & (Qt.ControlModifier | Qt.AltModifier)) && fen.lettre(event) !== "") {
                    // Une lettre ou un chiffre : la recherche commence
                    champRecherche.text = fen.lettre(event); champRecherche.forceActiveFocus(); champRecherche.cursorPosition = 1
                }
                else event.accepted = false
            }
            WheelHandler { onWheel: e => { liste.contentY = Math.max(0, Math.min(Math.max(0, liste.contentHeight - liste.height), liste.contentY - e.angleDelta.y)); e.accepted = true } }
            Texte { anchors.centerIn: parent; visible: liste.count === 0 && !fen.enCours; secondaire: true
                    text: fen.recherche.trim() ? Reglages.t("Aucun réglage ne correspond.", "No setting matches.") : Reglages.t("Chargement…", "Loading…") }
            delegate: Rectangle {
                id: ligne
                required property var modelData
                required property int index
                objectName: "nc-reglage-" + modelData.cle
                readonly property var r: modelData
                width: liste.width; height: Math.max(62, contenu.implicitHeight + 24); radius: 16
                color: ligne.ListView.isCurrentItem ? Couleurs.carteSurvol : Couleurs.carte
                border.width: ligne.ListView.isCurrentItem && liste.activeFocus ? 1.5 : 0; border.color: Couleurs.accent
                function editer() { saisie.forceActiveFocus(); saisie.selectAll() }
                MouseArea { anchors.fill: parent; z: -1; onClicked: { liste.currentIndex = ligne.index; liste.forceActiveFocus() } }
                Column {
                    id: contenu
                    x: 18; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 36 - commande.width - 16; spacing: 3
                    Row {
                        spacing: 8
                        Texte { text: ligne.r.nom; font.weight: Font.DemiBold; font.pixelSize: 14 }
                        Rectangle { visible: fen.recherche.trim() !== ""; anchors.verticalCenter: parent.verticalCenter; width: sec.implicitWidth + 14; height: 20; radius: 10; color: Couleurs.gris3
                                    Texte { id: sec; anchors.centerIn: parent; text: ligne.r.sectionNom; font.pixelSize: 11; secondaire: true } }
                        Ico { visible: ligne.r.modifie; anchors.verticalCenter: parent.verticalCenter; nom: "edit"; taille: 14; color: Couleurs.accent }
                    }
                    Texte { visible: ligne.r.aide !== ""; width: parent.width; text: ligne.r.aide; secondaire: true; font.pixelSize: 12; wrapMode: Text.Wrap; elide: Text.ElideNone }
                }
                // La commande, selon le genre du réglage
                Row {
                    id: commande
                    anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                    // Bascule oui / non
                    Rectangle {
                        visible: ligne.r.genre === "ouinon"; anchors.verticalCenter: parent.verticalCenter
                        width: 48; height: 28; radius: 14
                        color: ligne.r.valeur === "oui" ? Couleurs.accent : Couleurs.gris3
                        Behavior on color { ColorAnimation { duration: 140 } }
                        Rectangle { width: 22; height: 22; radius: 11; y: 3; x: ligne.r.valeur === "oui" ? parent.width - 25 : 3; color: "#ffffff"
                                    Behavior on x { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } } }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: fen.regler(ligne.r.cle, ligne.r.valeur === "oui" ? "non" : "oui") }
                        Accessible.role: Accessible.CheckBox; Accessible.name: ligne.r.nom
                    }
                    // Choix : pastilles quand ils sont peu nombreux, sinon ‹ valeur ›
                    Row {
                        visible: (ligne.r.genre === "choix" || ligne.r.genre === "hz") && ligne.r.choix.length <= 4; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                        Repeater {
                            model: ligne.r.choix.length <= 4 ? ligne.r.choix : []
                            Pastille { required property var modelData; petit: true; texte: modelData[1]; actif: ligne.r.valeur === modelData[0]; onClic: fen.regler(ligne.r.cle, modelData[0]) }
                        }
                    }
                    Row {
                        visible: (ligne.r.genre === "choix" || ligne.r.genre === "hz") && ligne.r.choix.length > 4; anchors.verticalCenter: parent.verticalCenter; spacing: 4
                        function decaler(d) {
                            var c = ligne.r.choix, i = 0
                            for (var k = 0; k < c.length; k++) if (c[k][0] === ligne.r.valeur) i = k
                            fen.regler(ligne.r.cle, c[(i + d + c.length) % c.length][0])
                        }
                        AssistantCommande { rond: true; width: 30; height: 30; icone: "chevron_left"; onClic: parent.decaler(-1) }
                        Rectangle { width: Math.max(120, aff.implicitWidth + 24); height: 30; radius: 15; color: Couleurs.gris2
                                    Texte { id: aff; anchors.centerIn: parent; text: ligne.r.affiche; font.pixelSize: 12; elide: Text.ElideRight; width: Math.min(implicitWidth, 260) } }
                        AssistantCommande { rond: true; width: 30; height: 30; icone: "chevron_right"; onClic: parent.decaler(1) }
                    }
                    // Nombre : − valeur + et une barre à glisser
                    Row {
                        visible: ligne.r.genre === "entier"; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                        AssistantCommande { rond: true; width: 30; height: 30; icone: "remove"; onClic: fen.regler(ligne.r.cle, fen.borner(ligne.r, Number(ligne.r.valeur) - ligne.r.pas)) }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter; spacing: 4
                            Texte { anchors.horizontalCenter: parent.horizontalCenter; text: ligne.r.affiche; font.pixelSize: 12; font.weight: Font.DemiBold }
                            Rectangle {
                                id: barre
                                width: 150; height: 8; radius: 4; color: Couleurs.gris3
                                readonly property real part: Math.max(0, Math.min(1, (Number(ligne.r.valeur) - ligne.r.mini) / Math.max(1, ligne.r.maxi - ligne.r.mini)))
                                Rectangle { width: parent.width * barre.part; height: parent.height; radius: 4; color: Couleurs.accent; Behavior on width { enabled: !zb.pressed; NumberAnimation { duration: 120 } } }
                                Rectangle { x: parent.width * barre.part - 7; y: -3; width: 14; height: 14; radius: 7; color: "#ffffff"; visible: zb.containsMouse || zb.pressed }
                                MouseArea {
                                    id: zb
                                    anchors.fill: parent; anchors.margins: -8; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    function valeurA(x) { return fen.borner(ligne.r, ligne.r.mini + (x - 8) / barre.width * (ligne.r.maxi - ligne.r.mini)) }
                                    onReleased: e => fen.regler(ligne.r.cle, valeurA(e.x))
                                }
                            }
                        }
                        AssistantCommande { rond: true; width: 30; height: 30; icone: "add"; onClic: fen.regler(ligne.r.cle, fen.borner(ligne.r, Number(ligne.r.valeur) + ligne.r.pas)) }
                    }
                    // Texte et dossier : un champ, Entrée pour valider
                    Rectangle {
                        visible: ligne.r.genre === "texte" || ligne.r.genre === "dossier"; anchors.verticalCenter: parent.verticalCenter
                        width: 260; height: 34; radius: 17; color: Couleurs.gris2; border.width: 1; border.color: saisie.activeFocus ? Couleurs.accent : "transparent"
                        TextInput {
                            id: saisie
                            anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; verticalAlignment: TextInput.AlignVCenter; clip: true; selectByMouse: true
                            color: Couleurs.texte; selectionColor: Couleurs.accent; font.pixelSize: 12
                            text: ligne.r.valeur
                            onAccepted: { fen.regler(ligne.r.cle, text); liste.forceActiveFocus() }
                            Keys.onEscapePressed: { text = ligne.r.valeur; liste.forceActiveFocus() }
                            Connections { target: ligne; function onRChanged() { if (!saisie.activeFocus) saisie.text = ligne.r.valeur } }
                        }
                    }
                    // Raccourci : ses touches en touche de clavier, puis changer, désactiver / réactiver, retirer
                    Rectangle {
                        visible: ligne.r.genre === "raccourci"; anchors.verticalCenter: parent.verticalCenter
                        width: touches.implicitWidth + 24; height: 32; radius: 9; color: Couleurs.gris2
                        border.width: 1; border.color: Couleurs.gris4
                        opacity: ligne.r.desactive ? 0.5 : 1
                        Texte { id: touches; anchors.centerIn: parent; text: ligne.r.affiche; font.pixelSize: 13; font.weight: Font.DemiBold
                                font.strikeout: !!ligne.r.desactive }
                    }
                    Pastille { visible: ligne.r.genre === "raccourci" && !!ligne.r.modifiable; anchors.verticalCenter: parent.verticalCenter; petit: true
                               texte: Reglages.t("Changer", "Change"); onClic: { liste.currentIndex = ligne.index; fen.capturer(ligne.r) } }
                    Pastille { visible: ligne.r.genre === "raccourci" && ligne.r.mien === ""; anchors.verticalCenter: parent.verticalCenter; petit: true
                               texte: ligne.r.desactive ? Reglages.t("Réactiver", "Turn on") : Reglages.t("Désactiver", "Disable")
                               onClic: { if (ligne.r.desactive) fen.raccourci(ligne.r, "reactiver"); else fen.raccourci(ligne.r, "desactiver") } }
                    Pastille { visible: ligne.r.genre === "raccourci" && ligne.r.mien !== ""; anchors.verticalCenter: parent.verticalCenter; petit: true
                               texte: Reglages.t("Retirer", "Remove"); onClic: fen.raccourci(ligne.r, "retirer") }
                    // Revenir à la valeur de la config (ou aux touches d'origine d'un raccourci)
                    AssistantCommande { rond: true; width: 30; height: 30; icone: "restart_alt"
                                        visible: ligne.r.modifie && !(ligne.r.genre === "raccourci" && (ligne.r.desactive || ligne.r.mien !== ""))
                                        aide: ligne.r.genre === "raccourci" ? Reglages.t("Touches d'origine", "Original keys") : Reglages.t("Valeur de la config", "Config value")
                                        onClic: fen.remettreLigne(ligne.r) }
                }
            }
        }

        // ── Capture des nouvelles touches d'un raccourci ──
        Rectangle {
            anchors.fill: parent; visible: !!fen.capture; color: Qt.rgba(0, 0, 0, 0.55); z: 20
            MouseArea { anchors.fill: parent; onClicked: fen.finCapture("") }
            Rectangle {
                anchors.centerIn: parent; width: Math.min(560, parent.width - 80); height: colCapture.implicitHeight + 48; radius: 22
                color: Couleurs.carte; border.width: 1.5; border.color: Couleurs.accent
                Column {
                    id: colCapture
                    anchors.centerIn: parent; width: parent.width - 48; spacing: 12
                    Ico { anchors.horizontalCenter: parent.horizontalCenter; nom: "keyboard"; taille: 34; color: Couleurs.accent }
                    Texte { width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; font.pixelSize: 16; font.weight: Font.Bold
                            text: fen.capture ? fen.capture.nom : "" }
                    Texte { width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; secondaire: true
                            text: Reglages.t("Appuie sur la nouvelle combinaison (avec Super, Ctrl ou Alt). Échap : annuler.",
                                             "Press the new combination (with Super, Ctrl or Alt). Esc: cancel.") }
                    Texte { width: parent.width; horizontalAlignment: Text.AlignHCenter; visible: fen.captureMessage !== ""; color: Couleurs.rouge; text: fen.captureMessage }
                }
            }
            Item {
                id: zoneCapture
                objectName: "nc-reglages-capture"
                anchors.fill: parent
                Keys.onPressed: event => {
                    event.accepted = true
                    var t = fen.combinaison(event)
                    if (t === "") return
                    if (t === "annuler") { fen.finCapture(""); return }
                    if (t === "?") { fen.captureMessage = Reglages.t("Ajoute au moins Super, Ctrl ou Alt (Échap pour annuler).", "Add at least Super, Ctrl or Alt (Esc to cancel)."); return }
                    fen.finCapture(t)
                }
                Keys.onShortcutOverride: event => { event.accepted = true }
            }
            Timer { running: !!fen.capture; interval: 20000; onTriggered: fen.finCapture("") }   // comme le retour automatique de Hyprland
        }

        // ── Pied : message de la dernière action ──
        Item {
            id: pied
            x: 22; y: tout.height - 40; width: tout.width - 44; height: 30
            Row {
                anchors.verticalCenter: parent.verticalCenter; spacing: 8
                Ico { visible: fen.message !== ""; anchors.verticalCenter: parent.verticalCenter; nom: fen.erreur ? "error" : "check_circle"; taille: 16; color: fen.erreur ? Couleurs.rouge : Couleurs.vert }
                Texte { anchors.verticalCenter: parent.verticalCenter; font.pixelSize: 12; elide: Text.ElideRight; width: pied.width - 30
                        color: fen.erreur ? Couleurs.rouge : Couleurs.texteSec
                        text: fen.enCours && !fen.message ? Reglages.t("Application…", "Applying…")
                            : (fen.message || (fen.courant && fen.courant.genre === "raccourci" && liste.activeFocus
                                ? Reglages.t("↑ ↓ choisir   Entrée nouvelles touches (ou réactiver)   Suppr désactiver / retirer   r touches d'origine   une lettre : chercher   Échap fermer",
                                             "↑ ↓ choose   Enter new keys (or turn on)   Del disable / remove   r original keys   a letter: search   Esc close") :
                                rangee.activeFocus ? Reglages.t("← → changer d'onglet   ↓ Entrée : les réglages   ↑ chercher   une lettre : chercher   Échap fermer",
                                                                            "← → switch tab   ↓ Enter: the settings   ↑ search   a letter: search   Esc close")
                                                : Reglages.t("↑ ↓ choisir (tout en haut : les onglets)   ← → changer   Entrée basculer   Tab section   r valeur de la config   une lettre : chercher   Échap fermer",
                                                             "↑ ↓ choose (at the top: the tabs)   ← → change   Enter toggle   Tab section   r config value   a letter: search   Esc close"))) }
            }
        }
    }
}
