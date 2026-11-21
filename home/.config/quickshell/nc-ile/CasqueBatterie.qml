pragma Singleton
// Batterie des casques et écouteurs Bluetooth, lue dans UPower (Quickshell.Services.UPower) : aucun processus, aucun
// sondage, UPower prévient quand le niveau change. Seuls les appareils de type Headset ou Headphones qui donnent un
// niveau (plus de 0 %) comptent : un casque sans batterie lisible ne montre rien. Réglage ILE_CASQUE_BATTERIE (nc-reglages).
// Même source pour souris, claviers, manettes et pavés tactiles sans fil (niveauAppareil, page Bluetooth de l'île).
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
    // Tous les appareils sans fil qui donnent un niveau : { nom, pct, chemin } (chemin UPower, ex. « /org/bluez/hci0/dev_AA_BB_… »)
    readonly property var peripheriques: !actif ? [] : UPower.devices.values
        .filter(d => d && d.isPresent && (d.type === UPowerDeviceType.Headset || d.type === UPowerDeviceType.Headphones
            || d.type === UPowerDeviceType.Mouse || d.type === UPowerDeviceType.Keyboard
            || d.type === UPowerDeviceType.GamingInput || d.type === UPowerDeviceType.Touchpad))
        .map(d => ({ nom: String(d.model || ""), pct: cb.pourcent(d.percentage), chemin: String(d.nativePath || "").toLowerCase() }))
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

    // Niveau d'un appareil Bluetooth, tout type : d'abord par son adresse (« AA:BB:… » ↔ « dev_aa_bb_… » dans le chemin
    // UPower, sûr même avec deux appareils de même nom) ; sinon par le nom, seulement s'il est unique ; 0 : rien à montrer
    function niveauAppareil(nom, adresse) {
        var l = peripheriques, ad = String(adresse || "").toLowerCase().replace(/:/g, "_"), n = String(nom || "").toLowerCase()
        if (ad !== "") {
            var p = l.find(x => x.chemin.indexOf("dev_" + ad) >= 0)
            if (p) return p.pct
        }
        var m = n === "" ? [] : l.filter(x => x.nom !== "" && x.nom.toLowerCase() === n)
        return m.length === 1 ? m[0].pct : 0
    }
}
