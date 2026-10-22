// Page « Musique » de l'île (comme l'activité en direct de l'iPhone) : grande pochette, titre, artiste, onde,
// progression avec temps écoulé / restant, commandes. Clic sur la pochette : ouvre le lecteur.
import QtQuick
import Quickshell
import Quickshell.Widgets

Item {
    id: m
    function temps(s) {
        s = Math.max(0, Math.floor(s || 0))
        return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0")
    }
    readonly property real duree: Etat.lecteur ? Etat.lecteur.length : 0
    readonly property real position: Etat.lecteur ? Etat.lecteur.position : 0

    Column {
        anchors.fill: parent
        spacing: 14

        Row {
            width: parent.width; height: 72; spacing: 14
            ClippingRectangle {
                width: 72; height: 72; radius: 16; color: Couleurs.gris2
                Image { anchors.fill: parent; source: Etat.pochette; fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize: Qt.size(144, 144) }
                Image { anchors.centerIn: parent; width: 44; height: 44; source: Etat.pochette === "" ? Etat.iconeLecteur : ""; sourceSize: Qt.size(88, 88); visible: Etat.pochette === "" }
                Ico { anchors.centerIn: parent; nom: "music_note"; taille: 32; color: Couleurs.texteSec; visible: Etat.pochette === "" && Etat.iconeLecteur === "" }
                MouseArea {
                    anchors.fill: parent
                    onClicked: if (Etat.lecteur && Etat.lecteur.canRaise) { Etat.lecteur.raise(); Etat.fermer() }
                }
            }
            Column {
                width: parent.width - 72 - 14 - 44; spacing: 3
                anchors.verticalCenter: parent.verticalCenter
                Texte { width: parent.width; text: Etat.titre !== "" ? Etat.titre : Reglages.t("Rien en lecture", "Not Playing"); font.pixelSize: 17; font.weight: Font.DemiBold }
                Texte { width: parent.width; text: Etat.artiste !== "" ? Etat.artiste : (Etat.lecteur ? Etat.lecteur.identity : ""); secondaire: true; font.pixelSize: 14 }
            }
            // Onde sonore (immobile en pause)
            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 3
                Repeater {
                    model: 5
                    Rectangle {
                        required property int index
                        width: 4; radius: 2
                        height: Etat.joue ? 8 + Etat.bandes[index] * 20 : 8
                        anchors.verticalCenter: parent.verticalCenter
                        color: Couleurs.texte; opacity: Etat.joue ? 1 : 0.4
                    }
                }
            }
        }

        // Progression
        Column {
            width: parent.width; spacing: 6
            Rectangle {
                width: parent.width; height: 6; radius: 3; color: Couleurs.gris3
                Rectangle {
                    height: parent.height; radius: 3; color: Couleurs.texte
                    width: m.duree > 0 ? parent.width * Math.min(1, m.position / m.duree) : 0
                }
                MouseArea {
                    anchors.fill: parent; anchors.margins: -8
                    enabled: Etat.lecteur && Etat.lecteur.canSeek && m.duree > 0
                    onClicked: e => { Etat.lecteur.position = m.duree * Math.max(0, Math.min(1, e.x / width)) }
                }
            }
            Item {
                width: parent.width; height: 14
                Texte { anchors.left: parent.left; text: m.temps(m.position); secondaire: true; font.pixelSize: 11 }
                Texte { anchors.right: parent.right; text: "-" + m.temps(m.duree - m.position); secondaire: true; font.pixelSize: 11 }
            }
        }

        // Commandes
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 44
            component Commande: Ico {
                id: cmd
                signal clic()
                color: Etat.lecteur ? Couleurs.texte : Couleurs.gris4
                scale: zoneClic.pressed ? 0.85 : 1
                Behavior on scale { SpringAnimation { spring: 6; damping: 0.4 } }
                MouseArea { id: zoneClic; anchors.fill: parent; anchors.margins: -10; onClicked: cmd.clic() }
            }
            Commande { nom: "fast_rewind"; taille: 34; onClic: if (Etat.lecteur) Etat.lecteur.previous() }
            Commande { nom: Etat.joue ? "pause" : "play_arrow"; taille: 44; onClic: Etat.lecturePause() }
            Commande { nom: "fast_forward"; taille: 34; onClic: if (Etat.lecteur) Etat.lecteur.next() }
        }
    }
}
