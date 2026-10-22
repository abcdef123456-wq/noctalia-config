pragma Singleton
// Mode graphique d'un portable à MUX (nc-gpu-mode) : Hybride (l'écran sur la carte intégrée) ou Dédiée (l'écran sur la
// carte NVIDIA). L'état est lu à la demande (ouverture de la page Système, demande de bascule), jamais en boucle : la
// carte NVIDIA n'est pas réveillée. Changer de mode redémarre le PC : la question est posée par une carte de l'île
// (ConfirmationGpu.qml), jamais par un bouton de notification, que tous les démons n'affichent pas. Elle s'ouvre par la
// page Système, par nc-reglages (Énergie → Changer de mode graphique…) ou par « qs -c nc-ile ipc call ile gpuMode ».
// Sur [Redémarrer…] seulement : nc-gpu-mode basculer --sans-question CIBLE.
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: mg
    readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
    property var etat: ({})                          // { mode, methode, bios_direct, carte_ecran } (nc-gpu-mode json)
    readonly property string mode: etat.mode || ""
    readonly property string methode: etat.methode || ""
    readonly property bool biosDirect: etat.bios_direct === true
    // Deux cartes et un écran interne : il y a un mode à choisir
    readonly property bool possible: mode === "hybride" || mode === "dediee"
    property bool demande: false                     // la carte de confirmation est affichée
    property string cible: ""                        // le mode proposé par la carte
    property string voulue: ""                       // le mode demandé, avant la lecture de l'état ("" : l'autre)
    property bool aDemander: false

    function nom(m) { return m === "dediee" ? Reglages.t("Dédiée", "Discrete") : (m === "hybride" ? Reglages.t("Hybride", "Hybrid") : "") }
    function lire() { if (!lecteur.running) lecteur.running = true }
    // Ouvre la carte de confirmation, vers ce mode ("" : l'autre que l'actuel), une fois l'état relu
    function demander(c) { voulue = c === "hybride" || c === "dediee" ? c : ""; aDemander = true; lire() }
    function annuler() { demande = false }
    function confirmer() {
        if (!demande || (cible !== "hybride" && cible !== "dediee")) return
        demande = false
        // Le BIOS sans démarrage direct : la carte n'a fait qu'expliquer, rien à lancer
        if (methode === "bios" && !biosDirect) return
        Quickshell.execDetached([bin + "nc-gpu-mode", "basculer", "--sans-question", cible])
    }

    // Textes de la carte, selon la manière de basculer sur ce PC
    readonly property string titre: Reglages.t("Passer en mode " + nom(cible) + " ?", "Switch to " + nom(cible) + " mode?")
    readonly property bool parLeBios: methode === "bios" || methode === ""
    readonly property string texte: parLeBios
        ? (biosDirect
           ? Reglages.t("Ton PC redémarre dans son BIOS : choisis GPU Working Mode → " + nom(cible) + ", puis F10. Les applis ouvertes seront fermées.",
                        "Your PC restarts into its BIOS: choose GPU Working Mode → " + nom(cible) + ", then F10. Open apps will be closed.")
           : Reglages.t("Ton PC change de mode dans son BIOS : redémarre, appuie sur F2 dès l'allumage, choisis GPU Working Mode → " + nom(cible) + ", puis F10.",
                        "Your PC switches mode in its BIOS: restart, press F2 right at power-on, choose GPU Working Mode → " + nom(cible) + ", then F10."))
        : Reglages.t("Ton PC passe en mode " + nom(cible) + ", puis redémarre. Les applis ouvertes seront fermées.",
                     "Your PC switches to " + nom(cible) + " mode, then restarts. Open apps will be closed.")
    // Sans démarrage direct dans le BIOS, rien à confirmer : un seul bouton, qui ferme
    readonly property bool aConfirmer: !(parLeBios && !biosDirect)
    readonly property string bouton: parLeBios ? Reglages.t("Redémarrer dans le BIOS", "Restart into BIOS") : Reglages.t("Redémarrer", "Restart")

    Process {
        id: lecteur
        command: [mg.bin + "nc-gpu-mode", "json"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { mg.etat = JSON.parse(text) } catch (e) { mg.etat = ({}) }
                if (!mg.aDemander) return
                mg.aDemander = false
                if (!mg.possible) return
                var c = mg.voulue !== "" ? mg.voulue : (mg.mode === "hybride" ? "dediee" : "hybride")
                if (c === mg.mode) return                    // déjà dans ce mode : rien à demander
                mg.cible = c
                mg.demande = true
            }
        }
    }
}
