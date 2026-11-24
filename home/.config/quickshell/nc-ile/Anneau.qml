// Jauge en anneau de points (widget « anneau », CarteWidget.qml) : 40 points sur un cercle, allumés jusqu'à la valeur, le
// pourcentage au milieu. Les points sont posés une fois : rien ne tourne, seule leur couleur suit la valeur. Aucun minuteur
// ici : la valeur vient de l'échantillonnage partagé de WidgetsTheme.qml.
import QtQuick

Item {
    id: anneau
    property real valeur: 0
    property string libelle: ""
    property real diametre: 160
    property color couleur: Couleurs.texte       // couleurs lisibles sur le fond du widget (CarteWidget : pri, sec)
    property color couleurSec: Couleurs.texteSec
    property string police: Couleurs.police          // le pourcentage ; policePetite : le libellé
    property string policePetite: Couleurs.police
    property int taillePetite: 11
    readonly property int points: 40
    readonly property int allumes: Number.isFinite(valeur) ? Math.round(Math.max(0, Math.min(1, valeur)) * points) : 0
    implicitWidth: diametre
    implicitHeight: diametre

    Repeater {
        model: anneau.points
        Rectangle {
            required property int index
            readonly property bool allume: index < anneau.allumes
            readonly property real angle: -Math.PI / 2 + index * 2 * Math.PI / anneau.points
            readonly property real rayonAnneau: anneau.diametre / 2 - anneau.diametre / 40
            width: Math.max(3, anneau.diametre / (allume ? 26 : 40))
            height: width
            radius: width / 2
            x: anneau.diametre / 2 + rayonAnneau * Math.cos(angle) - width / 2
            y: anneau.diametre / 2 + rayonAnneau * Math.sin(angle) - height / 2
            color: allume ? Couleurs.jauge : Couleurs.gris3
        }
    }
    Column {
        anchors.centerIn: parent
        Texte {
            anchors.horizontalCenter: parent.horizontalCenter
            text: Number.isFinite(anneau.valeur) ? Math.round(Math.max(0, Math.min(1, anneau.valeur)) * 100) + "%" : "—"
            color: anneau.couleur
            font.family: anneau.police
            font.pixelSize: Math.round(anneau.diametre * 0.24)
            font.weight: Font.Bold
        }
        Texte {
            anchors.horizontalCenter: parent.horizontalCenter
            text: anneau.libelle
            color: anneau.couleurSec
            font.family: anneau.policePetite
            font.pixelSize: anneau.taillePetite
            font.capitalization: Font.AllUppercase
            font.letterSpacing: Math.round(anneau.diametre / 60)
        }
    }
}
