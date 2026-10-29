// L'appli qui lit l'écran pendant un partage (carte « Partage » de PageNotifs.qml) : le nom du nœud PipeWire branché sur le
// flux de xdph (« xdph-streaming-… »), rien d'autre (texte brut, 40 caractères). Discord garde parfois la capture ouverte
// après la fin du stream : pour Hyprland, le partage continue ; la carte dit alors de l'arrêter dans l'appli.
// Chargé par son chemin seulement pendant un partage (comme AppelSource.qml) : sans PipeWire, rien d'autre ne s'y connecte.
import QtQuick
import Quickshell.Services.Pipewire

Item {
    readonly property string appli: {
        var noms = []
        for (const g of Pipewire.linkGroups.values) {
            if (!g || !g.source || !g.target || !/^xdph-streaming/.test(g.source.name || "")) continue
            var n = String(g.target.description || g.target.name || "").replace(/[\x00-\x1f]/g, " ").trim().slice(0, 40)
            if (n !== "" && noms.indexOf(n) < 0) noms.push(n)
        }
        return noms.join(", ")
    }
}
