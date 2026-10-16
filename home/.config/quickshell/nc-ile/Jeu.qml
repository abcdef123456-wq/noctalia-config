// Page « Mode jeu » (activité) : effets coupés, notifications en pause, profil Performance ; en direct, la charge et la
// température du processeur et de la carte graphique (nc-ile-etat jeu ; une carte NVIDIA en veille n'est pas réveillée).
import QtQuick
import Quickshell.Io

Item {
    id: j
    property var m: ({})
    Process {
        id: mesure
        command: [Etat.bin + "nc-ile-etat", "jeu"]
        stdout: StdioCollector {
            onStreamFinished: {
                var t = {}
                text.split("\n").forEach(l => { var p = l.indexOf("="); if (p > 0) t[l.slice(0, p)] = l.slice(p + 1) })
                j.m = t
            }
        }
    }
    Timer { interval: 2000; repeat: true; running: j.visible; triggeredOnStart: true; onTriggered: if (!mesure.running) mesure.running = true }

    Row {
        id: tete
        spacing: 14
        Rectangle {
            width: 56; height: 56; radius: 28; color: Couleurs.fondOrange
            Ico { anchors.centerIn: parent; nom: "sports_esports"; taille: 30; color: Couleurs.orange }
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter; spacing: 2
            Texte { text: "Mode jeu"; font.pixelSize: 22; font.weight: Font.DemiBold; color: Couleurs.orange }
            Texte { text: "Effets coupés, notifications en pause"; secondaire: true; font.pixelSize: 12 }
        }
    }
    Rond {
        anchors.right: parent.right; y: 5
        taille: 46; icone: "close"; actif: true; couleur: Couleurs.gris3; couleurIcone: Couleurs.texte
        onClic: Etat.faire(["hyprctl", "eval", "nc.mode_jeu()"])
    }

    // Mesures : une tuile par valeur ; la température vire à l'orange puis au rouge
    component Tuile: Rectangle {
        property string titre: ""
        property string valeur: "–"
        property string icone: ""
        property color teinte: Couleurs.texte
        width: (j.width - 10) / 2; height: 62; radius: 16; color: Couleurs.carte
        Ico { x: 12; y: 10; nom: parent.icone; taille: 16; color: Couleurs.texteSec }
        Texte { x: 34; y: 9; text: parent.titre; secondaire: true; font.pixelSize: 12 }
        Texte { x: 12; y: 30; text: parent.valeur; font.pixelSize: 20; font.weight: Font.DemiBold; color: parent.teinte }
    }
    function chaleur(t) { return t >= 85 ? Couleurs.rouge : (t >= 72 ? Couleurs.orange : Couleurs.texte) }
    readonly property bool gpuVeille: m.gpu === "veille"
    Grid {
        anchors.top: tete.bottom; anchors.topMargin: 16
        columns: 2; spacing: 10
        Tuile { icone: "memory"; titre: "Processeur"; valeur: j.m.cpu !== undefined ? j.m.cpu + " %" : "–" }
        Tuile { icone: "device_thermostat"; titre: "Processeur"; valeur: j.m.cpu_temp !== undefined ? j.m.cpu_temp + " °C" : "–"
                teinte: j.chaleur(parseInt(j.m.cpu_temp) || 0) }
        Tuile { icone: "developer_board"; titre: j.m.gpu_nom || "Carte graphique"
                valeur: j.gpuVeille ? "en veille" : (j.m.gpu !== undefined ? j.m.gpu + " %" + (j.m.gpu_watts ? " · " + j.m.gpu_watts + " W" : "") : "–") }
        Tuile { icone: "device_thermostat"; titre: "Carte graphique"; valeur: j.m.gpu_temp !== undefined ? j.m.gpu_temp + " °C" : "–"
                teinte: j.chaleur(parseInt(j.m.gpu_temp) || 0) }
    }
}
