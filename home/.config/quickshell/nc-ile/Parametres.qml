// Fenêtre des réglages (Super + Alt + , ; nc-reglages fenetre ; appli « Réglages du bureau ») : tous les réglages de
// nc-reglages, en graphique, avec une recherche. Même catalogue et mêmes règles que l'écran du terminal : la fenêtre
// lit « nc-reglages catalogue » (JSON) et change une valeur par « nc-reglages set », qui applique aussitôt
// (Hyprland, Noctalia, île, veille, terminal…). Une fenêtre classique de Hyprland (règle nc-reglages-fenetre).
// Sections en pastilles ; une recherche (Ctrl + F) cherche dans toutes les sections, sans accent ni majuscule ;
// bascule oui/non, pastilles de choix, curseur pour les nombres, champ pour le texte ; ↺ remet la valeur de la config.
// Au clavier : ↑ ↓ choisir, ← → changer la valeur, Entrée ou Espace basculer (ou saisir un texte), r valeur de la
// config, Tab et Maj + Tab changer de section, une lettre lance la recherche, Échap vide la recherche puis ferme.
// Même cadrage que le cockpit : nc/automatismes.lua la place à l'ouverture.
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
    property var file: []                           // écritures en attente : [[cle, valeur]]
    readonly property bool enCours: lecture.running || ecriture.running
    readonly property var sections: { var s = []; catalogue.forEach(r => { if (s.indexOf(r.sectionNom) < 0) s.push(r.sectionNom) }); return s }
    readonly property var visibles: {
        var q = normaliser(recherche.trim())
        if (q) return catalogue.filter(r => normaliser(r.nom + " " + r.aide + " " + r.cle + " " + r.sectionNom + " " + r.affiche).indexOf(q) >= 0)
        return catalogue.filter(r => r.sectionNom === section)
    }
    function normaliser(t) { return String(t).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "") }
    function afficher(nom) { surEcran(nom); visible = true; charger(); liste.forceActiveFocus() }
    function surEcran(nom) {
        var ecrans = Quickshell.screens
        for (var i = 0; i < ecrans.length; i++) if (ecrans[i].name === nom) { screen = ecrans[i]; return }
    }
    onClosed: close()
    function close() { visible = false }
    function charger() { if (!lecture.running) lecture.running = true }
    // Une valeur : nc-reglages set (ou reset pour revenir à la config) ; les demandes se suivent une par une
    function regler(cle, valeur) { file.push([cle, valeur]); file = file; suivant() }
    function remettre(cle) { regler(cle, null) }
    function suivant() {
        if (ecriture.running || !file.length) return
        var d = file.shift(); file = file
        ecriture.command = d[1] === null ? [bin + "nc-reglages", "reset", d[0]] : [bin + "nc-reglages", "set", d[0], String(d[1])]
        ecriture.running = true
    }
    function reglage(cle) { for (var i = 0; i < catalogue.length; i++) if (catalogue[i].cle === cle) return catalogue[i]; return null }
    function borner(r, v) { v = Math.round(v / r.pas) * r.pas; return Math.max(r.mini, Math.min(r.maxi, v)) }
    // ← → : la valeur d'après (d = 1) ou d'avant (d = -1), selon le genre du réglage
    function changer(r, d) {
        if (!r) return
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
        if (event.text && /^[\p{L}\p{N}]$/u.test(event.text)) return event.text
        if ((event.key >= Qt.Key_A && event.key <= Qt.Key_Z) || (event.key >= Qt.Key_0 && event.key <= Qt.Key_9)) return String.fromCharCode(event.key).toLowerCase()
        return ""
    }
    readonly property var courant: liste.currentIndex >= 0 && liste.currentIndex < visibles.length ? visibles[liste.currentIndex] : null

    Process {
        id: lecture
        command: [fen.bin + "nc-reglages", "catalogue"]
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

    Shortcut { sequence: "Escape"; onActivated: { if (fen.recherche !== "") { fen.recherche = ""; champRecherche.text = "" } else fen.close() } }
    Shortcut { sequences: ["Ctrl+F", "Ctrl+K"]; onActivated: { champRecherche.forceActiveFocus(); champRecherche.selectAll() } }

    component Pastille: Rectangle {
        id: pastille
        property string texte: ""
        property bool actif: false
        property bool petit: false
        signal clic()
        width: etiquette.implicitWidth + (petit ? 22 : 30); height: petit ? 30 : 36; radius: height / 2
        color: actif ? Couleurs.gris4 : (zp.containsMouse ? Couleurs.gris3 : Couleurs.gris2)
        border.width: actif ? 1.5 : 0; border.color: Couleurs.accent
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
                Keys.onDownPressed: liste.forceActiveFocus()
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
            x: 22; y: entete.y + entete.height + 14; width: tout.width - 44; spacing: 8
            opacity: fen.recherche.trim() ? 0.45 : 1
            Repeater {
                model: fen.sections
                Pastille { required property string modelData; texte: modelData; actif: !fen.recherche.trim() && fen.section === modelData
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
                else if (event.key === Qt.Key_Up) { if (currentIndex > 0) currentIndex--; else champRecherche.forceActiveFocus() }
                else if (event.key === Qt.Key_Right || event.key === Qt.Key_Plus) fen.changer(r, 1)
                else if (event.key === Qt.Key_Left || event.key === Qt.Key_Minus) fen.changer(r, -1)
                else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) fen.basculer(r)
                else if (event.key === Qt.Key_Tab) fen.sectionSuivante(1)
                else if (event.key === Qt.Key_Backtab) fen.sectionSuivante(-1)
                else if (event.key === Qt.Key_Home) currentIndex = count ? 0 : -1
                else if (event.key === Qt.Key_End) currentIndex = count - 1
                else if (event.key === Qt.Key_PageDown) currentIndex = Math.min(count - 1, currentIndex + 8)
                else if (event.key === Qt.Key_PageUp) currentIndex = Math.max(0, currentIndex - 8)
                else if ((event.key === Qt.Key_R || event.key === Qt.Key_Delete) && !(event.modifiers & Qt.ControlModifier)) { if (r && r.modifie) fen.remettre(r.cle) }
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
                    // Revenir à la valeur de la config
                    AssistantCommande { rond: true; width: 30; height: 30; icone: "restart_alt"; visible: ligne.r.modifie; aide: Reglages.t("Valeur de la config", "Config value"); onClic: fen.remettre(ligne.r.cle) }
                }
            }
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
                            : (fen.message || Reglages.t("↑ ↓ choisir   ← → changer   Entrée basculer   Tab section   r valeur de la config   une lettre : chercher   Échap fermer",
                                                         "↑ ↓ choose   ← → change   Enter toggle   Tab section   r config value   a letter: search   Esc close")) }
            }
        }
    }
}
