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
            Texte { text: Reglages.t("Mode jeu", "Game Mode"); font.pixelSize: 22; font.weight: Font.DemiBold; color: Couleurs.orange }
            Texte { text: Reglages.t("Effets coupés, notifications en pause", "Effects off, notifications paused"); secondaire: true; font.pixelSize: 12 }
        }
    }
    Rond {
        anchors.right: parent.right; y: 5
        taille: 46; icone: "close"; actif: true; couleur: Couleurs.gris3; couleurIcone: Couleurs.texte
        onClic: Etat.faire(["hyprctl", "eval", "nc.mode_jeu()"])
    }

    function chaleur(t) { return t >= 85 ? Couleurs.rouge : (t >= 72 ? Couleurs.orange : Couleurs.texte) }
    readonly property bool gpuVeille: m.gpu === "veille"
    Grid {
        id: grille
        anchors.top: tete.bottom; anchors.topMargin: 16
        columns: 2; spacing: 10
        readonly property real l: (j.width - 10) / 2
        TuileJeu { width: grille.l; icone: "memory"; titre: Reglages.t("Processeur", "CPU"); valeur: j.m.cpu !== undefined ? j.m.cpu + Reglages.t(" %", "%") : "–" }
        TuileJeu { width: grille.l; icone: "device_thermostat"; titre: Reglages.t("Processeur", "CPU"); valeur: j.m.cpu_temp !== undefined ? j.m.cpu_temp + " °C" : "–"
                teinte: j.chaleur(parseInt(j.m.cpu_temp) || 0) }
        TuileJeu { width: grille.l; icone: "developer_board"; titre: j.m.gpu_nom || Reglages.t("Carte graphique", "GPU")
                valeur: j.gpuVeille ? Reglages.t("en veille", "asleep") : (j.m.gpu !== undefined ? j.m.gpu + Reglages.t(" %", "%") + (j.m.gpu_watts ? " · " + j.m.gpu_watts + " W" : "") : "–") }
        TuileJeu { width: grille.l; icone: "device_thermostat"; titre: Reglages.t("Carte graphique", "GPU"); valeur: j.m.gpu_temp !== undefined ? j.m.gpu_temp + " °C" : "–"
                teinte: j.chaleur(parseInt(j.m.gpu_temp) || 0) }
    }
}
