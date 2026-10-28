// Rappel « Batterie à 80 % : tu peux débrancher » (nc-reglages → Énergie, BAT_RAPPEL_80 ; seuil BAT_RAPPEL_SEUIL, 80 par défaut).
// Pour garder la batterie en bonne santé : pendant la charge, UNE notification douce quand le niveau franchit le seuil, puis
// plus rien avant le prochain branchement. Aucun sondage ni minuteur : tout vient des changements de propriétés d'UPower
// déjà lus par Etat.qml (pourcent, enCharge, branche) et de Partage.retient.
//   - pas de batterie (PC fixe) ou réglage coupé : rien ;
//   - limite de charge matérielle active (Protéger la batterie) : rien, le rappel serait inutile (un seul « nc-conso suivre
//     --fois 1 » au moment de franchir le seuil, jamais avant) ;
//   - partage d'écran ou mode jeu (Partage.retient) : reporté, il vient à la fin s'il est encore en charge et branché ;
//   - déjà au-dessus du seuil au branchement ou au démarrage de l'île : rien (le niveau n'a rien « atteint »).
import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: br
    visible: false
    readonly property bool actif: Reglages.val("BAT_RAPPEL_80", "non") === "oui"
    readonly property int seuil: { var v = parseInt(Reglages.val("BAT_RAPPEL_SEUIL", "80")); return isNaN(v) ? 80 : Math.max(50, Math.min(100, v)) }
    property int dernier: -1               // dernier niveau vu (-1 : pas encore)
    property bool attente: false           // seuil franchi en charge, rappel pas encore donné
    property bool rappele: false           // déjà donné pour ce branchement

    function evaluer() {
        var p = Etat.pourcent
        if (!actif || !Etat.aBatterie || !Etat.branche) { attente = false; rappele = false; dernier = Etat.aBatterie ? p : -1; return }
        if (!rappele && Etat.enCharge && dernier >= 0 && dernier < seuil && p >= seuil) attente = true
        dernier = p
        if (attente && !Etat.enCharge) attente = false
        if (!attente || rappele || Partage.retient || verif.running) return
        verif.running = true
    }
    Connections {
        target: Etat
        function onPourcentChanged() { br.evaluer() }
        function onEnChargeChanged() { br.evaluer() }
        function onBrancheChanged() { br.evaluer() }
        function onABatterieChanged() { br.evaluer() }
    }
    Connections {
        target: Partage
        function onRetientChanged() { br.evaluer() }
    }
    onActifChanged: evaluer()
    Component.onCompleted: dernier = Etat.aBatterie ? Etat.pourcent : -1

    // Une limite de charge matérielle déjà active rend le rappel inutile ; réponse illisible : le rappel est donné
    Process {
        id: verif
        command: [Etat.bin + "nc-conso", "suivre", "--fois", "1"]
        stdout: StdioCollector {
            onStreamFinished: {
                var limite = false
                try { var j = JSON.parse(text.trim().split("\n").pop()); limite = !!(j.sante && j.sante.limite && j.sante.limite.active) } catch (e) { limite = false }
                br.attente = false
                br.rappele = true                      // une seule fois par branchement, avec ou sans rappel
                if (!limite && br.actif && Etat.branche && Etat.enCharge) { if (!Partage.retient) br.dire(); else { br.rappele = false; br.attente = true } }
            }
        }
    }
    function dire() { notifier.running = true }
    Process {
        id: notifier
        command: ["notify-send", "-a", Reglages.t("Batterie", "Battery"), "-u", "low", "-i", "battery-good",
                  Reglages.t("Batterie à " + br.seuil + " % : tu peux débrancher", "Battery at " + br.seuil + "%: you can unplug"),
                  Reglages.t("Pour la garder en bonne santé, évite de la laisser charger jusqu'à 100 %.",
                             "To keep it healthy, avoid charging it all the way to 100%.")]
    }
}
