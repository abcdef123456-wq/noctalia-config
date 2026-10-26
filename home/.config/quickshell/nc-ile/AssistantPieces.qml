// Pastilles de pièces jointes de l'assistant (issue #31) : les fichiers en attente (retirable : une croix retire le
// fichier avant l'envoi) ou ceux joints à un message déjà envoyé. Ni minuterie ni animation : rien ne tourne en fond.
// fichiers : une liste de {nom} ou de simples noms. Les noms s'affichent en texte brut (jamais interprétés).
import QtQuick

Flow {
    id: pieces
    property var fichiers: []
    property bool retirable: false
    property color teinte: Couleurs.accent
    signal retirer(int index)
    spacing: 6
    Repeater {
        model: pieces.fichiers
        Rectangle {
            id: pastille
            required property var modelData
            required property int index
            readonly property string nom: typeof modelData === "string" ? modelData : String(modelData.nom || "")
            height: 26; radius: 13
            width: Math.min(pieces.width, 8 + 14 + 5 + etiquette.implicitWidth + (pieces.retirable ? 5 + 16 + 6 : 10))
            color: pieces.retirable ? Couleurs.carte : Qt.alpha(pieces.teinte, 0.15)
            border.width: 1
            border.color: pieces.retirable ? Couleurs.gris3 : Qt.alpha(pieces.teinte, 0.35)
            Accessible.role: Accessible.StaticText
            Accessible.name: nom
            Ico {
                id: trombone
                x: 8; anchors.verticalCenter: parent.verticalCenter
                taille: 14; nom: "attach_file"; color: pieces.teinte
            }
            Texte {
                id: etiquette
                anchors.left: trombone.right; anchors.leftMargin: 5
                anchors.right: pieces.retirable ? retrait.left : parent.right
                anchors.rightMargin: pieces.retirable ? 5 : 10
                anchors.verticalCenter: parent.verticalCenter
                text: pastille.nom; textFormat: Text.PlainText; elide: Text.ElideMiddle
                font.pixelSize: 11
            }
            MouseArea {
                id: retrait
                visible: pieces.retirable
                anchors.right: parent.right; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter
                width: 16; height: 16; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: Reglages.t("Retirer ", "Remove ") + pastille.nom
                Accessible.onPressAction: pieces.retirer(pastille.index)
                Keys.onReturnPressed: pieces.retirer(pastille.index)
                Keys.onSpacePressed: pieces.retirer(pastille.index)
                Ico {
                    anchors.centerIn: parent; taille: 12; nom: "close"
                    color: retrait.containsMouse || retrait.activeFocus ? Couleurs.rouge : Couleurs.texteSec
                }
                onClicked: pieces.retirer(pastille.index)
            }
        }
    }
}
