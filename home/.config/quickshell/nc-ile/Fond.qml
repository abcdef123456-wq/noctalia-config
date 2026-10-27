// Fond d'écran animé (nc-reglages → Fonds d'écran → FOND_ANIME) : une couche par-dessus le fond d'écran choisi (jamais
// à sa place), sous les fenêtres, sur chaque écran, sans jamais prendre la souris. Rien à installer.
//   aurore : trois grandes lueurs aux couleurs du thème dérivent lentement (Lueurs.qml).
//   vivant : l'aurore prend la teinte de l'heure (nuit, aube, jour, crépuscule), pulse sur les basses de la musique
//            (le niveau que nc-pouls écrit dans XDG_RUNTIME_DIR/nc-pouls-niveau : pas de second cava) et suit la météo
//            de l'île (pluie, neige, brouillard).
// Économe : 15 images par seconde au plus, et rien de calculé (compteur arrêté, fichier du pouls plus surveillé) dès
// qu'une fenêtre est ouverte sur le bureau affiché (plein écran compris : le fond est caché), écran éteint ou session
// verrouillée, sur batterie (sauf FOND_ANIME_BATTERIE=oui), en mode Économie et en mode jeu.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import Quickshell.Services.UPower

PanelWindow {
    id: f
    required property var modelData
    property bool vivant: false
    screen: modelData
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Bottom
    WlrLayershell.namespace: "nc-fond"
    color: "transparent"
    mask: Region {}                                         // ne prend jamais la souris

    readonly property var moniteur: Hyprland.monitorFor(modelData)
    readonly property bool bureauVide: !moniteur || !moniteur.activeWorkspace
                                       || moniteur.activeWorkspace.toplevels.values.length === 0
    readonly property bool economie: PowerProfiles.profile === PowerProfile.PowerSaver
    readonly property bool batterieOk: !UPower.onBattery || Reglages.val("FOND_ANIME_BATTERIE", "non") === "oui"
    readonly property bool anime: Etat.ecranVu && bureauVide && batterieOk && !economie && !Etat.jeu

    // Le seul compteur du fond : tout ce qui bouge (lueurs, pouls, gouttes) ne dépend que de lui
    property real t: 0
    property real pouls: 0           // niveau des basses lissé, mis à jour au tic seulement (jamais à la cadence du fichier)
    property real niveau: 0          // dernier niveau lu de nc-pouls
    Timer {
        interval: 66; repeat: true; running: f.anime
        onTriggered: {
            f.t += 0.066
            if (f.vivant) {
                var n = f.surveille ? f.niveau : 0
                f.pouls = n > f.pouls ? n : f.pouls * 0.8 + n * 0.2        // montée immédiate, retombée douce
            }
        }
    }

    // Heure : relue à la reprise du fond, puis chaque minute tant qu'il tourne (rien en pause)
    property real heure: 12
    function majHeure() { var d = new Date(); heure = d.getHours() + d.getMinutes() / 60 }
    onAnimeChanged: if (anime) majHeure()
    Component.onCompleted: majHeure()
    Timer { interval: 60000; repeat: true; running: f.anime && f.vivant; onTriggered: f.majHeure() }

    // Météo déjà lue par l'île (nc-meteo, Etat.meteo) : rien de plus à demander
    readonly property int meteoCode: vivant && Etat.meteo.code !== undefined ? Etat.meteo.code : -1

    // Niveau des basses de nc-pouls (écrit en place, surveillé sans sondage) : seulement en mode vivant, fond actif et
    // musique en cours ; sinon le fichier n'est pas surveillé et le pouls retombe à zéro. Sans nc-pouls ni cava : pas de
    // fichier, le fond respire sans pulser. watchChanges est une propriété C++ évaluée à la demande : la surveillance
    // est pilotée par une propriété QML ordinaire, et relue ici pour que l'arrêt soit effectif tout de suite.
    readonly property bool surveille: vivant && anime && Etat.joue
    onSurveilleChanged: { void fichierPouls.watchChanges; if (surveille) fichierPouls.reload(); else niveau = 0 }
    FileView {
        id: fichierPouls
        path: Etat.dossierSession + "/nc-pouls-niveau"
        watchChanges: f.surveille
        printErrors: false
        onFileChanged: reload()
        onLoaded: f.niveau = f.surveille ? Math.max(0, Math.min(1, parseFloat(text()) || 0)) : 0    // (re)lu aussi quand la surveillance change
        onLoadFailed: f.niveau = 0
    }

    Lueurs {
        anchors.fill: parent
        t: f.t; anime: f.anime; vivant: f.vivant; heure: f.heure; pouls: f.pouls; meteoCode: f.meteoCode
    }
}
