// Page « Terminal » (activité) : la commande qui tourne depuis plus de 10 s, sa durée, l'heure de départ, et un bouton
// pour revenir au terminal. La commande s'affiche en texte brut (Texte.qml), jamais interprétée.
import QtQuick

Item {
    id: p
    readonly property real hauteur: contenu.implicitHeight
    onHauteurChanged: Etat.annoncerHauteur("terminal", hauteur)
    Component.onCompleted: { Etat.annoncerHauteur("terminal", hauteur); Terminal.verifier() }

    Column {
        id: contenu
        width: parent.width
        y: Math.max(0, (parent.height - implicitHeight) / 2)
        spacing: 12

        Row {
            width: parent.width; spacing: 16
            Rectangle {
                width: 56; height: 56; radius: 28; color: Couleurs.gris3
                anchors.verticalCenter: parent.verticalCenter
                Ico { anchors.centerIn: parent; nom: "terminal"; taille: 30; color: Couleurs.accentClair }
            }
            Column {
                anchors.verticalCenter: parent.verticalCenter; spacing: 3
                width: parent.width - 56 - 16
                Texte { width: parent.width; text: Terminal.commande; font.pixelSize: 17; font.weight: Font.DemiBold; font.family: "monospace"; maximumLineCount: 2; wrapMode: Text.WrapAnywhere }
                Row {
                    spacing: 6
                    Texte { text: Reglages.t("En cours depuis", "Running for"); secondaire: true; font.pixelSize: 14 }
                    Texte { text: Terminal.dureeTexte; color: Couleurs.accentClair; font.pixelSize: 14; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                    Texte {
                        secondaire: true; font.pixelSize: 14
                        text: Terminal.debut > 0 ? "· " + Reglages.t("lancée à ", "started at ") + Qt.formatTime(new Date(Terminal.debut * 1000), Reglages.val("ILE_HEURE", "24") === "12" ? "h:mm AP" : "hh:mm") : ""
                    }
                }
            }
        }

        Module {
            objectName: "nc-terminal-aller"
            width: parent.width; height: 52; radius: 16; cliquable: true
            onClic: Terminal.aller()
            Row {
                anchors.centerIn: parent; spacing: 10
                Ico { anchors.verticalCenter: parent.verticalCenter; nom: "open_in_new"; taille: 20 }
                Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Aller au terminal", "Go to the terminal"); font.pixelSize: 15; font.weight: Font.DemiBold }
            }
        }
    }
}
