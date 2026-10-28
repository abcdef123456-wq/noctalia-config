// Une pastille de choix en verre (réglages dans les panneaux : agent, modèle, oui/non…). Actif = l'accent.
// Un clic émet `clic`.
import QtQuick

Rectangle {
    id: pastille
    property string texte: ""
    property bool actif: false
    signal clic()
    height: 28; width: etiquette.implicitWidth + 24; radius: 14
    color: actif ? Qt.alpha(Couleurs.accent, 0.30) : zone.containsMouse ? Qt.alpha(Couleurs.accent, 0.14) : Qt.alpha(Couleurs.carte, 0.6)
    border.width: 1; border.color: actif ? Qt.alpha(Couleurs.accent, 0.7) : Qt.alpha(Couleurs.texte, 0.1)
    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
    Texte {
        id: etiquette
        anchors.centerIn: parent; text: pastille.texte; font.pixelSize: 12; elide: Text.ElideNone
        font.weight: pastille.actif ? Font.DemiBold : Font.Normal
        color: pastille.actif ? Couleurs.accent : Couleurs.texte
    }
    MouseArea { id: zone; anchors.fill: parent; hoverEnabled: true; onClicked: pastille.clic() }
}
