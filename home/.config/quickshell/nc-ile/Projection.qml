// Projection sur un second écran ou un projecteur, comme Windows + P : Super + O (ou nc-ecrans).
//   Écran du PC seulement · Dupliquer (miroir) · Étendre (second écran à droite, à gauche, au-dessus ou en dessous)
//   · Second écran seulement. Le choix est retenu pour cet écran : rebranché, il reprend son mode (nc-ecrans).
//   Clic ou Entrée : appliquer · ← → choisir · ↓ ↑ le côté du second écran (Étendre) · Échap ou clic dehors : fermer
//   Super + O encore, fenêtre ouverte : mode suivant
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland

PanelWindow {
    id: w
    screen: Quickshell.screens.find(s => Hyprland.focusedMonitor && s.name === Hyprland.focusedMonitor.name) || Quickshell.screens[0]
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "nc-projection"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    color: "transparent"

    // État des écrans, lu par nc-ecrans etat : principal, autres écrans, mode et côté retenus, logo de la distribution
    property var etat: null
    readonly property var externes: etat && etat.externes ? etat.externes : []
    readonly property bool aExterne: externes.length > 0
    readonly property bool portable: etat !== null && etat.principal !== null && etat.principal.interne
    readonly property string logo: etat && etat.logo ? "file://" + etat.logo : ""

    readonly property var modes: [
        { id: "pc",      titre: Reglages.t("Écran du PC seulement", "PC screen only"),      allume: [true, false] },
        { id: "miroir",  titre: Reglages.t("Dupliquer", "Duplicate"),                       allume: [true, true] },
        { id: "etendre", titre: Reglages.t("Étendre", "Extend"),                            allume: [true, true] },
        { id: "externe", titre: Reglages.t("Second écran seulement", "Second screen only"), allume: [false, true] }
    ]
    readonly property var cotes: [
        { id: "gauche", titre: Reglages.t("← À gauche", "← Left") },
        { id: "droite", titre: Reglages.t("À droite →", "Right →") },
        { id: "haut",   titre: Reglages.t("↑ Au-dessus", "↑ Above") },
        { id: "bas",    titre: Reglages.t("↓ En dessous", "↓ Below") }
    ]
    property int choix: 2
    property string cote: "droite"
    property bool surCotes: false        // clavier sur la rangée des côtés (Étendre)

    Process {
        command: [Etat.bin + "nc-ecrans", "etat"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try { w.etat = JSON.parse(text) } catch (e) { w.etat = { externes: [], principal: null, mode: "etendre", position: "droite" } }
                w.choix = Math.max(0, w.modes.findIndex(m => m.id === w.etat.mode))
                w.cote = w.etat.position || "droite"
            }
        }
    }

    function fermer() { Etat.projection = false }
    function appliquer(mode, cote) {
        if (!aExterne) return
        Quickshell.execDetached([Etat.bin + "nc-ecrans", mode, cote || w.cote])
        fermer()
    }
    function nomEcran(e) {
        if (e.interne) return Reglages.t("Écran du portable", "Laptop screen")
        return e.description && e.description !== "" ? e.description : e.nom
    }
    function detailEcran(e) {
        if (!e.actif) return Reglages.t("éteint", "off")
        var d = e.largeur + " × " + e.hauteur + (e.hz > 0 ? " · " + e.hz + " Hz" : "")
        return e.miroir ? d + Reglages.t(" · miroir", " · mirror") : d
    }

    // Son écran disparaît (éteint par la projection, débranché) : la fenêtre se ferme, sinon l'île la croirait
    // encore ouverte et Super + O ne ferait plus rien
    Connections {
        target: Quickshell
        function onScreensChanged() { if (Quickshell.screens.indexOf(w.screen) < 0) w.fermer() }
    }
    Connections {
        target: Etat
        function onProjectionSuivante() { w.surCotes = false; w.choix = (w.choix + 1) % w.modes.length }
    }

    // Ouverture : fondu et léger zoom
    property real entree: 0
    Component.onCompleted: entree = 1
    Behavior on entree { NumberAnimation { duration: Reglages.val("EFFETS", "tous") === "aucun" ? 0 : 200; easing.type: Easing.OutCubic } }

    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.45 * w.entree)
        MouseArea { anchors.fill: parent; onClicked: w.fermer() }
    }

    // Un écran dessiné : portable (avec sa base) ou écran (avec son pied) ; allumé, il montre le bureau aux couleurs
    // du thème (dégradé de gauche à droite : de1 → de2) et, s'il le faut, le logo de la distribution
    component Dessin: Item {
        property bool allume: true
        property bool enPortable: false
        property bool avecLogo: true
        property string image: ""          // logo (les composants internes ne voient pas « w »)
        property color de1: Qt.rgba(Couleurs.accent.r, Couleurs.accent.g, Couleurs.accent.b, 0.30)
        property color de2: Qt.rgba(Couleurs.violet.r, Couleurs.violet.g, Couleurs.violet.b, 0.30)
        width: 64; height: 52
        Rectangle {
            id: dalle
            width: parent.width; height: 40; radius: 6
            color: Couleurs.fond
            border.width: 1.5
            border.color: allume ? Couleurs.accent : Couleurs.gris4
            Rectangle {
                anchors.fill: parent; anchors.margins: 3; radius: 3.5
                visible: allume
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: de1 }
                    GradientStop { position: 1; color: de2 }
                }
            }
            Image {
                anchors.centerIn: parent
                width: 22; height: 26
                visible: allume && avecLogo && image !== ""
                source: image
                cache: false
                fillMode: Image.PreserveAspectFit
                smooth: true; mipmap: true
                sourceSize.height: 78
            }
        }
        // Base du portable
        Rectangle {
            visible: enPortable
            anchors { top: dalle.bottom; topMargin: 2; horizontalCenter: dalle.horizontalCenter }
            width: dalle.width + 14; height: 5; radius: 2.5
            color: allume ? Couleurs.gris5 : Couleurs.gris3
        }
        // Pied de l'écran
        Rectangle {
            id: pied
            visible: !enPortable
            anchors { top: dalle.bottom; horizontalCenter: dalle.horizontalCenter }
            width: 5; height: 6
            color: allume ? Couleurs.gris5 : Couleurs.gris3
        }
        Rectangle {
            visible: !enPortable
            anchors { top: pied.bottom; horizontalCenter: dalle.horizontalCenter }
            width: 24; height: 3; radius: 1.5
            color: allume ? Couleurs.gris5 : Couleurs.gris3
        }
    }

    Item {
        anchors.fill: parent
        focus: true
        Keys.onPressed: e => {
            if (e.key === Qt.Key_Escape) { w.fermer() }
            else if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter || e.key === Qt.Key_Space) {
                if (w.surCotes) w.appliquer("etendre", w.cote); else w.appliquer(w.modes[w.choix].id)
            }
            else if (e.key === Qt.Key_Left || e.key === Qt.Key_Right) {
                var d = e.key === Qt.Key_Left ? -1 : 1
                if (w.surCotes) {
                    var i = w.cotes.findIndex(c => c.id === w.cote)
                    w.cote = w.cotes[(i + d + w.cotes.length) % w.cotes.length].id
                } else w.choix = (w.choix + d + w.modes.length) % w.modes.length
            }
            else if (e.key === Qt.Key_Down && w.modes[w.choix].id === "etendre") { w.surCotes = true }
            else if (e.key === Qt.Key_Up) { w.surCotes = false }
            else if (e.key === Qt.Key_Tab) { w.surCotes = false; w.choix = (w.choix + 1) % w.modes.length }
            else return
            e.accepted = true
        }
    }

    Rectangle {
        id: carte
        anchors.centerIn: parent
        anchors.verticalCenterOffset: (1 - w.entree) * 16
        width: contenu.implicitWidth + 56
        height: contenu.implicitHeight + 52
        radius: 30
        color: Couleurs.fond
        border.width: 1
        border.color: Couleurs.gris3
        opacity: w.entree
        scale: 0.97 + 0.03 * w.entree
        MouseArea { anchors.fill: parent }      // un clic dans la carte ne la ferme pas

        Column {
            id: contenu
            anchors.centerIn: parent
            spacing: 20

            // ── En-tête : logo de la distribution, titre, écrans branchés ──
            Row {
                spacing: 14
                Image {
                    width: 40; height: 48
                    anchors.verticalCenter: parent.verticalCenter
                    visible: w.logo !== ""
                    source: w.logo
                    cache: false
                    fillMode: Image.PreserveAspectFit
                    smooth: true; mipmap: true
                    sourceSize.height: 144
                }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 3
                    Texte { text: Reglages.t("Projeter", "Project"); font.pixelSize: 21; font.weight: Font.DemiBold }
                    Texte {
                        secondaire: true
                        text: (w.etat && w.etat.distribution ? w.etat.distribution + "  ·  " : "")
                              + (w.etat === null ? "…"
                                 : w.aExterne ? Reglages.t((w.externes.length + 1) + " écrans", (w.externes.length + 1) + " displays")
                                 : Reglages.t("Aucun autre écran branché", "No other display connected"))
                    }
                }
            }

            // ── Les quatre modes ──
            Row {
                spacing: 12
                Repeater {
                    model: w.modes
                    Rectangle {
                        id: tuile
                        required property var modelData
                        required property int index
                        readonly property bool choisi: w.choix === index && !(w.surCotes && modelData.id !== "etendre")
                        readonly property bool actuel: w.aExterne && w.etat && w.etat.mode === modelData.id
                        width: 172; height: 164; radius: 20
                        color: zt.containsMouse && w.aExterne ? Couleurs.carteSurvol : Couleurs.carte
                        border.width: choisi ? 2 : 0
                        border.color: Couleurs.accent
                        opacity: w.aExterne ? 1 : 0.5
                        Behavior on color { ColorAnimation { duration: 120 } }

                        Row {
                            anchors { top: parent.top; topMargin: 26; horizontalCenter: parent.horizontalCenter }
                            spacing: tuile.modelData.id === "etendre" ? 4 : 12
                            Dessin {
                                image: w.logo
                                enPortable: w.portable
                                allume: tuile.modelData.allume[0]
                                // Étendre : un seul bureau sur les deux écrans, le dégradé continue de l'un à l'autre
                                de2: tuile.modelData.id === "etendre"
                                     ? Qt.rgba((Couleurs.accent.r + Couleurs.violet.r) / 2, (Couleurs.accent.g + Couleurs.violet.g) / 2, (Couleurs.accent.b + Couleurs.violet.b) / 2, 0.30)
                                     : Qt.rgba(Couleurs.violet.r, Couleurs.violet.g, Couleurs.violet.b, 0.30)
                            }
                            Dessin {
                                image: w.logo
                                allume: tuile.modelData.allume[1]
                                avecLogo: tuile.modelData.id !== "etendre"
                                de1: tuile.modelData.id === "etendre"
                                     ? Qt.rgba((Couleurs.accent.r + Couleurs.violet.r) / 2, (Couleurs.accent.g + Couleurs.violet.g) / 2, (Couleurs.accent.b + Couleurs.violet.b) / 2, 0.30)
                                     : Qt.rgba(Couleurs.accent.r, Couleurs.accent.g, Couleurs.accent.b, 0.30)
                            }
                        }
                        Texte {
                            anchors { top: parent.top; topMargin: 100; horizontalCenter: parent.horizontalCenter }
                            width: parent.width - 24
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignTop
                            wrapMode: Text.WordWrap
                            maximumLineCount: 2
                            text: tuile.modelData.titre
                            font.pixelSize: 14; font.weight: Font.DemiBold
                        }
                        // Mode en cours
                        Rectangle {
                            visible: tuile.actuel
                            anchors { top: parent.top; topMargin: 9; right: parent.right; rightMargin: 9 }
                            width: 8; height: 8; radius: 4
                            color: Couleurs.vert
                        }
                        MouseArea {
                            id: zt
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: w.aExterne ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onEntered: { w.surCotes = false; w.choix = tuile.index }
                            onClicked: w.appliquer(tuile.modelData.id)
                        }
                    }
                }
            }

            // ── Côté du second écran (Étendre) ──
            Row {
                spacing: 8
                opacity: w.modes[w.choix].id === "etendre" && w.aExterne ? 1 : 0.4
                Behavior on opacity { NumberAnimation { duration: 150 } }
                Texte {
                    anchors.verticalCenter: parent.verticalCenter
                    secondaire: true
                    rightPadding: 6
                    text: Reglages.t("Second écran :", "Second display:")
                }
                Repeater {
                    model: w.cotes
                    Rectangle {
                        id: puce
                        required property var modelData
                        readonly property bool pris: w.cote === modelData.id
                        width: etiq.implicitWidth + 28; height: 34; radius: 17
                        color: pris ? Couleurs.accent : (zc.containsMouse ? Couleurs.gris3 : Couleurs.gris2)
                        border.width: w.surCotes && pris ? 2 : 0
                        border.color: Couleurs.texte
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Texte {
                            id: etiq
                            anchors.centerIn: parent
                            text: puce.modelData.titre
                            color: puce.pris ? Couleurs.surAccent : Couleurs.texte
                            font.weight: Font.Medium
                        }
                        MouseArea {
                            id: zc
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { w.cote = puce.modelData.id; w.appliquer("etendre", puce.modelData.id) }
                        }
                    }
                }
            }

            // ── Écrans branchés ──
            Column {
                spacing: 6
                width: parent.width
                Repeater {
                    model: w.etat && w.etat.principal ? [w.etat.principal].concat(w.externes) : w.externes
                    Row {
                        required property var modelData
                        spacing: 10
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 7; height: 7; radius: 3.5
                            color: modelData.actif ? Couleurs.vert : Couleurs.gris5
                        }
                        Texte { text: w.nomEcran(modelData); font.weight: Font.Medium }
                        Texte { secondaire: true; text: w.detailEcran(modelData) }
                    }
                }
                Texte {
                    visible: w.etat !== null && !w.aExterne
                    secondaire: true
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: Reglages.t("Branche un écran ou un projecteur (HDMI, USB-C…) : il apparaîtra ici.",
                                     "Connect a display or a projector (HDMI, USB-C…): it will show up here.")
                }
            }

            // ── Pied : raccourcis clavier, projection sans fil ──
            Item {
                width: parent.width
                height: 34
                Texte {
                    anchors.verticalCenter: parent.verticalCenter
                    secondaire: true
                    font.pixelSize: 12
                    text: Reglages.t("← → choisir   ↓ côté   Entrée appliquer   Échap fermer",
                                     "← → choose   ↓ side   Enter apply   Esc close")
                }
                Rectangle {
                    visible: w.etat !== null && w.etat.sansfil === true
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    width: sf.implicitWidth + 28; height: 34; radius: 17
                    color: zs.containsMouse ? Couleurs.gris3 : Couleurs.gris2
                    Texte { id: sf; anchors.centerIn: parent; text: Reglages.t("Projeter sans fil…", "Wireless display…"); font.weight: Font.Medium }
                    MouseArea {
                        id: zs
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { Quickshell.execDetached([Etat.bin + "nc-ecrans", "sans-fil"]); w.fermer() }
                    }
                }
            }
        }
    }
}
