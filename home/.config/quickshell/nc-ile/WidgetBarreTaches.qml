pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Effects
import Quickshell.Hyprland
import "WidgetBarreFenetres.js" as Fenetres

Item {
    id: w
    required property Item barre
    readonly property var options: barre.definition
    readonly property var moniteur: barre.ecran ? Hyprland.monitorFor(barre.ecran) : Hyprland.focusedMonitor
    readonly property bool groupe: options.group_by_workspace === true
    readonly property bool titres: !barre.vertical && !groupe && options.show_window_title === true
    readonly property string contenuGroupe: options.workspace_group_content || "icons"
    readonly property color accent: barre.teinte(options.active_indicator_color || "primary", Couleurs.accent)
    readonly property real taille: Math.max(8, Math.min(28, Math.round(barre.tailleIcone * Number(options.icon_scale ?? (barre.type === "dock" ? 1.25 : 1.0)))))
    readonly property real espace: Number(options.item_spacing ?? 4)
    readonly property real plafond: Math.max(taille, Math.min(Number(options.taskbar_max_width ?? 8192),
        barre.ecran ? Math.floor(0.40 * (barre.vertical ? barre.ecran.height : barre.ecran.width)) : 480))
    readonly property var fenetres: Hyprland.toplevels.values.filter(t => {
        const b = t.workspace
        return (options.show_all_outputs === true || Fenetres.surEcran(t, barre.ecran))
            && (!b || b.id > 0 && (b.active || (options.hidden_workspaces || []).indexOf(b.name) < 0))
            && (options.only_active_workspace !== true || !b || b.active)
    })
    readonly property var groupes: {
        if (!groupe) return [{ bureau: null, applis: tuiles(fenetres, options.pinned || [], options.show_running !== false, false), fenetres: fenetres }]
        const choix = Hyprland.workspaces.values.filter(b => b.id > 0 && (options.show_all_outputs === true || b.monitor === moniteur)
            && (options.only_active_workspace !== true || b.active) && (b.active || (options.hidden_workspaces || []).indexOf(b.name) < 0))
        return choix.sort((a, b) => a.id - b.id).map(b => {
            const liste = fenetres.filter(f => f.workspace === b)
            return { bureau: b, fenetres: liste, applis: contenuGroupe === "icons" ? tuiles(liste, [], true, options.group_single_icon_per_app === true) : [] }
        }).filter(g => options.hide_empty_workspaces !== true || g.fenetres.length > 0)
    }
    readonly property int nbTuiles: groupes.length > 0 ? groupes[0].applis.length : 0
    readonly property real maxTitre: Math.max(0, Math.min(Number(options.window_title_max_width ?? 100), (plafond - Math.max(0, nbTuiles - 1) * espace) / Math.max(1, nbTuiles) - taille - 4))
    readonly property bool affiche: groupe ? groupes.length > 0 : nbTuiles > 0
    implicitWidth: barre.vertical ? strip.implicitWidth : Math.min(plafond, strip.implicitWidth)
    implicitHeight: barre.vertical ? Math.min(plafond, strip.implicitHeight) : strip.implicitHeight

    function tuiles(fenetres, epingles, montrer, regrouper) {
        const applications = [], parId = new Map()
        for (const id of epingles) {
            const entree = Fenetres.application(String(id))
            if (!entree || parId.has(entree.id)) continue
            const app = { id: entree.id, classe: id, entree: entree, epinglee: true, fenetres: [] }
            applications.push(app); parId.set(app.id, app)
        }
        for (const t of fenetres) {
            const classe = Fenetres.classe(t), entree = Fenetres.application(classe), id = entree ? entree.id : classe.toLowerCase()
            const app = parId.get(id)
            if (app) { app.fenetres.push(t); continue }
            if (!montrer) continue
            const nouvelle = { id: id, classe: classe, entree: entree, epinglee: false, fenetres: [t] }
            applications.push(nouvelle)
            if (regrouper && id) parId.set(id, nouvelle)
        }
        return applications
    }
    function activer(app) {
        if (app.fenetres.length) {
            const i = app.fenetres.indexOf(Hyprland.activeToplevel)
            Fenetres.agir(Etat.bin, "aller", app.fenetres[(i + 1) % app.fenetres.length])
        } else if (app.entree) app.entree.execute()
    }
    function changer(pas) {
        if (fenetres.length < 2) return
        const i = Math.max(0, fenetres.indexOf(Hyprland.activeToplevel))
        Fenetres.agir(Etat.bin, "aller", fenetres[(i + pas + fenetres.length) % fenetres.length])
    }

    Flickable {
        anchors.fill: parent
        clip: true
        contentWidth: strip.implicitWidth
        contentHeight: strip.implicitHeight
        flickableDirection: w.barre.vertical ? Flickable.VerticalFlick : Flickable.HorizontalFlick
        interactive: w.barre.vertical ? contentHeight > height : contentWidth > width
        Grid {
            id: strip
            columns: w.barre.vertical ? 1 : Math.max(1, w.groupes.length)
            horizontalItemAlignment: Grid.AlignHCenter
            verticalItemAlignment: Grid.AlignVCenter
            spacing: w.espace
            Repeater {
                model: w.groupes
                Item {
                    id: groupeVisuel
                    required property var modelData
                    readonly property var bureau: modelData.bureau
                    readonly property bool tag: !!bureau && w.options.show_workspace_label !== false
                    readonly property bool contour: !!bureau && w.options.workspace_group_capsule !== false
                    readonly property bool actif: !!bureau && bureau.active && (w.options.focused_output_only !== true || bureau.focused)
                    readonly property color couleurTag: !bureau ? w.barre.premierPlan : bureau.urgent ? w.barre.teinte(w.options.urgent_color || "error", Couleurs.rouge)
                        : actif ? w.barre.teinte(w.options.focused_color || "primary", Couleurs.accent)
                        : modelData.fenetres.length ? w.barre.teinte(w.options.occupied_color || "secondary", w.barre.premierPlan)
                        : w.barre.teinte(w.options.empty_color || "outline", Couleurs.texteSec)
                    readonly property bool compact: !!bureau && w.contenuGroupe !== "icons"
                    readonly property int marge: contour ? 3 : 0
                    width: contenu.implicitWidth + 2 * marge
                    height: contenu.implicitHeight + 2 * marge
                    Rectangle {
                        anchors.fill: parent
                        visible: groupeVisuel.contour
                        radius: Math.min(width / 2, height / 2, Number(w.options.capsule_radius ?? 10))
                        color: Qt.alpha(groupeVisuel.couleurTag, groupeVisuel.actif ? 0.15 : 0.06)
                        border.color: Qt.alpha(groupeVisuel.couleurTag, groupeVisuel.actif ? 0.6 : 0.3)
                    }
                    Grid {
                        id: contenu
                        anchors.centerIn: parent
                        columns: w.barre.vertical ? 1 : Math.max(1, groupeVisuel.modelData.applis.length + (groupeVisuel.tag ? 1 : 0) + (groupeVisuel.compact ? 1 : 0))
                        horizontalItemAlignment: Grid.AlignHCenter
                        verticalItemAlignment: Grid.AlignVCenter
                        spacing: groupeVisuel.bureau ? 4 : w.espace
                        Text {
                            visible: groupeVisuel.tag
                            text: groupeVisuel.bureau ? (w.options.label_source === "id" ? String(groupeVisuel.bureau.id) : groupeVisuel.bureau.name) : ""
                            textFormat: Text.PlainText; elide: Text.ElideRight
                            color: groupeVisuel.couleurTag; width: Math.min(implicitWidth, 45)
                            font.family: w.barre.police; font.pixelSize: w.barre.tailleTexte; font.weight: w.barre.graisse
                            MouseArea { anchors.fill: parent; onClicked: if (groupeVisuel.bureau) groupeVisuel.bureau.activate(); cursorShape: Qt.PointingHandCursor }
                        }
                        Item {
                            visible: groupeVisuel.compact
                            width: points.implicitWidth
                            height: points.implicitHeight
                            Row {
                                id: points
                                spacing: 3
                                readonly property var clients: groupeVisuel.modelData.fenetres
                                Repeater {
                                    model: w.contenuGroupe === "dots" ? Math.min(5, points.clients.length) : 0
                                    Rectangle {
                                        required property int index
                                        width: 5; height: width; radius: width / 2
                                        anchors.verticalCenter: points.verticalCenter
                                        color: w.options.show_active_indicator !== false && Hyprland.activeToplevel === points.clients[index] ? w.accent : groupeVisuel.couleurTag
                                    }
                                }
                                Text {
                                    readonly property int nombre: points.clients.length
                                    visible: w.contenuGroupe === "count" || nombre > 5
                                    text: w.contenuGroupe === "dots" ? "+" + (nombre - 5) : String(nombre)
                                    color: groupeVisuel.couleurTag
                                    font.family: w.barre.police; font.pixelSize: w.barre.tailleTexte
                                }
                            }
                            MouseArea { anchors.fill: parent; onClicked: if (groupeVisuel.bureau) groupeVisuel.bureau.activate(); cursorShape: Qt.PointingHandCursor }
                        }
                        Repeater {
                            model: groupeVisuel.modelData.applis
                            Tuile { required property var modelData; app: modelData }
                        }
                    }
                }
            }
        }
    }
    component Tuile: Item {
        id: tuile
        required property var app
        readonly property var active: app.fenetres.find(t => t.activated) || null
        readonly property var cible: active || app.fenetres[0] || null
        readonly property string nom: (cible ? Fenetres.titre(cible) : app.entree?.name) || app.classe || ""
        readonly property bool uneLigne: w.titres && w.maxTitre > 12 && nom !== ""
        property bool menuOuvert: false
        width: w.taille + (uneLigne ? etiquette.width + 4 : 0)
        height: w.taille + 4
        Image {
            id: logo
            width: w.taille; height: width
            x: w.barre.vertical ? (parent.width - width) / 2 : 0
            source: Fenetres.icone(tuile.app.classe, tuile.app.entree, w.options.prefer_symbolic_icons === true)
            fillMode: Image.PreserveAspectFit; sourceSize: Qt.size(width * 2, height * 2)
            opacity: !tuile.app.fenetres.length ? Number(w.options.pinned_opacity ?? 0.50)
                        : tuile.active ? Number(w.options.active_opacity ?? 1) : Number(w.options.inactive_opacity ?? 1)
            layer.enabled: w.options.colorize_icons === true || String(source).indexOf("-symbolic") >= 0
            layer.effect: MultiEffect { colorization: 1; colorizationColor: w.barre.premierPlan }
        }
        Text {
            id: etiquette
            visible: tuile.uneLigne
            anchors.left: logo.right; anchors.leftMargin: 4; anchors.verticalCenter: logo.verticalCenter
            width: Math.min(implicitWidth, w.maxTitre)
            text: tuile.nom; textFormat: Text.PlainText; elide: Text.ElideRight
            color: w.barre.premierPlan; font.family: w.barre.police; font.pixelSize: w.barre.tailleTexte; font.weight: w.barre.graisse
        }
        Rectangle {
            visible: !!tuile.active && w.options.show_active_indicator !== false
            anchors.horizontalCenter: logo.horizontalCenter; anchors.bottom: parent.bottom
            width: 4; height: 2; radius: height / 2; color: w.accent
        }
        Column {
            visible: tuile.app.fenetres.length > 1
            anchors.right: logo.right; anchors.bottom: logo.bottom
            spacing: 1
            Repeater { model: Math.min(3, tuile.app.fenetres.length); Rectangle { width: 3; height: width; radius: width / 2; color: w.accent; border.color: Couleurs.carte; border.width: 0.5 } }
        }
        MouseArea {
            id: zone
            anchors.fill: parent; hoverEnabled: true
            enabled: w.options.interactive !== false
            acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton | Qt.BackButton | Qt.ForwardButton
            cursorShape: Qt.PointingHandCursor
            onClicked: e => {
                if (e.button === Qt.LeftButton) w.activer(tuile.app)
                else if (e.button === Qt.MiddleButton) Fenetres.agir(Etat.bin, "fermer", tuile.cible)
                else w.barre.clic(e.button, null, () => tuile.menuOuvert = !tuile.menuOuvert)
            }
            onWheel: e => { e.accepted = w.barre.molette(e.angleDelta.y || e.angleDelta.x, w.changer, !e.angleDelta.y) }
        }
        WidgetBarreBulle { barre: w.barre; ancre: tuile; survol: zone.containsMouse && !tuile.menuOuvert; texte: w.options.show_tooltip !== false ? tuile.nom : "" }
        WidgetBarrePopup {
            barre: w.barre; ancre: tuile
            visible: tuile.visible && tuile.menuOuvert
            grabFocus: true
            onVisibleChanged: if (!visible) tuile.menuOuvert = false
            implicitWidth: 230
            implicitHeight: menu.implicitHeight + 12
            Rectangle {
                anchors.fill: parent; color: Couleurs.carte; radius: Couleurs.rayon(8, width, height); border.color: Couleurs.gris3
                Column {
                    id: menu
                    anchors.centerIn: parent; width: parent.width - 12
                    Choix { visible: !!tuile.app.entree; label: Reglages.t("Nouvelle fenêtre", "New window"); onChoisi: { tuile.menuOuvert = false; tuile.app.entree.execute() } }
                    Choix { visible: !!tuile.cible; label: Reglages.t("Masquer", "Hide"); onChoisi: { tuile.menuOuvert = false; Fenetres.agir(Etat.bin, "reduire", tuile.cible) } }
                    Choix { visible: !!tuile.cible; label: Reglages.t("Fermer", "Close"); onChoisi: { tuile.menuOuvert = false; Fenetres.agir(Etat.bin, "fermer", tuile.cible) } }
                }
            }
        }
    }
    component Choix: Rectangle {
        id: choix
        required property string label
        signal choisi()
        width: parent.width; height: 29; radius: Couleurs.rayon(5, width, height)
        color: action.containsMouse ? Couleurs.carteSurvol : "transparent"
        Text {
            anchors.verticalCenter: parent.verticalCenter; x: 7
            text: choix.label; color: Couleurs.texte
            font.family: w.barre.police; font.pixelSize: w.barre.tailleTexte
        }
        MouseArea {
            id: action
            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
            onClicked: choix.choisi()
        }
    }
}
