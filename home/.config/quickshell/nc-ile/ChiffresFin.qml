// Chiffres « fin » : l'heure en texte, dans la police des widgets (le style d'avant ; Doto : des points ronds).
// Chargé par CarteWidget.qml d'après le champ « chiffres » ; carte : le CarteWidget (couleurs, taille, heure).
import QtQuick

Texte {
    required property var carte
    text: carte.type === "horloge-fine" ? carte.donnees.lignes("horloge-fine")[0] : carte.donnees.heure(carte.d)
    color: carte.pri
    font.family: carte.police
    font.pixelSize: Math.round(carte.tailleHeure)
    font.weight: carte.type === "horloge-fine" ? Font.ExtraLight : Font.Bold
    font.variableAxes: ({ "ROND": 100 })     // police à points (Doto) : des points ronds ; sans effet ailleurs
}
