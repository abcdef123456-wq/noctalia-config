// Un groupe de touches de la fiche des raccourcis (Fiche.qml) : « Super + Ctrl + molette », précédé de « ou » s'il
// n'est pas le premier.
import QtQuick

Row {
    id: groupe
    property var touches: []
    property bool premier: true
    property bool edite: false                      // les touches se changent d'un toucher : bord de l'accent
    spacing: 5
    Texte { visible: !groupe.premier; text: Reglages.t("ou", "or"); secondaire: true; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
    Repeater {
        model: groupe.touches
        Row {
            id: touche
            required property string modelData
            required property int index
            spacing: 5
            Texte { visible: touche.index > 0; text: "+"; secondaire: true; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
            Rectangle {
                height: 24; width: libTouche.implicitWidth + 16; radius: 7
                color: Qt.alpha(Couleurs.carte, 0.6)
                border.width: groupe.edite ? 1.5 : 1
                border.color: groupe.edite ? Couleurs.accent : Qt.alpha(Couleurs.texte, 0.25)
                Texte { id: libTouche; anchors.centerIn: parent; text: touche.modelData; font.pixelSize: 12; font.weight: Font.DemiBold }
            }
        }
    }
}
