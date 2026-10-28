pragma Singleton
// Projection en cours : l'écran du PC est dupliqué (miroir) ou éteint au profit d'un second écran ou d'un projecteur (modes
// « Dupliquer » et « Second écran seulement » de nc-ecrans, Super + O). Étendre le bureau sur un écran de bureau n'en fait pas
// partie : personne ne regarde par-dessus ton épaule. Sert à « Ne pas déranger automatique » (Partage.qml, réglage NPD_AUTO).
// Aucun sondage : Hyprland prévient (monitoradded, monitorremoved, configreloaded sur le canal que Quickshell écoute déjà) ;
// l'état est alors relu une fois (hyprctl monitors all -j, 0,8 s après le dernier événement). Rien écran éteint ou réglage
// coupé ; sans hyprctl ou sans Hyprland : jamais actif, sans bruit.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland

Singleton {
    id: pj
    property bool actif: false
    property string mode: ""             // miroir | externe | ""
    readonly property bool veille: Reglages.val("NPD_AUTO", "oui") !== "non"

    function interne(m) { return /^(eDP|LVDS|DSI)/.test(m.name || "") }
    // Réponse de « hyprctl monitors all -j » : met actif et mode à jour (une réponse illisible : pas de projection)
    function analyser(texte) {
        var l
        try { l = JSON.parse(texte) } catch (e) { l = [] }
        if (!Array.isArray(l)) l = []
        var allumes = l.filter(m => m && !m.disabled)
        var externes = allumes.filter(m => !pj.interne(m) && !/^(HEADLESS|FALLBACK)/.test(m.name || ""))
        var miroir = externes.length > 0 && allumes.some(m => m.mirrorOf !== undefined && m.mirrorOf !== "none" && m.mirrorOf !== "")
        var externeSeul = externes.length > 0 && l.some(m => m && pj.interne(m) && m.disabled)
        mode = miroir ? "miroir" : (externeSeul ? "externe" : "")
        actif = mode !== ""
    }
    function lire() { if (veille && Etat.ecranVu && !lecteur.running) lecteur.running = true }

    Process {
        id: lecteur
        command: ["hyprctl", "monitors", "all", "-j"]
        stdout: StdioCollector { onStreamFinished: pj.analyser(text) }
    }
    Timer { id: apres; interval: 800; onTriggered: pj.lire() }
    Connections {
        target: Hyprland
        function onRawEvent(event) { if (/^(monitoradded|monitorremoved|monitoraddedv2|monitorremovedv2|configreloaded)$/.test(event.name)) apres.restart() }
    }
    // Écran rallumé ou réglage remis : une relecture ; réglage coupé : plus rien
    Connections { target: Etat; function onEcranVuChanged() { pj.lire() } }
    onVeilleChanged: { if (veille) lire(); else { mode = ""; actif = false } }
    Component.onCompleted: lire()
}
