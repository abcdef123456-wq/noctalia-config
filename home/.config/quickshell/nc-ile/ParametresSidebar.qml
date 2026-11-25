// Volet des réglages : accueil, domaines extensibles, recherche et filtre global.
import QtQuick
import QtQuick.Controls

Rectangle {
    id: rail
    property var domaines: []
    property var chiffres: ({})
    property string domaineActif: ""
    property string sectionActive: ""
    property string recherche: ""
    property bool filtreModifies: false
    property int totalReglages: 0
    property int nbModifies: 0
    property bool enCours: false
    property var domainesDeplies: ({})
    property string repere: "accueil"
    readonly property bool filtreActif: recherche.trim() !== "" || filtreModifies
    readonly property string routeActive: sectionActive ? "section:" + sectionActive
        : domaineActif ? "domaine:" + domaineActif : "accueil"
    onRouteActiveChanged: Qt.callLater(synchroniserRoute)

    readonly property alias champRecherche: champInput
    readonly property alias zoneSections: listeSections

    signal choisirAccueil()
    signal choisirDomaine(string id)
    signal choisirSection(string id)
    signal changerRecherche(string texte)
    signal basculerFiltreModifies()
    signal allerListe()
    signal sectionDelta(int delta)
    signal demarrerRecherche(string lettre)
    signal relire()

    color: Couleurs.surfaceDouce

    function deplier(id, oui) {
        if (!!domainesDeplies[id] === oui) return
        const copie = Object.assign({}, domainesDeplies)
        if (oui) copie[id] = true
        else delete copie[id]
        domainesDeplies = copie
    }
    function synchroniserRoute() {
        if (domaineActif) deplier(domaineActif, true)
        viser(routeActive)
    }
    function viser(cle) {
        repere = cle
        Qt.callLater(revelerRepere)
    }
    function revelerRepere() {
        const i = elementsRail.findIndex(e => e.cle === repere)
        const ligne = i >= 0 ? entreesRail.itemAt(i) : null
        if (!ligne) return
        const y = ligne.y
        if (y < defileSections.contentY) defileSections.contentY = y
        else if (y + ligne.height > defileSections.contentY + defileSections.height)
            defileSections.contentY = y + ligne.height - defileSections.height
    }
    function choisir(e) {
        viser(e.cle)
        if (e.genre === "accueil") choisirAccueil()
        else if (e.genre === "domaine") { deplier(e.id, true); choisirDomaine(e.id) }
        else choisirSection(e.id)
    }
    function basculerDomaine(e) {
        deplier(e.id, !domainesDeplies[e.id])
        viser(e.cle)
    }

    readonly property var elementsRail: {
        const entrees = [{ genre: "accueil", cle: "accueil", nom: Reglages.t("Accueil", "Home"), icone: "home" }]
        for (const d of domaines) {
            entrees.push({ genre: "domaine", cle: "domaine:" + d.id, id: d.id, nom: d.nom, icone: d.icone })
            if (!domainesDeplies[d.id]) continue
            for (const s of d.sections)
                entrees.push({ genre: "section", cle: "section:" + s.id, id: s.id, nom: s.nom, icone: s.icone })
        }
        return entrees
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
            radius: Couleurs.rayonBouton
            color: Couleurs.surfaceActive
            border.width: Couleurs.epaisseurBordureCarte; border.color: Couleurs.accentBord
            Ico { anchors.centerIn: parent; nom: "tune"; taille: 18; color: Couleurs.texteSurSurfaceActive }
        }
        Column {
            width: enteteRail.width - 44
            anchors.verticalCenter: parent.verticalCenter
            spacing: 1
            Texte {
                width: parent.width
                text: Reglages.t("Réglages", "Settings")
                font.pixelSize: 16; font.weight: Font.Bold
            }
            Texte {
                width: parent.width
                secondaire: true; font.pixelSize: 11
                text: rail.totalReglages > 0
                    ? (rail.totalReglages + Reglages.t(" options · ", " options · ") + Couleurs.nomThemeAffiche)
                    : Couleurs.nomThemeAffiche
            }
        }
    }

    // ── Champ de recherche intégré ──
    Rectangle {
        id: blocRecherche
        x: 14; y: enteteRail.y + enteteRail.height + 12
        width: parent.width - 28; height: 36
        radius: Couleurs.rayonBouton
        color: Couleurs.surfaceDouce
        border.width: champInput.activeFocus ? 2 : Couleurs.epaisseurBordureCarte
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
            color: Couleurs.texte; selectionColor: Couleurs.accent; selectedTextColor: Couleurs.surAccent
            font.family: Couleurs.police; font.pixelSize: 13
            Accessible.name: Reglages.t("Chercher dans tous les réglages", "Search all settings")
            onTextChanged: rail.changerRecherche(text)
            Keys.onDownPressed: {
                if (rail.recherche.trim() !== "") rail.allerListe()
                else listeSections.forceActiveFocus()
            }
            Keys.onReturnPressed: rail.allerListe()
            Keys.onTabPressed: rail.sectionDelta(1)
            Keys.onBacktabPressed: rail.sectionDelta(-1)
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
            width: 24; height: 24; radius: Couleurs.rayonBouton
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
        visible: rail.nbModifies > 0 || rail.filtreModifies
        x: 14; y: blocRecherche.y + blocRecherche.height + 8
        width: parent.width - 28; height: visible ? 32 : 0
        radius: Couleurs.rayonBouton
        color: rail.filtreModifies ? Couleurs.surfaceActive : (zMod.containsMouse || activeFocus ? Couleurs.carteSurvol : Couleurs.surfaceDouce)
        border.width: activeFocus ? 2 : Couleurs.epaisseurBordureCarte
        border.color: activeFocus ? Couleurs.accent : rail.filtreModifies ? Couleurs.accentBord : Couleurs.bordureSubtile
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: Reglages.t("Modifiés uniquement", "Modified only")
        Accessible.checkable: true
        Accessible.checked: rail.filtreModifies
        Accessible.onPressAction: rail.basculerFiltreModifies()
        Keys.onReturnPressed: rail.basculerFiltreModifies()
        Keys.onSpacePressed: rail.basculerFiltreModifies()

        Row {
            anchors.left: parent.left; anchors.leftMargin: 10; anchors.verticalCenter: parent.verticalCenter
            spacing: 7
            Ico { anchors.verticalCenter: parent.verticalCenter; nom: "edit"; taille: 14; color: rail.filtreModifies ? Couleurs.texteSurSurfaceActive : Couleurs.texteSec }
            Texte {
                anchors.verticalCenter: parent.verticalCenter
                text: Reglages.t("Modifiés uniquement", "Modified only")
                font.pixelSize: 12; font.weight: rail.filtreModifies ? Font.DemiBold : Font.Medium
                color: rail.filtreModifies ? Couleurs.texteSurSurfaceActive : Couleurs.texteSec
            }
        }
        Rectangle {
            anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter
            width: Math.max(20, tMod.implicitWidth + 10); height: 20; radius: Couleurs.rayonBouton
            color: rail.filtreModifies ? Qt.alpha(Couleurs.texteSurSurfaceActive, 0.16) : Couleurs.gris3
            Texte {
                id: tMod; anchors.centerIn: parent
                text: String(rail.nbModifies); font.pixelSize: 11; font.weight: Font.Bold
                color: rail.filtreModifies ? Couleurs.texteSurSurfaceActive : Couleurs.texte
            }
        }
        MouseArea {
            id: zMod; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
            onClicked: rail.basculerFiltreModifies()
        }
    }

    // ── Navigation hiérarchique : ↑↓ pour parcourir, Entrée pour ouvrir, ←→ pour replier/déplier ──
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
            activeFocusOnTab: true
            onActiveFocusChanged: {
                if (!activeFocus) return
                viser(elementsRail.some(e => e.cle === routeActive) ? routeActive : (rail.domaineActif ? "domaine:" + rail.domaineActif : "accueil"))
            }

            Keys.onPressed: event => {
                if (event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)) { event.accepted = false; return }
                const liste = rail.elementsRail
                const i = Math.max(0, liste.findIndex(e => e.cle === rail.repere))
                const e = liste[i]
                event.accepted = true
                if (event.key === Qt.Key_Down) {
                    if (i < liste.length - 1) rail.viser(liste[i + 1].cle)
                    else rail.allerListe()
                } else if (event.key === Qt.Key_Up) {
                    if (i > 0) rail.viser(liste[i - 1].cle)
                    else champInput.forceActiveFocus()
                } else if (event.key === Qt.Key_Right) {
                    if (e.genre === "domaine") {
                        if (!rail.domainesDeplies[e.id]) rail.deplier(e.id, true)
                        else if (i + 1 < liste.length) rail.viser(liste[i + 1].cle)
                    } else if (e.genre === "section") rail.sectionDelta(1)
                    else rail.allerListe()
                } else if (event.key === Qt.Key_Left) {
                    if (e.genre === "domaine") rail.deplier(e.id, false)
                    else if (e.genre === "section") rail.sectionDelta(-1)
                    else champInput.forceActiveFocus()
                } else if (event.key === Qt.Key_Tab) rail.sectionDelta(1)
                else if (event.key === Qt.Key_Backtab) rail.sectionDelta(-1)
                else if (event.key === Qt.Key_Home) rail.viser(liste[0].cle)
                else if (event.key === Qt.Key_End) rail.viser(liste[liste.length - 1].cle)
                else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) rail.choisir(e)
                else if (/^[a-zA-Z0-9À-ÿ]$/.test(event.text)) rail.demarrerRecherche(event.text)
                else event.accepted = false
            }

            Repeater {
                id: entreesRail
                model: rail.elementsRail
                Rectangle {
                    id: itemRail
                    required property var modelData
                    readonly property bool estDomaine: modelData.genre === "domaine"
                    readonly property bool estSection: modelData.genre === "section"
                    readonly property bool estActif: !rail.filtreActif && modelData.cle === rail.routeActive
                    readonly property bool estFocusClavier: modelData.cle === rail.repere && listeSections.activeFocus
                    readonly property bool deployee: estDomaine && !!rail.domainesDeplies[modelData.id]
                    readonly property var compte: rail.chiffres[estSection ? modelData.id : modelData.cle]
                    readonly property int nbMod: compte ? compte.modifies : 0
                    readonly property color encre: estActif ? Couleurs.texteSurSurfaceActive : Couleurs.texte

                    objectName: estDomaine ? "nc-reglages-domaine-" + modelData.id
                        : estSection ? "nc-reglages-tab-" + modelData.id : "nc-reglages-tab-accueil"
                    x: estSection ? 15 : 0
                    width: listeSections.width - x
                    height: estSection ? 32 : 37
                    radius: Couleurs.rayonBouton
                    color: estActif ? Couleurs.surfaceActive
                        : (zSec.containsMouse || zDeplier.containsMouse || estFocusClavier) ? Couleurs.carteSurvol : "transparent"
                    border.width: estFocusClavier ? 2 : estActif ? Couleurs.epaisseurBordureCarte : 0
                    border.color: estFocusClavier ? (estActif ? encre : Couleurs.accent) : Couleurs.accentBord
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData.nom
                    Accessible.onPressAction: rail.choisir(modelData)

                    Rectangle {
                        visible: itemRail.estSection && !itemRail.estActif
                        x: 1; anchors.verticalCenter: parent.verticalCenter
                        width: 1; height: parent.height
                        color: Couleurs.separateur
                    }
                    Ico {
                        id: icoSec
                        x: 11; anchors.verticalCenter: parent.verticalCenter
                        nom: itemRail.modelData.icone; taille: itemRail.estSection ? 15 : 17
                        color: itemRail.estActif ? itemRail.encre : Couleurs.texteSec
                    }
                    Texte {
                        anchors.left: icoSec.right; anchors.leftMargin: 8
                        anchors.right: pastilleMod.visible ? pastilleMod.left : controleDroit.left
                        anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter
                        text: itemRail.modelData.nom
                        font.pixelSize: itemRail.estSection ? 12 : 13
                        font.weight: itemRail.estSection && !itemRail.estActif ? Font.Medium : Font.DemiBold
                        color: itemRail.encre
                    }
                    Rectangle {
                        id: pastilleMod
                        visible: itemRail.nbMod > 0
                        anchors.right: controleDroit.left; anchors.rightMargin: 4; anchors.verticalCenter: parent.verticalCenter
                        width: Math.max(18, tNb.implicitWidth + 8); height: 18
                        radius: Couleurs.rayonBouton
                        color: itemRail.estActif ? Qt.alpha(itemRail.encre, 0.16) : Couleurs.gris3
                        Texte {
                            id: tNb; anchors.centerIn: parent
                            text: String(itemRail.nbMod); font.pixelSize: 10; font.weight: Font.Bold
                            color: itemRail.estActif ? itemRail.encre : Couleurs.accent
                        }
                    }

                    MouseArea {
                        id: zSec
                        anchors.top: parent.top; anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: controleDroit.left
                        hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: rail.choisir(itemRail.modelData)
                    }
                    Item {
                        id: controleDroit
                        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                        width: itemRail.estDomaine ? 35 : 0; height: parent.height
                        visible: itemRail.estDomaine
                        objectName: itemRail.estDomaine ? "nc-reglages-deplier-" + itemRail.modelData.id : ""
                        Accessible.role: Accessible.Button
                        Accessible.name: itemRail.deployee ? Reglages.t("Replier", "Collapse") : Reglages.t("Déplier", "Expand")
                        Accessible.description: itemRail.modelData.nom
                        Accessible.onPressAction: rail.basculerDomaine(itemRail.modelData)
                        Rectangle {
                            anchors.centerIn: parent
                            width: 25; height: 25; radius: Couleurs.rayonBouton
                            color: zDeplier.containsMouse ? Qt.alpha(itemRail.encre, 0.16) : "transparent"
                            Ico {
                                anchors.centerIn: parent
                                nom: itemRail.deployee ? "expand_more" : "chevron_right"
                                taille: 17; color: itemRail.encre
                            }
                        }
                        MouseArea {
                            id: zDeplier
                            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: rail.basculerDomaine(itemRail.modelData)
                        }
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
