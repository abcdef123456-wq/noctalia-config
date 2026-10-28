// Page « Résumé » (activité « Bonjour » / « Bonsoir ») : la météo du jour, les prochains rendez-vous, les mises à jour du
// système et la batterie, tels que Resume.qml les a réunis au réveil. Un titre d'événement ou un nom de paquet vient de
// l'extérieur : texte brut (Texte.qml), jamais interprété. Une ligne sans donnée n'existe pas.
import QtQuick

Item {
    id: p
    readonly property var c: Resume.contenu
    readonly property real hauteur: contenu.implicitHeight
    onHauteurChanged: Etat.annoncerHauteur("resume", hauteur)
    Component.onCompleted: Etat.annoncerHauteur("resume", hauteur)

    Column {
        id: contenu
        width: parent.width
        y: Math.max(0, (parent.height - implicitHeight) / 2)
        spacing: 10

        Row {
            width: parent.width; spacing: 14
            Rectangle {
                width: 48; height: 48; radius: 24; color: Couleurs.gris3
                anchors.verticalCenter: parent.verticalCenter
                Ico { anchors.centerIn: parent; nom: Resume.soir ? "bedtime" : "wb_sunny"; taille: 28; color: Resume.soir ? Couleurs.accentClair : Couleurs.jaune }
            }
            Column {
                anchors.verticalCenter: parent.verticalCenter; spacing: 2
                width: parent.width - 48 - 14
                Texte { objectName: "nc-resume-salut"; width: parent.width; text: Resume.salut; font.pixelSize: 20; font.weight: Font.DemiBold }
                Texte { width: parent.width; secondaire: true; font.pixelSize: 13; text: Qt.formatDate(Etat.maintenant, "dddd d MMMM") }
            }
        }

        Module {
            objectName: "nc-resume-meteo"
            visible: !!p.c.meteo
            width: parent.width; height: visible ? 56 : 0; radius: 16
            Row {
                anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 14; spacing: 12
                Ico { anchors.verticalCenter: parent.verticalCenter; nom: p.c.meteo ? p.c.meteo.icone : "cloud"; taille: 30; color: Couleurs.jaune }
                Texte { anchors.verticalCenter: parent.verticalCenter; text: p.c.meteo ? p.c.meteo.temp + "°" : ""; font.pixelSize: 24; font.weight: Font.DemiBold }
                Column {
                    anchors.verticalCenter: parent.verticalCenter; spacing: 1; width: parent.width - 120
                    Texte { width: parent.width; font.pixelSize: 13; font.weight: Font.DemiBold; visible: !Reglages.en && text !== ""; text: p.c.meteo ? p.c.meteo.texte : "" }
                    Texte { width: parent.width; secondaire: true; font.pixelSize: 12; visible: !!p.c.meteo && p.c.meteo.min !== undefined && p.c.meteo.max !== undefined
                            text: p.c.meteo ? "min " + p.c.meteo.min + "° · max " + p.c.meteo.max + "°" : "" }
                }
            }
        }

        Module {
            objectName: "nc-resume-agenda"
            visible: p.c.nbEvenements > 0
            width: parent.width; height: visible ? agenda.implicitHeight + 24 : 0; radius: 16
            Column {
                id: agenda
                x: 14; y: 12; width: parent.width - 28; spacing: 5
                Texte { width: parent.width; secondaire: true; font.pixelSize: 12; font.weight: Font.DemiBold
                        text: Resume.pluriel(p.c.nbEvenements, "rendez-vous aujourd'hui", "rendez-vous aujourd'hui", "event today", "events today") }
                Repeater {
                    model: p.c.evenements
                    Row {
                        required property var modelData
                        width: agenda.width; spacing: 10
                        Texte { width: 48; font.pixelSize: 13; font.features: { "tnum": 1 }; color: Couleurs.accentClair; elide: Text.ElideNone
                                text: parent.modelData.journee ? Reglages.t("Journée", "All day") : parent.modelData.heure }
                        Texte { width: parent.width - 58; font.pixelSize: 13; text: parent.modelData.titre }
                    }
                }
                Texte { visible: p.c.nbEvenements > p.c.evenements.length; secondaire: true; font.pixelSize: 12
                        text: Reglages.t("et ", "and ") + (p.c.nbEvenements - p.c.evenements.length) + Reglages.t(" autres", " more") }
            }
        }

        Module {
            objectName: "nc-resume-maj"
            visible: p.c.maj > 0
            width: parent.width; height: visible ? 52 : 0; radius: 16
            Row {
                anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 14; spacing: 12
                Ico { anchors.verticalCenter: parent.verticalCenter; nom: "system_update"; taille: 22; color: Couleurs.accent }
                Column {
                    anchors.verticalCenter: parent.verticalCenter; spacing: 1; width: parent.width - 40
                    Texte { width: parent.width; font.pixelSize: 13; font.weight: Font.DemiBold; text: Resume.pluriel(p.c.maj, "mise à jour du système", "mises à jour du système", "system update", "system updates") }
                    Texte { width: parent.width; secondaire: true; font.pixelSize: 12; visible: p.c.importants.length > 0
                            text: Reglages.t("Importantes : ", "Important: ") + p.c.importants.join(", ") }
                }
            }
        }

        Module {
            objectName: "nc-resume-batterie"
            visible: p.c.batterie >= 0
            width: parent.width; height: visible ? 44 : 0; radius: 16
            Row {
                anchors.centerIn: parent; spacing: 10
                Ico { anchors.verticalCenter: parent.verticalCenter; nom: "battery_android_full"; taille: 20; color: p.c.batterie <= 20 ? Couleurs.orange : Couleurs.texte }
                Texte { anchors.verticalCenter: parent.verticalCenter; font.pixelSize: 13; font.weight: Font.DemiBold
                        text: Reglages.t("Sur batterie : ", "On battery: ") + p.c.batterie + " %" }
            }
        }
    }
}
