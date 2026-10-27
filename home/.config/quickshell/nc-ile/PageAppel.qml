// Page « Appel » (activité, comme la musique) : l'appli qui enregistre le micro, la durée de l'appel, le niveau du
// micro, un bouton pour le couper ou le réactiver (sur la source qu'utilise l'appli), un rappel quand un casque
// Bluetooth est en mode appel (son mono). Les noms venus de PipeWire s'affichent en texte brut (Texte.qml).
import QtQuick

Item {
    id: p
    readonly property real hauteur: contenu.implicitHeight
    onHauteurChanged: Etat.annoncerHauteur("appel", hauteur)
    Component.onCompleted: Etat.annoncerHauteur("appel", hauteur)

    Column {
        id: contenu
        width: parent.width
        y: Math.max(0, (parent.height - implicitHeight) / 2)
        spacing: 12

        Row {
            width: parent.width; spacing: 16
            Rectangle {
                width: 56; height: 56; radius: 28; color: Couleurs.fondVert
                anchors.verticalCenter: parent.verticalCenter
                Image {
                    anchors.centerIn: parent; width: 32; height: 32
                    source: Appel.icone; sourceSize: Qt.size(64, 64); visible: Appel.icone !== ""
                }
                Ico { anchors.centerIn: parent; nom: "call"; taille: 30; color: Couleurs.vert; visible: Appel.icone === "" }
            }
            Column {
                anchors.verticalCenter: parent.verticalCenter; spacing: 3
                width: parent.width - 56 - 16 - 16 - 40
                Texte { width: parent.width; text: Appel.appli !== "" ? Appel.appli : Appel.derniereAppli; font.pixelSize: 20; font.weight: Font.DemiBold }
                Row {
                    spacing: 6
                    Texte { text: Reglages.t("Appel en cours", "Call in progress"); secondaire: true; font.pixelSize: 14 }
                    Texte { text: "· " + Appel.dureeTexte; color: Couleurs.vert; font.pixelSize: 14; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                }
            }
            // Niveau du micro : cinq barres, immobiles et grises micro coupé
            Row {
                objectName: "nc-appel-niveau"
                anchors.verticalCenter: parent.verticalCenter; spacing: 3
                Repeater {
                    model: 5
                    Rectangle {
                        required property int index
                        readonly property real facteur: [0.5, 0.8, 1, 0.8, 0.5][index]
                        width: 4; radius: 2
                        height: Appel.muet ? 8 : 8 + Appel.niveau * 24 * facteur
                        anchors.verticalCenter: parent.verticalCenter
                        color: Appel.muet ? Couleurs.gris4 : Couleurs.vert
                    }
                }
            }
        }

        // Micro coupé : on parle, personne n'entend
        Row {
            objectName: "nc-appel-muet"
            visible: Appel.muet; spacing: 8
            Ico { anchors.verticalCenter: parent.verticalCenter; nom: "mic_off"; taille: 18; color: Couleurs.orange }
            Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Micro coupé : on ne t'entend pas.", "Microphone muted: nobody can hear you."); color: Couleurs.orange; font.weight: Font.DemiBold }
        }
        // Casque Bluetooth en profil appel : son mono, le temps de l'appel
        Row {
            objectName: "nc-appel-mono"
            visible: Appel.monoBt; spacing: 8; width: parent.width
            Ico { anchors.verticalCenter: parent.verticalCenter; nom: "headset_mic"; taille: 18; color: Couleurs.texteSec }
            Texte {
                anchors.verticalCenter: parent.verticalCenter; width: parent.width - 26; secondaire: true
                text: Reglages.t("Mode appel du casque Bluetooth : son mono le temps de l'appel.", "Bluetooth headset in call mode: mono sound for the duration of the call.")
            }
        }

        // Couper / réactiver le micro, sur la source de l'appel (sinon la source par défaut)
        Module {
            objectName: "nc-appel-micro"
            width: parent.width; height: 52; radius: 16; cliquable: true
            color: Appel.muet ? Couleurs.fondOrange : Couleurs.carte
            onClic: Appel.basculerMicro()
            Row {
                anchors.centerIn: parent; spacing: 10
                Ico { anchors.verticalCenter: parent.verticalCenter; nom: Appel.muet ? "mic" : "mic_off"; taille: 20; color: Appel.muet ? Couleurs.orange : Couleurs.texte }
                Texte {
                    anchors.verticalCenter: parent.verticalCenter; font.pixelSize: 15; font.weight: Font.DemiBold
                    color: Appel.muet ? Couleurs.orange : Couleurs.texte
                    text: Appel.muet ? Reglages.t("Réactiver le micro", "Unmute microphone") : Reglages.t("Couper le micro", "Mute microphone")
                }
                Texte { anchors.verticalCenter: parent.verticalCenter; text: Appel.nomSource; secondaire: true; visible: Appel.nomSource !== ""; width: Math.min(implicitWidth, 140) }
            }
        }
    }
}
