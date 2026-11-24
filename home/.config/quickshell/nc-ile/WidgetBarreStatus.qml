import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Services.Pipewire
import Quickshell.Services.UPower

WidgetBarreLibelle {
    id: w
    readonly property string type: barre.type
    readonly property var options: barre.definition
    readonly property bool micro: type === "volume" && options.device === "input"
    readonly property var audio: type !== "volume" ? null : micro ? Pipewire.defaultAudioSource : Etat.sortie
    readonly property int volume: audio && audio.audio ? Math.round(audio.audio.volume * 100) : 0
    readonly property bool muet: audio && audio.audio ? audio.audio.muted || volume <= 0 : true
    readonly property var reseau: chargeurReseau.item ? chargeurReseau.item.service : null
    readonly property var bluetooth: chargeurBluetooth.item ? chargeurBluetooth.item.service : null
    readonly property var pointAcces: {
        if (!reseau) return null
        for (const d of reseau.wifi) {
            if (!d.connected) continue
            const point = d.networks.values.find(n => n.connected)
            if (point) return point
        }
        return null
    }
    readonly property var ethernet: reseau ? reseau.filaire.find(d => d.connected) || null : null
    readonly property int signalWifi: pointAcces ? Math.round(pointAcces.signalStrength * (pointAcces.signalStrength <= 1 ? 100 : 1)) : 0
    readonly property bool vpn: type === "network" && options.vpn_status !== "hidden" && VpnEtat.actif
    readonly property string nomWifi: ethernet ? (ethernet.network && ethernet.network.name || ethernet.name) : pointAcces ? pointAcces.name : ""
    readonly property string nomReseau: vpn && options.show_vpn_label === true ? (options.vpn_status === "both" && nomWifi ? nomWifi + " · " : "") + VpnEtat.libelle : nomWifi
    readonly property string glypheReseau: ethernet ? "lan" : pointAcces ? (signalWifi < 26 ? "wifi_1_bar" : signalWifi < 61 ? "wifi_2_bar" : "wifi")
                                                    : reseau && reseau.wifiActive ? "wifi_off" : "signal_wifi_off"
    readonly property var adaptateur: bluetooth ? bluetooth.adaptateur : null
    readonly property var appareils: adaptateur && adaptateur.enabled ? adaptateur.devices.values.filter(d => d.connected) : []
    readonly property string nomBluetooth: appareils.map(d => d.name).join(", ")
    readonly property bool economie: type === "power_profile" && Etat.profil === PowerProfile.PowerSaver
    readonly property bool performance: type === "power_profile" && Etat.profil === PowerProfile.Performance
    readonly property string profil: economie ? Reglages.t("Économie", "Power saver") : performance ? "Performance" : Reglages.t("Équilibré", "Balanced")
    property string disposition: ""

    affiche: {
        if (largeurContenu <= 0 || hauteurContenu <= 0) return false
        switch (type) {
        case "power_profile": return !Etat.profilsAbsents
        case "volume": return !!audio && (!micro || options.hide_when_inactive !== true || Etat.microActif)
        case "network": return !!reseau || vpn
        case "bluetooth": return !!bluetooth && (options.hide_when_adapter_off !== true || !!adaptateur && adaptateur.enabled)
                               && (options.hide_when_no_connected_device !== true || appareils.length > 0)
        case "notifications": return options.hide_when_no_unread !== true || Notifs.nonLues > 0
        case "keyboard_layout": return disposition !== ""
        case "privacy": return Etat.microActif || Etat.cameraActive || Partage.silence
        default: return true
        }
    }
    glyphe: {
        switch (type) {
        case "volume": return micro ? (muet ? "mic_off" : "mic") : muet ? "volume_off" : volume < 45 ? "volume_down" : "volume_up"
        case "network": return vpn && (!reseau || options.vpn_status !== "both") ? "shield" : glypheReseau
        case "bluetooth": return !adaptateur || !adaptateur.enabled ? "bluetooth_disabled" : appareils.length ? "bluetooth_connected" : "bluetooth"
        case "power_profile": return economie ? "eco" : performance ? "bolt" : "balance"
        case "notifications": return Notifs.concentration ? "notifications_off" : Notifs.nonLues ? "notifications_active" : "notifications"
        case "brightness": return "brightness_6"
        case "keyboard_layout": return "keyboard"
        case "caffeine": return Etat.cafe ? "coffee" : "coffee_maker"
        case "nightlight": return Etat.nuit ? "nightlight" : "nightlight_off"
        case "privacy": return Partage.silence ? "screen_share" : Etat.cameraActive ? "videocam" : "mic"
        default: return ""
        }
    }
    visuel: reseau && vpn && options.vpn_status === "both" && options.show_glyph !== false ? deuxGlyphes : null
    encreGlyphe: type === "volume" && muet ? barre.teinte(options.mute_color || "error", barre.premierPlan) : barre.premierPlan
    plein: performance || economie || type === "notifications" && Notifs.nonLues > 0
    libelle: {
        switch (type) {
        case "volume": return options.show_label !== false && (!muet || options.hide_label_when_muted !== true) ? volume + "%" : ""
        case "brightness": return options.show_label !== false ? Math.round(Etat.luminosite * 100) + "%" : ""
        case "network": return options.show_label !== false ? (barre.vertical ? nomReseau.slice(0, 3) : nomReseau) : ""
        case "bluetooth": return options.show_label === true ? (barre.vertical ? nomBluetooth.slice(0, 3) : nomBluetooth) : ""
        case "notifications": return Notifs.nonLues > 0 ? String(Notifs.nonLues) : ""
        case "keyboard_layout": return barre.vertical ? disposition.slice(0, 3) : disposition
        default: return options.custom_label || ""
        }
    }
    infobulle: {
        switch (type) {
        case "volume": return (micro ? Reglages.t("Microphone", "Microphone") : Reglages.t("Volume", "Volume")) + " · " + volume + "%"
        case "brightness": return Reglages.t("Luminosité", "Brightness") + " · " + Math.round(Etat.luminosite * 100) + "%"
        case "network":
            if (!reseau) return vpn ? VpnEtat.libelle : ""
            return (nomWifi || Reglages.t("Réseau déconnecté", "Network disconnected"))
                   + (pointAcces && !ethernet ? " · " + signalWifi + "% · " + pointAcces.device.name : "") + (vpn ? "\n" + VpnEtat.libelle : "")
        case "bluetooth": return nomBluetooth || (adaptateur && adaptateur.enabled ? "Bluetooth" : Reglages.t("Bluetooth désactivé", "Bluetooth off"))
        case "power_profile": return profil
        case "notifications": return Notifs.concentration ? Reglages.t("Ne pas déranger", "Do Not Disturb") : Reglages.t("Notifications", "Notifications") + " · " + Notifs.nonLues
        case "keyboard_layout": return disposition
        case "caffeine": return Reglages.t("Empêcher la mise en veille", "Inhibit idle")
        case "nightlight": return Reglages.t("Veilleuse", "Night light")
        case "privacy": return [Etat.appliMicro, Etat.appliCamera, Partage.silence ? Reglages.t("Partage d’écran", "Screen sharing") : ""].filter(x => x).join(" · ")
        default: return ""
        }
    }
    maximum: barre.vertical ? 38 : 126
    gauche: () => {
        switch (type) {
        case "volume": case "privacy": barre.page("son"); break
        case "network": barre.page("reseau"); break
        case "bluetooth": barre.page("bluetooth"); break
        case "brightness": barre.page("centre"); break
        case "notifications": barre.page("notifications"); break
        case "power_profile": cycle(1); break
        case "caffeine": Etat.basculerCafe(); break
        case "nightlight": Etat.nuit = !Etat.nuit; Etat.faire(["noctalia", "msg", "nightlight-force-toggle"]); break
        case "keyboard_layout": Quickshell.execDetached(["hyprctl", "switchxkblayout", "all", "next"]); break
        }
    }
    droit: () => {
        switch (type) {
        case "volume": if (audio && audio.audio) audio.audio.muted = !audio.audio.muted; break
        case "bluetooth": if (adaptateur) adaptateur.enabled = !adaptateur.enabled; break
        case "notifications": Notifs.basculerConcentration(); break
        case "power_profile": cycle(-1); break
        case "network":
            if (!reseau) break
            if (ethernet) ethernet.disconnect()
            else if (pointAcces || reseau.wifi.some(d => d.nmManaged)) reseau.basculerWifi()
            else {
                const d = reseau.filaire.find(d => d.hasLink && d.nmManaged)
                if (d) Quickshell.execDetached(["nmcli", "device", "connect", d.name])
            }
            break
        }
    }
    molette: type === "power_profile" ? cycle : type === "volume" || type === "brightness" ? ajuster : null
    function cycle(pas) {
        const profils = Etat.performanceDisponible ? [PowerProfile.PowerSaver, PowerProfile.Balanced, PowerProfile.Performance]
                                                    : [PowerProfile.PowerSaver, PowerProfile.Balanced]
        const i = profils.indexOf(Etat.profil)
        Etat.choisirProfil(profils[(i + pas + profils.length) % profils.length])
    }
    function ajuster(pas) {
        if (type === "brightness") Etat.reglerLuminosite(Etat.luminosite + pas * 0.05)
        else if (audio && audio.audio) {
            audio.audio.muted = false
            audio.audio.volume = Math.max(0, Math.min(1, audio.audio.volume + pas * 0.05))
        }
    }
    Component.onCompleted: {
        if (type === "brightness") Etat.lireLuminosite(false)
        if (type === "keyboard_layout") clavier.running = true
    }
    // Sans ces modules facultatifs, le reste de la barre doit pouvoir se charger.
    Loader {
        id: chargeurReseau
        active: w.type === "network"
        sourceComponent: QtObject {
            id: sondeReseau
            property var service: null
            Component.onCompleted: {
                try {
                    service = Qt.createQmlObject(`import QtQuick; import Quickshell.Networking
                        QtObject {
                            readonly property var wifi: Networking.devices.values.filter(d => d.type === DeviceType.Wifi)
                            readonly property var filaire: Networking.devices.values.filter(d => d.type === DeviceType.Wired)
                            readonly property bool wifiActive: Networking.wifiEnabled
                            function basculerWifi() { Networking.wifiEnabled = !Networking.wifiEnabled }
                        }`, sondeReseau, "BarreReseau")
                } catch (e) {
                    console.warn("Module réseau de la barre indisponible : " + e)
                }
            }
        }
    }
    Loader {
        id: chargeurBluetooth
        active: w.type === "bluetooth"
        sourceComponent: QtObject {
            id: sondeBluetooth
            property var service: null
            Component.onCompleted: {
                try {
                    service = Qt.createQmlObject(`import QtQuick; import Quickshell.Bluetooth
                        QtObject { readonly property var adaptateur: Bluetooth.defaultAdapter }`, sondeBluetooth, "BarreBluetooth")
                } catch (e) {
                    console.warn("Module Bluetooth de la barre indisponible : " + e)
                }
            }
        }
    }
    Connections {
        target: w.type === "keyboard_layout" ? Hyprland : null
        function onRawEvent(e) {
            if (e.name === "activelayout") { const p = e.data.indexOf(","); if (p >= 0) w.disposition = e.data.slice(p + 1) }
        }
    }
    Process {
        id: clavier
        command: ["hyprctl", "-j", "devices"]
        stdout: StdioCollector { onStreamFinished: {
            try { const cl = JSON.parse(text).keyboards; w.disposition = (cl.find(c => c.main) || cl[0]).active_keymap || "" } catch (e) {}
        } }
    }
    Component {
        id: deuxGlyphes
        Item {
            implicitWidth: w.barre.vertical ? w.barre.tailleIcone : 2 * w.barre.tailleIcone + 2
            implicitHeight: w.barre.vertical ? 2 * w.barre.tailleIcone + 2 : w.barre.tailleIcone
            Ico { width: w.barre.tailleIcone; height: width; nom: w.glypheReseau; taille: width; color: w.barre.premierPlan }
            Ico { x: w.barre.vertical ? 0 : width + 2; y: w.barre.vertical ? height + 2 : 0; width: w.barre.tailleIcone; height: width; nom: "shield"; taille: width; color: w.barre.premierPlan }
        }
    }
}
