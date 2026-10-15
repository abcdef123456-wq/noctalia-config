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

    // ── Île ouverte (nom de l'écran, "" = fermée) et page du centre de contrôle ──
    property string ecranOuvert: ""
    property string page: "accueil"

    function basculer(ecran) {
        if (ecranOuvert === ecran) { fermer(); return }
        page = "accueil"
        ecranOuvert = ecran
        activiteType = ""
        lire()
        lireLuminosite(false)
    }
    function fermer() { ecranOuvert = "" }
    function aller(p) { page = p; lirePage() }

    // ── Heure ──
    property date maintenant: new Date()
    Timer { interval: 1000; running: true; repeat: true; onTriggered: etat.maintenant = new Date() }
    readonly property var jours: ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]
    readonly property var mois: ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    readonly property string heure: Qt.formatTime(maintenant, "hh:mm")
    readonly property string dateLongue: jours[maintenant.getDay()] + " " + maintenant.getDate() + " " + mois[maintenant.getMonth()]
    readonly property var moisCourts: ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
    readonly property string dateCourte: jours[maintenant.getDay()].slice(0, 3) + ". " + maintenant.getDate() + " " + moisCourts[maintenant.getMonth()]

    // ── Musique : le lecteur qui joue, sinon le premier ──
    readonly property var lecteurs: Mpris.players.values
    readonly property var lecteur: {
        var l = lecteurs
        for (var i = 0; i < l.length; i++) if (l[i].isPlaying) return l[i]
        return l.length > 0 ? l[0] : null
    }
    readonly property bool joue: lecteur !== null && lecteur.isPlaying
    readonly property string titre: lecteur ? (lecteur.trackTitle || "") : ""
    readonly property string artiste: lecteur ? (lecteur.trackArtist || "") : ""
    readonly property string pochette: lecteur ? (lecteur.trackArtUrl || "") : ""
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
    onBrancheChanged: if (aBatterie) activite("charge")
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
    Timer { interval: 2000; repeat: true; running: etat.ecranOuvert !== ""; onTriggered: { etat.lire(); if (etat.page !== "accueil") etat.lirePage() } }

    // Listes des pages Wi-Fi, Bluetooth, Son
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
        var quoi = ({ wifi: "wifi", bluetooth: "bt", son: "son" })[page]
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

    // ── Égaliseur de la pilule : basses lues par cava pendant la lecture ──
    property var bandes: [0, 0, 0, 0, 0]
    Process {
        running: etat.joue && etat.ecranOuvert === ""
        command: ["sh", "-c", "f=\"${XDG_RUNTIME_DIR:-/tmp}/nc-ile-cava.conf\"; printf '[general]\\nbars = 10\\nframerate = 30\\n[input]\\nmethod = pipewire\\nsource = auto\\n[output]\\nmethod = raw\\nraw_target = /dev/stdout\\ndata_format = ascii\\nascii_max_range = 100\\nbar_delimiter = 59\\nframe_delimiter = 10\\n' > \"$f\"; exec cava -p \"$f\""]
        stdout: SplitParser {
            onRead: data => {
                var v = data.split(";")
                if (v.length < 6) return
                var b = []
                for (var i = 0; i < 5; i++) b.push(Math.min(1, (parseInt(v[i]) || 0) / 100))
                etat.bandes = b
            }
        }
    }
}
