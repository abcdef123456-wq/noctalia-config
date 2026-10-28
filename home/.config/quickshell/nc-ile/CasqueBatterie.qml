pragma Singleton
// Batterie des casques et écouteurs Bluetooth, lue dans UPower (Quickshell.Services.UPower) : aucun processus, aucun
// sondage, UPower prévient quand le niveau change. Seuls les appareils de type Headset ou Headphones qui donnent un
// niveau (plus de 0 %) comptent : un casque sans batterie lisible ne montre rien. Réglage ILE_CASQUE_BATTERIE (nc-reglages).
// Servi à la réaction « AirPods 80 % » de la pilule (Etat.casqueBatterie) et à la page Son.
import QtQuick
import Quickshell
import Quickshell.Services.UPower

Singleton {
    id: cb
    readonly property bool actif: Reglages.val("ILE_CASQUE_BATTERIE", "oui") !== "non"
    // { nom, pct } pour chaque casque qui donne son niveau
    readonly property var appareils: !actif ? [] : UPower.devices.values
        .filter(d => d && (d.type === UPowerDeviceType.Headset || d.type === UPowerDeviceType.Headphones) && d.isPresent)
        .map(d => ({ nom: String(d.model || ""), pct: cb.pourcent(d.percentage) }))
        .filter(a => a.pct > 0)

    function pourcent(v) { return typeof v === "number" ? Math.round(v * (v <= 1 ? 100 : 1)) : 0 }
    // Le niveau du casque appelé « nom » (celui que PipeWire connaît) ; à défaut de nom qui colle, le seul casque connu ; 0 : aucun
    function niveauPour(nom) {
        var l = appareils, n = String(nom || "").toLowerCase()
        if (l.length === 0) return 0
        var a = n === "" ? null : l.find(x => x.nom !== "" && (n.indexOf(x.nom.toLowerCase()) >= 0 || x.nom.toLowerCase().indexOf(n) >= 0))
        if (a) return a.pct
        return l.length === 1 ? l[0].pct : 0
    }
}
