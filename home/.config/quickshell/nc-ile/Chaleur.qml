pragma Singleton
// Veille de surchauffe du processeur (page Santé : Sante.qml). Presque gratuite : le fichier de température du
// processeur (hwmon, trouvé une seule fois au démarrage par nc-ile-etat capteurs) et /proc/stat sont relus toutes les
// 20 s par l'île elle-même (FileView : aucun processus), seulement écran allumé et session déverrouillée (Etat.ecranVu).
// Au-delà du seuil (CHALEUR_ALERTE, 95 °C par défaut ; 0 : jamais) pendant plus d'une minute, la pilule le dit et UNE
// notification explique les causes probables et les gestes utiles (bouton « Performance » : le profil d'énergie, par
// le service de profils, comme le centre de contrôle) ; puis silence jusqu'au retour 10 °C sous le seuil. Un pic court
// ne déclenche rien. Machine sans capteur du processeur (tour, machine virtuelle) : rien ne tourne.
// Jamais d'écriture dans /sys, jamais de droits administrateur : on lit, on explique, et le profil passe par le
// mécanisme existant.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.UPower

Singleton {
    id: ch

    property string fichierCpu: ""         // …/hwmon*/temp1_input du processeur ("" : pas de capteur)
    property string fabricant: ""          // constructeur (DMI), pour un conseil adapté (Fn + Q sur un Lenovo Legion…)
    readonly property bool lenovo: /lenovo/i.test(fabricant)
    readonly property int seuil: Math.max(0, Math.min(110, parseInt(Reglages.val("CHALEUR_ALERTE", "95")) || 0))
    property int intervalle: 20000         // entre deux lectures (ms)
    property int duree: 60000              // au-dessus du seuil pendant au moins ce temps avant d'alerter (ms)
    readonly property bool veille: fichierCpu !== "" && seuil > 0 && Etat.ecranVu

    property int temperature: 0            // dernière lecture (°C)
    property int charge: -1                // charge du processeur entre deux lectures (%), -1 : pas encore connue
    property real chaudDepuis: 0           // première lecture au-dessus du seuil (ms), 0 : sous le seuil
    property real derniereLecture: 0
    property bool alerte: false            // annoncée ; retombe 10 °C sous le seuil
    property int chargeAlerte: 0           // charge au moment de l'alerte
    property string programme: ""          // programme le plus gourmand au moment de l'alerte ("" : rien qui pèse)
    property int programmePct: 0
    property real totAvant: 0
    property real idleAvant: 0

    // Lancée par shell.qml au démarrage de l'île (un seul nc-ile-etat capteurs, jamais relancé)
    function demarrer() { if (!trouver.running) trouver.running = true }
    Process {
        id: trouver
        command: [Etat.bin + "nc-ile-etat", "capteurs"]
        stdout: StdioCollector {
            onStreamFinished: {
                var t = {}
                text.split("\n").forEach(l => { var p = l.indexOf("="); if (p > 0) t[l.slice(0, p)] = l.slice(p + 1) })
                ch.fabricant = t.fabricant || ""
                ch.fichierCpu = t.cpu || ""
                Etat.capteursSante = t.capteurs === "1"
            }
        }
    }
    // Lectures synchrones (blockLoading) de deux fichiers minuscules du noyau : quelques microsecondes, aucun processus
    FileView { id: temp; path: ch.fichierCpu; blockLoading: true; printErrors: false }
    FileView { id: stat; path: "/proc/stat"; blockLoading: true; printErrors: false }
    Timer { interval: ch.intervalle; repeat: true; running: ch.veille; triggeredOnStart: true; onTriggered: ch.relever() }

    function relever() {
        if (fichierCpu === "") return
        var maintenant = Date.now()
        // Longue pause (écran éteint, veille) : la série d'avant ne compte plus, on repart d'une lecture neuve
        if (maintenant - derniereLecture > 3 * intervalle) { chaudDepuis = 0; charge = -1; totAvant = 0 }
        derniereLecture = maintenant
        temp.reload()
        var t = parseInt(temp.text())
        if (isNaN(t)) return
        temperature = Math.round(t / 1000)
        stat.reload()
        var l = (stat.text().split("\n")[0] || "").trim().split(/\s+/)
        if (l.length >= 5) {
            var tot = 0
            for (let i = 1; i < l.length; i++) tot += parseInt(l[i]) || 0
            var idle = (parseInt(l[4]) || 0) + (parseInt(l[5]) || 0)
            if (totAvant > 0 && tot > totAvant) charge = Math.round(100 * ((tot - totAvant) - (idle - idleAvant)) / (tot - totAvant))
            totAvant = tot; idleAvant = idle
        }
        if (temperature >= seuil) {
            if (chaudDepuis === 0) chaudDepuis = maintenant
            else if (!alerte && maintenant - chaudDepuis >= duree) annoncer()
        } else if (temperature < seuil - 5) {
            chaudDepuis = 0
        }
        if (alerte && temperature <= seuil - 10) alerte = false
    }

    // Une seule fois par épisode : la pilule, puis le programme le plus gourmand (un nc-ile-etat sante, 0,4 s) et la
    // notification avec les causes et les gestes
    function annoncer() {
        alerte = true
        chargeAlerte = Math.max(0, charge)
        programme = ""; programmePct = 0
        Etat.activite("chaleur", 6000)
        if (!details.running) details.running = true
    }
    Process {
        id: details
        command: [Etat.bin + "nc-ile-etat", "sante"]
        stdout: StdioCollector {
            onStreamFinished: {
                text.split("\n").forEach(l => {
                    if (l.indexOf("top=") === 0) { var c = l.slice(4).split("\t"); ch.programme = c[0] || ""; ch.programmePct = parseInt(c[1]) || 0 }
                })
                if (ch.alerte && !notifier.running) notifier.running = true
            }
        }
    }
    readonly property bool performancePossible: Etat.profil !== PowerProfile.Performance
    // Texte de la notification et de la carte de la page Santé
    function titre() { return Reglages.t("Processeur à " + temperature + " °C", "CPU at " + temperature + "°C") }
    function situation() {
        var p = programme !== "" ? Reglages.t(", surtout « " + programme + " » (" + programmePct + " %)", ", mostly “" + programme + "” (" + programmePct + "%)") : ""
        return chargeAlerte >= 60
            ? Reglages.t("Depuis plus d'une minute, sous forte charge (" + chargeAlerte + " %" + p + ").",
                         "For over a minute, under heavy load (" + chargeAlerte + "%" + p + ").")
            : Reglages.t("Depuis plus d'une minute, presque au repos (" + chargeAlerte + " % de charge" + p + ") : ce n'est pas normal.",
                         "For over a minute, almost idle (" + chargeAlerte + "% load" + p + "): that's not normal.")
    }
    function causes() {
        return Reglages.t("Causes probables : ventilateurs trop lents (profil Équilibré ou Silencieux), grilles d'aération bouchées ou PC posé sur du tissu, pâte thermique fatiguée.",
                          "Likely causes: fans too slow (Balanced or Quiet profile), blocked air vents or the PC on fabric, worn thermal paste.")
    }
    function gestes() {
        var fn = lenovo ? Reglages.t(" (ou Fn + Q)", " (or Fn + Q)") : ""
        return Reglages.t("Gestes : passer en Performance" + fn + " pour pousser les ventilateurs, poser le PC sur une surface dure, dépoussiérer les grilles.",
                          "What to do: switch to Performance" + fn + " to push the fans, put the PC on a hard surface, dust the vents.")
    }
    Process {
        id: notifier
        command: ["notify-send", "-a", Reglages.t("Santé", "Health"), "-u", "critical", "-i", "dialog-warning"]
                 .concat(ch.performancePossible ? ["-A", "perf=" + Reglages.t("Mode Performance", "Performance Mode")] : [])
                 .concat([ch.titre(), ch.situation() + "\n" + ch.causes() + "\n" + ch.gestes()])
        stdout: StdioCollector { onStreamFinished: if (text.trim() === "perf") Etat.choisirProfil(PowerProfile.Performance) }
    }
}
