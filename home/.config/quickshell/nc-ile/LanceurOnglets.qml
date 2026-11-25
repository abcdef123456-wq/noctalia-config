// Onglets du lanceur (Recherche.qml) : Applis, Fichiers, Actions ; l'actif en gras, souligné de 2 px, sur un filet de 1 px
import QtQuick

Item {
    id: o
    property string espace: "applis"
    property var espaces: ["applis", "fichiers", "actions"]      // ceux qui existent (Fichiers coupé : pas d'onglet)
    signal choisir(string nom)
    height: 31
    readonly property var noms: [["applis", Reglages.t("Applis", "Apps")], ["fichiers", Reglages.t("Fichiers", "Files")],
                                 ["actions", Reglages.t("Actions", "Actions")]].filter(n => espaces.indexOf(n[0]) >= 0)

    Row {
        id: rangee
        x: 20; y: 5; spacing: 19
        Repeater {
            model: o.noms
            Texte {
                required property var modelData
                readonly property bool actif: modelData[0] === o.espace
                objectName: "nc-lanceur-onglet-" + modelData[0]
                text: modelData[1]; font.pixelSize: 13
                font.weight: actif ? Font.Bold : Font.Normal
                secondaire: !actif
                MouseArea { anchors.fill: parent; anchors.margins: -6; onClicked: o.choisir(parent.modelData[0]) }
            }
        }
    }
    Rectangle { x: 18; y: o.height - 1; width: o.width - 36; height: 1; color: Qt.alpha(Couleurs.voile, 0.16) }
    Rectangle {
        id: trait
        readonly property Item cible: {
            for (let i = 0; i < rangee.children.length; i++)
                if (rangee.children[i].objectName === "nc-lanceur-onglet-" + o.espace) return rangee.children[i]
            return null
        }
        x: rangee.x + (cible ? cible.x : 0); y: o.height - 2
        width: cible ? cible.width : 0; height: 2
        radius: Couleurs.rayon(1, width, height); color: Couleurs.texte
        Behavior on x { enabled: !Reglages.sobre; NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
        Behavior on width { enabled: !Reglages.sobre; NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
    }
}
