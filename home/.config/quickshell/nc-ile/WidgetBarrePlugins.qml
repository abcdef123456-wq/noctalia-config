import QtQuick

WidgetBarreLibelle {
    id: w
    readonly property bool vpn: barre.type === "vpn" || barre.type === "nc/vpn:vpn"
    readonly property bool garmin: barre.type === "garmin" || barre.type === "nc/garmin:garmin"
    readonly property var niveau: garmin ? WidgetBarreGarmin.niveau : undefined
    readonly property string garminTexte: Number.isFinite(niveau) ? String(Math.round(niveau)) : ""
    affiche: vpn ? VpnEtat.lu && VpnEtat.disponible : garmin ? WidgetBarreGarmin.affiche : true
    glyphe: vpn ? (VpnEtat.actif ? "verified_user" : "shield") : garmin ? "favorite" : TourEtat.enStream ? "smart_display" : "desktop_windows"
    plein: vpn ? VpnEtat.actif : garmin || TourEtat.enLigne || TourEtat.enStream
    encreGlyphe: vpn ? (VpnEtat.actif ? Couleurs.vert : Couleurs.texteSec)
        : garmin ? Couleurs.rouge : TourEtat.enStream ? Couleurs.bleu : TourEtat.enLigne ? Couleurs.vert : Couleurs.texteSec
    libelle: {
        if (vpn) {
            if (VpnEtat.masque) return "VPN"
            if (!VpnEtat.actif) return ""
            if (barre.vertical) return VpnEtat.indPays
            if (barre.compact && VpnEtat.indPays) return VpnEtat.drapeau + " " + VpnEtat.indPays
            return VpnEtat.libelle
        }
        if (garmin) return garminTexte
        if (!TourEtat.enLigne && !TourEtat.enStream) return ""
        if (Partage.silence) return "Tour"
        if (TourEtat.enStream) return barre.vertical ? "▶" : "Stream"
        return TourEtat.pingMs > 0 ? TourEtat.pingMs + (barre.vertical ? "" : " ms") : "Tour"
    }
    infobulle: vpn ? (VpnEtat.actif ? VpnEtat.libelle : "VPN") : garmin ? (garminTexte ? "Body Battery · " + garminTexte : "Garmin") : TourEtat.libelle
    maximum: barre.vertical ? 32 : 180
    gauche: () => {
        if (vpn) VpnEtat.demanderPanneau()
        else if (garmin) GarminEtat.demanderPanneau()
        else TourEtat.demanderPanneau()
    }
}
