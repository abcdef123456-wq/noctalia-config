// Tuile de mesure de la page Mode jeu : petite icône, titre, grande valeur (la température vire à l'orange puis au rouge)
import QtQuick

Rectangle {
    property string titre: ""
    property string valeur: "–"
    property string icone: ""
    property color teinte: Couleurs.texte
    height: 62; radius: 16; color: Couleurs.carte
    Ico { x: 12; y: 10; nom: parent.icone; taille: 16; color: Couleurs.texteSec }
    Texte { x: 34; y: 9; text: parent.titre; secondaire: true; font.pixelSize: 12; width: parent.width - 44 }
    Texte { x: 12; y: 30; text: parent.valeur; font.pixelSize: 20; font.weight: Font.DemiBold; color: parent.teinte }
}
