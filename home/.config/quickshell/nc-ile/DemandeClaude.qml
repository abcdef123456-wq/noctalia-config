// Demande de Claude Code (nc-claude) : l'île s'étire en bannière, comme coucou. Autoriser une commande (une fois,
// toujours, ou refuser), ou choisir la réponse à une question ; « Terminal » : y répondre dans le terminal de Claude
// (il passe au premier plan). Aussi en haut de la page Claude de l'île.
import QtQuick

Item {
    id: d
    property var vue: null                                // la demande reste dessinée pendant que l'île se referme
    readonly property var dem: Agents.demande
    onDemChanged: if (dem) vue = dem
    Component.onCompleted: vue = dem
    readonly property bool question: vue !== null && vue.genre === "question"
    readonly property color teinte: (Agents.ias[vue && vue.agent ? vue.agent : "claude"] || Agents.ias.claude).couleur
    implicitHeight: question ? 78 + 40 * Math.ceil((vue.options || []).length / 2) : 146

    component Bouton: Rectangle {
        property string texte: ""
        property color teinte: Agents.couleur
        property bool principal: false
        signal clic()
        width: Math.max(86, lb.implicitWidth + 28); height: 32; radius: 16
        color: principal ? (zb.containsMouse ? Qt.lighter(teinte, 1.12) : teinte)
                         : (zb.containsMouse ? Couleurs.gris4 : Couleurs.gris2)
        scale: zb.pressed ? 0.94 : 1
        Behavior on scale { SpringAnimation { spring: 6; damping: 0.4 } }
        Texte { id: lb; anchors.centerIn: parent; text: parent.texte; font.pixelSize: 13; font.weight: Font.DemiBold
                color: parent.principal ? "#ffffff" : Couleurs.texte; width: Math.min(implicitWidth, 180) }
        MouseArea { id: zb; anchors.fill: parent; hoverEnabled: true; onClicked: parent.clic() }
    }
    function choisir(c) { if (vue) Agents.repondre(vue.id, c) }

    // En-tête : étincelle, « Claude Code · projet », bouton Terminal
    Row {
        id: tete
        x: 18; y: 14; spacing: 8
        Etincelle { anchors.verticalCenter: parent.verticalCenter; taille: 16; agent: d.vue && d.vue.agent ? d.vue.agent : "claude" }
        Texte { anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.pixelSize: 12
                text: (Agents.ias[d.vue && d.vue.agent ? d.vue.agent : "claude"] || Agents.ias.claude).titre + " · " + (d.vue ? d.vue.projet : "")
                width: Math.min(implicitWidth, d.width - 170) }
    }
    Rectangle {
        anchors.right: parent.right; anchors.rightMargin: 16; y: 10
        width: rt.implicitWidth + 30; height: 24; radius: 12
        color: zt.containsMouse ? Couleurs.gris4 : Couleurs.gris2
        Row {
            id: rt; anchors.centerIn: parent; spacing: 4
            Ico { anchors.verticalCenter: parent.verticalCenter; nom: "terminal"; taille: 14 }
            Texte { anchors.verticalCenter: parent.verticalCenter; text: "Terminal"; font.pixelSize: 12 }
        }
        MouseArea { id: zt; anchors.fill: parent; hoverEnabled: true
                    onClicked: { if (d.vue) { Agents.repondre(d.vue.id, "terminal"); Agents.allerTerminal(d.vue.terminal) } } }
    }

    Column {
        x: 18; y: 40; width: d.width - 36; spacing: 8
        Texte { width: parent.width; text: d.vue ? d.vue.titre : ""; font.pixelSize: 14; font.weight: Font.DemiBold
                wrapMode: Text.Wrap; maximumLineCount: 2 }
        // Commande ou fichier concerné, en police de terminal
        Rectangle {
            visible: !d.question && d.vue !== null && (d.vue.detail || "") !== ""
            width: parent.width; height: det.implicitHeight + 12; radius: 9; color: Couleurs.gris2
            Text {
                id: det
                x: 10; y: 6; width: parent.width - 20
                text: d.vue ? (d.vue.detail || "") : ""
                font.family: "monospace"; font.pixelSize: 12; color: Couleurs.texteDoux
                elide: Text.ElideRight; maximumLineCount: 1
            }
        }
        // Permission : Refuser · Toujours · Autoriser
        Row {
            visible: !d.question
            anchors.right: parent.right; spacing: 8
            Bouton { texte: "Refuser"; onClic: d.choisir("non") }
            Bouton { texte: "Toujours"; visible: d.vue !== null && d.vue.toujours === true; onClic: d.choisir("toujours") }
            Bouton { texte: "Autoriser"; principal: true; teinte: d.teinte; onClic: d.choisir("oui") }
        }
        // Question : un bouton par réponse
        Flow {
            visible: d.question
            width: parent.width; spacing: 8
            Repeater {
                model: d.question ? d.vue.options : []
                Bouton { required property string modelData; texte: modelData; width: (d.width - 36 - 8) / 2; onClic: d.choisir("choix:" + modelData) }
            }
        }
    }
}
