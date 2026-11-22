// Un bouton du panneau Cloud JARVIS : pilule arrondie, texte, couleur d'accent ou rouge (action définitive)
import QtQuick

Rectangle {
    id: b
    property string texte: ""
    property bool danger: false
    property bool principal: false
    signal clic()
    height: 30; width: t.implicitWidth + 24; radius: Couleurs.rayon(15, width, height)
    opacity: enabled ? 1 : 0.45
    color: danger ? Couleurs.rouge : (principal ? Couleurs.accent : (zone.containsMouse ? Couleurs.carteSurvol : Couleurs.carte))
    Texte { id: t; anchors.centerIn: parent; text: b.texte; color: b.danger || b.principal ? Couleurs.surAccent : Couleurs.texte }
    MouseArea { id: zone; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: b.clic() }
    Accessible.role: Accessible.Button
    Accessible.name: b.texte
}
