import QtQuick
import Quickshell
import "WidgetBarreActions.js" as Actions

Item {
    id: racine
    required property string nom
    required property var definition
    required property var ecran
    property bool vertical: false
    property string position: vertical ? "left" : "top"
    property point origine: Qt.point(0, 0)
    property color premierPlan: Couleurs.texte
    property int tailleTexte: 12
    property int graisse: 600
    property string police: Couleurs.police
    property var resoudreTeinte: null
    property real limiteLargeur: 0
    property real largeurClip: 0
    property color fondClip: "transparent"
    property bool compact: false
    readonly property real echelle: Math.max(0.25, Number(definition.scale ?? 1))
    property int resteMolette: 0
    property string dernierSensMolette: ""
    property double instantMolette: 0
    property bool gesteTraite: false

    readonly property string type: String(definition.type || nom).replace(/^(power|active|keyboard|custom|theme)-/, "$1_")
    readonly property bool affiche: definition.enabled !== false && chargeur.item !== null && chargeur.item.affiche
    readonly property real tailleIcone: Math.max(8, Math.round((tailleTexte + 3) * echelle))
    readonly property int bordInterieur: position === "bottom" ? Edges.Top : position === "left" ? Edges.Right
                                        : position === "right" ? Edges.Left : Edges.Bottom
    visible: affiche
    implicitWidth: affiche ? Math.ceil(chargeur.item.implicitWidth) : 0
    implicitHeight: affiche ? Math.ceil(chargeur.item.implicitHeight) : 0

    function aAction(cle) { return !!definition.actions && typeof definition.actions[cle] === "string" }
    function agir(cle, defaut) {
        if (aAction(cle) && Actions.lancerDepuisBarre(definition.actions[cle], (nom, repli) => page(nom, repli))) return
        if (defaut) defaut()
    }
    function clic(bouton, gauche, droit, milieu, retour, avance) {
        if (bouton === Qt.LeftButton) agir("left", gauche)
        else if (bouton === Qt.RightButton) agir("right", droit)
        else if (bouton === Qt.MiddleButton) agir("middle", milieu || (() => Quickshell.execDetached(["noctalia", "msg", "settings-toggle"])))
        else if (bouton === Qt.BackButton) agir("back", retour)
        else if (bouton === Qt.ForwardButton) agir("forward", avance)
    }
    function molette(delta, defaut, horizontal = false) {
        if (!delta) return false
        const cle = horizontal ? (delta > 0 ? "scroll_right" : "scroll_left") : (delta > 0 ? "scroll_up" : "scroll_down")
        if (!defaut && !aAction(cle)) return false
        const instant = Date.now()
        if (cle !== dernierSensMolette || instant - instantMolette > 180) {
            resteMolette = 0
            gesteTraite = false
        }
        instantMolette = instant
        dernierSensMolette = cle
        resteMolette += Math.abs(delta)
        const pas = Math.trunc(resteMolette / 120)
        if (pas === 0) return true
        resteMolette %= 120
        const action = aAction(cle) ? definition.actions[cle] : ""
        const repetition = definition.scroll_repeat === "steps" || definition.scroll_repeat !== "gesture"
            && (action ? /^(ipc\s+)?(volume-|mic-volume-|brightness-)/.test(action) : type === "volume" || type === "brightness")
        if (repetition || !gesteTraite) {
            for (let i = 0; i < (repetition ? pas : 1); ++i)
                agir(cle, defaut ? () => defaut(delta > 0 ? 1 : -1) : null)
            gesteTraite = true
        }
        return true
    }
    function page(nom, repli) {
        const cible = repli ? Etat.pageOu(nom, repli) : nom
        const sortie = ecran ? ecran.name : ""
        if (Etat.estPageControle(cible)) {
            Etat.basculerControle(sortie, cible, position, Etat.ancreControle(racine, origine))
            return true
        }
        if (Etat.vues.indexOf(cible) >= 0) {
            if (Etat.ecranOuvert === sortie && !Etat.recherche && Etat.vueActive === cible) { Etat.fermer(); return true }
            if (Etat.ecranOuvert !== sortie) Etat.basculer(sortie, false)
            Etat.aller(cible)
            return true
        }
        return false
    }
    function ipc(commande) { Quickshell.execDetached(["qs", "-c", "nc-ile", "ipc", "call", "ile", commande]) }
    function teinte(nom, repli) {
        if (resoudreTeinte && nom) return resoudreTeinte(nom, repli)
        switch (nom) {
        case "primary": return Couleurs.accent
        case "on_primary": return Couleurs.surAccent
        case "secondary": return Couleurs.texteDoux
        case "tertiary": return Couleurs.violet
        case "outline": return Couleurs.texteSec
        case "error": return Couleurs.rouge
        case "surface": return Couleurs.carte
        case "on_surface": return premierPlan
        case "on_surface_variant": return Couleurs.texteSec
        default: return typeof nom === "string" && /^#[0-9a-f]{6}$/i.test(nom) ? nom : repli
        }
    }

    Loader {
        id: chargeur
        anchors.centerIn: parent
        sourceComponent: {
            switch (racine.type) {
            case "workspaces": return bureaux
            case "active_window": case "nc/fenetres:titre": return titre
            case "taskbar": case "dock": return taches
            case "tray": return tray
            case "sysmon": return sysmon
            case "battery": case "nc/batterie:batterie": return batterie
            case "media": return media
            case "clock": case "date": return heure
            case "nc/vpn:vpn": case "vpn": case "nc/garmin:garmin": case "garmin": case "nc/tour:tour": case "tour": return plugins
            case "volume": case "network": case "bluetooth": case "power_profile": case "brightness":
            case "notifications": case "keyboard_layout": case "caffeine": case "nightlight": case "privacy": return etats
            case "control-center": case "logo": case "launcher": case "app-launcher": case "session":
            case "text": case "spacer": case "custom_button": return boutons
            default: return null
            }
        }
        active: racine.definition.enabled !== false
    }
    Component { id: bureaux; WidgetBarreBureaux { barre: racine } }
    Component { id: titre; WidgetBarreTitre { barre: racine } }
    Component { id: taches; WidgetBarreTaches { barre: racine } }
    Component { id: tray; WidgetBarreTray { barre: racine } }
    Component { id: sysmon; WidgetBarreSysmon { barre: racine } }
    Component { id: batterie; WidgetBarreBatterie { barre: racine } }
    Component { id: media; WidgetBarreMedia { barre: racine } }
    Component { id: heure; WidgetBarreHorloge { barre: racine } }
    Component { id: plugins; WidgetBarrePlugins { barre: racine } }
    Component { id: etats; WidgetBarreStatus { barre: racine } }
    Component { id: boutons; WidgetBarreBouton { barre: racine } }
}
