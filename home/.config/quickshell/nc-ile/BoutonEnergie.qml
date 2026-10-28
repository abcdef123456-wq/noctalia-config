// Petit bouton arrondi de la carte « Profils d'énergie poussés » (EnergieProfils.qml) : icône et texte, enfoncement doux au clic
import QtQuick

Rectangle {
    id: b
    property string texte: ""
    property string icone: ""
    property color teinte: Couleurs.gris2
    property color surTeinte: Couleurs.texte
    property bool actif: true
    signal clic()
    implicitWidth: ligne.implicitWidth + 28
    height: 32; radius: 16
    opacity: actif ? 1 : 0.4
    color: zone.containsMouse && actif ? Qt.lighter(teinte, 1.12) : teinte
    scale: zone.pressed && actif ? 0.95 : 1
    Behavior on scale { SpringAnimation { spring: 6; damping: 0.45 } }
    Row {
        id: ligne
        anchors.centerIn: parent; spacing: 6
        Ico { visible: b.icone !== ""; nom: b.icone; taille: 16; color: b.surTeinte; anchors.verticalCenter: parent.verticalCenter }
        Texte { text: b.texte; font.pixelSize: 12; font.weight: Font.DemiBold; color: b.surTeinte; elide: Text.ElideNone; anchors.verticalCenter: parent.verticalCenter }
    }
    MouseArea { id: zone; anchors.fill: parent; hoverEnabled: true; enabled: b.actif; onClicked: b.clic() }
}
