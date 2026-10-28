pragma Singleton
// Commande longue dans le terminal (activité en direct) : une commande zsh qui dure plus de 10 s (compilation, copie,
// mise à jour…) s'affiche dans la pilule (le nom du programme et sa durée) et dans la page Terminal ; à la fin,
// « Terminée » ou « Échec » avec sa durée, et un clic ramène au terminal.
// Source : ~/.config/nc/terminal.zsh (chargé par ~/.zshrc) écrit deux fichiers dans le dossier privé de la session,
// avec les commandes internes de zsh seulement (aucun processus lancé) :
//   XDG_RUNTIME_DIR/nc-terminal        pendant une commande : pid du terminal, début (s), pid du shell, programme
//   XDG_RUNTIME_DIR/nc-terminal-fini   après une commande de 10 s ou plus : code, durée (s), fin (s), pid du terminal, programme
// Vie privée : terminal.zsh n'écrit que le NOM du programme (make, cargo, rsync…), jamais ses arguments ; ici il
// s'affiche en texte brut (Texte.qml) et ne part jamais dans une commande : seul le pid (un entier vérifié) sert à
// retrouver la fenêtre du terminal (hl.dsp.focus de Hyprland). Pendant un partage d'écran (Partage.silence, comme les
// aperçus du presse-papiers), le nom est remplacé par « Commande ». Sans XDG_RUNTIME_DIR (repli /tmp, lisible par
// tous) : rien.
// L'île surveille les fichiers (FileView, comme nc-video et nc-mode-jeu) : aucun sondage. Le shell disparu en pleine
// commande (terminal fermé) : le fichier est vérifié (kill -0 du shell, un seul processus) seulement sur un événement,
// à la relecture, au réveil de l'écran et à l'ouverture de la page ; jamais en boucle.
// Le pid du terminal est le parent du shell ($PPID) : juste quand le terminal lance zsh lui-même (kitty, foot,
// alacritty…) ; sous tmux, ou dans une instance unique de kitty à plusieurs fenêtres, la fenêtre ramenée peut être
// une autre, ou aucune (hyprctl ne trouve rien : rien ne se passe).
// Réglage ILE_TERMINAL (nc-reglages → Île) : non = rien de tout ça.
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: t

    readonly property bool reglage: Reglages.val("ILE_TERMINAL", "oui") !== "non" && (Quickshell.env("XDG_RUNTIME_DIR") || "") !== ""
    // Partage d'écran en cours : le nom du programme ne s'affiche pas devant tout le monde
    readonly property bool masque: Partage.silence
    readonly property string generique: Reglages.t("Commande", "Command")
    property int delai: 10000               // ms avant de parler de commande longue (même seuil que terminal.zsh)
    property string commande: ""            // le programme en cours (fichier présent)
    readonly property string commandeAffichee: masque ? generique : commande
    readonly property string finiAffichee: fini === null ? "" : (masque ? generique : fini.commande)
    property int pid: 0                     // pid du terminal (fenêtre à ramener)
    property int pidShell: 0
    property real debut: 0                  // s
    property bool enCours: false            // depuis plus de `delai`
    readonly property int duree: enCours ? Math.max(0, Math.floor(Etat.maintenant.getTime() / 1000 - debut)) : 0
    readonly property string dureeTexte: Etat.duree(duree)
    property var fini: null                 // { code, duree, commande, pid } de la dernière commande longue finie
    property string finiTexte: ""

    FileView {
        id: fichier
        path: Etat.dossierSession + "/nc-terminal"; watchChanges: true; printErrors: false
        onFileChanged: reload()
        onLoaded: t.lireEnCours(text())
        onLoadFailed: t.arreter()
    }
    FileView {
        path: Etat.dossierSession + "/nc-terminal-fini"; watchChanges: true; printErrors: false
        onFileChanged: reload()
        onLoaded: t.lireFini(text())
    }
    function entier(x) { var n = parseInt(x); return isNaN(n) || n < 0 ? 0 : n }
    function lireEnCours(texte) {
        var l = texte.split("\n")
        var p = entier(l[0]), d = parseFloat(l[1]) || 0, s = entier(l[2]), c = (l[3] || "").trim()
        if (!reglage || c === "" || d <= 0) { arreter(); return }
        pid = p; debut = d; pidShell = s; commande = c
        var age = Date.now() - d * 1000
        if (age >= delai) { enCours = true; verifier() }          // île relancée en pleine commande : vérifiée tout de suite
        else { enCours = false; seuil.interval = Math.max(50, delai - age); seuil.restart() }
    }
    function arreter() { seuil.stop(); enCours = false; commande = ""; pid = 0; pidShell = 0; debut = 0 }
    Timer { id: seuil; onTriggered: if (t.reglage && t.commande !== "") t.enCours = true }
    function lireFini(texte) {
        if (!reglage || texte === finiTexte) return
        finiTexte = texte
        var l = texte.split("\n"), c = (l[4] || "").trim()
        if (c === "") return
        fini = { code: entier(l[0]), duree: entier(l[1]), pid: entier(l[3]), commande: c }
        Etat.activite("terminal-fini", 4500)
    }
    onReglageChanged: if (!reglage) arreter()

    // Le shell est-il encore là ? (terminal fermé en pleine commande : le fichier resterait) Sur événement seulement.
    Process {
        id: vivant
        command: ["sh", "-c", "kill -0 \"$1\" 2>/dev/null", "sh", String(t.pidShell)]
        onExited: code => { if (code !== 0 && t.enCours) t.arreter() }
    }
    function verifier() { if (enCours && pidShell > 0 && !vivant.running) vivant.running = true }
    Connections { target: Etat; function onEcranVuChanged() { if (Etat.ecranVu) t.verifier() } }

    // Ramener la fenêtre du terminal (pid entier seulement, jamais la commande)
    function aller(p) {
        var n = entier(p !== undefined ? p : pid)
        if (n > 0) Quickshell.execDetached(["hyprctl", "dispatch", "hl.dsp.focus({ window = 'pid:" + n + "' })"])
        Etat.fermer()
    }
}
