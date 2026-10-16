// Texte de l'île : blanc ou gris système d'Apple
import QtQuick

Text {
    property bool secondaire: false
    color: secondaire ? Couleurs.texteSec : Couleurs.texte
    font.family: "Adwaita Sans"
    font.pixelSize: 13
    elide: Text.ElideRight
    verticalAlignment: Text.AlignVCenter
}
