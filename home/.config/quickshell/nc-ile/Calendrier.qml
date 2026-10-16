// Page « Calendrier » : mois en cours (ou feuilleté avec les flèches), aujourd'hui entouré de rouge comme sur iPhone
import QtQuick

Item {
    id: ca
    property int decalage: 0
    readonly property date premier: new Date(Etat.maintenant.getFullYear(), Etat.maintenant.getMonth() + decalage, 1)
    readonly property int nbJours: new Date(premier.getFullYear(), premier.getMonth() + 1, 0).getDate()
    readonly property int debut: (premier.getDay() + 6) % 7          // lundi en premier
    onVisibleChanged: if (visible) decalage = 0

    Column {
        anchors.fill: parent; spacing: 10
        Item {
            width: parent.width; height: 34
            Texte {
                anchors.verticalCenter: parent.verticalCenter
                text: Etat.mois[ca.premier.getMonth()].charAt(0).toUpperCase() + Etat.mois[ca.premier.getMonth()].slice(1) + " " + ca.premier.getFullYear()
                font.pixelSize: 20; font.weight: Font.Bold
            }
            Row {
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                Rond { taille: 32; icone: "chevron_left"; onClic: ca.decalage-- }
                Rond { taille: 32; icone: "today"; visible: ca.decalage !== 0; onClic: ca.decalage = 0 }
                Rond { taille: 32; icone: "chevron_right"; onClic: ca.decalage++ }
            }
        }
        Grid {
            columns: 7; columnSpacing: 0; rowSpacing: 4
            Repeater {
                model: ["L", "M", "M", "J", "V", "S", "D"]
                Texte { required property string modelData; width: ca.width / 7; height: 22; text: modelData; secondaire: true; horizontalAlignment: Text.AlignHCenter; font.weight: Font.DemiBold; font.pixelSize: 12 }
            }
            Repeater {
                model: ca.debut + ca.nbJours
                Item {
                    required property int index
                    readonly property int jour: index - ca.debut + 1
                    readonly property bool aujourdhui: ca.decalage === 0 && jour === Etat.maintenant.getDate()
                    width: ca.width / 7; height: 40
                    Rectangle {
                        anchors.centerIn: parent; width: 34; height: 34; radius: 17
                        color: parent.aujourdhui ? Couleurs.rouge : "transparent"
                    }
                    Texte {
                        anchors.centerIn: parent; visible: parent.jour > 0
                        text: parent.jour; font.pixelSize: 15
                        font.weight: parent.aujourdhui ? Font.Bold : Font.Normal
                        color: parent.aujourdhui ? Couleurs.surCouleur : ((index % 7) >= 5 ? Couleurs.texteSec : Couleurs.texte)
                    }
                }
            }
        }
    }
}
