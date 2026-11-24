pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: g
    readonly property string dossier: Quickshell.env("XDG_RUNTIME_DIR") || ""
    property var publication: null
    readonly property bool affiche: dossier !== "" && !GarminEtat.masque && publication !== null && publication.actif === true
    readonly property var niveau: affiche && publication.metriques ? publication.metriques.body_battery : undefined
    // Laisser le connecteur écrire le fichier partagé ; la barre ne déclenche aucune synchronisation distante.
    Component.onCompleted: GarminEtat.relire()
    FileView {
        path: g.dossier ? g.dossier + "/nc-garmin-barre.json" : ""
        watchChanges: true; printErrors: false
        onFileChanged: reload()
        onLoaded: { try { g.publication = JSON.parse(text()) } catch (e) { g.publication = null } }
        onLoadFailed: g.publication = null
    }
}
