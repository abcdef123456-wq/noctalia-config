// Page « Météo » de l'île : température, ciel, ressenti, min / max, les 6 prochaines heures et les 5 prochains jours
// (nc-meteo, Open-Meteo). Ville : un clic sur son nom (ou nc-reglages → Île → « Ville de la météo »).
import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: p
    readonly property var m: Etat.meteo
    // En anglais : le ciel d'après le code de l'OMM, les jours et les heures (nc-meteo les écrit en français)
    readonly property var ciel: ({
        0: "Clear", 1: "Mostly Clear", 2: "Partly Cloudy", 3: "Cloudy", 45: "Fog", 48: "Freezing Fog",
        51: "Light Drizzle", 53: "Drizzle", 55: "Heavy Drizzle", 56: "Freezing Drizzle", 57: "Freezing Drizzle",
        61: "Light Rain", 63: "Rain", 65: "Heavy Rain", 66: "Freezing Rain", 67: "Freezing Rain",
        71: "Light Snow", 73: "Snow", 75: "Heavy Snow", 77: "Snow Grains", 80: "Showers", 81: "Showers",
        82: "Heavy Showers", 85: "Snow Showers", 86: "Snow Showers", 95: "Thunderstorm", 96: "Thunderstorm with Hail",
        99: "Thunderstorm with Hail" })
    function texteCiel() {
        if (Reglages.en && m.code !== undefined && ciel[m.code] !== undefined) return ciel[m.code]
        return m.texte || ""
    }
    function nomJour(j) {
        if (!Reglages.en) return j
        var n = ({ "lun.": 1, "mar.": 2, "mer.": 3, "jeu.": 4, "ven.": 5, "sam.": 6, "dim.": 0 })[j]
        return n !== undefined ? Reglages.locale.dayName(n, Locale.ShortFormat) : (j === "Aujourd'hui" ? "Today" : j)
    }
    function heure(h) {
        var n = parseInt(h)
        if (!Reglages.en || isNaN(n)) return h
        return (n % 12 || 12) + (n < 12 ? " AM" : " PM")
    }

    Row {
        id: haut
        width: parent.width; spacing: 16
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: p.m.icone || "cloud"; taille: 58; color: Couleurs.jaune }
        Column {
            anchors.verticalCenter: parent.verticalCenter; spacing: 1
            // La ville : un clic pour en taper une autre (vide : d'après la connexion internet)
            Item {
                width: Math.max(ville.width, saisie.visible ? 220 : 0); height: 20
                Row {
                    id: ville
                    visible: !saisie.visible; spacing: 4
                    Ico { anchors.verticalCenter: parent.verticalCenter; nom: "location_on"; taille: 14; color: Couleurs.texteSec }
                    Texte { text: p.m.ville ? p.m.ville + (p.m.estimee ? Reglages.t(" (estimée)", " (estimated)") : "") : Reglages.t("Météo", "Weather"); secondaire: true; font.pixelSize: 14 }
                    Ico { anchors.verticalCenter: parent.verticalCenter; nom: "edit"; taille: 12; color: Couleurs.texteSec; opacity: zone.containsMouse ? 1 : 0.5 }
                }
                MouseArea { id: zone; anchors.fill: ville; visible: ville.visible; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: { saisie.visible = true; saisie.text = ""; saisie.forceActiveFocus() } }
                Rectangle {
                    visible: saisie.visible; anchors.fill: parent; anchors.margins: -3; radius: 8; color: Couleurs.gris2
                    border.width: 1.5; border.color: Couleurs.jaune
                }
                TextInput {
                    id: saisie
                    visible: false; anchors.fill: parent; anchors.leftMargin: 6
                    color: Couleurs.texte; selectionColor: Couleurs.jaune; font.pixelSize: 14; clip: true
                    // Écrit par nc-reglages (verrou et écriture atomique : un autre changement en même temps n'est pas perdu)
                    onAccepted: { villeEcrire.command = [Quickshell.env("HOME") + "/.local/bin/nc-reglages", "set", "METEO_VILLE",
                                                         text.trim().replace(/[\r\n=]/g, " ") || "auto"]
                                  villeEcrire.running = true; visible = false }
                    Keys.onEscapePressed: visible = false
                    onActiveFocusChanged: if (!activeFocus) visible = false
                    Texte { visible: saisie.text === ""; anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.pixelSize: 13
                            text: Reglages.t("Ville… (vide : automatique)", "City… (empty: automatic)") }
                }
                Process { id: villeEcrire }
            }
            // Ville saisie mais introuvable (nc-meteo ne se rabat pas sur l'IP)
            Texte {
                visible: Etat.meteoErreur !== "" && !saisie.visible
                text: Reglages.t("Ville introuvable : un clic sur le nom pour en taper une autre", "City not found: click the name to type another"); font.pixelSize: 12; color: Couleurs.orange
            }
            // Météo gardée depuis plus de 3 h (hors ligne) : dit discrètement
            Texte {
                visible: !!p.m.perime && !saisie.visible
                text: Reglages.t("Hors ligne : météo ancienne", "Offline: old data"); font.pixelSize: 11; secondaire: true
            }
            // Ville estimée d'après l'IP (METEO_VILLE vide ou « auto ») : peut être fausse, un clic ouvre la saisie de la ville
            Texte {
                visible: !!p.m.estimee && !saisie.visible
                text: Reglages.t("Choisir ma ville", "Choose my city"); font.pixelSize: 12; font.underline: true; color: Couleurs.jaune
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: { saisie.visible = true; saisie.text = ""; saisie.forceActiveFocus() } }
            }
            Row {
                spacing: 10
                Texte { text: (p.m.temp !== undefined ? p.m.temp : "–") + "°"; font.pixelSize: 44; font.weight: Font.DemiBold }
                Column {
                    anchors.verticalCenter: parent.verticalCenter; spacing: 2
                    Texte { text: p.texteCiel(); font.pixelSize: 14; font.weight: Font.DemiBold }
                    Texte { visible: p.m.temp !== undefined; text: Reglages.t("Ressenti ", "Feels like ") + p.m.ressenti + "° · min " + p.m.min + "° · max " + p.m.max + "°"; secondaire: true; font.pixelSize: 12 }
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
                    Texte { anchors.horizontalCenter: parent.horizontalCenter; text: p.heure(parent.modelData.h); secondaire: true; font.pixelSize: 12 }
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
                Texte { anchors.verticalCenter: parent.verticalCenter; text: p.nomJour(ligne.modelData.jour); width: 50; font.pixelSize: 13 }
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
