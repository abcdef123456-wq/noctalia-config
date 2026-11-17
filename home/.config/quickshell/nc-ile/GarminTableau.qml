// Tableau Garmin (Garmin.qml) : 5 jauges, 3 courbes de la journée, sommeil en phases, distance. Tout vient de GarminEtat.metriquesVisibles : vide pendant le partage d'écran.
import QtQuick

Column {
    id: ta
    readonly property var m: GarminEtat.metriquesVisibles
    function num(v) { return typeof v === "number" && isFinite(v) ? v : null }
    function aff(v, suffixe) { var n = num(v); return n === null ? "—" : Math.round(n) + (suffixe || "") }
    function serie(v) { return Array.isArray(v) && v.length >= 2 ? v : [] }
    function frac(v, max) { var n = num(v); return n === null ? 0 : Math.max(0, Math.min(1, n / max)) }
    readonly property var phases: [num(m.sommeil_profond_s), num(m.sommeil_leger_s), num(m.sommeil_paradoxal_s), num(m.sommeil_eveil_s)]
    readonly property bool rien: Object.keys(m).length === 0
    visible: GarminEtat.panneauOuvert && GarminEtat.actif && !GarminEtat.masque && !rien
    spacing: 10
    Row {
        id: jauges
        objectName: "nc-garmin-jauges"
        spacing: 6
        Repeater {
            model: [
                { n: "bb", t: Reglages.t("Énergie", "Energy"), v: ta.frac(ta.m.body_battery, 100), s: ta.aff(ta.m.body_battery), c: Couleurs.vert },
                { n: "fc", t: Reglages.t("Cœur", "Heart"), v: ta.frac(ta.m.fc_repos, 120), s: ta.aff(ta.m.fc_repos), c: Couleurs.rose },
                { n: "sommeil", t: Reglages.t("Sommeil", "Sleep"), v: ta.frac(ta.m.sommeil_score, 100), s: ta.aff(ta.m.sommeil_score), c: Couleurs.violet },
                { n: "stress", t: Reglages.t("Stress", "Stress"), v: ta.frac(ta.m.stress_moyen, 100), s: ta.aff(ta.m.stress_moyen), c: Couleurs.orange },
                { n: "pas", t: Reglages.t("Pas", "Steps"), v: ta.frac(ta.m.pas, 10000), s: ta.aff(ta.m.pas), c: Couleurs.bleu }
            ]
            Column {
                spacing: 2
                GarminJauge { objectName: "nc-garmin-jauge-" + modelData.n; width: 56; height: 56; valeur: modelData.v; couleur: modelData.c; texte: modelData.s }
                Texte { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.t; secondaire: true; font.pixelSize: 10 }
            }
        }
    }
    Texte {
        objectName: "nc-garmin-distance"
        text: Reglages.t("Distance ", "Distance ") + (ta.num(ta.m.distance_m) === null ? "—" : (ta.m.distance_m / 1000).toFixed(1) + " km")
        secondaire: true; font.pixelSize: 12
    }
    Repeater {
        model: [
            { n: "bb", t: Reglages.t("Énergie", "Energy"), p: ta.serie(ta.m.bb_serie), c: Couleurs.vert },
            { n: "fc", t: Reglages.t("Cœur", "Heart"), p: ta.serie(ta.m.fc_serie), c: Couleurs.rose },
            { n: "stress", t: Reglages.t("Stress", "Stress"), p: ta.serie(ta.m.stress_serie), c: Couleurs.orange }
        ]
        Row {
            spacing: 8
            visible: modelData.p.length >= 2
            objectName: "nc-garmin-courbe-ligne-" + modelData.n
            Texte { width: 56; text: modelData.t; secondaire: true; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
            GarminCourbe { objectName: "nc-garmin-courbe-" + modelData.n; width: 200; points: modelData.p; couleur: modelData.c }
        }
    }
    GarminSommeil { objectName: "nc-garmin-sommeil"; width: 280; phases: ta.phases }
}
