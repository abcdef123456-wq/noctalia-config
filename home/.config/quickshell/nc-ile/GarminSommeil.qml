// Barre segmentée des 4 phases du sommeil (Garmin.qml) : `phases` = [profond, léger, paradoxal, éveil] en secondes ; cachée sans données
import QtQuick

Column {
    id: so
    property var phases: []
    readonly property real total: {
        var t = 0
        for (var i = 0; i < 4; i++) { var v = phases[i]; if (typeof v === "number" && isFinite(v) && v > 0) t += v }
        return t
    }
    readonly property var couleurs: [Couleurs.violet, Couleurs.bleu, Couleurs.rose, Couleurs.orange]
    readonly property var noms: [Reglages.t("Profond", "Deep"), Reglages.t("Léger", "Light"), Reglages.t("Paradoxal", "REM"), Reglages.t("Éveil", "Awake")]
    visible: total > 0
    spacing: 6
    Row {
        objectName: "nc-garmin-sommeil-barre"
        width: parent.width; height: 10; spacing: 2
        Repeater {
            model: 4
            Rectangle {
                readonly property real v: typeof so.phases[index] === "number" && isFinite(so.phases[index]) && so.phases[index] > 0 ? so.phases[index] : 0
                objectName: "nc-garmin-sommeil-" + index
                visible: v > 0
                height: 10; radius: 5
                width: Math.max(4, (so.width - 6) * v / so.total)
                color: so.couleurs[index]
            }
        }
    }
    Row {
        spacing: 12
        Repeater {
            model: 4
            Texte { text: so.noms[index]; secondaire: true; font.pixelSize: 11; color: so.couleurs[index] }
        }
    }
}
