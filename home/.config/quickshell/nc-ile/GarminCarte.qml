// Carte détaillée du tableau Garmin : valeur alignée, puis courbe, phases et actions selon l'indicateur.
import QtQuick

Rectangle {
    id: c
    required property string identifiant
    required property string titre
    required property string icone
    required property string valeur
    required property string sous
    required property color couleur
    property string statut: ""
    property var courbe: []
    property string nomCourbe: ""
    property real echelleCourbe: 0                // 0 : ajuster la plage aux points
    property var phases: []
    property real objectif: -1                     // négatif : pas de barre de progression

    radius: Couleurs.rayon(22, width, height)
    color: Qt.alpha(Couleurs.carte, 0.85)
    border.width: 1
    border.color: Qt.alpha(Couleurs.texte, 0.09)
    implicitHeight: col.implicitHeight + 34

    Column {
        id: col
        x: 20; y: 17; width: parent.width - 40; spacing: 11

        Row {
            width: parent.width; spacing: 12
            Column {
                width: parent.width - valeurTexte.width - parent.spacing
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Row {
                    width: parent.width; spacing: 8
                    Ico {
                        id: icone
                        anchors.verticalCenter: parent.verticalCenter
                        nom: c.icone; taille: 18; color: c.couleur
                    }
                    Texte {
                        width: Math.min(implicitWidth, parent.width - icone.width - parent.spacing
                                        - (c.statut === "" ? 0 : statutTexte.width + parent.spacing))
                        text: c.titre; font.pixelSize: 16; font.weight: Font.Bold
                    }
                    Texte {
                        id: statutTexte
                        visible: c.statut !== ""
                        anchors.verticalCenter: parent.verticalCenter
                        text: c.statut; secondaire: true; font.pixelSize: 13
                    }
                }
                Texte {
                    visible: c.sous !== ""; width: parent.width
                    text: c.sous; secondaire: true; font.pixelSize: 12
                    wrapMode: Text.Wrap
                }
            }
            Texte {
                id: valeurTexte
                objectName: "nc-garmin-valeur-" + c.identifiant
                anchors.verticalCenter: parent.verticalCenter
                width: Math.min(implicitWidth, parent.width * 0.43)
                horizontalAlignment: Text.AlignRight
                text: c.valeur; color: c.valeur === "—" ? Couleurs.texteSec : c.couleur
                font.pixelSize: parent.width < 430 ? 18 : (c.identifiant === "frequence_cardiaque" ? 24 : 22)
                font.weight: Font.Bold; font.features: { "tnum": 1 }
            }
        }
        Loader {
            active: c.nomCourbe !== ""
            visible: c.courbe.length >= 2
            width: parent.width; height: c.nomCourbe === "stress" ? 54 : 66
            sourceComponent: GarminCourbe {
                objectName: "nc-garmin-courbe-" + c.nomCourbe
                points: c.courbe; couleur: c.couleur; echelle: c.echelleCourbe
            }
        }
        Loader {
            active: c.identifiant === "sommeil"
            visible: item !== null && item.total > 0
            width: parent.width
            sourceComponent: GarminSommeil {
                objectName: "nc-garmin-sommeil"
                phases: c.phases
            }
        }
        Rectangle {
            visible: c.objectif >= 0
            width: parent.width; height: 10
            color: Couleurs.gris3; radius: Couleurs.rayon(5, width, height)
            Rectangle {
                width: Math.round(parent.width * Math.max(0, Math.min(1, c.objectif))); height: parent.height
                color: c.couleur; radius: Couleurs.rayon(5, width, height)
            }
        }
        Loader {
            active: c.identifiant === "hydratation"
            visible: active
            anchors.right: parent.right
            sourceComponent: Row {
                spacing: 8
                GarminBouton {
                    objectName: "nc-garmin-eau-250"; texte: "+250 ml"; icone: "add"
                    onClic: GarminEtat.hydrater("+250")
                }
                GarminBouton {
                    objectName: "nc-garmin-eau-500"; texte: "+500 ml"; icone: "add"
                    onClic: GarminEtat.hydrater("+500")
                }
            }
        }
    }
}
