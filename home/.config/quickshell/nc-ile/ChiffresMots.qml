// Chiffres « mots » : l'heure en toutes lettres, à cinq minutes près (« Il est » / « neuf heures et cinq »).
// Chargé par CarteWidget.qml d'après le champ « chiffres ».
import QtQuick

Column {
    id: mots
    required property var carte
    readonly property real taille: Math.min(carte.tailleHeure, 72 * carte.t)
    spacing: 2
    Repeater {
        model: mots.carte.donnees.mots(mots.carte.d)
        Texte {
            required property string modelData
            required property int index
            x: mots.carte.ax(mots.width, width)
            width: Math.min(implicitWidth, mots.carte.largeurUtile)
            horizontalAlignment: mots.carte.aligne
            text: modelData
            color: index > 0 ? mots.carte.sec : mots.carte.pri
            font.family: mots.carte.policeDe(Math.max(11, Math.round(mots.taille * (index === 0 ? 1 : 0.6))))
            font.pixelSize: Math.max(11, Math.round(mots.taille * (index === 0 ? 1 : 0.6)))
        }
    }
}
