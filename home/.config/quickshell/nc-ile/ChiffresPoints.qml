// Chiffres « points » : chaque chiffre dessiné en matrice de 5 × 7 points ronds (les formes des chiffres de Doto), le
// séparateur en deux points ronds de la même taille (le « : » de Doto sort en croix). Rien ne dépend d'une police
// installée : même dessin partout. Chargé par CarteWidget.qml d'après le champ « chiffres ».
import QtQuick

Row {
    id: points
    required property var carte
    readonly property real pas: Math.max(3, carte.tailleHeure * 0.72 / 7)     // 7 rangées = la hauteur d'un chiffre
    readonly property real point: Math.round(pas * 0.86)
    // Une rangée = 5 bits, de gauche à droite (16 : colonne 1 … 1 : colonne 5)
    readonly property var formes: ({
        "0": [4, 10, 17, 17, 17, 10, 4], "1": [4, 12, 20, 4, 4, 4, 31], "2": [14, 17, 1, 6, 8, 16, 31],
        "3": [31, 1, 2, 6, 1, 17, 14], "4": [2, 6, 10, 18, 31, 2, 2], "5": [31, 16, 22, 25, 1, 17, 14],
        "6": [6, 8, 16, 22, 25, 17, 14], "7": [31, 1, 2, 2, 4, 8, 8], "8": [14, 17, 17, 14, 17, 17, 14],
        "9": [14, 17, 19, 13, 1, 2, 12]
    })
    spacing: Math.round(pas * 1.2)
    Repeater {
        model: points.carte.donnees.heure(points.carte.d).split("")
        Item {
            id: signe
            required property string modelData
            readonly property var forme: points.formes[modelData] || []
            width: Math.round(points.pas * (modelData === ":" ? 1 : 5)); height: Math.round(points.pas * 7)
            // Séparateur : deux points, rangées 2 et 4 (au milieu de la hauteur)
            Repeater {
                model: signe.modelData === ":" ? [2, 4] : []
                Rectangle {
                    required property int modelData
                    objectName: "nc-chiffres-separateur"
                    y: Math.round(modelData * points.pas)
                    width: points.point; height: width; radius: width / 2
                    color: points.carte.pri
                }
            }
            Repeater {
                model: signe.forme.length > 0 ? 35 : 0
                Rectangle {
                    required property int index
                    visible: ((signe.forme[Math.floor(index / 5)] >> (4 - index % 5)) & 1) === 1
                    x: Math.round(index % 5 * points.pas); y: Math.round(Math.floor(index / 5) * points.pas)
                    width: points.point; height: width; radius: width / 2
                    color: points.carte.pri
                }
            }
        }
    }
}
