// Barre latérale structurée de la fenêtre des réglages (Parametres.qml) :
// en-tête, recherche (Ctrl + F), filtre « Modifiés », et rail de navigation par catégories avec icônes.
import QtQuick
import QtQuick.Controls

Rectangle {
    id: rail
    property var sections: []
    property var catalogue: []
    property string sectionActive: ""
    property string recherche: ""
    property bool filtreModifies: false
    property int totalReglages: 0
    property int nbModifies: 0
    property bool enCours: false

    readonly property alias champRecherche: champInput
    readonly property alias zoneSections: listeSections

    signal choisirSection(string nom)
    signal changerRecherche(string texte)
    signal basculerFiltreModifies()
    signal allerListe()
    signal sectionDelta(int delta)
    signal demarrerRecherche(string lettre)
    signal relire()
    signal fermer()

    color: Qt.alpha(Couleurs.carte, Couleurs.sombre ? 0.56 : 0.72)

    // Métadonnées de chaque section (FR et EN) : icône et catégorie logique
    function metaSection(nom) {
        var carte = ({
            "Apparence":                 { ico: "palette",              cat: "bureau" },
            "Appearance":                { ico: "palette",              cat: "bureau" },
            "Fonds d'écran":             { ico: "wallpaper",            cat: "bureau" },
            "Wallpapers":                { ico: "wallpaper",            cat: "bureau" },
            "Barre et dock":             { ico: "dock_to_bottom",       cat: "bureau" },
            "Bar and Dock":              { ico: "dock_to_bottom",       cat: "bureau" },
            "Fenêtres":                  { ico: "window",               cat: "bureau" },
            "Windows":                   { ico: "window",               cat: "bureau" },
            "Animations":                { ico: "animation",            cat: "bureau" },

            "Île":                       { ico: "widgets",              cat: "ile" },
            "Island":                    { ico: "widgets",              cat: "ile" },
            "Pages de l’île":            { ico: "layers",               cat: "ile" },
            "Island pages":              { ico: "layers",               cat: "ile" },
            "Notifications":             { ico: "notifications",        cat: "ile" },

            "Énergie":                   { ico: "bolt",                 cat: "systeme" },
            "Power":                     { ico: "bolt",                 cat: "systeme" },
            "Son et luminosité":         { ico: "volume_up",            cat: "systeme" },
            "Sound and Brightness":      { ico: "volume_up",            cat: "systeme" },
            "Lumière nocturne":          { ico: "wb_twilight",          cat: "systeme" },
            "Night Light":               { ico: "wb_twilight",          cat: "systeme" },
            "Clavier et souris":         { ico: "keyboard",             cat: "systeme" },
            "Keyboard and Mouse":        { ico: "keyboard",             cat: "systeme" },
            "Veille":                    { ico: "bedtime",              cat: "systeme" },
            "Sleep":                     { ico: "bedtime",              cat: "systeme" },
            "Captures":                  { ico: "screenshot_monitor",   cat: "systeme" },
            "Screenshots":               { ico: "screenshot_monitor",   cat: "systeme" },

            "Raccourcis":                { ico: "keyboard_command_key", cat: "apps" },
            "Shortcuts":                 { ico: "keyboard_command_key", cat: "apps" },
            "Terminal":                  { ico: "terminal",             cat: "apps" },
            "Applications":              { ico: "apps",                 cat: "apps" },

            "Intelligence artificielle": { ico: "auto_awesome",         cat: "ia" },
            "Artificial intelligence":   { ico: "auto_awesome",         cat: "ia" },
            "Agents IA (coucou)":        { ico: "smart_toy",            cat: "ia" },
            "AI Agents (coucou)":        { ico: "smart_toy",            cat: "ia" },
            "Cloud JARVIS":              { ico: "cloud",                cat: "ia" },
            "JARVIS Cloud":              { ico: "cloud",                cat: "ia" },
            "Santé Garmin":              { ico: "favorite",             cat: "ia" },
            "Garmin health":             { ico: "favorite",             cat: "ia" },
            "Intégration Google":        { ico: "calendar_month",       cat: "ia" },
            "Google integration":        { ico: "calendar_month",       cat: "ia" },

            "Mises à jour":              { ico: "system_update",        cat: "maint" },
            "Updates":                   { ico: "system_update",        cat: "maint" },
            "Composants":                { ico: "extension",            cat: "maint" },
            "Components":                { ico: "extension",            cat: "maint" },
            "Nouveautés":                { ico: "new_releases",         cat: "maint" },
            "What's New":                { ico: "new_releases",         cat: "maint" }
        })
        return carte[nom] || { ico: "tune", cat: "autres" }
    }

    function libelleCategorie(id) {
        var c = ({
            bureau:  ["Bureau & style", "Desktop & style"],
            ile:     ["Île & alertes",  "Island & alerts"],
            systeme: ["Système",        "System"],
            apps:    ["Apps & touches", "Apps & shortcuts"],
            ia:      ["IA & services",  "AI & services"],
            maint:   ["Maintenance",    "Maintenance"],
            autres:  ["Autres",         "Other"]
        })[id]
        return c ? Reglages.t(c[0], c[1]) : id
    }

    // Nombre de réglages modifiés par section
    readonly property var modifiesParSection: {
        var m = {}
        for (var i = 0; i < catalogue.length; i++) {
            var r = catalogue[i]
            if (r && r.modifie) m[r.sectionNom] = (m[r.sectionNom] || 0) + 1
        }
        return m
    }

    // Liste structurée des entrées du rail (titres de catégories + sections, seulement si plusieurs catégories)
    readonly property var elementsRail: {
        var ordre = ["bureau", "ile", "systeme", "apps", "ia", "maint", "autres"]
        var groupes = {}
        for (var i = 0; i < sections.length; i++) {
            var nom = sections[i]
            var cat = metaSection(nom).cat
            if (!groupes[cat]) groupes[cat] = []
            groupes[cat].push(nom)
        }
        var nbCats = Object.keys(groupes).length
        var out = []
        for (var k = 0; k < ordre.length; k++) {
            var c = ordre[k]
            if (!groupes[c] || !groupes[c].length) continue
            if (nbCats > 1 && sections.length > 5) out.push({ genre: "titre", texte: libelleCategorie(c), nom: "" })
            for (var j = 0; j < groupes[c].length; j++) {
                var s = groupes[c][j]
                out.push({ genre: "section", nom: s, ico: metaSection(s).ico })
            }
        }
        return out
    }

    // Filet de séparation sur le bord droit du rail
    Rectangle {
        anchors.top: parent.top; anchors.bottom: parent.bottom; anchors.right: parent.right
        width: 1; color: Couleurs.separateur
    }

    // ── En-tête du rail ──
    Row {
        id: enteteRail
        x: 16; y: 16; width: parent.width - 32; height: 38; spacing: 10

        Rectangle {
            width: 34; height: 34
            anchors.verticalCenter: parent.verticalCenter
            radius: Couleurs.rayon(11, width, height)
            color: Couleurs.accentDoux
            border.width: 1; border.color: Couleurs.accentBord
            Ico { anchors.centerIn: parent; nom: "tune"; taille: 18; color: Couleurs.accent }
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter
            spacing: 1
            Texte {
                text: Reglages.t("Réglages", "Settings")
                font.pixelSize: 16; font.weight: Font.Bold
            }
            Texte {
                secondaire: true; font.pixelSize: 11
                text: rail.totalReglages > 0
                    ? (rail.totalReglages + Reglages.t(" options · ", " options · ") + Couleurs.themeActif)
                    : Couleurs.themeActif
            }
        }
    }

    // ── Champ de recherche intégré ──
    Rectangle {
        id: blocRecherche
        x: 14; y: enteteRail.y + enteteRail.height + 12
        width: parent.width - 28; height: 36
        radius: Couleurs.rayon(12, width, height)
        color: Couleurs.gris2
        border.width: champInput.activeFocus ? 1.5 : 1
        border.color: champInput.activeFocus ? Couleurs.accent : Couleurs.bordureSubtile

        Ico {
            x: 10; anchors.verticalCenter: parent.verticalCenter
            nom: "search"; taille: 16
            color: champInput.activeFocus ? Couleurs.accent : Couleurs.texteSec
        }
        TextInput {
            id: champInput
            objectName: "nc-reglages-recherche"
            anchors.fill: parent; anchors.leftMargin: 32; anchors.rightMargin: 30
            verticalAlignment: TextInput.AlignVCenter; clip: true; selectByMouse: true
            color: Couleurs.texte; selectionColor: Couleurs.accent
            font.family: Couleurs.police; font.pixelSize: 13
            onTextChanged: rail.changerRecherche(text)
            Keys.onDownPressed: {
                if (rail.recherche.trim() !== "") rail.allerListe()
                else listeSections.forceActiveFocus()
            }
            Keys.onReturnPressed: rail.allerListe()
            Keys.onTabPressed: rail.sectionDelta(1)
            Text {
                anchors.fill: parent; verticalAlignment: Text.AlignVCenter
                visible: !champInput.text
                color: Couleurs.texteSec; font: champInput.font
                textFormat: Text.PlainText
                text: Reglages.t("Chercher (Ctrl+F)…", "Search (Ctrl+F)…")
            }
        }
        Rectangle {
            visible: champInput.text !== ""
            anchors.right: parent.right; anchors.rightMargin: 5; anchors.verticalCenter: parent.verticalCenter
            width: 24; height: 24; radius: width / 2
            color: zClr.containsMouse ? Couleurs.gris3 : "transparent"
            Ico { anchors.centerIn: parent; nom: "close"; taille: 14; color: Couleurs.texteSec }
            MouseArea {
                id: zClr; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: { champInput.text = ""; champInput.forceActiveFocus() }
            }
        }
    }

    // ── Filtre rapide « Modifiés » (apparaît dès qu'un réglage est personnalisé) ──
    Rectangle {
        id: boutonModifies
        objectName: "nc-reglages-filtre-modifies"
        visible: rail.nbModifies > 0
        x: 14; y: blocRecherche.y + blocRecherche.height + 8
        width: parent.width - 28; height: visible ? 32 : 0
        radius: Couleurs.rayon(10, width, height)
        color: rail.filtreModifies ? Couleurs.accentDoux : (zMod.containsMouse ? Couleurs.gris2 : "transparent")
        border.width: 1; border.color: rail.filtreModifies ? Couleurs.accentBord : Couleurs.bordureSubtile

        Row {
            anchors.left: parent.left; anchors.leftMargin: 10; anchors.verticalCenter: parent.verticalCenter
            spacing: 7
            Ico { anchors.verticalCenter: parent.verticalCenter; nom: "edit"; taille: 14; color: rail.filtreModifies ? Couleurs.accent : Couleurs.texteSec }
            Texte {
                anchors.verticalCenter: parent.verticalCenter
                text: Reglages.t("Modifiés uniquement", "Modified only")
                font.pixelSize: 12; font.weight: rail.filtreModifies ? Font.DemiBold : Font.Medium
                color: rail.filtreModifies ? Couleurs.texte : Couleurs.texteSec
            }
        }
        Rectangle {
            anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter
            width: Math.max(20, tMod.implicitWidth + 10); height: 20; radius: height / 2
            color: rail.filtreModifies ? Couleurs.accent : Couleurs.gris3
            Texte {
                id: tMod; anchors.centerIn: parent
                text: String(rail.nbModifies); font.pixelSize: 11; font.weight: Font.Bold
                color: rail.filtreModifies ? Couleurs.surAccent : Couleurs.texte
            }
        }
        MouseArea {
            id: zMod; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
            onClicked: rail.basculerFiltreModifies()
        }
    }

    // ── Rail des sections par catégories (focusable au clavier : ← → ↑ ↓) ──
    Flickable {
        id: defileSections
        anchors.top: boutonModifies.visible ? boutonModifies.bottom : blocRecherche.bottom
        anchors.topMargin: 10
        anchors.left: parent.left; anchors.right: parent.right
        anchors.bottom: piedRail.top; anchors.bottomMargin: 8
        anchors.leftMargin: 10; anchors.rightMargin: 10
        contentWidth: width
        contentHeight: listeSections.implicitHeight + 8
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
            id: listeSections
            objectName: "nc-reglages-sections"
            width: defileSections.width
            spacing: 3
            opacity: (rail.recherche.trim() !== "" || rail.filtreModifies) && !activeFocus ? 0.5 : 1

            Keys.onPressed: event => {
                event.accepted = true
                if (event.key === Qt.Key_Right || event.key === Qt.Key_Tab) rail.sectionDelta(1)
                else if (event.key === Qt.Key_Left || event.key === Qt.Key_Backtab) rail.sectionDelta(-1)
                else if (event.key === Qt.Key_Home) { if (rail.sections.length) rail.choisirSection(rail.sections[0]) }
                else if (event.key === Qt.Key_End) { if (rail.sections.length) rail.choisirSection(rail.sections[rail.sections.length - 1]) }
                else if (event.key === Qt.Key_Down || event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) rail.allerListe()
                else if (event.key === Qt.Key_Up) champInput.forceActiveFocus()
                else if (!(event.modifiers & (Qt.ControlModifier | Qt.AltModifier)) && event.text && event.text.length === 1 && /^[a-zA-Z0-9À-ÿ]$/.test(event.text)) {
                    rail.demarrerRecherche(event.text)
                }
                else event.accepted = false
            }

            Repeater {
                model: rail.elementsRail
                Item {
                    id: itemRail
                    required property var modelData
                    readonly property bool estTitre: modelData.genre === "titre"
                    readonly property bool estActif: !estTitre && !rail.recherche.trim() && !rail.filtreModifies && rail.sectionActive === modelData.nom
                    readonly property bool estFocusClavier: estActif && listeSections.activeFocus
                    readonly property int nbMod: estTitre ? 0 : (rail.modifiesParSection[modelData.nom] || 0)

                    width: listeSections.width
                    height: estTitre ? 26 : 34

                    // En-tête de catégorie
                    Texte {
                        visible: itemRail.estTitre
                        x: 10; anchors.bottom: parent.bottom; anchors.bottomMargin: 4
                        text: itemRail.modelData.texte || ""
                        secondaire: true; font.pixelSize: 10; font.weight: Font.Bold
                        font.letterSpacing: 0.7
                        opacity: 0.72
                    }

                    // Entrée de section cliquable
                    Rectangle {
                        visible: !itemRail.estTitre
                        objectName: !itemRail.estTitre ? ("nc-reglages-tab-" + itemRail.modelData.nom) : ""
                        anchors.fill: parent
                        radius: Couleurs.rayon(10, width, height)
                        color: itemRail.estFocusClavier ? Couleurs.accent
                             : (itemRail.estActif ? Couleurs.accentDoux : (zSec.containsMouse ? Couleurs.gris2 : "transparent"))
                        border.width: itemRail.estFocusClavier ? 1.5 : (itemRail.estActif ? 1 : 0)
                        border.color: itemRail.estFocusClavier ? Couleurs.texte : Couleurs.accentBord
                        Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 110 } }

                        // Barre d'accent gauche sur la section active
                        Rectangle {
                            visible: itemRail.estActif && !itemRail.estFocusClavier
                            x: 3; anchors.verticalCenter: parent.verticalCenter
                            width: 3; height: 16
                            radius: Couleurs.rayon(2, width, height)
                            color: Couleurs.accent
                        }

                        Ico {
                            id: icoSec
                            x: 12; anchors.verticalCenter: parent.verticalCenter
                            nom: itemRail.modelData.ico || "tune"; taille: 16
                            color: itemRail.estFocusClavier ? Couleurs.surAccent
                                 : (itemRail.estActif ? Couleurs.accent : Couleurs.texteSec)
                        }

                        Texte {
                            anchors.left: icoSec.right; anchors.leftMargin: 9
                            anchors.right: pastilleMod.visible ? pastilleMod.left : parent.right
                            anchors.rightMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            text: itemRail.modelData.nom || ""
                            font.pixelSize: 13
                            font.weight: itemRail.estActif ? Font.DemiBold : Font.Medium
                            color: itemRail.estFocusClavier ? Couleurs.surAccent
                                 : (itemRail.estActif ? Couleurs.texte : Couleurs.texteDoux)
                        }

                        Rectangle {
                            id: pastilleMod
                            visible: itemRail.nbMod > 0
                            anchors.right: parent.right; anchors.rightMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            width: Math.max(18, tNb.implicitWidth + 8); height: 18
                            radius: height / 2
                            color: itemRail.estFocusClavier ? Qt.alpha(Couleurs.surAccent, 0.25) : Couleurs.gris3
                            Texte {
                                id: tNb; anchors.centerIn: parent
                                text: String(itemRail.nbMod); font.pixelSize: 10; font.weight: Font.Bold
                                color: itemRail.estFocusClavier ? Couleurs.surAccent : Couleurs.accent
                            }
                        }

                        MouseArea {
                            id: zSec; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: rail.choisirSection(itemRail.modelData.nom)
                        }
                        Accessible.role: Accessible.Button
                        Accessible.name: itemRail.modelData.nom || ""
                    }
                }
            }
        }
    }

    // ── Pied du rail : relire / fermer ──
    Item {
        id: piedRail
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        height: 46

        Rectangle {
            anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
            anchors.leftMargin: 14; anchors.rightMargin: 14
            height: 1; color: Couleurs.separateur
        }

        Row {
            anchors.left: parent.left; anchors.leftMargin: 14; anchors.verticalCenter: parent.verticalCenter
            spacing: 6
            AssistantCommande {
                rond: true; width: 30; height: 30; icone: "refresh"
                aide: Reglages.t("Relire", "Reload"); enabled: !rail.enCours
                onClic: rail.relire()
            }
            Texte {
                anchors.verticalCenter: parent.verticalCenter
                secondaire: true; font.pixelSize: 11
                text: rail.enCours ? Reglages.t("Synchronisation…", "Syncing…") : Reglages.t("À jour", "Up to date")
            }
        }
    }
}
