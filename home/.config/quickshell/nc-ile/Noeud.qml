pragma Singleton
// JARVIS qui pilote ce PC (nc-noeud, issue #12) : une action qui demande ta confirmation (commande, fichier, capture,
// presse-papiers) arrive dans …/nc-noeud/demande.json (XDG_RUNTIME_DIR, 0700) ; nc-noeud prévient l'île par
// « qs -c nc-ile ipc call ile noeud » (shell.qml), qui relit le fichier. La carte (ConfirmationNoeud.qml) écrit
// « autoriser » ou « refuser » dans …/nc-noeud/reponses/ID, que nc-noeud attend. Sans réponse à l'échéance de cette
// action (« expire », 3 à 17 s selon l'action, toujours avant que le serveur abandonne), la carte se ferme et nc-noeud
// refuse. Un « Autoriser » qui arrive trop tard n'est pas envoyé : la carte dit « Trop tard » et rien n'est fait.
// Rien n'est relu en boucle : la minuterie ne tourne que pendant une demande.
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
    property bool tropTard: false                     // « Autoriser » après l'échéance : rien n'est envoyé, la carte le dit
    readonly property real marge: 0.5                 // nc-noeud relit la réponse toutes les 0,15 s : un clic au ras de
                                                      // l'échéance compte déjà comme trop tard

    // Session de confiance (issue #21) : nc-noeud écrit son état dans …/nc-noeud/session.json (ouverte, expire,
    // reste_s, reste_actions, origine). L'île l'affiche et propose « Arrêter la session », qui écrit …/nc-noeud/
    // session-stop ; nc-noeud le relit avant chaque action et ferme la session. Rien n'est relu en boucle.
    property var session: null                        // { expire, reste_s, reste_actions, minutes, origine, serveur }
    readonly property bool sessionActive: session !== null
                && Number(session.expire) > Date.now() / 1000 && Number(session.reste_actions) > 0
    readonly property int sessionReste: session ? Math.max(0, Math.ceil(Number(session.expire) - maintenant)) : 0
    function arreterSession() {
        session = null
        Quickshell.execDetached(["sh", "-c",
            "mkdir -p \"$1\" && : > \"$1/session-stop\"", "sh", dossier])
    }
    function lireSession(t) {
        var d = null
        try { d = JSON.parse(t) } catch (e) { d = null }
        session = (d && Number(d.expire) > Date.now() / 1000 && Number(d.reste_actions) > 0) ? d : null
    }

    function relire() { fichier.reload() }
    function lire(t) {
        if (tropTard) return                          // le message reste affiché ; relu à la fin (finTropTard)
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
        if (!demande || tropTard) return
        var id = demande.id
        repondue = id
        if (choix === "autoriser" && Date.now() / 1000 >= Number(demande.expire) - marge) {
            // JARVIS a déjà abandonné : rien n'est écrit, nc-noeud a refusé (une seule réponse au serveur)
            tropTard = true
            finTropTard.restart()
            return
        }
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
    // L'état de la session de confiance, suivi en continu (créé et effacé par nc-noeud)
    FileView {
        id: fichierSession
        path: n.dossier + "/session.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: n.lireSession(text())
        onLoadFailed: n.lireSession("")
    }
    // Compte à rebours de la session (seulement quand elle est affichée)
    Timer {
        interval: 1000; repeat: true; running: n.sessionActive
        onTriggered: { n.maintenant = Date.now() / 1000; if (n.sessionReste <= 0) n.session = null }
    }
    // Compte à rebours de la carte, seulement pendant une demande
    Timer {
        interval: 1000; repeat: true; running: n.demande !== null && !n.tropTard
        onTriggered: { n.maintenant = Date.now() / 1000; if (n.reste <= 0) n.demande = null }
    }
    // « Trop tard » se lit 2,5 s, puis la carte se ferme (ou montre la demande suivante)
    Timer {
        id: finTropTard
        interval: 2500
        onTriggered: { n.tropTard = false; n.demande = null; fichier.reload() }
    }
}
