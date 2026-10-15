// Page « Recharge » (activité en direct) : pourcentage, temps avant la charge complète, santé de la batterie
import QtQuick
import Quickshell.Services.UPower

Item {
    id: charge
    readonly property real restant: Etat.batterie ? Etat.batterie.timeToFull : 0
    Row {
        anchors.verticalCenter: parent.verticalCenter; spacing: 18
        Rectangle {
            width: 76; height: 76; radius: 38; color: "#0d3318"
            Ico { anchors.centerIn: parent; nom: "bolt"; taille: 40; color: "#30d158" }
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter; spacing: 3
            Texte { text: "En charge"; secondaire: true; font.pixelSize: 14 }
            Texte { text: Etat.pourcent + " %"; font.pixelSize: 38; font.weight: Font.DemiBold; color: "#30d158" }
            Texte {
                secondaire: true
                text: charge.restant > 60
                      ? "Pleine dans " + Math.floor(charge.restant / 3600) + " h " + String(Math.floor((charge.restant % 3600) / 60)).padStart(2, "0")
                      : "Branchée sur secteur"
            }
        }
    }
}
