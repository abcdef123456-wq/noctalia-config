import QtQuick

Item {
    id: l
    required property Item barre
    property bool affiche: largeurContenu > 0 && hauteurContenu > 0
    property string glyphe: ""
    property color encreGlyphe: barre.premierPlan
    property bool plein: false
    property string libelle: ""
    property string infobulle: libelle
    property real maximum: barre.vertical ? 34 : 240
    property real minimum: 0
    property real largeurClip: 0
    property color fondClip: "transparent"
    property bool iconeApres: barre.definition.glyph_position === "after"
    property bool interagir: barre.definition.interactive !== false
    property bool texteVisible: barre.definition.peek !== true || !aGlyphe && !visuel || revele
    property string defilement: "none"
    property Component visuel: null
    property var gauche: null
    property var droit: null
    property var milieu: null
    property var retour: null
    property var avance: null
    property var molette: null
    readonly property bool survol: zone.containsMouse
    property bool revele: false
    onSurvolChanged: {
        if (survol && barre.definition.peek === true) delaiPeek.restart()
        else { delaiPeek.stop(); revele = false }
    }
    Timer { id: delaiPeek; interval: Number(l.barre.definition.peek_delay_ms ?? 100); onTriggered: l.revele = true }
    readonly property bool aGlyphe: glyphe !== "" && barre.definition.show_glyph !== false
    readonly property real largeurIcone: visuel ? pictogramme.implicitWidth : aGlyphe ? barre.tailleIcone : 0
    readonly property real hauteurIcone: visuel ? pictogramme.implicitHeight : aGlyphe ? barre.tailleIcone : 0
    readonly property real largeurTexte: aTexte ? Math.min(maximum, Math.max(minimum, texte.implicitWidth)) : 0
    readonly property real hauteurTexte: aTexte ? texte.implicitHeight : 0
    readonly property bool aTexte: texteVisible && libelle !== ""
    readonly property real espace: largeurIcone > 0 && aTexte ? (barre.vertical ? 2 : 4) : 0
    readonly property real largeurContenu: barre.vertical ? Math.max(largeurIcone, largeurTexte) : largeurIcone + espace + largeurTexte
    readonly property real hauteurContenu: barre.vertical ? hauteurIcone + espace + hauteurTexte : Math.max(hauteurIcone, hauteurTexte)
    readonly property real largeurTexteClip: !barre.vertical && largeurClip > 0
        ? Math.min(largeurTexte, Math.max(0, largeurClip - largeurIcone - espace))
        : largeurTexte
    readonly property bool estClippe: !barre.vertical && largeurClip > 0 && largeurTexteClip < largeurTexte - 0.5
    readonly property bool anime: !Reglages.sobre && aTexte && texte.implicitWidth > largeurTexte && !barre.vertical
                                  && (defilement === "always" || (defilement === "on_hover" && survol))
    implicitWidth: largeurContenu
    implicitHeight: hauteurContenu

    Item {
        id: icon
        width: l.largeurIcone; height: l.hauteurIcone
        visible: width > 0 && height > 0
        x: l.barre.vertical ? (l.width - width) / 2 : l.iconeApres ? l.largeurTexteClip + l.espace : 0
        y: l.barre.vertical ? (l.iconeApres ? l.hauteurTexte + l.espace : 0) : (l.height - height) / 2
        Ico {
            visible: !l.visuel && l.aGlyphe
            anchors.centerIn: parent
            nom: l.glyphe; color: l.encreGlyphe; taille: l.barre.tailleIcone; plein: l.plein
        }
        Loader { id: pictogramme; anchors.centerIn: parent; sourceComponent: l.visuel }
    }
    Item {
        id: vueTexte
        // Clip GPU seul pendant les animations : texte.width reste figé à l.largeurTexte (zéro ré-élision QTextLayout).
        width: l.largeurTexteClip; height: l.hauteurTexte
        visible: l.aTexte && width > 0
        clip: true
        x: l.barre.vertical ? (l.width - width) / 2 : l.iconeApres ? 0 : l.largeurIcone + l.espace
        y: l.barre.vertical ? (l.iconeApres ? 0 : l.hauteurIcone + l.espace) : (l.height - height) / 2
        Text {
            id: texte
            width: l.anime ? implicitWidth : l.largeurTexte
            text: l.libelle
            textFormat: Text.PlainText
            elide: l.anime ? Text.ElideNone : Text.ElideRight
            horizontalAlignment: l.barre.vertical ? Text.AlignHCenter : Text.AlignLeft
            color: l.barre.premierPlan
            font.family: l.barre.police
            font.pixelSize: Math.max(5, Math.round(l.barre.tailleTexte * l.barre.echelle))
            font.weight: l.barre.graisse
            onTextChanged: if (l.anime) glissement.restart()
        }
        Rectangle {
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.right: parent.right
            width: Math.min(20, parent.width * 0.45)
            visible: l.estClippe && l.fondClip.a > 0.05
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Qt.alpha(l.fondClip, 0) }
                GradientStop { position: 1; color: l.fondClip }
            }
        }
        SequentialAnimation {
            id: glissement
            running: l.anime; loops: Animation.Infinite
            onStopped: texte.x = 0
            PauseAnimation { duration: 700 }
            NumberAnimation { target: texte; property: "x"; from: 0; to: Math.min(0, l.largeurTexte - texte.implicitWidth)
                              duration: Math.max(600, Math.abs(to) * 28) }
            PauseAnimation { duration: 850 }
            PropertyAction { target: texte; property: "x"; value: 0 }
        }
    }
    MouseArea {
        id: zone
        anchors.fill: parent
        hoverEnabled: l.interagir
        enabled: l.interagir
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton | Qt.BackButton | Qt.ForwardButton
        cursorShape: l.gauche || l.droit || l.milieu || l.barre.aAction("left") ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: souris => l.barre.clic(souris.button, l.gauche, l.droit, l.milieu, l.retour, l.avance)
        onWheel: roue => { roue.accepted = l.barre.molette(roue.angleDelta.y || roue.angleDelta.x, l.molette, !roue.angleDelta.y) }
    }
    WidgetBarreBulle { barre: l.barre; ancre: l; survol: l.survol; texte: l.barre.definition.show_tooltip === false ? "" : l.infobulle }
}
