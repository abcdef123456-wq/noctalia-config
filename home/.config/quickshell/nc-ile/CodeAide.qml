// Une aide de touche du pied de l'espace de code (Code.qml) : la touche dans une petite pastille, puis ce qu'elle fait.
// Sa largeur naturelle (implicitWidth) sert à Code.qml pour masquer les aides les moins utiles quand la place manque.
import QtQuick

Row {
    id: aide
    property string touche: ""
    property string libelle: ""
    readonly property color teinte: Qt.tint(Couleurs.texteSec, Qt.alpha(Couleurs.texte, 0.35))
    spacing: 6
    Rectangle {
        width: libTouche.implicitWidth + 12; height: 20; radius: 6
        color: Qt.alpha(Couleurs.carte, 0.7); border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.1)
        Texte { id: libTouche; anchors.centerIn: parent; text: aide.touche; font.pixelSize: 10; elide: Text.ElideNone; color: aide.teinte }
    }
    Texte { height: 20; text: aide.libelle; font.pixelSize: 11; elide: Text.ElideNone; color: aide.teinte }
}
