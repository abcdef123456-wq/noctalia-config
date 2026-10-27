// Source du micro qu'utilise l'appli en appel (Appel.qml) : le nœud PipeWire relié au flux qui enregistre (lien
// source → flux), sinon la source par défaut. Suivie (PwObjectTracker) seulement pendant l'appel, pour lire et changer
// son état coupé ; jamais le flux de l'appli lui-même (s'y attacher faisait planter Quickshell quand plusieurs flux
// disparaissaient d'un coup). Casque Bluetooth en profil appel (HFP) : sa source s'appelle bluez_input.<adresse>.
import QtQuick
import Quickshell.Services.Pipewire

Item {
    id: s
    PwNodeLinkTracker { id: liens; node: Appel.noeud }
    readonly property var source: {
        var g = liens.linkGroups
        for (let i = 0; i < g.length; i++) if (g[i].source && !g[i].source.isStream) return g[i].source
        return Pipewire.defaultAudioSource
    }
    PwObjectTracker { objects: s.source ? [s.source] : [] }
    readonly property bool lie: !!(source && source.audio)
    readonly property bool muet: lie ? source.audio.muted : false
    readonly property bool monoBt: source ? (source.name || "").indexOf("bluez_input.") === 0 : false
    readonly property string nomSource: source ? (source.description || source.nickname || source.name || "") : ""
    function basculer() { if (lie) source.audio.muted = !source.audio.muted }
}
