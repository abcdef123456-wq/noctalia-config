// Icône pleine et arrondie (police Material Symbols Rounded, la plus proche des SF Symbols d'Apple).
// nom : nom du symbole (ex. "wifi", "bluetooth", "dark_mode"), voir fonts.google.com/icons
import QtQuick

Text {
    property string nom: ""
    property real taille: 22
    property bool plein: true
    property int graisse: 500
    text: nom
    color: "white"
    font.family: "Material Symbols Rounded"
    font.pixelSize: taille
    font.variableAxes: ({ "FILL": plein ? 1 : 0, "wght": graisse, "opsz": Math.min(48, Math.max(20, taille)), "GRAD": 0 })
    renderType: Text.NativeRendering      // rendu FreeType : formes qui se chevauchent dessinées correctement
    horizontalAlignment: Text.AlignHCenter
    verticalAlignment: Text.AlignVCenter
}
