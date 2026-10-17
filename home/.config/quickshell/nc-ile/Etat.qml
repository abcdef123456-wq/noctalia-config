pragma Singleton
// Île dynamique (Quickshell) : état partagé par toutes les îles (une par écran).
// Musique (MPRIS), son (PipeWire), batterie et profils (UPower) : lus en direct ; Wi-Fi, Bluetooth, ne pas déranger,
// luminosité… : lus par ~/.local/bin/nc-ile-etat quand l'île est ouverte. Réactions (« activités ») : la pilule
// s'étire quelques secondes pour montrer un changement, comme sur iPhone.

import QtQuick
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
    // Musique au premier plan pendant la lecture, et encore 15 min après une pause (comme l'iPhone)
    readonly property bool aMusique: lecteur !== null && titre !== ""
                                     && (joue || (lecteur === dernierLecteur && finLecture > 0
                                                  && maintenant.getTime() - finLecture < 15 * 60000))
    readonly property var activites: {
        var a = []
        if (aMusique) a.push("musique")
        if (Agents.aPage || Agents.demande !== null) a.push("claude")      // Claude Code (nc-claude)
        if (minuteurFin > 0) a.push("minuteur")
        if (enCharge) a.push("charge")
        if (jeu) a.push("jeu")
        return a
    }
    readonly property var vues: activites.concat(["centre", "notifications"],
                                                 ["son", "reseau", "bluetooth", "systeme", "calendrier"],
                                                 meteo.temp !== undefined ? ["meteo"] : [], ["presse"],
                                                 minuteurFin > 0 ? [] : ["minuteur"])
    property string vueNom: "centre"
    readonly property int vue: Math.max(0, vues.indexOf(vueNom))
    readonly property string vueActive: vues[vue]
    // Hauteur du contenu annoncée par les pages à liste (Son, Wi-Fi, Bluetooth) : l'île s'y ajuste
    property var hauteurs: ({})
    function annoncerHauteur(nom, h) {
        if (hauteurs[nom] === Math.round(h)) return
        var t = Object.assign({}, hauteurs); t[nom] = Math.round(h); hauteurs = t
    }
    function changerVue(d) { aller(vues[Math.max(0, Math.min(vues.length - 1, vue + d))]) }
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
        recherche = false
        vueNom = versCentre || activites.length === 0 ? "centre" : activites[0]
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
    property bool projection: false        // fenêtre de projection, comme Windows + P (Projection.qml, Super + O)
    property string saisie: ""           // texte déjà tapé à l'ouverture (commande « rechercher »)
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
            var longue = pomoSeance % 4 === 0
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
        Quickshell.execDetached(["sh", "-c", "notify-send -a Pomodoro \"$1\" \"$2\"; command -v canberra-gtk-play >/dev/null && "
                                 + "canberra-gtk-play -i complete || true", "sh", msg[0], msg[1]])
    }
    onMinuteurResteChanged: {
        if (minuteurFin > 0 && minuteurReste === 0 && pomodoro) {
            minuteurFin = 0
            etapePomodoro()
        } else if (minuteurFin > 0 && minuteurReste === 0) {
            minuteurFin = 0
            Quickshell.execDetached(["sh", "-c", "notify-send -a \"$1\" -u critical \"$2\" \"$3\"; "
                + "command -v canberra-gtk-play >/dev/null && canberra-gtk-play -i alarm-clock-elapsed || true", "sh",
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
    readonly property bool meteoPilule: Reglages.val("ILE_METEO", "oui") !== "non" && meteo.temp !== undefined
    Process {
        id: lireMeteo
        command: [etat.bin + "nc-meteo"]
        stdout: StdioCollector { onStreamFinished: { try { var m = JSON.parse(text); if (m.temp !== undefined) etat.meteo = m } catch (e) {} } }
    }
    Timer { interval: 10 * 60000; repeat: true; running: Reglages.val("ILE_METEO", "oui") !== "non"; triggeredOnStart: true
            onTriggered: if (!lireMeteo.running) lireMeteo.running = true }
    Connections { target: Reglages; function onValeursChanged() { if (!lireMeteo.running) lireMeteo.running = true } }

    // ── Presse-papiers : les 12 derniers textes ou images copiés (en mémoire seulement ; jamais ce qu'un gestionnaire
    //    de mots de passe marque comme secret) ; un clic les recopie ──
    property var presse: []
    Process {
        running: Reglages.val("ILE_PRESSE", "oui") !== "non"
        command: ["wl-paste", "--watch", "sh", "-c",
            "t=$(wl-paste --list-types 2>/dev/null); case \"$t\" in *x-kde-passwordManagerHint*|*x-nc-secret*) exit 0;; esac; "
            + "if printf '%s' \"$t\" | grep -q '^image/png'; then d=\"${XDG_RUNTIME_DIR:-/tmp}/nc-ile-presse\"; mkdir -p \"$d\"; "
            + "f=\"$d/$(date +%s%N).png\"; wl-paste -t image/png > \"$f\" && printf 'I:%s\\n' \"$f\"; "
            + "elif printf '%s' \"$t\" | grep -qE '^(text/plain|UTF8_STRING|STRING|TEXT)'; then "
            + "printf 'T:'; wl-paste --no-newline -t text 2>/dev/null | head -c 4000 | tr '\\n\\r' '\\037\\037'; printf '\\n'; fi"]
        stdout: SplitParser {
            onRead: ligne => {
                var e = null
                if (ligne.indexOf("T:") === 0) {
                    var t = ligne.slice(2).replace(/\x1f/g, "\n")    // retours à la ligne passés en \x1f (une ligne par copie)
                    if (t.trim() === "") return
                    e = { genre: "texte", texte: t }
                } else if (ligne.indexOf("I:") === 0) e = { genre: "image", chemin: ligne.slice(2) }
                if (!e) return
                e.t = Date.now()
                var l = etat.presse.filter(x => !(x.genre === "texte" && e.genre === "texte" && x.texte === e.texte))
                l.unshift(e)
                etat.presse = l.slice(0, 12)
            }
        }
    }
    function recopier(e) {
        if (e.genre === "texte") Quickshell.execDetached(["wl-copy", "--", e.texte])
        else Quickshell.execDetached(["sh", "-c", "wl-copy -t image/png < \"$1\"", "sh", e.chemin])
    }
    function oublierPresse() {
        presse = []
        Quickshell.execDetached(["sh", "-c", "rm -rf \"${XDG_RUNTIME_DIR:-/tmp}/nc-ile-presse\""])
    }

    // ── Enregistrement d'écran (nc-video) : point rouge et durée dans la pilule ; un clic dessus l'arrête ──
    property real debutVideo: 0
    readonly property bool enregistre: debutVideo > 0

    // ── Téléchargements du navigateur (fichiers .part de Firefox, .crdownload des Chrome) : taille, vitesse, fin ──
    property var telechargements: []          // { nom, taille, vitesse } (octets, octets/s)
    property string telechargeFini: ""
    property var tailles: ({})
    readonly property string sansNom: Reglages.t("Téléchargement", "Download")    // fichier Chrome pas encore nommé
    readonly property bool telecharge: telechargements.length > 0 && Reglages.val("ILE_TELECHARGEMENTS", "oui") !== "non"
    Process {
        id: lecteurTel
        command: ["sh", "-c", "d=$(xdg-user-dir DOWNLOAD 2>/dev/null); [ -d \"$d\" ] || d=$HOME/Downloads; "
                  + "find \"$d\" -maxdepth 1 -type f \\( -name '*.part' -o -name '*.crdownload' \\) -printf '%s\\t%f\\n' 2>/dev/null; echo \"#$d\""]
        stdout: StdioCollector {
            onStreamFinished: {
                var l = [], vu = {}, dossier = ""
                text.split("\n").forEach(x => {
                    if (x.startsWith("#")) { dossier = x.slice(1); return }
                    var p = x.split("\t")
                    if (p.length < 2) return
                    var nom = p[1].replace(/\.(part|crdownload)$/, "").replace(/^Unconfirmed \d+$/, etat.sansNom)
                    var taille = parseInt(p[0]) || 0, avant = etat.tailles[p[1]]
                    vu[p[1]] = { taille: taille, nom: nom }
                    l.push({ nom: nom, taille: taille, vitesse: avant !== undefined ? Math.max(0, (taille - avant.taille) / 2) : 0 })
                })
                // Un fichier temporaire disparu : téléchargement fini (si le vrai fichier est là, pas annulé)
                for (var k in etat.tailles) if (!vu[k] && etat.tailles[k].nom !== etat.sansNom) verifFin.verifier(dossier, etat.tailles[k].nom)
                etat.tailles = vu
                etat.telechargements = l
            }
        }
    }
    Process {
        id: verifFin
        property string nom: ""
        function verifier(dossier, n) { nom = n; command = ["test", "-s", dossier + "/" + n]; running = true }
        onExited: code => { if (code === 0 && Reglages.val("ILE_TELECHARGEMENTS", "oui") !== "non") { etat.telechargeFini = nom; etat.activite("telechargement-fini", 4500) } }
    }
    Timer { interval: 2000; repeat: true; running: true; onTriggered: if (!lecteurTel.running) lecteurTel.running = true }
    function octets(n) {
        if (Reglages.en) return n >= 1e9 ? (n / 1e9).toFixed(1) + " GB" : (n >= 1e6 ? Math.round(n / 1e6) + " MB" : Math.round(n / 1e3) + " kB")
        return n >= 1e9 ? (n / 1e9).toFixed(1).replace(".", ",") + " Go" : (n >= 1e6 ? Math.round(n / 1e6) + " Mo" : Math.round(n / 1e3) + " ko")
    }
    Process {
        id: lireVideo
        command: ["sh", "-c", "f=\"${XDG_RUNTIME_DIR:-/tmp}/nc-video\"; [ -s \"$f\" ] && kill -0 \"$(head -1 \"$f\")\" 2>/dev/null && sed -n 2p \"$f\" || echo 0"]
        stdout: StdioCollector { onStreamFinished: etat.debutVideo = parseInt(text) || 0 }
    }
    Timer { interval: 1000; repeat: true; running: true; onTriggered: if (!lireVideo.running) lireVideo.running = true }
    function arreterVideo() { Quickshell.execDetached([bin + "nc-video", "arreter"]); debutVideo = 0 }

    // ── Café : empêche la mise en veille (Noctalia) ──
    property bool cafe: false
    function basculerCafe() { cafe = !cafe; Quickshell.execDetached(["noctalia", "msg", cafe ? "caffeine-enable" : "caffeine-disable"]) }

    // ── Heure ──
    property date maintenant: new Date()
    Timer { interval: 1000; running: true; repeat: true; onTriggered: etat.maintenant = new Date() }
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

    // ── Musique : le lecteur qui joue, sinon le dernier qui a joué, sinon le premier qui a un titre ──
    readonly property var lecteurs: Mpris.players.values.filter(p => (p.trackTitle || "") !== "")
    property var dernierLecteur: null
    property real finLecture: 0          // heure de la dernière pause (ms)
    readonly property var lecteur: {
        var l = lecteurs
        for (var i = 0; i < l.length; i++) if (l[i].isPlaying) return l[i]
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
    readonly property string pochette: lecteur ? (lecteur.trackArtUrl || "") : ""
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
    readonly property bool aBatterie: batterie && batterie.isLaptopBattery
    readonly property int pourcent: batterie ? Math.round(batterie.percentage * (batterie.percentage <= 1 ? 100 : 1)) : 0
    readonly property bool branche: !UPower.onBattery
    // Vraie recharge (pas seulement branché : la limite de charge peut la bloquer vers 80 %)
    readonly property bool enCharge: aBatterie && batterie.state === UPowerDeviceState.Charging
    onBrancheChanged: { if (aBatterie) activite("charge"); if (branche) seuilAlerte = 100 }

    // ── Micro et caméra utilisés (point orange / vert à côté de la pilule, comme sur iPhone) ──
    // Micro : flux PipeWire qui enregistre (pas les captures du son des haut-parleurs : cava, halo, indicateurs).
    // Seulement le type, le nom et la description des flux, lisibles sans s'y attacher : s'attacher (PwObjectTracker) à
    // tous les flux des applis faisait planter Quickshell quand plusieurs disparaissaient d'un coup (quitter Discord en
    // déconnectant le casque).
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
    Timer { interval: 3000; repeat: true; running: true; onTriggered: if (!lireCamera.running) lireCamera.running = true }
    readonly property bool microActif: appliMicro !== ""
    readonly property bool cameraActive: appliCamera !== ""
    onMicroActifChanged: if (microActif) activite("micro", 3200)
    onCameraActiveChanged: if (cameraActive) activite("micro", 3200)
    function nomJoli(n) { return n === "WEBRTC VoiceEngine" ? "Discord" : (n.charAt(0).toUpperCase() + n.slice(1)) }

    // ── Casque / écouteurs Bluetooth qui se connectent (AirPods…) : la pilule montre leur nom et leur batterie ──
    // Repérés par leur adresse (pas par le nœud PipeWire : passer en mode appel recrée le nœud sans reconnexion)
    readonly property var adressesBt: Pipewire.nodes.values.filter(n => n.isSink && !n.isStream && (n.name || "").indexOf("bluez_output.") === 0)
        .map(n => ({ mac: n.name.split(".")[1].replace(/_/g, ":"), nom: n.description || n.nickname || Reglages.t("Casque", "Headphones") }))
    property var btConnus: []
    property string casqueNom: ""
    property string casqueBatterie: ""
    onAdressesBtChanged: {
        var avant = btConnus, macs = []
        for (var i = 0; i < adressesBt.length; i++) {
            var a = adressesBt[i]
            macs.push(a.mac)
            if (avant.indexOf(a.mac) < 0 && macs.indexOf(a.mac) === macs.length - 1 && pret) {
                casqueNom = a.nom; casqueBatterie = ""
                lireBatterieBt.command = ["sh", "-c", "sleep 1.5; bluetoothctl info " + a.mac + " | sed -n 's/.*Battery Percentage:.*(\\([0-9]*\\)).*/\\1/p' | head -1"]
                lireBatterieBt.running = true
                activite("casque", 4500)
            }
        }
        btConnus = macs
    }
    Process {
        id: lireBatterieBt
        stdout: StdioCollector { onStreamFinished: etat.casqueBatterie = text.trim() }
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

    // ── Mode jeu (fichier de la session) ──
    property bool jeu: false
    property bool jeuEnCours: false
    Process {
        id: testeJeu
        command: ["sh", "-c", "[ -e \"${XDG_RUNTIME_DIR:-/tmp}/nc-mode-jeu\" ] && echo 1 || echo 0"]
        stdout: StdioCollector {
            onStreamFinished: {
                var j = this.text.trim() === "1"
                if (j !== etat.jeu) { etat.jeu = j; etat.jeuEnCours = true; activite("jeu"); finJeu.restart() }
            }
        }
    }
    Timer { id: finJeu; interval: 4000; onTriggered: etat.jeuEnCours = false }
    Timer { interval: 1500; repeat: true; running: true; onTriggered: if (!testeJeu.running) testeJeu.running = true }

    // ── État du système (centre de contrôle ouvert) ──
    property var sys: ({})
    property bool nuit: false
    Process {
        id: lecteurEtat
        command: [etat.bin + "nc-ile-etat"]
        stdout: StdioCollector {
            onStreamFinished: {
                var t = {}
                var lignes = this.text.split("\n")
                for (var i = 0; i < lignes.length; i++) {
                    var p = lignes[i].indexOf("=")
                    if (p > 0) t[lignes[i].slice(0, p)] = lignes[i].slice(p + 1)
                }
                etat.sys = t
            }
        }
    }
    function lire() { if (!lecteurEtat.running) lecteurEtat.running = true }
    Timer { interval: 2000; repeat: true; running: etat.ecranOuvert !== ""; onTriggered: { etat.lire(); etat.lirePage() } }

    // Listes des pages Wi-Fi, Bluetooth, et mesures de la page Système
    property var liste: []
    Process {
        id: lecteurPage
        stdout: StdioCollector {
            onStreamFinished: {
                var l = []
                var lignes = this.text.split("\n")
                for (var i = 0; i < lignes.length; i++) {
                    var p = lignes[i].indexOf("=")
                    if (p > 0) l.push({ genre: lignes[i].slice(0, p), champs: lignes[i].slice(p + 1).split("\t") })
                }
                etat.liste = l
            }
        }
    }
    function lirePage() {
        var quoi = ({ reseau: "wifi", bluetooth: "bt", systeme: "systeme" })[vueActive]
        if (!quoi || lecteurPage.running) return
        lecteurPage.command = [bin + "nc-ile-etat", quoi]
        lecteurPage.running = true
    }

    // Lance une commande puis relit l'état
    function faire(cmd) {
        Quickshell.execDetached(cmd)
        relecture.restart()
    }
    Timer { id: relecture; interval: 700; onTriggered: { etat.lire(); etat.lirePage() } }

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
    property real dernierSon: 0
    Timer {
        interval: 110; repeat: true
        running: etat.joue && etat.maintenant.getTime() - etat.dernierSon > 1500
        property real t: 0
        onTriggered: {
            t += 0.55
            var b = []
            for (var i = 0; i < 5; i++) b.push(0.25 + 0.22 * Math.sin(t + i * 1.3) + 0.12 * Math.sin(t * 1.7 + i))
            etat.bandes = b
        }
    }
    Process {
        running: etat.joue
        command: ["sh", "-c", "f=\"${XDG_RUNTIME_DIR:-/tmp}/nc-ile-cava.conf\"; printf '[general]\\nbars = 10\\nframerate = 30\\n[input]\\nmethod = pipewire\\nsource = auto\\n[output]\\nmethod = raw\\nraw_target = /dev/stdout\\ndata_format = ascii\\nascii_max_range = 100\\nbar_delimiter = 59\\nframe_delimiter = 10\\n' > \"$f\"; exec cava -p \"$f\""]
        stdout: SplitParser {
            onRead: data => {
                var v = data.split(";")
                if (v.length < 6) return
                var b = []
                var somme = 0
                for (var i = 0; i < 5; i++) { b.push(Math.min(1, (parseInt(v[i]) || 0) / 100)); somme += b[i] }
                if (somme < 0.04) return
                etat.dernierSon = Date.now()
                etat.bandes = b
            }
        }
    }
}
