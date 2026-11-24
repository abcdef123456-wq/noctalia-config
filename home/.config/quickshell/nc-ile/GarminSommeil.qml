// Barre segmentée des 4 phases du sommeil (Garmin.qml) : `phases` = [profond, léger, paradoxal, éveil] en secondes ; cachée sans données
import QtQuick

Column {
    id: so
    property var phases: []
    readonly property var durees: phases.map(v => typeof v === "number" && Number.isFinite(v) && v >= 0 ? v : null)
    readonly property real total: durees.reduce((t, v) => t + (v || 0), 0)
    readonly property int segments: durees.filter(v => v > 0).length
    readonly property var couleurs: [Couleurs.bleu, Qt.tint(Couleurs.bleu, Qt.alpha(Couleurs.texte, 0.38)), Couleurs.violet, Couleurs.orange]
    readonly property var noms: [Reglages.t("Profond", "Deep"), Reglages.t("Léger", "Light"), "REM", Reglages.t("Éveil", "Awake")]
    visible: total > 0
    spacing: 9
    Row {
        id: barre
        objectName: "nc-garmin-sommeil-barre"
        width: parent.width; height: 14; spacing: 3
        Repeater {
            model: so.durees
            delegate: Rectangle {
                required property var modelData
                required property int index
                objectName: "nc-garmin-sommeil-" + index
                visible: modelData > 0
                height: barre.height; radius: Couleurs.rayon(6, width, height)
                width: modelData > 0 ? (barre.width - barre.spacing * (so.segments - 1)) * modelData / so.total : 0
                color: so.couleurs[index]
            }
        }
    }
    Flow {
        width: parent.width; spacing: 16
        Repeater {
            model: so.noms
            delegate: Row {
                required property string modelData
                required property int index
                readonly property var secondes: so.durees[index]
                readonly property int minutes: Math.floor((secondes || 0) / 60)
                readonly property string duree: secondes === null ? "—"
                                                 : minutes < 60 ? minutes + "m"
                                                 : Math.floor(minutes / 60) + "h " + String(minutes % 60).padStart(2, "0") + "m"
                spacing: 6
                Rectangle {
                    width: 10; height: 10; radius: Couleurs.rayon(5, width, height)
                    anchors.verticalCenter: parent.verticalCenter; color: so.couleurs[index]
                }
                Texte { text: parent.modelData + " : " + parent.duree; font.pixelSize: 12 }
            }
        }
    }
}
