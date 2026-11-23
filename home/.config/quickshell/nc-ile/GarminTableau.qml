// Tableau Garmin : les jauges résument les mêmes indicateurs, dans le même ordre, que les cartes détaillées.
import QtQuick

Column {
    id: ta
    // Les valeurs exposées par GarminEtat sont déjà masquées pendant un partage d'écran.
    readonly property var m: GarminEtat.metriquesVisibles
    readonly property var idsJauges: ({ body_battery: "bb", frequence_cardiaque: "fc", sommeil: "sommeil", stress: "stress", pas: "pas" })
    readonly property var widgets: GarminEtat.widgetsActifs
    readonly property var jauges: widgets.filter(id => idsJauges.hasOwnProperty(id))
    visible: GarminEtat.panneauOuvert && GarminEtat.actif && GarminEtat.pret && !GarminEtat.masque && widgets.length > 0
    spacing: 14

    function num(v) { return typeof v === "number" && Number.isFinite(v) ? v : null }
    function aff(v, suffixe) { return num(v) === null ? "—" : v + (suffixe || "") }
    function serie(v) { return Array.isArray(v) && v.length >= 2 ? v : [] }
    function duree(s) {
        return num(s) === null ? "—" : Math.floor(s / 3600) + "h " + String(Math.floor(s % 3600 / 60)).padStart(2, "0") + "m"
    }

    function fiche(id) {
        const t = Reglages.t
        const f = { titre: GarminEtat.nomDe(id), sous: "", valeur: "—" }
        switch (id) {
        case "body_battery":
            f.icone = "bolt"; f.couleur = Couleurs.bleu
            f.titre = "Body Battery"
            f.sous = t("Réserve d'énergie corporelle", "Body energy reserve")
            f.valeur = aff(m.body_battery, " / 100")
            f.jauge = { titre: "Body Battery", valeur: aff(m.body_battery, t(" %", "%")), taux: (num(m.body_battery) || 0) / 100 }
            f.courbe = serie(m.bb_serie); f.echelleCourbe = 100
            break
        case "frequence_cardiaque": {
            f.icone = "favorite"; f.couleur = Couleurs.rose
            f.titre = t("Fréquence cardiaque", "Heart Rate")
            f.sous = t("Repos : ", "Resting: ") + aff(m.fc_repos, " bpm") + t(" · Max : ", " · Max: ") + aff(m.fc_max, " bpm")
            f.courbe = serie(m.fc_serie)
            const fc = num(f.courbe[f.courbe.length - 1]) ?? num(m.fc_repos)
            f.valeur = aff(fc, " bpm")
            f.jauge = { titre: t("Cœur", "Heart"), valeur: f.valeur,
                        sous: num(m.fc_repos) === null ? "" : t("Repos ", "Rest ") + m.fc_repos,
                        taux: fc === null ? 0 : Math.max(0.15, (fc - 40) / 140) }
            break
        }
        case "sommeil": {
            f.icone = "bedtime"; f.couleur = Couleurs.violet
            f.titre = t("Sommeil de la dernière nuit", "Last Night's Sleep")
            const temps = duree(m.sommeil_s)
            const score = aff(m.sommeil_score, "/100")
            f.sous = t("Durée : ", "Duration: ") + temps + (num(m.spo2) === null ? "" : " · SpO₂ " + m.spo2 + t(" %", "%"))
            f.valeur = score === "—" ? "—" : t("Score ", "Score ") + score
            f.jauge = { titre: t("Sommeil", "Sleep"), valeur: score === "—" ? temps : score,
                        sous: score !== "—" && temps !== "—" ? temps : "", taux: (num(m.sommeil_score) || 0) / 100 }
            f.phases = [m.sommeil_profond_s, m.sommeil_leger_s, m.sommeil_paradoxal_s, m.sommeil_eveil_s]
            break
        }
        case "stress": {
            const stress = num(m.stress_moyen)
            const niveau = stress === null ? "" : stress < 26 ? t("Calme", "Rest")
                         : stress < 51 ? t("Faible", "Low") : stress < 76 ? t("Moyen", "Medium") : t("Élevé", "High")
            f.icone = "self_improvement"
            f.couleur = stress === null ? Couleurs.texteSec : stress < 51 ? Couleurs.vert : stress < 76 ? Couleurs.orange : Couleurs.rouge
            f.titre = t("Stress de la journée", "Daily Stress")
            f.sous = t("Niveau moyen sur la journée", "Daily average level")
            f.statut = niveau ? "· " + niveau : ""
            f.valeur = aff(stress, " / 100")
            f.jauge = { titre: "Stress", valeur: aff(stress), sous: niveau, taux: (stress || 0) / 100 }
            f.courbe = serie(m.stress_serie); f.echelleCourbe = 100
            break
        }
        case "pas": {
            f.icone = "directions_walk"; f.couleur = Couleurs.vert
            f.titre = t("Pas & Distance du jour", "Daily Steps & Distance")
            const distance = num(m.distance_m) === null ? "" : (m.distance_m / 1000).toFixed(2) + " km"
            const objectif = num(m.pas_objectif)
            const pas = num(m.pas)
            f.objectif = objectif > 0 && pas !== null ? pas / objectif : -1
            f.sous = t("Objectif : ", "Goal: ") + aff(objectif, t(" pas", " steps")) + (distance ? " · " + distance : "")
            f.valeur = aff(pas, t(" pas", " steps"))
            f.jauge = { titre: t("Pas", "Steps"), valeur: aff(pas), sous: distance, taux: Math.max(0, f.objectif) }
            break
        }
        case "vfc":
            f.icone = "monitor_heart"; f.couleur = Couleurs.rose; f.valeur = aff(m.vfc_nuit, " ms")
            break
        case "activite":
            f.icone = "directions_run"; f.couleur = Couleurs.vert
            f.sous = m.activite_nom || ""; f.valeur = aff(m.activite_minutes, " min")
            break
        case "calories":
            f.icone = "local_fire_department"; f.couleur = Couleurs.orange; f.valeur = aff(m.calories_actives, " kcal")
            f.sous = t("Étages : ", "Floors: ") + aff(m.etages) + t(" · Minutes intenses : ", " · Intensity minutes: ") + aff(m.minutes_intenses)
            break
        case "oxygene":
            f.icone = "air"; f.couleur = Couleurs.bleu; f.valeur = aff(m.spo2, t(" %", "%"))
            f.sous = t("Respiration : ", "Breathing: ") + aff(m.respiration, " brpm")
            break
        case "forme":
            f.icone = "emoji_events"; f.couleur = Couleurs.jaune; f.valeur = aff(m.readiness, " / 100")
            f.sous = "VO₂ max : " + aff(m.vo2max)
            break
        case "hydratation":
            f.icone = "water_drop"; f.couleur = Couleurs.bleu; f.valeur = aff(m.hydratation_ml, " ml")
            break
        }
        return f
    }

    Row {
        id: rangee
        objectName: "nc-garmin-jauges"
        visible: ta.jauges.length > 0 && Object.keys(ta.m).length > 0
        width: ta.width
        spacing: width < 460 ? 6 : 12
        readonly property real largeurCase: Math.floor((width - (ta.jauges.length - 1) * spacing) / Math.max(1, ta.jauges.length))
        Repeater {
            model: ta.jauges
            delegate: Rectangle {
                id: caseJauge
                required property string modelData
                readonly property string code: ta.idsJauges[modelData]
                readonly property var f: ta.fiche(modelData)
                readonly property var j: f.jauge
                width: rangee.largeurCase
                height: width < 94 ? 104 : 136
                radius: Couleurs.rayon(20, width, height)
                color: Qt.alpha(Couleurs.carte, 0.85)
                border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.09)

                GarminJauge {
                    objectName: "nc-garmin-jauge-" + caseJauge.code
                    y: 10; anchors.horizontalCenter: parent.horizontalCenter
                    width: Math.min(82, parent.width - 4); height: width
                    valeur: caseJauge.j.taux; couleur: caseJauge.f.couleur
                    texte: caseJauge.j.valeur; sousTexte: caseJauge.j.sous || ""
                    objetSousTexte: caseJauge.code === "pas" ? "nc-garmin-distance" : ""
                }
                Row {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom; anchors.bottomMargin: 10
                    spacing: 5
                    Ico {
                        visible: caseJauge.width >= 94
                        anchors.verticalCenter: parent.verticalCenter
                        nom: caseJauge.f.icone; taille: 14; color: caseJauge.f.couleur
                    }
                    Texte {
                        anchors.verticalCenter: parent.verticalCenter
                        width: caseJauge.width < 94 ? Math.min(implicitWidth, caseJauge.width - 6) : implicitWidth
                        text: caseJauge.j.titre; horizontalAlignment: Text.AlignHCenter
                        font.pixelSize: caseJauge.width < 94 ? 10 : 12; font.weight: Font.DemiBold
                    }
                }
            }
        }
    }

    Column {
        objectName: "nc-garmin-grille"
        width: ta.width; spacing: ta.spacing
        Repeater {
            model: ta.widgets
            delegate: GarminCarte {
                required property string modelData
                readonly property var f: ta.fiche(modelData)
                objectName: "nc-garmin-carte-" + identifiant
                width: ta.width
                identifiant: modelData
                titre: f.titre; icone: f.icone; valeur: f.valeur
                sous: f.sous; couleur: f.couleur; statut: f.statut || ""
                courbe: f.courbe || []
                nomCourbe: f.courbe ? ta.idsJauges[modelData] : ""
                echelleCourbe: f.echelleCourbe || 0
                phases: f.phases || []
                objectif: f.objectif ?? -1
            }
        }
    }
}
