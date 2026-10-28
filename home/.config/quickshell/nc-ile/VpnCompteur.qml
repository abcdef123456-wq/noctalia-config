// Les deux compteurs d'une interface réseau : octets reçus et envoyés, lus dans /sys/class/net/IF/statistics/{rx,tx}_bytes
// (racine /sys, ou NC_SYSFS pour les tests). Rien ne tourne ici : VpnDebit.qml appelle recharger() une fois par seconde,
// seulement fenêtre ouverte et écran allumé. -1 = illisible (interface disparue, fichier absent).
import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: c
    property string interfaceNom: ""
    property real rx: -1
    property real tx: -1
    // Un nom d'interface sûr : lettres, chiffres, « _ », « . », « - », 15 signes au plus, ni « . » ni « .. »
    readonly property bool valide: /^[A-Za-z0-9_.-]{1,15}$/.test(interfaceNom) && interfaceNom !== "." && interfaceNom !== ".."
    readonly property string base: (Quickshell.env("NC_SYSFS") || "/sys") + "/class/net/" + interfaceNom + "/statistics/"
    function recharger() {
        if (!valide) { rx = -1; tx = -1; return }
        fichierRx.reload(); fichierTx.reload()
    }
    FileView {
        id: fichierRx
        path: c.valide ? c.base + "rx_bytes" : ""
        onLoaded: { var n = parseInt(text()); c.rx = isNaN(n) || n < 0 ? -1 : n }
        onLoadFailed: c.rx = -1
    }
    FileView {
        id: fichierTx
        path: c.valide ? c.base + "tx_bytes" : ""
        onLoaded: { var n = parseInt(text()); c.tx = isNaN(n) || n < 0 ? -1 : n }
        onLoadFailed: c.tx = -1
    }
}
