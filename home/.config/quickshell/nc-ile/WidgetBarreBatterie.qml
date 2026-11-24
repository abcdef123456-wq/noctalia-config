import QtQuick
import Quickshell.Widgets
import Quickshell.Services.UPower

WidgetBarreLibelle {
    id: w
    readonly property var options: barre.definition
    readonly property bool plugin: barre.type === "nc/batterie:batterie"
    readonly property var batterie: {
        const choix = String(options.device || "auto")
        if (plugin || choix === "auto" && Etat.aBatterie) return Etat.aBatterie && Etat.batterie.isPresent ? Etat.batterie : null
        let cible = null
        for (const d of UPower.devices.values) {
            if (!d.ready || !d.isPresent || d.type === UPowerDeviceType.LinePower || !Number.isFinite(d.percentage)) continue
            if (choix !== "auto") {
                const nom = d.nativePath.split("/").pop()
                if (choix === d.nativePath || choix === d.model || choix === nom || nom && choix.endsWith("_" + nom)) return d
            } else if (d.percentage > 0 && (!cible || d.percentage < cible.percentage)) cible = d
        }
        return cible
    }
    readonly property int pourcent: batterie ? Math.min(100, Math.max(0, Math.round(batterie.percentage * 100))) : 0
    readonly property int etat: batterie ? batterie.state : UPowerDeviceState.Unknown
    readonly property bool enCharge: etat === UPowerDeviceState.Charging
    readonly property bool secteur: !!batterie && (batterie.isLaptopBattery ? Etat.branche : enCharge || etat === UPowerDeviceState.FullyCharged)
    readonly property bool chargePleine: etat === UPowerDeviceState.FullyCharged || pourcent >= 100
    readonly property real watts: plugin && WidgetBarreSonde.wattsBatterie >= 0 ? WidgetBarreSonde.wattsBatterie
                                  : batterie ? Math.abs(batterie.changeRate) : 0
    readonly property real secondes: batterie ? (enCharge ? batterie.timeToFull : secteur ? 0 : batterie.timeToEmpty) : 0
    readonly property bool graphique: plugin || options.display_mode === "graphic"
    readonly property bool montrerChiffre: options.show_label !== false && !(graphique && barre.vertical && pourcent >= 100)
    readonly property int seuil: Etat.alerte1
    readonly property color encre: !secteur && seuil > 0 && pourcent <= seuil ? barre.teinte(options.warning_color || "error", Couleurs.rouge) : barre.premierPlan
    readonly property bool lireWatts: plugin && survol && !!batterie
    property bool souscrit: false
    onLireWattsChanged: {
        if (lireWatts && !souscrit) { souscrit = true; ++WidgetBarreSonde.survolsBatterie }
        else if (!lireWatts && souscrit) { souscrit = false; --WidgetBarreSonde.survolsBatterie }
    }
    Component.onDestruction: if (souscrit) --WidgetBarreSonde.survolsBatterie

    affiche: !!batterie && (options.hide_when_plugged !== true || !secteur) && (options.hide_when_full !== true || !chargePleine)
              && largeurContenu > 0 && hauteurContenu > 0
    glyphe: graphique || options.display_mode === "none" ? "" : enCharge ? "battery_charging_full" : pourcent >= 95 ? "battery_full"
        : pourcent <= 8 ? "battery_alert" : "battery_" + Math.max(1, Math.min(6, Math.ceil(pourcent * 6 / 100))) + "_bar"
    plein: true
    encreGlyphe: encre
    visuel: graphique ? dessin : null
    libelle: graphique || !montrerChiffre ? "" : valeur(false)
    infobulle: pourcent + "% · " + (enCharge ? Reglages.t("En charge", "Charging") : secteur ? Reglages.t("Branchée", "Plugged in") : Reglages.t("Sur batterie", "On battery"))
        + (watts > 0 ? "\n" + watts.toFixed(1) + " W" : "") + (secondes > 0 ? " · " + duree(false) : "")
    gauche: () => barre.page("charge", "systeme")
    function duree(courte) {
        const m = Math.floor(secondes / 60), h = Math.floor(m / 60)
        if (!h) return m + (courte ? "m" : " min")
        return h + (courte ? ":" : " h ") + String(m % 60).padStart(2, "0") + (courte ? "" : " min")
    }
    function valeur(court) {
        if (!barre.vertical && options.label_content === "time" && secondes > 0) return duree(court)
        if (!barre.vertical && options.label_content === "rate" && watts > 0) return court ? (watts < 1 ? "<1W" : Math.round(watts) + "W") : watts.toFixed(1) + " W"
        return pourcent + (court ? "" : "%")
    }

    Component {
        id: dessin
        Item {
            id: batterieGraphique
            readonly property bool verticale: w.barre.vertical
            readonly property bool etatVisible: w.secteur
            readonly property real diametre: 13
            implicitWidth: verticale ? corps.width : corps.width + borne.width + (etatVisible ? diametre + 2 : 0)
            implicitHeight: verticale ? corps.height + borne.height + (etatVisible ? diametre + 2 : 0) : corps.height
            ClippingRectangle {
                id: corps
                width: batterieGraphique.verticale ? (w.montrerChiffre ? 18 : 14) : 25
                height: batterieGraphique.verticale ? (w.montrerChiffre ? 23 : 22) : 15
                y: batterieGraphique.verticale ? borne.height : 0
                radius: Couleurs.rayon(4, width, height)
                color: Couleurs.carte
                Rectangle { anchors.fill: parent; color: w.encre; opacity: 0.65 }
                Rectangle {
                    anchors.left: parent.left; anchors.bottom: parent.bottom
                    width: batterieGraphique.verticale ? corps.width : corps.width * w.pourcent / 100
                    height: batterieGraphique.verticale ? corps.height * w.pourcent / 100 : corps.height
                    color: w.encre; radius: Couleurs.rayon(3, width, height)
                }
                Text {
                    anchors.fill: parent
                    anchors.margins: 1
                    visible: w.montrerChiffre
                    text: w.valeur(true)
                    font.family: w.barre.police; font.pixelSize: batterieGraphique.verticale ? 11 : 13; font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    fontSizeMode: Text.Fit; minimumPixelSize: 7; color: Couleurs.carte
                }
            }
            Rectangle {
                id: borne
                width: batterieGraphique.verticale ? 7 : 3; height: batterieGraphique.verticale ? 3 : 7
                x: batterieGraphique.verticale ? (corps.width - width) / 2 : corps.width
                y: batterieGraphique.verticale ? 0 : (corps.height - height) / 2
                radius: Math.min(width, height) / 2; color: w.encre
            }
            Ico {
                visible: batterieGraphique.etatVisible
                width: batterieGraphique.diametre; height: width
                x: batterieGraphique.verticale ? (corps.width - width) / 2 : corps.width + borne.width + 2
                y: batterieGraphique.verticale ? corps.y + corps.height + 2 : (corps.height - height) / 2
                nom: w.enCharge ? "bolt" : "power"; color: w.encre; taille: width
            }
        }
    }
}
