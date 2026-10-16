// Page « Mode jeu » (activité) : effets coupés, notifications en pause ; bouton pour en sortir
import QtQuick

Item {
    Row {
        anchors.verticalCenter: parent.verticalCenter; spacing: 18
        Rectangle {
            width: 76; height: 76; radius: 38; color: "#3a2a10"
            Ico { anchors.centerIn: parent; nom: "sports_esports"; taille: 40; color: "#ff9f0a" }
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter; spacing: 3
            Texte { text: "Mode jeu"; font.pixelSize: 24; font.weight: Font.DemiBold; color: "#ff9f0a" }
            Texte { text: "Effets coupés, notifications en pause"; secondaire: true }
        }
    }
    Rond {
        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
        taille: 46; icone: "close"; actif: true; couleur: Couleurs.gris3
        onClic: Etat.faire(["hyprctl", "eval", "nc.mode_jeu()"])
    }
}
