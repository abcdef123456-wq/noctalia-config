// Page « Météo » de l'île : température, ciel, ressenti, min / max, les 6 prochaines heures et les 5 prochains jours
// (nc-meteo, Open-Meteo). Ville : nc-reglages → Île → « Ville de la météo ».
import QtQuick

Item {
    id: p
    readonly property var m: Etat.meteo

    Row {
        id: haut
        width: parent.width; spacing: 16
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: p.m.icone || "cloud"; taille: 58; color: Couleurs.jaune }
        Column {
            anchors.verticalCenter: parent.verticalCenter; spacing: 1
            Texte { text: p.m.ville || "Météo"; secondaire: true; font.pixelSize: 14 }
            Row {
                spacing: 10
                Texte { text: (p.m.temp !== undefined ? p.m.temp : "–") + "°"; font.pixelSize: 44; font.weight: Font.DemiBold }
                Column {
                    anchors.verticalCenter: parent.verticalCenter; spacing: 2
                    Texte { text: p.m.texte || ""; font.pixelSize: 14; font.weight: Font.DemiBold }
                    Texte { text: "Ressenti " + p.m.ressenti + "° · min " + p.m.min + "° · max " + p.m.max + "°"; secondaire: true; font.pixelSize: 12 }
                }
            }
        }
    }

    // Les prochaines heures
    Rectangle {
        id: heures
        anchors.top: haut.bottom; anchors.topMargin: 14
        width: parent.width; height: 78; radius: 16; color: Couleurs.carte
        Row {
            anchors.centerIn: parent; spacing: 0
            Repeater {
                model: p.m.heures || []
                Column {
                    required property var modelData
                    width: (heures.width - 16) / Math.max(1, (p.m.heures || []).length); spacing: 3
                    Texte { anchors.horizontalCenter: parent.horizontalCenter; text: parent.modelData.h; secondaire: true; font.pixelSize: 12 }
                    Ico { anchors.horizontalCenter: parent.horizontalCenter; nom: parent.modelData.icone; taille: 20 }
                    Texte { anchors.horizontalCenter: parent.horizontalCenter; text: parent.modelData.t + "°"; font.pixelSize: 13; font.weight: Font.DemiBold }
                }
            }
        }
    }

    // Les prochains jours : min et max sur une barre, comme sur iPhone
    Column {
        anchors.top: heures.bottom; anchors.topMargin: 12
        width: parent.width; spacing: 4
        readonly property var jours: (p.m.jours || []).slice(1)
        readonly property real bas: Math.min.apply(null, (p.m.jours || [{ min: 0 }]).map(j => j.min))
        readonly property real hautT: Math.max.apply(null, (p.m.jours || [{ max: 1 }]).map(j => j.max))
        Repeater {
            model: parent.jours
            Item {
                id: ligne
                required property var modelData
                width: parent.width; height: 24
                readonly property real bas: parent.bas
                readonly property real ecart: Math.max(1, parent.hautT - parent.bas)
                Texte { anchors.verticalCenter: parent.verticalCenter; text: ligne.modelData.jour; width: 50; font.pixelSize: 13 }
                Ico { x: 54; anchors.verticalCenter: parent.verticalCenter; nom: ligne.modelData.icone; taille: 18 }
                Texte { x: 88; anchors.verticalCenter: parent.verticalCenter; text: ligne.modelData.min + "°"; secondaire: true; width: 34; horizontalAlignment: Text.AlignRight; font.pixelSize: 13 }
                Rectangle {
                    x: 130; anchors.verticalCenter: parent.verticalCenter
                    width: ligne.width - 180; height: 5; radius: 2.5; color: Couleurs.gris3
                    Rectangle {
                        x: parent.width * (ligne.modelData.min - ligne.bas) / ligne.ecart
                        width: Math.max(6, parent.width * (ligne.modelData.max - ligne.modelData.min) / ligne.ecart)
                        height: parent.height; radius: 2.5
                        gradient: Gradient { orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: Couleurs.bleu } GradientStop { position: 1; color: Couleurs.orange } }
                    }
                }
                Texte { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; text: ligne.modelData.max + "°"; font.pixelSize: 13; font.weight: Font.DemiBold }
            }
        }
    }
}
