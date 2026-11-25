import QtQuick
import QtQuick.Controls

// Zone interactive au-dessus d'une surface dessinée par le panneau.
AbstractButton {
    id: action
    readonly property bool contientPointeur: hovered || visualFocus
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    background: Item {}
    contentItem: Item {}
    Keys.onReturnPressed: event => { if (!event.isAutoRepeat) clicked() }
    Keys.onEnterPressed: event => { if (!event.isAutoRepeat) clicked() }
    onVisualFocusChanged: {
        if (!visualFocus) return
        for (let p = parent; p; p = p.parent) {
            if (!(p instanceof Flickable)) continue
            const y = mapToItem(p.contentItem, 0, 0).y
            if (y < p.contentY) p.contentY = y
            else if (y + height > p.contentY + p.height) p.contentY = y + height - p.height
            break
        }
    }
    HoverHandler { cursorShape: Qt.PointingHandCursor }
    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
        visible: action.visualFocus
        color: "transparent"
        border.color: Couleurs.accent
        border.width: 2
    }
}
