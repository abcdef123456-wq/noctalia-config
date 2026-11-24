pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.UPower

Singleton {
    id: sonde
    property int utilisateurs: 0
    property int disques: 0
    property int reseaux: 0
    property int survolsBatterie: 0
    readonly property bool active: utilisateurs > 0 && Etat.ecranVu
    property var valeurs: ({})
    property var disque: ({})
    property var historique: ({})
    property var dernierCpu: []
    property var dernierReseau: []
    property double derniereMesure: 0
    property real wattsBatterie: -1
    readonly property var batteries: survolsBatterie > 0 ? UPower.devices.values.filter(d => d.isLaptopBattery && d.isPresent)
        .map(d => d.nativePath.split("/").pop()).filter(n => /^[a-zA-Z0-9_-]+$/.test(n)) : []

    FileView { id: proc; path: sonde.utilisateurs > 0 ? "/proc/stat" : ""; blockLoading: true; printErrors: false }
    FileView { id: mem; path: sonde.utilisateurs > 0 ? "/proc/meminfo" : ""; blockLoading: true; printErrors: false }
    FileView { id: temp; path: sonde.utilisateurs > 0 ? Chaleur.fichierCpu : ""; blockLoading: true; printErrors: false }
    FileView { id: net; path: sonde.reseaux > 0 ? "/proc/net/dev" : ""; blockLoading: true; printErrors: false }
    Timer { interval: 1500; running: sonde.active; triggeredOnStart: true; repeat: true; onTriggered: sonde.relever() }
    onActiveChanged: if (!active) {
        dernierCpu = []; dernierReseau = []; derniereMesure = 0
        valeurs = ({}); historique = ({})
    }

    function relever() {
        const sortie = {}, hist = {}
        proc.reload()
        const cpu = (proc.text().split("\n", 1)[0] || "").trim().split(/\s+/, 9).slice(1).map(Number)
        if (cpu.length >= 4) {
            const total = cpu.reduce((a, b) => a + b, 0), idle = cpu[3] + (cpu[4] || 0)
            if (dernierCpu.length && total > dernierCpu[0]) sortie.cpu_usage = Math.round(100 * (1 - (idle - dernierCpu[1]) / (total - dernierCpu[0])))
            dernierCpu = [total, idle]
        }
        mem.reload()
        const ram = /\bMemTotal:\s+(\d+)/.exec(mem.text()), libre = /\bMemAvailable:\s+(\d+)/.exec(mem.text())
        if (ram && libre && Number(ram[1]) > 0) sortie.ram_used = Math.round(100 * (1 - Number(libre[1]) / Number(ram[1])))
        if (Chaleur.fichierCpu) {
            temp.reload()
            const t = parseInt(temp.text(), 10)
            if (t >= 1000 && t <= 125000) sortie.cpu_temp = Math.round(t / 1000)
        }
        if (reseaux > 0) {
            net.reload()
            const compteur = [0, 0], maintenant = Date.now()
            for (const ligne of net.text().split("\n")) {
                const c = /^\s*([^:]+):\s*(.*)$/.exec(ligne)
                if (!c || /^(lo|tun\d*|wg\d*|tailscale\d*|veth.*|docker\d*)$/.test(c[1])) continue
                const n = c[2].split(/\s+/)
                compteur[0] += Number(n[0]) || 0
                compteur[1] += Number(n[8]) || 0
            }
            if (derniereMesure > 0 && maintenant > derniereMesure) {
                const facteur = 1000 / (maintenant - derniereMesure)
                sortie.net_rx = Math.max(0, (compteur[0] - dernierReseau[0]) * facteur)
                sortie.net_tx = Math.max(0, (compteur[1] - dernierReseau[1]) * facteur)
            }
            derniereMesure = maintenant
            dernierReseau = compteur
        } else if (derniereMesure) { derniereMesure = 0; dernierReseau = [] }
        for (const cle in sortie) hist[cle] = (historique[cle] || []).slice(-23).concat(sortie[cle])
        if (disques > 0)
            for (const cle in disque) hist[cle] = (historique[cle] || []).slice(-23).concat(disque[cle])
        valeurs = sortie
        historique = hist
    }
    Process {
        id: df
        command: ["df", "-kP", "/"]
        stdout: StdioCollector { onStreamFinished: {
            const d = /\s(\d+)\s+(\d+)\s+(\d+)\s+(\d+)%\s+\/\s*$/.exec(text)
            sonde.disque = d ? { disk_used_pct: +d[4], disk_free_pct: 100 - +d[4], disk_used: +d[2] * 1024, disk_free: +d[3] * 1024 } : ({})
        } }
    }
    Timer { interval: 30000; running: sonde.disques > 0 && Etat.ecranVu; triggeredOnStart: true; repeat: true; onTriggered: if (!df.running) df.running = true }

    Instantiator {
        id: accu
        model: sonde.batteries
        delegate: FileView {
            required property string modelData
            path: "/sys/class/power_supply/" + modelData + "/uevent"
            blockLoading: true; printErrors: false
        }
        onObjectAdded: Qt.callLater(sonde.releverBatterie)
    }
    Timer { interval: 1000; running: sonde.survolsBatterie > 0 && Etat.ecranVu; triggeredOnStart: true; repeat: true; onTriggered: sonde.releverBatterie() }
    onSurvolsBatterieChanged: if (!survolsBatterie) wattsBatterie = -1

    function releverBatterie() {
        if (!survolsBatterie) return
        let w = 0, connu = false
        for (let i = 0; i < accu.count; i++) {
            const fichier = accu.objectAt(i)
            if (!fichier) continue
            fichier.reload()
            const u = fichier.text(), p = /^POWER_SUPPLY_POWER_NOW=(-?\d+)$/m.exec(u)
            if (p) { w += Math.abs(Number(p[1])) / 1e6; connu = true; continue }
            const a = /^POWER_SUPPLY_CURRENT_NOW=(-?\d+)$/m.exec(u), v = /^POWER_SUPPLY_VOLTAGE_NOW=(\d+)$/m.exec(u)
            if (a && v) { w += Math.abs(Number(a[1]) * Number(v[1])) / 1e12; connu = true }
        }
        wattsBatterie = connu ? w : -1
    }
}
