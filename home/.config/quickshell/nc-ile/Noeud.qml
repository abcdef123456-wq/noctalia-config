pragma Singleton
// JARVIS qui pilote ce PC (nc-noeud, issue #12) : une action qui demande ta confirmation (commande, fichier, capture,
// presse-papiers) arrive dans …/nc-noeud/demande.json (XDG_RUNTIME_DIR, 0700) ; nc-noeud prévient l'île par
// « qs -c nc-ile ipc call ile noeud » (shell.qml), qui relit le fichier. La carte (ConfirmationNoeud.qml) écrit
// « autoriser » ou « refuser » dans …/nc-noeud/reponses/ID, que nc-noeud attend. Sans réponse à l'heure dite (25 s),
// la carte se ferme et nc-noeud refuse. Rien n'est relu en boucle : la minuterie ne tourne que pendant une demande.
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: n
    readonly property string dossier: (Quickshell.env("XDG_RUNTIME_DIR") || "/tmp") + "/nc-noeud"
    property var demande: null                        // { id, serveur, action, resume, texte, court, expire }
    property real maintenant: Date.now() / 1000
    readonly property int reste: demande ? Math.max(0, Math.ceil(demande.expire - maintenant)) : 0
    property bool toutVoir: false                     // « Voir tout » : le texte entier, pas seulement le début
    property string repondue: ""                      // la carte déjà répondue ne revient pas avant que le fichier parte

    function relire() { fichier.reload() }
    function lire(t) {
        var d = null
        try { d = JSON.parse(t) } catch (e) { d = null }
        if (d && (typeof d.id !== "string" || !/^[0-9a-f]{32}$/.test(d.id) || d.id === repondue
                  || !(Number(d.expire) > Date.now() / 1000)))
            d = null
        var nouvelle = d !== null && (!demande || d.id !== demande.id)
        if (!d || nouvelle) toutVoir = false
        maintenant = Date.now() / 1000
        demande = d
        // La carte ne s'affiche que sur l'île fermée : une page ouverte se referme (pas le Spotlight en pleine saisie)
        if (nouvelle && Etat.ecranOuvert !== "" && !Etat.recherche) Etat.fermer()
    }
    function repondre(choix) {
        if (!demande) return
        var id = demande.id
        repondue = id
        demande = null
        // Écrite d'un coup (fichier caché puis renommé) : nc-noeud ne lit jamais une réponse à moitié écrite
        Quickshell.execDetached(["sh", "-c", "mkdir -p \"$1\" && printf %s \"$2\" > \"$1/.$3\" && mv -f \"$1/.$3\" \"$1/$3\"",
                                 "sh", dossier + "/reponses", choix, id])
    }
    function autoriser() { repondre("autoriser") }
    function refuser() { repondre("refuser") }

    FileView {
        id: fichier
        path: n.dossier + "/demande.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: n.lire(text())
        onLoadFailed: n.lire("")
    }
    // Compte à rebours de la carte, seulement pendant une demande
    Timer {
        interval: 1000; repeat: true; running: n.demande !== null
        onTriggered: { n.maintenant = Date.now() / 1000; if (n.reste <= 0) n.demande = null }
    }
}
