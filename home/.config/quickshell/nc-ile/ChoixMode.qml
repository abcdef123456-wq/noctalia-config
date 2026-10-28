// Une ligne de l'éditeur d'un mode Concentration (EditeurMode.qml) : un titre et des puces à choix unique.
// options : [{ valeur, texte }] ; valeur : la puce choisie ; choisi(valeur) au clic. Les textes viennent de la config ou de
// nc-energie (nom d'un profil) : texte brut (Texte.qml).
import QtQuick

Column {
    id: c
    property string titre: ""
    property var options: []
    property string valeur: ""
    property bool actif: true
    signal choisi(string valeur)
    spacing: 4
    Texte { width: parent.width; text: c.titre; secondaire: true; font.pixelSize: 11 }
    Flow {
        width: parent.width; spacing: 6
        Repeater {
            model: c.options
            BoutonEnergie {
                required property var modelData
                objectName: "choixMode"
                texte: modelData.texte
                actif: c.actif
                teinte: c.valeur === modelData.valeur ? Couleurs.accent : Couleurs.gris2
                surTeinte: c.valeur === modelData.valeur ? Couleurs.surCouleur : Couleurs.texte
                onClic: c.choisi(modelData.valeur)
            }
        }
    }
}
