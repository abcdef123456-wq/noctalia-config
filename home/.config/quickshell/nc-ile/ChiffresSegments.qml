// Chiffres « segments » : l'heure en 7 segments dessinés (Rectangle), les segments éteints à peine visibles comme sur
// un afficheur ; le séparateur en deux carrés. Chargé par CarteWidget.qml d'après le champ « chiffres ».
import QtQuick

Row {
    id: seg
    required property var carte
    readonly property real h: Math.round(carte.tailleHeure * 0.72)
    readonly property real l: Math.round(h * 0.55)
    readonly property real e: Math.max(2, Math.round(h * 0.12))          // épaisseur d'un segment
    // Segments allumés, dans l'ordre a (haut), b (haut droite), c (bas droite), d (bas), e (bas gauche), f (haut gauche), g (milieu)
    readonly property var allumes: ({ "0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg", "5": "acdfg", "6": "acdefg",
                                      "7": "abc", "8": "abcdefg", "9": "abcdfg" })
    spacing: Math.round(e * 1.2)
    Repeater {
        model: seg.carte.donnees.heure(seg.carte.d).split("")
        Item {
            id: chiffre
            required property string modelData
            width: modelData === ":" ? seg.e : seg.l; height: seg.h
            Repeater {
                model: chiffre.modelData === ":" ? [] : [
                    ["a", seg.e, 0, seg.l - 2 * seg.e, seg.e], ["b", seg.l - seg.e, seg.e, seg.e, (seg.h - 3 * seg.e) / 2],
                    ["c", seg.l - seg.e, (seg.h + seg.e) / 2, seg.e, (seg.h - 3 * seg.e) / 2], ["d", seg.e, seg.h - seg.e, seg.l - 2 * seg.e, seg.e],
                    ["e", 0, (seg.h + seg.e) / 2, seg.e, (seg.h - 3 * seg.e) / 2], ["f", 0, seg.e, seg.e, (seg.h - 3 * seg.e) / 2],
                    ["g", seg.e, (seg.h - seg.e) / 2, seg.l - 2 * seg.e, seg.e]]
                Rectangle {
                    required property var modelData
                    x: modelData[1]; y: modelData[2]; width: modelData[3]; height: modelData[4]
                    radius: seg.e / 3
                    color: (seg.allumes[chiffre.modelData] || "").indexOf(modelData[0]) >= 0 ? seg.carte.pri
                           : Qt.rgba(seg.carte.pri.r, seg.carte.pri.g, seg.carte.pri.b, 0.08)
                }
            }
            Repeater {
                model: chiffre.modelData === ":" ? [seg.h / 3, seg.h * 2 / 3] : []
                Rectangle {
                    required property real modelData
                    y: Math.round(modelData - seg.e / 2)
                    width: seg.e; height: seg.e
                    color: seg.carte.pri
                }
            }
        }
    }
}
