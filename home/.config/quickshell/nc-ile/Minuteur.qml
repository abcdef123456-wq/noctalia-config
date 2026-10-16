// Page « Minuteur » : en cours, grand décompte et anneau orange (comme l'activité en direct de l'iPhone) ;
// sinon, choix d'une durée. Le décompte s'affiche aussi dans la pilule.
import QtQuick

Item {
    id: m
    readonly property bool enCours: Etat.minuteurFin > 0
    readonly property real fraction: enCours && Etat.minuteurDuree > 0 ? Etat.minuteurReste * 1000 / Etat.minuteurDuree : 0

    // ── En cours ──
    Row {
        visible: m.enCours
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width; spacing: 18
        // Anneau de progression
        Canvas {
            id: anneau
            width: 92; height: 92
            property real f: m.fraction
            onFChanged: requestPaint()
            onPaint: {
                var c = getContext("2d"); c.reset()
                c.lineWidth = 8; c.lineCap = "round"
                c.strokeStyle = String(Couleurs.fondOrange); c.beginPath(); c.arc(46, 46, 40, 0, 2 * Math.PI); c.stroke()
                c.strokeStyle = String(Couleurs.orange); c.beginPath(); c.arc(46, 46, 40, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * f); c.stroke()
            }
            Ico { anchors.centerIn: parent; nom: "timer"; taille: 30; color: Couleurs.orange }
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter; spacing: 2
            Texte { text: "Minuteur"; secondaire: true; font.pixelSize: 14 }
            Texte { text: Etat.duree(Etat.minuteurReste); font.pixelSize: 40; font.weight: Font.DemiBold; color: Couleurs.orange }
        }
    }
    Row {
        visible: m.enCours
        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 10
        Rond { taille: 46; icone: "add"; couleur: Couleurs.gris3; onClic: Etat.ajouterMinute() }
        Rond { taille: 46; icone: "close"; actif: true; couleur: Couleurs.rouge; onClic: Etat.arreterMinuteur() }
    }

    // ── À lancer : durées ──
    Column {
        visible: !m.enCours
        anchors.fill: parent; spacing: 14
        Row {
            spacing: 10
            Ico { nom: "timer"; taille: 26; color: Couleurs.orange }
            Texte { text: "Minuteur"; font.pixelSize: 20; font.weight: Font.Bold; anchors.verticalCenter: parent.verticalCenter }
        }
        Grid {
            columns: 3; spacing: 10
            Repeater {
                model: [1, 3, 5, 10, 15, 25, 30, 45, 60]
                Module {
                    required property int modelData
                    width: (m.width - 20) / 3; height: 52; radius: 16; cliquable: true
                    onClic: Etat.lancerMinuteur(modelData)
                    Texte {
                        anchors.centerIn: parent; font.pixelSize: 16; font.weight: Font.DemiBold
                        text: modelData >= 60 ? "1 h" : modelData + " min"
                    }
                }
            }
        }
    }
}
