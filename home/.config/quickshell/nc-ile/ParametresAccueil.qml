import QtQuick
import QtQuick.Controls

Flickable {
    id: page
    objectName: domaine ? "nc-reglages-menu-" + domaine.id : "nc-reglages-accueil"
    property var domaines: []
    property var domaine: null
    property var stats: ({})
    property int total: 0
    property int modifies: 0
    property bool enCours: false
    readonly property var cartes: domaine ? domaine.sections : domaines
    readonly property bool apparenceDisponible: domaines.some(d => d.sections.some(s => s.id === "apparence"))

    signal choisirDomaine(string id)
    signal choisirSection(string id)
    signal montrerModifies()
    signal allerRail()
    signal demarrerRecherche(string lettre)

    contentWidth: width
    contentHeight: contenu.implicitHeight
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    flickableDirection: Flickable.VerticalFlick
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
    activeFocusOnTab: true

    onDomaineChanged: contentY = 0
    onVisibleChanged: if (visible) contentY = 0

    function suivre(item) {
        const y = item.mapToItem(contenu, 0, 0).y
        if (y < contentY) contentY = y
        else if (y + item.height > contentY + height) contentY = y + item.height - height
    }
    function nombreSections(n) { return n + Reglages.t(n === 1 ? " rubrique" : " rubriques", n === 1 ? " section" : " sections") }
    function nombreOptions(n) { return n + Reglages.t(n === 1 ? " option" : " options", n === 1 ? " option" : " options") }
    function nombreModifies(n) { return n + Reglages.t(n === 1 ? " modifiée" : " modifiées", " modified") }
    Keys.onPressed: event => {
        event.accepted = true
        if (event.key === Qt.Key_Up || event.key === Qt.Key_Left) allerRail()
        else if (event.key === Qt.Key_Down || event.key === Qt.Key_Right || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            const premier = boutons.itemAt(0)
            if (premier) premier.forceActiveFocus()
            else event.accepted = false
        } else if (!(event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)) && /^[a-zA-Z0-9À-ÿ]$/.test(event.text)) {
            demarrerRecherche(event.text)
        } else event.accepted = false
    }

    component ActionAccueil: AbstractButton {
        id: action
        property string icone: ""
        property bool principale: false
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        padding: 0
        implicitWidth: indicateur.implicitWidth + 24
        implicitHeight: 34
        Accessible.name: text
        onActiveFocusChanged: if (activeFocus) page.suivre(action)
        Keys.onReturnPressed: clicked()
        Keys.onEnterPressed: clicked()
        background: Rectangle {
            radius: Couleurs.rayonBouton
            color: action.principale ? Couleurs.surfaceActive : (action.hovered ? Couleurs.carteSurvol : Couleurs.surfaceDouce)
            border.width: action.activeFocus ? 2 : Couleurs.epaisseurBordureCarte
            border.color: action.activeFocus ? Couleurs.texte : (action.principale ? Couleurs.accentBord : Couleurs.bordureSubtile)
        }
        contentItem: Item {
            Row {
                id: indicateur
                anchors.centerIn: parent; spacing: 6
                Ico {
                    anchors.verticalCenter: parent.verticalCenter
                    nom: action.icone; taille: 15
                    color: label.color
                }
                Texte {
                    id: label
                    anchors.verticalCenter: parent.verticalCenter
                    text: action.text; font.pixelSize: 12; font.weight: Font.DemiBold
                    color: action.principale ? Couleurs.texteSurSurfaceActive : Couleurs.texte
                }
            }
        }
    }

    Column {
        id: contenu
        width: page.width
        spacing: 16
        bottomPadding: 8

        Rectangle {
            id: hero
            visible: !page.domaine
            width: parent.width
            height: apercu.implicitHeight + 36
            radius: Couleurs.rayonPanneau
            color: Couleurs.surfaceDouce
            border.width: Couleurs.epaisseurBordureCarte; border.color: Couleurs.bordureSubtile
            clip: true

            Rectangle {
                anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
                anchors.margins: Couleurs.epaisseurBordureCarte
                height: Couleurs.styleBrut || Couleurs.styleTerminal ? 3 : 2
                color: Couleurs.accent
                opacity: Couleurs.styleEditorial ? 0.48 : 0.8
            }

            Column {
                id: apercu
                anchors.left: parent.left; anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter; anchors.leftMargin: 20; anchors.rightMargin: 20
                spacing: 12

                Item {
                    width: parent.width
                    implicitHeight: Math.max(identite.implicitHeight, miniature.height)

                    Column {
                        id: identite
                        anchors.left: parent.left; anchors.right: miniature.left; anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 4
                        Texte {
                            width: parent.width
                            text: Reglages.t("THÈME ACTIF", "ACTIVE THEME")
                            color: Couleurs.accent; font.pixelSize: 10; font.weight: Font.Bold; font.letterSpacing: 1.2
                        }
                        Texte {
                            width: parent.width; elide: Text.ElideNone; wrapMode: Text.Wrap
                            text: Couleurs.nomThemeAffiche
                            font.pixelSize: Couleurs.styleEditorial ? 30 : 27; font.weight: Font.Bold
                        }
                        Texte {
                            width: parent.width; elide: Text.ElideNone; wrapMode: Text.Wrap
                            text: Couleurs.libelleArchetype + " · " + (Couleurs.sombre ? Reglages.t("Palette sombre", "Dark palette") : Reglages.t("Palette claire", "Light palette"))
                            secondaire: true; font.pixelSize: 12
                        }
                    }

                    // Une miniature construite avec les mêmes surfaces et formes que le bureau.
                    Rectangle {
                        id: miniature
                        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                        width: Math.max(84, Math.min(154, parent.width / 3)); height: 76
                        radius: Couleurs.rayonBloc; color: Couleurs.fond
                        border.width: Couleurs.epaisseurBordureCarte; border.color: Couleurs.bordureSubtile
                        Rectangle {
                            anchors.top: parent.top; anchors.topMargin: 8; anchors.horizontalCenter: parent.horizontalCenter
                            width: Couleurs.forme === "point" ? 7 : parent.width / 3; height: 7
                            radius: Couleurs.rayon(4, width, height); color: Couleurs.accent
                        }
                        Rectangle {
                            anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                            anchors.margins: 12; height: 38
                            radius: Couleurs.rayonBouton; color: Couleurs.carte
                            border.width: Couleurs.epaisseurBordureCarte; border.color: Couleurs.bordureSubtile
                            Column {
                                anchors.centerIn: parent; width: parent.width - 20; spacing: 5
                                Rectangle { width: parent.width * 0.68; height: 3; radius: Couleurs.rayon(2, width, height); color: Couleurs.texte }
                                Rectangle { width: parent.width * 0.46; height: 3; radius: Couleurs.rayon(2, width, height); color: Couleurs.accent }
                            }
                        }
                    }
                }

                Row {
                    objectName: "nc-reglages-palette"
                    spacing: 5
                    Repeater {
                        model: [Couleurs.fond, Couleurs.carte, Couleurs.texte, Couleurs.accent, Couleurs.vert, Couleurs.orange, Couleurs.violet]
                        Rectangle {
                            required property color modelData
                            width: 27; height: 15; radius: Couleurs.rayonBouton / 2
                            color: modelData; border.width: Couleurs.epaisseurBordureCarte; border.color: Couleurs.bordureSubtile
                        }
                    }
                }

                Flow {
                    width: parent.width; spacing: 8
                    ActionAccueil {
                        visible: page.apparenceDisponible
                        objectName: "nc-reglages-theme-apparence"
                        icone: "palette"; principale: true
                        text: Reglages.t("Ouvrir Apparence", "Open Appearance")
                        onClicked: page.choisirSection("apparence")
                    }
                    ActionAccueil {
                        visible: page.modifies > 0
                        objectName: "nc-reglages-accueil-modifies"
                        icone: "edit"
                        text: page.modifies + Reglages.t(page.modifies === 1 ? " réglage modifié" : " réglages modifiés", page.modifies === 1 ? " modified setting" : " modified settings")
                        onClicked: page.montrerModifies()
                    }
                }
            }
        }

        Row {
            width: parent.width; spacing: 10
            Texte {
                text: page.domaine ? Reglages.t("Rubriques", "Sections") : Reglages.t("Domaines", "Categories")
                font.pixelSize: 16; font.weight: Font.Bold
            }
            Texte {
                anchors.verticalCenter: parent.verticalCenter
                text: page.domaine ? page.nombreSections(page.cartes.length) : page.nombreOptions(page.total)
                secondaire: true; font.pixelSize: 12
            }
        }

        Grid {
            id: grille
            width: parent.width; spacing: 10
            columns: width >= 560 ? 2 : 1

            Repeater {
                id: boutons
                model: page.cartes
                AbstractButton {
                    id: carte
                    required property var modelData
                    required property int index
                    readonly property var chiffres: page.stats[page.domaine ? modelData.id : "domaine:" + modelData.id]
                    objectName: "nc-reglages-carte-" + modelData.id
                    text: modelData.nom
                    width: (grille.width - grille.spacing * (grille.columns - 1)) / grille.columns
                    height: Math.max(105, texteCarte.implicitHeight + 30)
                    hoverEnabled: true
                    focusPolicy: Qt.StrongFocus
                    padding: 0
                    Accessible.name: text
                    Accessible.description: modelData.description
                    onActiveFocusChanged: if (activeFocus) page.suivre(carte)
                    onClicked: if (page.domaine) page.choisirSection(modelData.id); else page.choisirDomaine(modelData.id)
                    Keys.onReturnPressed: clicked()
                    Keys.onEnterPressed: clicked()
                    Keys.onPressed: event => {
                        event.accepted = true
                        let delta = 0
                        if (event.key === Qt.Key_Up) delta = -grille.columns
                        else if (event.key === Qt.Key_Down) delta = grille.columns
                        else if (event.key === Qt.Key_Left) delta = -1
                        else if (event.key === Qt.Key_Right) delta = 1
                        else { event.accepted = false; return }
                        const suivante = boutons.itemAt(index + delta)
                        if (suivante) suivante.forceActiveFocus()
                        else if (delta < 0) page.allerRail()
                    }

                    background: Rectangle {
                        radius: Couleurs.rayonBloc
                        color: carte.hovered || carte.activeFocus ? Couleurs.carteSurvol : Couleurs.surfaceDouce
                        border.width: carte.activeFocus ? 2 : Couleurs.epaisseurBordureCarte
                        border.color: carte.hovered || carte.activeFocus ? Couleurs.accent : Couleurs.bordureSubtile
                    }
                    contentItem: Item {
                        Rectangle {
                            id: iconeCarte
                            x: 14; y: 15; width: 36; height: 36
                            radius: Couleurs.rayonBouton; color: Couleurs.surfaceActive
                            border.width: Couleurs.epaisseurBordureCarte; border.color: Couleurs.accentBord
                            Ico { anchors.centerIn: parent; nom: carte.modelData.icone; taille: 19; color: Couleurs.texteSurSurfaceActive }
                        }
                        Ico {
                            id: fleche
                            anchors.right: parent.right; anchors.rightMargin: 12; y: 18
                            nom: "chevron_right"; taille: 18; color: carte.hovered ? Couleurs.accent : Couleurs.texteSec
                        }
                        Column {
                            id: texteCarte
                            anchors.left: iconeCarte.right; anchors.leftMargin: 12; anchors.right: fleche.left; anchors.rightMargin: 5
                            y: 14; spacing: 4
                            Texte { width: parent.width; text: carte.text; font.pixelSize: 14; font.weight: Font.Bold }
                            Texte {
                                width: parent.width; wrapMode: Text.Wrap; elide: Text.ElideNone
                                text: carte.modelData.description; secondaire: true; font.pixelSize: 12
                            }
                            Texte {
                                width: parent.width
                                text: {
                                    const s = carte.chiffres
                                    const n = page.domaine ? page.nombreOptions(s ? s.total : 0) : page.nombreSections(carte.modelData.sections.length)
                                    if (!s || !s.modifies) return n
                                    return n + " · " + (page.domaine ? page.nombreModifies(s.modifies)
                                        : s.modifies + Reglages.t(s.modifies === 1 ? " option modifiée" : " options modifiées", s.modifies === 1 ? " modified option" : " modified options"))
                                }
                                color: carte.chiffres && carte.chiffres.modifies ? Couleurs.accent : Couleurs.texteSec
                                font.pixelSize: 11; font.weight: Font.DemiBold
                            }
                        }
                    }
                }
            }
        }
        Texte {
            visible: page.cartes.length === 0
            width: parent.width; secondaire: true
            text: page.enCours ? Reglages.t("Chargement du catalogue…", "Loading the settings catalogue…")
                 : Reglages.t("Aucune rubrique disponible.", "No sections available.")
        }
    }
}
