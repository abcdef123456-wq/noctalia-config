// Texte de l'île : blanc ou gris système d'Apple
import QtQuick

Text {
    property bool secondaire: false
    color: secondaire ? "#98989d" : "white"
    font.family: "Adwaita Sans"
    font.pixelSize: 13
    elide: Text.ElideRight
    verticalAlignment: Text.AlignVCenter
}
