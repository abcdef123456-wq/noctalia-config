import QtQuick
import Quickshell.Hyprland
import "WidgetBarreFenetres.js" as Fenetres

WidgetBarreLibelle {
    id: w
    readonly property var options: barre.definition
    readonly property bool plugin: barre.type === "nc/fenetres:titre"
    readonly property var moniteur: barre.ecran ? Hyprland.monitorFor(barre.ecran) : Hyprland.focusedMonitor
    readonly property var bureau: moniteur ? moniteur.activeWorkspace : null
    readonly property var fenetres: bureau ? bureau.toplevels.values.slice().sort((a, b) => Fenetres.position(a) - Fenetres.position(b)) : []
    readonly property var masquees: plugin ? Hyprland.toplevels.values.filter(t => t.workspace && t.workspace.name === "special:reduites") : []
    property var derniere: null
    readonly property var courante: {
        const active = Hyprland.activeToplevel
        if (active && Fenetres.surEcran(active, barre.ecran) && (!bureau || active.workspace === bureau)) return active
        return derniere && fenetres.indexOf(derniere) >= 0 ? derniere : (fenetres.find(t => t.activated) || fenetres[0] || null)
    }
    readonly property string classe: Fenetres.classe(courante)
    readonly property string titre: Fenetres.titre(courante)
    readonly property bool montreTexte: options.display !== "icon_only"
    readonly property bool montreIcone: options.display !== "text_only"
    readonly property real dimension: Math.max(8, Math.min(40, Number(options.icon_size ?? barre.tailleIcone)))
    readonly property int nbMasquees: masquees.length
    readonly property bool survole: zoneSurvol.hovered || panneauSurvol.hovered
    property bool developpe: false
    property var survolee: null
    onSurvoleChanged: {
        if (!plugin) return
        if (survole) { replier.stop(); if (!developpe) deplier.restart() }
        else { deplier.stop(); replier.restart() }
    }
    affiche: (courante !== null || plugin && nbMasquees > 0) && largeurContenu > 0 && hauteurContenu > 0
    glyphe: montreIcone ? "web_asset" : ""
    visuel: montreIcone && (courante || nbMasquees > 0) ? iconeFenetre : null
    libelle: montreTexte ? (barre.vertical && montreIcone ? "" : titre) : ""
    infobulle: plugin ? "" : titre
    defilement: options.title_scroll || "none"
    minimum: barre.vertical ? 0 : Math.max(0, Number(options.min_length ?? 0) - largeurIcone - espace)
    maximum: {
        if (barre.vertical) return 34
        const cap = Math.max(24, Math.min(420, Number(options.max_length ?? 240)) - largeurIcone - espace)
        return barre.limiteLargeur > 0 ? Math.min(cap, Math.max(36, barre.limiteLargeur - largeurIcone - espace)) : cap
    }
    gauche: plugin ? () => barre.page("fenetres") : null
    droit: plugin ? () => barre.ipc("vue") : null
    molette: plugin ? changer : null
    function changer(pas) {
        if (fenetres.length < 2) return
        const i = Math.max(0, fenetres.indexOf(courante))
        Fenetres.agir(Etat.bin, "aller", fenetres[(i + pas + fenetres.length) % fenetres.length])
    }
    Connections {
        target: Hyprland
        function onActiveToplevelChanged() {
            const active = Hyprland.activeToplevel
            if (active && Fenetres.surEcran(active, w.barre.ecran)) w.derniere = active
        }
    }
    HoverHandler { id: zoneSurvol; enabled: w.plugin && w.interagir && w.options.show_tooltip !== false }
    Timer { id: deplier; interval: 220; onTriggered: w.developpe = true }
    Timer { id: replier; interval: 180; onTriggered: { w.developpe = false; w.survolee = null } }
    Component {
        id: iconeFenetre
        Item {
            implicitWidth: w.barre.vertical ? Math.max(w.dimension, badge.implicitWidth) : w.dimension + (w.nbMasquees ? badge.implicitWidth + 3 : 0)
            implicitHeight: w.barre.vertical ? w.dimension + (w.nbMasquees ? badge.implicitHeight : 0) : w.dimension
            Image {
                visible: !!w.courante; x: w.barre.vertical ? (parent.width - width) / 2 : 0
                width: w.dimension; height: width; sourceSize: Qt.size(width * 2, height * 2); fillMode: Image.PreserveAspectFit
                source: w.courante ? Fenetres.icone(w.classe, Fenetres.application(w.classe)) : ""
            }
            Ico { visible: !w.courante; x: w.barre.vertical ? (parent.width - width) / 2 : 0; nom: "web_asset"; taille: w.dimension; color: w.barre.premierPlan }
            Text {
                id: badge
                visible: w.nbMasquees > 0
                x: w.barre.vertical ? (parent.width - width) / 2 : w.dimension + 3
                y: w.barre.vertical ? w.dimension : (parent.height - height) / 2
                text: w.nbMasquees > 0 ? "−" + w.nbMasquees : ""
                textFormat: Text.PlainText; color: w.barre.premierPlan
                font.family: w.barre.police; font.pixelSize: Math.max(9, w.barre.tailleTexte - 3)
            }
        }
    }
    WidgetBarrePopup {
        barre: w.barre; ancre: w
        visible: w.visible && w.developpe
        implicitWidth: 260
        implicitHeight: panneau.implicitHeight + 16
        Rectangle {
            anchors.fill: parent
            radius: Couleurs.rayon(10, width, height); color: Couleurs.carte; border.color: Couleurs.gris3
            HoverHandler { id: panneauSurvol }
            Column {
                id: panneau
                x: 8; y: 8; width: parent.width - 16; spacing: 5
                Flickable {
                    width: panneau.width
                    height: Math.min(180, grille.implicitHeight)
                    contentWidth: width; contentHeight: grille.implicitHeight; clip: true
                    Grid {
                        id: grille
                        columns: 8; spacing: 4
                        Repeater {
                            model: w.developpe ? w.fenetres.concat(w.masquees) : []
                            Item {
                                id: tuile
                                required property var modelData
                                readonly property string classe: Fenetres.classe(modelData)
                                readonly property bool masquee: w.masquees.indexOf(modelData) >= 0
                                width: 26; height: 26
                                Rectangle {
                                    anchors.fill: parent; radius: Couleurs.rayon(5, width, height)
                                    color: zone.containsMouse ? Couleurs.carteSurvol : w.courante === tuile.modelData ? Couleurs.gris3 : "transparent"
                                }
                                Image {
                                    anchors.centerIn: parent; width: 18; height: 18
                                    sourceSize: Qt.size(36, 36); fillMode: Image.PreserveAspectFit
                                    source: Fenetres.icone(tuile.classe, Fenetres.application(tuile.classe))
                                    opacity: tuile.masquee ? 0.5 : 1
                                }
                                MouseArea {
                                    id: zone
                                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onEntered: w.survolee = tuile.modelData
                                    onExited: if (w.survolee === tuile.modelData) w.survolee = null
                                    onClicked: { Fenetres.agir(Etat.bin, "aller", tuile.modelData); w.developpe = false }
                                }
                            }
                        }
                    }
                }
                Text {
                    width: panneau.width
                    text: w.survolee ? Fenetres.titre(w.survolee) + (w.masquees.indexOf(w.survolee) >= 0 ? Reglages.t(" · masquée", " · hidden") : "") : w.titre
                    textFormat: Text.PlainText; elide: Text.ElideRight; color: Couleurs.texte
                    font.family: w.barre.police; font.pixelSize: w.barre.tailleTexte; font.weight: w.barre.graisse
                }
                Row {
                    spacing: 12
                    Rond { taille: 24; visible: !!w.courante; icone: "remove"; Accessible.name: Reglages.t("Masquer la fenêtre", "Hide window"); onClic: Fenetres.agir(Etat.bin, "reduire", w.courante) }
                    Rond { taille: 24; icone: "list"; Accessible.name: Reglages.t("Fenêtres", "Windows"); onClic: { w.developpe = false; w.barre.page("fenetres") } }
                }
            }
        }
    }
}
