// Niveau du micro pendant un appel (Appel.qml) : PwNodePeakMonitor de Quickshell mesure la crête du signal de la source
// (un chiffre par image, jamais le son : rien n'est enregistré ni gardé). Ouvert seulement pendant que le niveau
// s'affiche (actif), lu à 30 images par seconde (Pas.qml), à 0 dès l'arrêt. Sans source : la source par défaut.
import QtQuick
import Quickshell.Services.Pipewire

Item {
    id: n
    property var source: null
    property bool actif: false
    property real niveau: 0
    PwNodePeakMonitor { id: crete; node: n.source || Pipewire.defaultAudioSource; enabled: n.actif && node !== null }
    Pas {
        running: n.actif
        onTriggered: n.niveau = Math.max(0, Math.min(1, crete.peak * 2.2))
        onRunningChanged: if (!running) n.niveau = 0
    }
}
