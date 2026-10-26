// Texte de l'île : blanc ou gris système d'Apple
import QtQuick

Text {
    property bool secondaire: false
    color: secondaire ? Couleurs.texteSec : Couleurs.texte
    font.family: "Adwaita Sans"
    font.pixelSize: 13
    // Texte brut : un titre de fenêtre, un texte copié ou un nom de flux venu de l'extérieur n'est jamais lu comme du HTML
    textFormat: Text.PlainText
    elide: Text.ElideRight
    verticalAlignment: Text.AlignVCenter
}
