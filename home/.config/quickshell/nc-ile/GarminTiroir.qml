// Tiroir « Personnaliser » de Garmin.qml : cocher, décocher, monter, descendre. Les ids viennent du catalogue du moteur.
import QtQuick

Column {
    id: t
    spacing: 6
    Repeater {
        model: GarminEtat.catalogue
        delegate: Rectangle {
            id: l
            required property var modelData
            required property int index
            width: t.width; height: 40; radius: Couleurs.rayon(20, width, height)
            color: Qt.alpha(Couleurs.carte, 0.6)
            Row {
                anchors.verticalCenter: parent.verticalCenter
                x: 14; spacing: 10
                Rectangle {
                    objectName: "nc-garmin-coche-" + l.modelData.id
                    width: 22; height: 22; radius: 11
                    color: l.modelData.actif ? Couleurs.accent : "transparent"
                    border.width: 1.5; border.color: l.modelData.actif ? Couleurs.accent : Couleurs.gris4
                    Texte { anchors.centerIn: parent; visible: l.modelData.actif; text: "✓"; color: Couleurs.surAccent; font.pixelSize: 13 }
                    MouseArea { anchors.fill: parent; onClicked: GarminEtat.widget("basculer", l.modelData.id) }
                }
                Texte { anchors.verticalCenter: parent.verticalCenter; text: l.modelData.nom }
            }
            Row {
                anchors.verticalCenter: parent.verticalCenter
                anchors.right: parent.right; anchors.rightMargin: 10; spacing: 6
                visible: l.modelData.actif
                Repeater {
                    model: [{ s: "↑", a: "monter" }, { s: "↓", a: "descendre" }]
                    delegate: Rectangle {
                        required property var modelData
                        width: 28; height: 28; radius: 14; color: Couleurs.carteSurvol
                        Texte { anchors.centerIn: parent; text: parent.modelData.s }
                        MouseArea { anchors.fill: parent; onClicked: GarminEtat.widget(parent.modelData.a, l.modelData.id) }
                    }
                }
            }
        }
    }
}
