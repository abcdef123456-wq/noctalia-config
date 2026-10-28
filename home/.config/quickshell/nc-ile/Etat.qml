pragma Singleton
// Île dynamique (Quickshell) : état partagé par toutes les îles (une par écran).
// Musique (MPRIS), son (PipeWire), batterie et profils (UPower) : lus en direct ; Wi-Fi, Bluetooth, ne pas déranger,
// luminosité… : lus par ~/.local/bin/nc-ile-etat quand l'île est ouverte. Réactions (« activités ») : la pilule
// s'étire quelques secondes pour montrer un changement, comme sur iPhone.

import QtQuick
import QtQml
import Quickshell
import Quickshell.Io
import Quickshell.Services.Mpris
import Quickshell.Services.Pipewire
import Quickshell.Services.UPower

Singleton {
    id: etat

    readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"

    // ── Île ouverte (nom de l'écran, "" = fermée) et pages ──
    // Comme sur iPhone : d'abord les activités en cours (musique, minuteur, recharge, mode jeu), puis le centre de
    // contrôle et ses pages de détails ; on descend de l'une à l'autre (points sur le bord droit).
    property string ecranOuvert: ""
    // Lanceur qui sort de la pilule (ILE_LANCEUR_FONDU, LanceurFondu.qml) : chaque île inscrit sa pilule (objet, jamais un
    // état qui bouge) ; pendant l'animation, « lanceurFondu » = écran dont la pilule est cachée, « lanceurProprio » = le lanceur
    property var pilules: ({})
    property string lanceurFondu: ""
    property var lanceurProprio: null
    function enregistrerPilule(nom, pilule) { pilules[nom] = pilule }
    function oublierPilule(nom, pilule) { if (pilules[nom] === pilule) delete pilules[nom] }
    // Musique au premier plan pendant la lecture, et encore 15 min après une pause (comme l'iPhone)
    readonly property bool aMusique: lecteur !== null && titre !== ""
                                     && (joue || (lecteur === dernierLecteur && finLecture > 0
                                                  && maintenant.getTime() - finLecture < 15 * 60000))
    readonly property var activites: {
        var a = []
        if (Appel.enCours) a.push("appel")                                 // appel en cours (Appel.qml)
        if (aMusique) a.push("musique")
        if (Agents.aPage || Agents.demande !== null) a.push("claude")      // Claude Code (nc-claude)
        if (minuteurFin > 0) a.push("minuteur")
        if (enCharge) a.push("charge")
        if (jeu) a.push("jeu")
        if (Terminal.enCours) a.push("terminal")                           // commande longue dans le terminal (Terminal.qml)
        if (Resume.actif) a.push("resume")                                 // « Bonjour » au réveil (Resume.qml)
        return a
    }
    // Page Batterie (Charge.qml) juste après le centre, seulement sur un PC qui a une batterie ; pendant une recharge,
    // elle est déjà en tête parmi les activités : jamais deux fois
    // Page Santé (Sante.qml) après Système, seulement si la machine a des capteurs (températures, ventilateurs : vu une
    // fois au démarrage par Chaleur.qml, nc-ile-etat capteurs) ; machine virtuelle ou tour sans capteur : pas de page
    property bool capteursSante: false
    readonly property var vues: Reglages.filtrerPages(activites.concat(["centre"],
                                                 batteriePc && activites.indexOf("charge") < 0 ? ["charge"] : [],
                                                 ["assistant", "notifications"], Modes.pagePossible ? ["concentration"] : [],
                                                 ["son", "reseau", "bluetooth", "systeme"], capteursSante ? ["sante"] : [], ["calendrier"],
                                                 (meteo.temp !== undefined || meteoErreur !== "") ? ["meteo"] : [], ["presse", "fenetres"],
                                                 minuteurFin > 0 ? [] : ["minuteur"]))
    property string vueNom: "centre"
    readonly property int vue: Math.max(0, vues.indexOf(vueNom))
    readonly property string vueActive: vues[vue] || ""
    onVuesChanged: {
        if (vues.indexOf(vueNom) < 0) {
            vueNom = vues[0] || ""
            if (ecranOuvert !== "" && !recherche) {
                if (!vues.length) fermer()
                else Qt.callLater(lirePage)
            }
        }
    }
    // Hauteur du contenu annoncée par les pages à liste (Son, Wi-Fi, Bluetooth) : l'île s'y ajuste
    property var hauteurs: ({})
    function annoncerHauteur(nom, h) {
        if (hauteurs[nom] === Math.round(h)) return
        var t = Object.assign({}, hauteurs); t[nom] = Math.round(h); hauteurs = t
    }
    function changerVue(d) { aller(vues[Math.max(0, Math.min(vues.length - 1, vue + d))]) }
    // La page voulue si elle est affichable, sinon le repli (clic sur la batterie de la barre : Batterie, sinon Système)
    function pageOu(nom, repli) { return vues.indexOf(nom) >= 0 ? nom : repli }
    function aller(nom) {
        if (vues.indexOf(nom) < 0) return
        recherche = false
        vueNom = nom
        lirePage()
    }

    // versCentre : ouvrir directement sur le centre de contrôle (Super + C) plutôt que sur ce qui se passe (clic)
    // Ouverte en passant le curseur dessus (Ile.qml) : se referme quand il en sort, tant qu'on n'a pas cliqué dedans
    property bool parSurvol: false
    function basculer(ecran, versCentre) {
        parSurvol = false
        if (ecranOuvert === ecran) { fermer(); return }
        if (!vues.length) return
        recherche = false
        var disponibles = Reglages.filtrerPages(activites)
        vueNom = versCentre || disponibles.length === 0 ? (vues.indexOf("centre") >= 0 ? "centre" : vues[0]) : disponibles[0]
        ecranOuvert = ecran
        activiteType = ""
        lire()
        lireLuminosite(false)
        lirePage()
    }
    function fermer() { ecranOuvert = ""; recherche = false; parSurvol = false }

    // Spotlight (Super + R) : l'île s'ouvre en longue capsule de recherche
    property bool recherche: false
    property bool vueFenetres: false       // vue de toutes les fenêtres (Vue.qml)
    property bool vuePause: false          // la vue lâche clavier et souris (nc-capture : choix d'une zone)
    // Les ItemGrabResult sont gardés avec leur URL : l'image survit à la destruction de Vue.qml, sans fichier disque.
    // Au plus 12 images et 8 millions de pixels (~32 Mio RGBA), libérés avec le processus de l'île.
    property var vueImages: ({})
    property var vueCaptures: ({})
    property var vueLots: []
    readonly property bool vueMasquageEnCours: vueLots.length > 0
    function masquerVue(lot) {
        vueLots = vueLots.concat([lot])
        executerMasquageVue()
    }
    function executerMasquageVue() {
        if (masquageVue.running || vueLots.length === 0) return
        masquageVue.command = [bin + "nc-fenetre", "reduire-lot", JSON.stringify(vueLots[0])]
        masquageVue.running = true
    }
    Process {
        id: masquageVue
        onExited: code => {
            if (code !== 0) {
                console.warn("nc-fenetre: échec d'un lot de masquages (" + code + ")")
                Quickshell.execDetached(["notify-send", "-a", Reglages.t("Fenêtres", "Windows"),
                    Reglages.t("Certaines fenêtres n'ont pas pu être masquées.", "Some windows couldn't be hidden.")])
            }
            etat.vueLots = etat.vueLots.slice(1)
            Qt.callLater(etat.executerMasquageVue)
        }
    }
    function conserverVueImage(adresse, resultat, pixels) {
        var images = Object.assign({}, vueImages)
        delete images[adresse]
        images[adresse] = { resultat: resultat, url: resultat.url, pixels: pixels }
        var cles = Object.keys(images), total = cles.reduce((n, k) => n + images[k].pixels, 0)
        while (cles.length > 12 || total > 8 * 1024 * 1024) {
            let k = cles.shift(); total -= images[k].pixels; delete images[k]
        }
        vueImages = images
    }
    function captureVue(token, enCours) {
        var c = Object.assign({}, vueCaptures)
        if (enCours) c[token] = true; else delete c[token]
        vueCaptures = c
    }
    property bool projection: false        // fenêtre de projection, comme Windows + P (Projection.qml, Super + O)
    property string saisie: ""           // texte déjà tapé à l'ouverture (commande « rechercher »)
    property string texteIA: ""          // « ! » du Spotlight sur ce texte-là (presse-papiers de l'île), pas la sélection
    property bool agirAuto: false        // « @ » lancé tout de suite à l'ouverture (raccourcis « Organiser les fenêtres »)
    property string agirPortee: ""       // son bureau seulement (Super + Ctrl + O) : nc-ia agir --bureau N
    signal validerRecherche()            // comme Entrée dans le Spotlight (commande « valider »)
    function chercher(ecran) {
        if (ecranOuvert === ecran && recherche) { fermer(); return }
        recherche = true
        ecranOuvert = ecran
        activiteType = ""
    }

    // ── Minuteur (activité en direct, décompte dans la pilule) ──
    property real minuteurFin: 0
    property real minuteurDuree: 0
    readonly property int minuteurReste: minuteurFin > 0 ? Math.max(0, Math.ceil((minuteurFin - maintenant.getTime()) / 1000)) : 0
    function lancerMinuteur(minutes) {
        minuteurDuree = minutes * 60000
        minuteurFin = Date.now() + minuteurDuree
        vueNom = "minuteur"
    }
    function ajouterMinute() { if (minuteurFin > 0) { minuteurFin += 60000; minuteurDuree += 60000 } }
    function arreterMinuteur() {
        minuteurFin = 0; if (vueNom === "minuteur") vueNom = "centre"
        if (pomodoro) { pomodoro = false; concentrationPomodoro(false) }
    }
    // Pomodoro : 25 min de travail (Ne pas déranger), 5 min de pause, 15 toutes les 4 séances ; enchaîne tout seul
    property bool pomodoro: false
    property bool pomoPause: false
    property int pomoSeance: 1
    property bool dndAvantPomo: false
    function concentrationPomodoro(actif) {
        if (Reglages.val("POMODORO_CONCENTRATION", "oui") === "non") return
        if (actif) { dndAvantPomo = Notifs.concentration; Notifs.concentration = true }
        else Notifs.concentration = dndAvantPomo
    }
    function lancerPomodoro() {
        pomodoro = true; pomoPause = false; pomoSeance = 1
        concentrationPomodoro(true)
        lancerMinuteur(25)
    }
    function etapePomodoro() {
        var msg
        if (!pomoPause) {
            pomoPause = true
            concentrationPomodoro(false)
            let longue = pomoSeance % 4 === 0
            msg = [Reglages.t("Pause !", "Break!"), longue ? Reglages.t("15 minutes : lève-toi, bouge un peu.", "15 minutes: stand up and move around.")
                                                          : Reglages.t("5 minutes pour souffler.", "5 minutes to catch your breath.")]
            lancerMinuteur(longue ? 15 : 5)
        } else {
            pomoPause = false; pomoSeance++
            concentrationPomodoro(true)
            msg = [Reglages.t("Au travail", "Back to work"), Reglages.t("Séance " + pomoSeance + " : 25 minutes de concentration.",
                                                                      "Session " + pomoSeance + ": 25 minutes of focus.")]
            lancerMinuteur(25)
        }
        Quickshell.execDetached(["sh", "-c", "notify-send -a Pomodoro \"$1\" \"$2\"", "sh", msg[0], msg[1]])
        jouerSon("complete")
    }
    // Son du thème freedesktop : canberra-gtk-play s'il est là, sinon pw-play sur le fichier du thème (paquet
    // sound-theme-freedesktop). Rien si ni l'un ni l'autre, sans message.
    function jouerSon(nom) {
        Quickshell.execDetached(["sh", "-c", "f=/usr/share/sounds/freedesktop/stereo/\"$1\".oga; "
            + "{ command -v canberra-gtk-play >/dev/null 2>&1 && canberra-gtk-play -i \"$1\"; } 2>/dev/null "
            + "|| { command -v pw-play >/dev/null 2>&1 && [ -r \"$f\" ] && pw-play \"$f\"; } 2>/dev/null; true", "sh", nom])
    }
    onMinuteurResteChanged: {
        if (minuteurFin > 0 && minuteurReste === 0 && pomodoro) {
            minuteurFin = 0
            etapePomodoro()
        } else if (minuteurFin > 0 && minuteurReste === 0) {
            minuteurFin = 0
            jouerSon("alarm-clock-elapsed")
            Quickshell.execDetached(["sh", "-c", "notify-send -a \"$1\" -u critical \"$2\" \"$3\"", "sh",
                Reglages.t("Minuteur", "Timer"), Reglages.t("Minuteur terminé", "Timer Done"), Reglages.t("Le temps est écoulé.", "Time's up.")])
            activite("minuteur-fini", 5000)
        }
    }
    function duree(s) {
        var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60
        return (h > 0 ? h + ":" + String(m).padStart(2, "0") : String(m)) + ":" + String(x).padStart(2, "0")
    }

    // ── Météo (nc-meteo : Open-Meteo, gardée 20 min en cache) : pilule au repos et page Météo ──
    property var meteo: ({})
    property string meteoErreur: ""
    readonly property bool meteoPilule: Reglages.val("ILE_METEO", "oui") !== "non" && meteo.temp !== undefined
    Process {
        id: lireMeteo
        command: [etat.bin + "nc-meteo"]
        stdout: StdioCollector { onStreamFinished: { try {
            let m = JSON.parse(text)
            if (m.temp !== undefined) { etat.meteo = m; etat.meteoErreur = "" }
            else if (m.erreur === "ville introuvable") { etat.meteo = ({}); etat.meteoErreur = m.erreur }   // la météo d'une autre ville serait fausse
        } catch (e) {} } }
    }
    // Toutes les 10 min ; toutes les 30 min sur batterie (moins de réveils et de réseau, la météo change peu)
    Timer { interval: (UPower.onBattery ? 30 : 10) * 60000; repeat: true; running: etat.ecranVu && Reglages.val("ILE_METEO", "oui") !== "non"     // écran éteint : suspendu, un rafraîchissement dès le réveil
            triggeredOnStart: true; onTriggered: if (!lireMeteo.running) lireMeteo.running = true }
    Connections { target: Reglages; function onValeursChanged() { if (!lireMeteo.running) lireMeteo.running = true } }

    // ── Presse-papiers : voir PressePapiers.qml (gardé d'une session à l'autre, épinglés, limites) ──
    readonly property var presse: PressePapiers.liste
    function recopier(e) { PressePapiers.recopier(e) }
    function oublierPresse() { PressePapiers.toutEffacer() }

    // ── Enregistrement d'écran (nc-video) : point rouge et durée dans la pilule ; un clic dessus l'arrête ──
    // Le fichier d'état de nc-video (XDG_RUNTIME_DIR/nc-video : pid, début) est surveillé : plus de sondage chaque
    // seconde ; à chaque changement, lireVideo vérifie que l'enregistreur tourne encore, et toutes les 15 s pendant un
    // enregistrement au cas où il aurait planté
    property real debutVideo: 0
    readonly property bool enregistre: debutVideo > 0
    readonly property string dossierSession: Quickshell.env("XDG_RUNTIME_DIR") || "/tmp"
    FileView {
        path: etat.dossierSession + "/nc-video"; watchChanges: true; printErrors: false
        onFileChanged: reload()
        onLoaded: if (!lireVideo.running) lireVideo.running = true
        onLoadFailed: etat.debutVideo = 0
    }

    // ── Téléchargements du navigateur (fichiers .part de Firefox, .crdownload des Chrome) : taille, vitesse, fin ──
    property var telechargements: []          // { nom, taille, vitesse } (octets, octets/s)
    property string telechargeFini: ""
    property string dossierTel: ""            // le dossier Téléchargements (vu par le relevé) : un clic sur « téléchargé » l'ouvre
    property var tailles: ({})
    readonly property string sansNom: Reglages.t("Téléchargement", "Download")    // fichier Chrome pas encore nommé
    readonly property bool telecharge: telechargements.length > 0 && Reglages.val("ILE_TELECHARGEMENTS", "oui") !== "non"
    Process {
        id: lecteurTel
        command: ["sh", "-c", "d=$(xdg-user-dir DOWNLOAD 2>/dev/null); [ -d \"$d\" ] || d=$HOME/Downloads; "
                  + "find \"$d\" -maxdepth 1 -type f \\( -name '*.part' -o -name '*.crdownload' -o -name '*.tmp' \\) -printf '%s\\t%f\\n' 2>/dev/null; echo \"#$d\""]
        stdout: StdioCollector {
            onStreamFinished: {
                var l = [], vu = {}, dossier = ""
                text.split("\n").forEach(x => {
                    if (x.startsWith("#")) { dossier = x.slice(1); return }
                    var p = x.split("\t")
                    if (p.length < 2) return
                    var nom = p[1].replace(/\.(part|crdownload|tmp)$/, "").replace(/^Unconfirmed \d+$/, etat.sansNom)
                    var taille = parseInt(p[0]) || 0, avant = etat.tailles[p[1]]
                    vu[p[1]] = { taille: taille, nom: nom }
                    l.push({ nom: nom, taille: taille, vitesse: avant !== undefined ? Math.max(0, (taille - avant.taille) / 2) : 0 })
                })
                // Un fichier temporaire disparu : téléchargement fini (si le vrai fichier est là, pas annulé)
                for (let k in etat.tailles) if (!vu[k] && etat.tailles[k].nom !== etat.sansNom) verifFin.verifier(dossier, etat.tailles[k].nom)
                if (dossier.charAt(0) === "/") etat.dossierTel = dossier
                etat.tailles = vu
                etat.telechargements = l
            }
        }
    }
    Process {
        id: verifFin
        property string nom: ""
        function verifier(dossier, n) { nom = n; command = ["test", "-s", dossier + "/" + n]; running = true }
        onExited: code => { if (code === 0 && Reglages.val("ILE_TELECHARGEMENTS", "oui") !== "non" && !Partage.silence) { etat.telechargeFini = nom; etat.activite("telechargement-fini", 4500) } }
    }
    // Fin d'un téléchargement vue par inotify (inotifywait, du paquet inotify-tools, s'il est installé) : le dossier Téléchargements
    // est surveillé, et le relevé ci-dessus ne se fait qu'à l'apparition ou à la disparition d'un .part, .crdownload ou .tmp. Au
    // repos, plus aucun réveil. Sans inotifywait (ou s'il s'arrête), on revient au relevé régulier plus bas. Suspendu écran éteint
    // ou session verrouillée (relevé dès le réveil), rien du tout si ILE_TELECHARGEMENTS=non.
    property bool surveillance: false
    property bool sansInotify: false
    readonly property bool veilleTelVoulue: ecranVu && Reglages.val("ILE_TELECHARGEMENTS", "oui") !== "non" && !sansInotify
    Process {
        id: veilleTel
        command: ["sh", "-c", "d=$(xdg-user-dir DOWNLOAD 2>/dev/null); [ -d \"$d\" ] || d=$HOME/Downloads; [ -d \"$d\" ] || exit 3; "
                  + "command -v inotifywait >/dev/null 2>&1 || exit 4; "
                  + "exec inotifywait -m -q -e create -e moved_to -e moved_from -e delete -e close_write --format '%f' \"$d\""]
        running: etat.veilleTelVoulue
        onStarted: etat.surveillance = true
        onExited: code => { etat.surveillance = false; if (etat.veilleTelVoulue && code !== 0) etat.sansInotify = true }
        stdout: SplitParser { onRead: nom => { if (/\.(part|crdownload|tmp)$/.test(nom)) relectureTel.restart() } }
    }
    Timer { id: relectureTel; interval: 400; onTriggered: if (!lecteurTel.running) lecteurTel.running = true }
    // Un clic sur « téléchargé » (pilule) : le dossier s'ouvre
    function ouvrirTelechargements() { if (dossierTel.charAt(0) === "/") Quickshell.execDetached(["xdg-open", dossierTel]) }
    // Toutes les 2 s pendant un téléchargement (vitesse) ; sans inotifywait, aussi un find du dossier Téléchargements toutes les 6 s,
    // toutes les 30 s sur batterie (moins de réveils) ; suspendu écran éteint ou session verrouillée, relevé dès le réveil. Pas de
    // FolderListModel : un paquet de plus sous Debian, absent des installations déjà faites, et l'île entière ne se chargerait plus
    Timer { interval: etat.telechargements.length ? 2000 : (UPower.onBattery ? 30000 : 6000); repeat: true; running: etat.ecranVu && Reglages.val("ILE_TELECHARGEMENTS", "oui") !== "non" && (etat.telechargements.length > 0 || !etat.surveillance); triggeredOnStart: true; onTriggered: if (!lecteurTel.running) lecteurTel.running = true }
    function octets(n) {
        if (Reglages.en) return n >= 1e9 ? (n / 1e9).toFixed(1) + " GB" : (n >= 1e6 ? Math.round(n / 1e6) + " MB" : Math.round(n / 1e3) + " kB")
        return n >= 1e9 ? (n / 1e9).toFixed(1).replace(".", ",") + " Go" : (n >= 1e6 ? Math.round(n / 1e6) + " Mo" : Math.round(n / 1e3) + " ko")
    }
    Process {
        id: lireVideo
        command: ["sh", "-c", "if [ -r \"$1\" ]; then . \"$1\"; else nc_pid_notre() { kill -0 \"${1:-0}\" 2>/dev/null; }; fi; f=\"${XDG_RUNTIME_DIR:-/tmp}/nc-video\"; [ -s \"$f\" ] || { echo 0; exit; }; { read -r p; read -r d; read -r _; read -r s; } < \"$f\"; if nc_pid_notre \"$p\" \"$s\" wf-recorder; then echo \"$d\"; else echo 0; fi", "sh", bin + "nc-pid"]
        stdout: StdioCollector { onStreamFinished: etat.debutVideo = parseInt(text) || 0 }
    }
    Timer { interval: 15000; repeat: true; running: etat.enregistre; onTriggered: if (!lireVideo.running) lireVideo.running = true }
    function arreterVideo() { Quickshell.execDetached([bin + "nc-video", "arreter"]); debutVideo = 0 }

    // ── Café : empêche la mise en veille (Noctalia) ──
    property bool cafe: false
    function basculerCafe() { cafe = !cafe; Quickshell.execDetached(["noctalia", "msg", cafe ? "caffeine-enable" : "caffeine-disable"]) }

    // ── Heure ──
    property date maintenant: new Date()
    property date minute: new Date()        // ne change qu'au changement de minute : moins de recalculs (calendrier, notifications)
    // Écran éteint ou session verrouillée : personne ne voit la pilule. nc-ecran note l'extinction dans
    // XDG_RUNTIME_DIR/nc-ecran-eteint et hypridle le verrouillage dans nc-verrouille ; les deux fichiers sont surveillés
    // (comme nc-mode-jeu plus bas), sans processus ni sondage. Relus aussi toutes les 30 s tant que l'un est posé, au
    // cas où la surveillance de Quickshell perdrait le fichier remplacé : l'île ne reste jamais figée.
    property bool ecranEteint: false
    property bool verrouille: false
    readonly property bool ecranVu: !ecranEteint && !verrouille
    FileView {
        id: marqueEteint
        path: etat.dossierSession + "/nc-ecran-eteint"; watchChanges: true; printErrors: false
        onFileChanged: reload()
        onLoaded: etat.ecranEteint = true
        onLoadFailed: etat.ecranEteint = false
    }
    FileView {
        id: marqueVerrou
        path: etat.dossierSession + "/nc-verrouille"; watchChanges: true; printErrors: false
        onFileChanged: reload()
        onLoaded: etat.verrouille = true
        onLoadFailed: etat.verrouille = false
    }
    Timer { interval: 30000; repeat: true; running: !etat.ecranVu; onTriggered: { marqueEteint.reload(); marqueVerrou.reload() } }
    function majHeure() {
        var d = new Date(); maintenant = d
        if (d.getMinutes() !== minute.getMinutes() || d.getHours() !== minute.getHours() || d.getDate() !== minute.getDate()) minute = d
    }
    // La pendule s'arrête quand personne ne voit l'île, et redonne l'heure juste tout de suite au réveil. Le minuteur
    // (et le Pomodoro) garde sa fin en heure absolue (Date.now) mais sa fin est détectée par cette pendule : elle
    // continue tant qu'un minuteur court, pour que la sonnerie et la notification partent à l'heure.
    Timer { interval: 1000; running: etat.ecranVu || etat.minuteurFin > 0; repeat: true; triggeredOnStart: true; onTriggered: etat.majHeure() }
    // En anglais : noms de Reglages.locale (0 = dimanche, comme getDay())
    readonly property var jours: Reglages.en ? [0, 1, 2, 3, 4, 5, 6].map(i => Reglages.locale.dayName(i, Locale.LongFormat))
                                             : ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]
    readonly property var mois: Reglages.en ? [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11].map(i => Reglages.locale.standaloneMonthName(i, Locale.LongFormat))
                                            : ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    // Format réglable (nc-reglages, ILE_HEURE : 24 ou 12)
    readonly property string heure: Reglages.val("ILE_HEURE", "24") === "12" ? Qt.formatTime(maintenant, "h:mm AP")
                                                                            : Qt.formatTime(maintenant, "hh:mm")
    readonly property string dateLongue: Reglages.en ? maintenant.toLocaleDateString(Reglages.locale, "dddd, MMMM d")
                                                     : jours[maintenant.getDay()] + " " + maintenant.getDate() + " " + mois[maintenant.getMonth()]
    readonly property var moisCourts: ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
    readonly property string dateCourte: Reglages.en ? maintenant.toLocaleDateString(Reglages.locale, "ddd, MMM d")
                                                     : jours[maintenant.getDay()].slice(0, 3) + ". " + maintenant.getDate() + " " + moisCourts[maintenant.getMonth()]

    // ── Musique (playerctld est un miroir du vrai lecteur : écarté) : le lecteur qui joue, sinon le dernier qui a joué, sinon le premier qui a un titre ──
    readonly property var lecteurs: Mpris.players.values.filter(p => (p.trackTitle || "") !== "" && !(p.dbusName || "").endsWith(".playerctld"))
    property var dernierLecteur: null
    property real finLecture: 0          // heure de la dernière pause (ms)
    readonly property var lecteur: {
        var l = lecteurs
        for (let i = 0; i < l.length; i++) if (l[i].isPlaying) return l[i]
        if (dernierLecteur && l.indexOf(dernierLecteur) >= 0) return dernierLecteur
        return l.length > 0 ? l[0] : null
    }
    readonly property bool joue: lecteur !== null && lecteur.isPlaying
    // Pause notée seulement pour le lecteur qui jouait (pas quand il disparaît et qu'un autre, en pause depuis
    // longtemps, prend sa place)
    onJoueChanged: {
        if (joue) dernierLecteur = lecteur; else if (lecteur !== null && lecteur === dernierLecteur) finLecture = Date.now()
        // Heure du dernier départ / arrêt de lecture : l'écran de verrouillage (nc-verrou-media) montre une pause récente
        Quickshell.execDetached(["sh", "-c", "d=\"${XDG_CACHE_HOME:-$HOME/.cache}/nc\"; mkdir -p \"$d\" && date +%s > \"$d/derniere-lecture\""])
    }
    Component.onCompleted: if (joue) dernierLecteur = lecteur

    // Navigateurs : sans métadonnées du site, MPRIS donne le titre de l'onglet (« Épisode 3 – Série – Crunchyroll ») ;
    // on le découpe : le site devient la source, le reste le titre. Préfixe « (3) » des notifications retiré.
    readonly property bool navigateur: lecteur !== null
        && /firefox|chrom|brave|vivaldi|opera|edge|zen|librewolf|floorp/i.test((lecteur.identity || "") + " " + (lecteur.desktopEntry || ""))
    readonly property var morceauxOnglet: {
        if (!navigateur || (lecteur.trackArtist || "") !== "") return []
        var p = (lecteur.trackTitle || "").replace(/^\(\d+\)\s*/, "").split(/\s+[–—|·-]\s+/)
        return p.length > 1 ? p : []
    }
    readonly property string titre: !lecteur ? ""
        : (morceauxOnglet.length > 1 ? morceauxOnglet.slice(0, -1).join(" – ") : (lecteur.trackTitle || "").replace(/^\(\d+\)\s*/, ""))
    readonly property string artiste: !lecteur ? ""
        : ((lecteur.trackArtist || "") !== "" ? lecteur.trackArtist : (morceauxOnglet.length > 1 ? morceauxOnglet[morceauxOnglet.length - 1] : ""))
    // Pas de pochette en Économie (ECO_IMAGES) : l'icône du lecteur la remplace partout
    readonly property string pochette: lecteur && !Reglages.imagesLegeres ? (lecteur.trackArtUrl || "") : ""
    // Sans pochette : icône de l'appli qui joue (Firefox, Spotify…)
    readonly property string iconeLecteur: !lecteur ? ""
        : (Quickshell.iconPath(lecteur.desktopEntry || "", true) || Quickshell.iconPath((lecteur.identity || "").toLowerCase(), true) || "")
    function lecturePause() { if (lecteur && lecteur.canTogglePlaying) lecteur.togglePlaying() }
    // Position : relue chaque seconde pendant la lecture (MPRIS ne l'envoie pas en continu)
    Timer { interval: 1000; repeat: true; running: etat.joue && etat.ecranOuvert !== ""; onTriggered: if (etat.lecteur) etat.lecteur.positionChanged() }
    onTitreChanged: if (joue && titre !== "") activite("piste", 3200)

    // ── Son (sortie par défaut) ──
    PwObjectTracker { objects: [Pipewire.defaultAudioSink, Pipewire.defaultAudioSource] }
    readonly property var sortie: Pipewire.defaultAudioSink
    readonly property real volume: sortie && sortie.audio ? sortie.audio.volume : 0
    readonly property bool muet: sortie && sortie.audio ? sortie.audio.muted : false
    readonly property bool microMuet: Pipewire.defaultAudioSource && Pipewire.defaultAudioSource.audio ? Pipewire.defaultAudioSource.audio.muted : false
    function reglerVolume(v) {
        if (!sortie || !sortie.audio) return
        sortie.audio.muted = false
        sortie.audio.volume = Math.max(0, Math.min(1, v))
    }
    function basculerMuet() { if (sortie && sortie.audio) sortie.audio.muted = !sortie.audio.muted }
    function basculerMicro() {
        var s = Pipewire.defaultAudioSource
        if (s && s.audio) s.audio.muted = !s.audio.muted
    }
    onVolumeChanged: activite("volume")
    onMuetChanged: activite("volume")

    // ── Batterie et profils d'énergie ──
    readonly property var batterie: UPower.displayDevice
    // Sans UPower ou sans batterie (PC fixe) : faux et 0, jamais « undefined »
    readonly property bool aBatterie: batterie ? batterie.isLaptopBattery === true : false
    readonly property int pourcent: batterie && typeof batterie.percentage === "number" ? Math.round(batterie.percentage * (batterie.percentage <= 1 ? 100 : 1)) : 0
    readonly property bool branche: !UPower.onBattery
    // Vraie recharge (pas seulement branché : la limite de charge peut la bloquer vers 80 %)
    readonly property bool enCharge: aBatterie && batterie.state === UPowerDeviceState.Charging
    onBrancheChanged: { if (aBatterie) activite("charge"); if (branche) seuilAlerte = 100 }
    // Une vraie batterie du PC dans /sys (pas celle d'une souris : scope Device), lue une fois au démarrage par
    // nc-conso (sans UPower aussi) : la page Batterie n'existe que là
    property bool batteriePc: false
    Process {
        running: true
        command: [etat.bin + "nc-conso", "a-batterie"]
        onExited: code => etat.batteriePc = code === 0
    }

    // ── Micro et caméra utilisés (point orange / vert à côté de la pilule, comme sur iPhone) ──
    // Micro : flux PipeWire qui enregistre (pas les captures du son des haut-parleurs : cava, halo, indicateurs).
    // Seulement le type, le nom et la description des flux, lisibles sans s'y attacher : s'attacher (PwObjectTracker) à
    // tous les flux des applis faisait planter Quickshell quand plusieurs disparaissaient d'un coup (quitter Discord en
    // déconnectant le casque). (La mesure du niveau du micro pendant un appel, NiveauMicro.qml, est un flux « peak » /
    // « stream.monitor » de Quickshell : Appel.qml l'écarte de ses flux, pas d'ici.)
    readonly property var fluxMicro: Pipewire.nodes.values.filter(n => n.type === PwNodeType.AudioInStream
        && !/cava|pouls|pavucontrol|volume control|noctalia|peak|nc-ile|monitor/i.test((n.name || "") + " " + (n.description || "")))
    readonly property string appliMicro: fluxMicro.length ? (fluxMicro[0].description || fluxMicro[0].name || Reglages.t("Une appli", "An app")) : ""
    // Caméra : allumée si la webcam est sortie de veille (simple fichier à lire) ; le nom de l'appli n'est cherché
    // qu'à ce moment-là (parcourir les fichiers ouverts de tous les programmes coûte cher : pas toutes les 3 s)
    property string appliCamera: ""
    Process {
        id: lireCamera
        command: ["sh", "-c", "for v in /sys/class/video4linux/video*; do d=$(readlink -f \"$v/device\"); "
            + "s=$(cat \"$d/power/runtime_status\" 2>/dev/null || cat \"$d/../power/runtime_status\" 2>/dev/null); "
            + "[ \"$s\" = active ] || continue; "
            + "for f in /proc/[0-9]*/fd/*; do case \"$(readlink \"$f\" 2>/dev/null)\" in /dev/video*) p=${f#/proc/}; cat /proc/${p%%/*}/comm;; esac; done 2>/dev/null "
            + "| grep -v -x -E 'pipewire|wireplumber|xdg-desktop-por.*' | head -1 | grep . || echo '" + Reglages.t("Une appli", "An app") + "'; exit; done"]
        stdout: StdioCollector { onStreamFinished: etat.appliCamera = text.trim() }
    }
    // État des webcams lu directement (fichiers runtime_status trouvés au démarrage, puis chaque minute pour une webcam
    // USB branchée plus tard) : aucun processus toutes les 5 s tant qu'aucune caméra n'est allumée
    property var fichiersCamera: []
    Process {
        id: trouverCameras
        running: true
        command: ["sh", "-c", "for v in /sys/class/video4linux/video*; do d=$(readlink -f \"$v/device\"); "
            + "for f in \"$d/power/runtime_status\" \"$d/../power/runtime_status\"; do [ -r \"$f\" ] && { readlink -f \"$f\"; break; }; done; done | sort -u"]
        stdout: StdioCollector { onStreamFinished: { var l = text.split("\n").filter(x => x !== ""); if (JSON.stringify(l) !== JSON.stringify(etat.fichiersCamera)) etat.fichiersCamera = l } }
    }
    Instantiator {
        id: etatsCamera
        model: etat.fichiersCamera
        delegate: FileView { required property string modelData; path: modelData; blockLoading: true; printErrors: false }
    }
    Timer {
        interval: 5000; repeat: true; running: etat.ecranVu; triggeredOnStart: true     // écran éteint : suspendu, et un contrôle dès le réveil
        property int tours: 0
        onTriggered: {
            if (++tours % 12 === 0 && !trouverCameras.running) trouverCameras.running = true
            var allumee = false
            for (let i = 0; i < etatsCamera.count; i++) {
                let f = etatsCamera.objectAt(i)
                if (!f) continue
                f.reload()
                if (f.text().trim() === "active") allumee = true
            }
            if (!allumee) etat.appliCamera = ""
            else if (!lireCamera.running) lireCamera.running = true     // allumée : quelle appli s'en sert
        }
    }
    readonly property bool microActif: appliMicro !== ""
    readonly property bool cameraActive: appliCamera !== ""
    onMicroActifChanged: if (microActif) activite("micro", 3200)
    onCameraActiveChanged: if (cameraActive) activite("micro", 3200)
    // (l'enregistreur de nc-dictee est montré comme « Dictée » : le point orange l'affiche déjà pendant l'écoute)
    function nomJoli(n) { return n === "WEBRTC VoiceEngine" ? "Discord" : (/^(parec|pw-record|arecord)$/i.test(n) ? Reglages.t("Dictée", "Dictation") : (n.charAt(0).toUpperCase() + n.slice(1))) }

    // ── Casque / écouteurs Bluetooth qui se connectent (AirPods…) : la pilule montre leur nom et leur batterie ──
    // Repérés par leur adresse (pas par le nœud PipeWire : passer en mode appel recrée le nœud sans reconnexion)
    readonly property var adressesBt: Pipewire.nodes.values.filter(n => n.isSink && !n.isStream && (n.name || "").indexOf("bluez_output.") === 0)
        .map(n => ({ mac: n.name.split(".")[1].replace(/_/g, ":"), nom: n.description || n.nickname || Reglages.t("Casque", "Headphones") }))
    property var btConnus: []
    property string casqueNom: ""
    // Niveau donné par UPower (CasqueBatterie.qml) : vide tant que le casque ne le donne pas (ou si le réglage est coupé)
    readonly property string casqueBatterie: { var n = casqueNom === "" ? 0 : CasqueBatterie.niveauPour(casqueNom); return n > 0 ? String(n) : "" }
    onAdressesBtChanged: {
        var avant = btConnus, macs = []
        for (let i = 0; i < adressesBt.length; i++) {
            let a = adressesBt[i]
            macs.push(a.mac)
            if (avant.indexOf(a.mac) < 0 && macs.indexOf(a.mac) === macs.length - 1 && pret) {
                casqueNom = a.nom
                activite("casque", 3000)
            }
        }
        btConnus = macs
    }

    // ── Batterie faible : alerte à 20 % puis à 10 % (sur batterie), avec un bouton « Mode Économie » ──
    // Premier seuil réglable (nc-reglages, BATTERIE_ALERTE ; 0 : jamais), le second à la moitié
    readonly property int alerte1: Math.max(0, Math.min(50, parseInt(Reglages.val("BATTERIE_ALERTE", "20")) || 0))
    readonly property int alerte2: Math.round(alerte1 / 2)
    property int seuilAlerte: 100       // dernier seuil annoncé (remis à 100 quand on branche)
    onPourcentChanged: {
        if (!aBatterie || branche || pourcent <= 0 || alerte1 === 0) return
        var seuil = pourcent <= alerte2 ? alerte2 : (pourcent <= alerte1 ? alerte1 : 100)
        if (seuil < seuilAlerte) { seuilAlerte = seuil; alerteBatterie.running = true }
    }
    Process {
        id: alerteBatterie
        command: ["notify-send", "-a", Reglages.t("Batterie", "Battery"), "-u", etat.seuilAlerte <= etat.alerte2 ? "critical" : "normal", "-i", "battery-caution",
                  "-A", "eco=" + Reglages.t("Mode Économie", "Low Power Mode"),
                  Reglages.t("Batterie faible : " + etat.pourcent + " %", "Low Battery: " + etat.pourcent + "%"),
                  etat.seuilAlerte <= etat.alerte2 ? Reglages.t("Branche ton PC maintenant.", "Plug in your computer now.")
                                                   : Reglages.t("Pense à brancher ton PC, ou passe en mode Économie.", "Plug in your computer soon, or switch to Low Power Mode.")]
        stdout: StdioCollector { onStreamFinished: if (text.trim() === "eco") etat.choisirProfil(PowerProfile.PowerSaver) }
    }
    readonly property int profil: PowerProfiles.profile
    onProfilChanged: if (!jeuEnCours) activite("profil")
    function choisirProfil(p) { PowerProfiles.profile = p }
    // Le service de profils propose Performance (sans lui, ou sans ce profil : pas de bouton Performance dans Santé)
    readonly property bool performanceDisponible: PowerProfiles.hasPerformanceProfile

    // ── Luminosité (nc-brightness, même échelle que les touches) ──
    property real luminosite: 0.5
    property bool luminositeVueParTouche: false
    Process {
        id: lecteurLum
        command: [etat.bin + "nc-brightness", "get"]
        stdout: StdioCollector {
            onStreamFinished: {
                var v = parseInt(this.text)
                if (!isNaN(v)) etat.luminosite = v / 100
                if (etat.luminositeVueParTouche) activite("luminosite")
                etat.luminositeVueParTouche = false
            }
        }
    }
    function lireLuminosite(touche) { luminositeVueParTouche = touche; if (!lecteurLum.running) lecteurLum.running = true }
    // Réglage depuis le curseur : appliqué au plus toutes les 60 ms pendant le glissement
    property real luminositeVoulue: -1
    Timer {
        interval: 60; repeat: true; running: etat.luminositeVoulue >= 0
        onTriggered: {
            Quickshell.execDetached([etat.bin + "nc-brightness", "set", String(Math.max(1, Math.round(etat.luminositeVoulue * 100)))])
            etat.luminositeVoulue = -1
        }
    }
    function reglerLuminosite(v) { luminosite = Math.max(0, Math.min(1, v)); luminositeVoulue = luminosite }

    // ── Mode jeu (fichier de la session, posé et retiré par nc.mode_jeu dans Hyprland) : surveillé, pas sondé ──
    property bool jeu: false
    property bool jeuEnCours: false
    function majJeu(j) { if (j !== jeu) { jeu = j; jeuEnCours = true; activite("jeu"); finJeu.restart() } }
    FileView {
        path: etat.dossierSession + "/nc-mode-jeu"; watchChanges: true; printErrors: false
        onFileChanged: reload()
        onLoaded: etat.majJeu(true)
        onLoadFailed: etat.majJeu(false)
    }
    Timer { id: finJeu; interval: 4000; onTriggered: etat.jeuEnCours = false }

    // ── État du système (centre de contrôle ouvert) ──
    property var sys: ({})
    property bool nuit: false
    LectureFile {
        id: lecteurEtat
        commande: [etat.bin + "nc-ile-etat", "sans-media"]
        actif: etat.pageSys
        onLu: texte => {
            var t = {}
            var lignes = texte.split("\n")
            for (let i = 0; i < lignes.length; i++) {
                let p = lignes[i].indexOf("=")
                if (p > 0) t[lignes[i].slice(0, p)] = lignes[i].slice(p + 1)
            }
            etat.sys = t
            reac.confirmer()
        }
    }
    // nc-ile-etat (une centaine de ms de calcul) : seulement pour les pages qui lisent Etat.sys. Une lecture demandée
    // pendant une autre est mise en file (une seule en attente), pas ignorée
    readonly property bool pageSys: ["centre", "systeme", "reseau", "bluetooth"].indexOf(vueActive) >= 0
    function lire() { if (pageSys) lecteurEtat.demander() }
    Timer { interval: 2000; repeat: true; running: etat.ecranOuvert !== "" && etat.pageSys && etat.ecranVu; onTriggered: { etat.lire(); etat.lirePage() } }
    onPageSysChanged: if (pageSys && ecranOuvert !== "") lire()

    // Listes des pages Wi-Fi, Bluetooth, et mesures de la page Système
    property var liste: []
    LectureFile {
        id: lecteurPage
        onLu: texte => {
            var l = []
            var lignes = texte.split("\n")
            for (let i = 0; i < lignes.length; i++) {
                let p = lignes[i].indexOf("=")
                if (p > 0) l.push({ genre: lignes[i].slice(0, p), champs: lignes[i].slice(p + 1).split("\t") })
            }
            etat.liste = l
            reac.confirmer()
        }
    }
    function lirePage() {
        var quoi = ({ reseau: "wifi", bluetooth: "bt", systeme: "systeme" })[vueActive]
        lecteurPage.commande = quoi ? [bin + "nc-ile-etat", quoi] : []
        lecteurPage.demander()
    }

    // ── Interrupteurs réactifs (Voulu.qml) : le bouton bascule au clic, sans attendre la mesure ──
    // Mesure d'une clé : Etat.sys (wifi, bluetooth, halo…) ou une ligne de la page Système (protection…)
    function mesureDe(cle) {
        if (sys[cle] !== undefined) return sys[cle]
        for (let i = 0; i < liste.length; i++) if (liste[i].genre === cle) return liste[i].champs[0]
        return undefined
    }
    // À lier à l'état d'un bouton : Etat.valeur("wifi", Etat.sys.wifi) === "on"
    function valeur(cle, mesure) { return reac.valeur(cle, mesure) }
    function voulu(cle, valeur) { reac.voulu(cle, valeur) }
    readonly property var contraire: ({ on: "off", off: "on", "1": "0", "0": "1" })
    // Inverse l'interrupteur `cle` et lance la commande qui le fait vraiment ; si elle échoue, retour immédiat à la mesure
    function inverser(cle, cmd) {
        var cible = contraire[String(reac.valeur(cle, mesureDe(cle)))]
        if (cible !== undefined) reac.voulu(cle, cible)
        faire(cmd, cle)
    }
    Voulu {
        id: reac
        mesure: cle => etat.mesureDe(cle)
        onEchec: cle => Quickshell.execDetached(["notify-send", "-a", Reglages.t("Île", "Island"), "-i", "dialog-warning",
                                                 Reglages.t("La commande a échoué", "The command failed")])
        // Relecture dès la fin de la commande, puis une seconde fois pour les transitions lentes (BlueZ, NetworkManager)
        onFini: { etat.lire(); etat.lirePage(); relecture.restart() }
    }

    // Lance une commande (suivie : on connaît sa fin) puis relit l'état
    function faire(cmd, cle) { reac.lancer(cmd, cle) }
    Timer { id: relecture; interval: 1500; onTriggered: { etat.lire(); etat.lirePage() } }

    // ── Activités (réactions de la pilule) ──
    property string activiteType: ""
    property bool pret: false
    Timer { interval: 2000; running: true; onTriggered: etat.pret = true }   // pas de réaction au démarrage
    Timer { id: finActivite; onTriggered: etat.activiteType = "" }
    function activite(t, duree) {
        if (!pret || ecranOuvert !== "") return
        activiteType = t
        finActivite.interval = duree || 2200
        finActivite.restart()
    }

    // ── Onde sonore (pilule, page Musique) : basses lues par cava pendant la lecture ; si cava n'entend rien (son
    //    coupé, cava absent), une onde douce tourne quand même, pour ne pas laisser des barres à plat ──
    property var bandes: [0, 0, 0, 0, 0]
    // Économie ou sans effets : l'onde se pose sur une forme calme au lieu de rester figée au milieu d'un mouvement
    Connections { target: Reglages; function onSobreChanged() { if (Reglages.sobre) etat.bandes = [0.3, 0.45, 0.55, 0.45, 0.3] } }
    // Barres réellement affichées : pilule fermée en mode musique (même règle que « mode » de Compact.qml), ou île
    // ouverte sur la page Musique. Écran éteint ou session verrouillée : jamais.
    readonly property bool barresAffichees: joue && ecranVu && (ecranOuvert === "" ? (aMusique && activiteType === "" && !enregistre
                                                                                          && !Partage.indicateur && AssistantEtat.activitePilule === "" && !Agents.attendTerminal)
                                                                                    : vueActive === "musique")
    property real dernierSon: 0
    // 30 images/s, sans animation entre deux pas (une animation de 70 ms à chaque pas faisait redessiner l'île à 165 Hz)
    Timer {
        interval: 33; repeat: true
        running: etat.barresAffichees && etat.maintenant.getTime() - etat.dernierSon > 1500 && !Reglages.sobre
        property real t: 0
        onTriggered: {
            t += 0.165
            var b = []
            for (let i = 0; i < 5; i++) b.push(0.25 + 0.22 * Math.sin(t + i * 1.3) + 0.12 * Math.sin(t * 1.7 + i))
            etat.bandes = b
        }
    }
    // cava (analyse du son, 30 fois par seconde) : pas en Économie ni sans effets ; l'onde reste alors immobile
    Process {
        running: etat.joue && etat.ecranVu && !Reglages.sobre
        command: ["sh", "-c", "f=\"${XDG_RUNTIME_DIR:-/tmp}/nc-ile-cava.conf\"; printf '[general]\\nbars = 10\\nframerate = 30\\n[input]\\nmethod = pipewire\\nsource = auto\\n[output]\\nmethod = raw\\nraw_target = /dev/stdout\\ndata_format = ascii\\nascii_max_range = 100\\nbar_delimiter = 59\\nframe_delimiter = 10\\n' > \"$f\"; exec cava -p \"$f\""]
        stdout: SplitParser {
            onRead: data => {
                var v = data.split(";")
                if (v.length < 6) return
                var b = []
                var somme = 0
                for (let i = 0; i < 5; i++) { b.push(Math.min(1, (parseInt(v[i]) || 0) / 100)); somme += b[i] }
                if (somme < 0.04) return
                etat.dernierSon = Date.now()
                etat.bandes = b
            }
        }
    }
}
