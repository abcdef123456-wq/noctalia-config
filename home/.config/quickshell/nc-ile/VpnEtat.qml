pragma Singleton
// État des tunnels VPN et WireGuard de NetworkManager pour l'île (panneau Vpn.qml, bouclier de la pilule).
// Tout vient de nc-vpn (etat-json, connecter, deconnecter, tout-deconnecter, importer, ip-publique) ; jamais nmcli directement,
// sauf « nmcli monitor » : il n'envoie que des événements. Mise à jour sur événements seulement : une ligne de nmcli monitor
// relance, après 600 ms de calme, UN « nc-vpn etat-json » ; jamais un relevé toutes les N secondes.
//   - le moniteur ne tourne que si NetworkManager répond ET (le panneau est ouvert OU au moins un tunnel est configuré
//     et l'indicateur est voulu) ; il s'arrête écran éteint ou session verrouillée (Etat.ecranVu) et un relevé suit le réveil ;
//   - NetworkManager ou nmcli absent : « disponible » reste faux, rien ne tourne, aucune erreur ;
//   - noms, interfaces et IP sont masqués pendant un partage d'écran (Partage.silence) ;
//   - l'IP publique n'est demandée que si VPN_IP_PUBLIQUE=oui ET VPN_IP_SERVICE est une adresse https://, à l'ouverture du
//     panneau et quand l'ensemble des tunnels change panneau ouvert ; jamais en partage d'écran, jamais en boucle.
//   - la pilule lit « nc-vpn indicateur --json » (un seul nmcli, léger) : fournisseur et pays déduits des noms, sans réseau ;
//     le panneau ouvert lit en plus « etat-json » (tous les tunnels). Un client installé mais pas monté ne compte jamais ;
//   - en partage d'écran, le texte de la pilule et du panneau est « VPN » seul (ni fournisseur, ni pays).
//   - application officielle Mullvad (commande `mullvad`, tunnel hors de NetworkManager) : lue par nc-vpn (`mullvad status --json`),
//     seulement si la commande existe ; rafraîchie par `mullvad status listen` (une ligne = une relecture, son texte n'est jamais
//     lu ni gardé) uniquement écran allumé ET (panneau ouvert OU tunnel actif) ; jamais de numéro de compte lu ni affiché.
// Réglages (nc-reglages → Île) : VPN_INDICATEUR (oui : bouclier dans la pilule quand un tunnel est monté), VPN_IP_PUBLIQUE (non),
// VPN_IP_SERVICE (vide).
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: v

    readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
    signal ouvrirPanneau()                        // un clic sur l'indicateur de la pilule : shell.qml ouvre le panneau complet
    function demanderPanneau() { ouvrirPanneau() }
    property bool panneauOuvert: false            // posé par Vpn.qml
    property bool disponible: false
    property bool lu: false
    property var connexions: []                   // [{uuid, nom, type, active, interface}]
    property var actives: []
    property string erreur: ""                    // dernier message de nc-vpn (texte brut)
    property string cible: ""                     // uuid en cours d'action ("tout" pour tout-deconnecter)
    property string ip: ""

    // Ce que dit « nc-vpn indicateur --json » : le premier tunnel réellement monté
    property bool indActif: false
    property string indFournisseur: ""
    property string indPays: ""                   // deux lettres majuscules validées, ou vide
    property string indNom: ""
    property int indNombre: 0
    property bool mullvadInstalle: false          // la commande `mullvad` existe (dit par nc-vpn indicateur)
    property var mullvad: ({ installe: false, connecte: false, pays: "", hote: "", compte: null })   // pour le panneau

    // Kill switch (nc-vpn killswitch etat-json) : lu panneau ouvert et hors partage d'écran seulement, puis après chaque action
    property bool ksInstalle: false
    property bool ksVoulu: false
    property var ksActif: null                    // true, false ou null (inconnu)
    property string ksRefus: ""                   // pourquoi on ne peut pas l'activer maintenant (texte brut de nc-vpn)
    property var ksLimites: []

    readonly property bool actif: disponible && indActif
    readonly property bool indicateur: disponible && indActif && Reglages.val("VPN_INDICATEUR", "oui") !== "non"
    readonly property bool masque: Partage.silence
    readonly property bool ipVoulue: Reglages.val("VPN_IP_PUBLIQUE", "non") === "oui"
                                     && String(Reglages.val("VPN_IP_SERVICE", "")).indexOf("https://") === 0
    // Une signature des tunnels montés : l'IP n'est redemandée que si elle change
    readonly property string signature: actives.map(c => c.uuid).sort().join(",")
    readonly property bool veille: Etat.ecranVu && disponible && (panneauOuvert || Reglages.val("VPN_INDICATEUR", "oui") !== "non")
    readonly property bool voulu: Etat.ecranVu && (panneauOuvert || Reglages.val("VPN_INDICATEUR", "oui") !== "non")

    // Le drapeau : les deux indicateurs régionaux Unicode du code pays validé ; jamais une image
    readonly property string drapeau: /^[A-Z]{2}$/.test(indPays)
        ? String.fromCodePoint(0x1F1E6 + indPays.charCodeAt(0) - 65, 0x1F1E6 + indPays.charCodeAt(1) - 65) : ""
    // « Fournisseur · 🇫🇷 FR » (+1 si plusieurs tunnels) ; inconnu : le nom de la connexion ; partage d'écran : « VPN » seul
    readonly property string libelle: {
        if (masque) return "VPN"
        var t = indFournisseur !== "" ? indFournisseur : indNom
        if (t === "") t = "VPN"
        if (indPays !== "") t += " · " + drapeau + " " + indPays
        if (indNombre > 1) t += " +" + (indNombre - 1)
        return t
    }

    function relire() {
        if (panneauOuvert && !lecture.running) lecture.running = true      // tous les tunnels : panneau ouvert seulement
        if (panneauOuvert && mullvadInstalle && !lectureMullvad.running) lectureMullvad.running = true
        if (!resume.running) resume.running = true
    }
    Process {
        id: resume
        command: [v.bin + "nc-vpn", "indicateur", "--json"]
        stdout: StdioCollector {
            onStreamFinished: {
                var d = null
                try { d = JSON.parse(text) } catch (e) { d = null }
                if (d && d.disponible === true) {
                    var ok = d.actif === true
                    v.indActif = ok
                    v.indFournisseur = ok && typeof d.fournisseur === "string" ? d.fournisseur.slice(0, 40) : ""
                    v.indPays = ok && typeof d.pays === "string" && /^[A-Z]{2}$/.test(d.pays) ? d.pays : ""
                    v.indNom = ok && typeof d.nom === "string" ? d.nom.slice(0, 40) : ""
                    v.indNombre = ok && typeof d.nombre === "number" ? Math.max(0, Math.min(99, Math.floor(d.nombre))) : 0
                    v.mullvadInstalle = d.mullvad === true
                    v.disponible = true
                } else {
                    v.mullvadInstalle = false
                    v.indActif = false; v.indFournisseur = ""; v.indPays = ""; v.indNom = ""; v.indNombre = 0
                    v.disponible = false
                }
                v.lu = true
            }
        }
    }
    onVouluChanged: if (voulu) relire()           // premier relevé, et relevé au réveil de l'écran
    onPanneauOuvertChanged: { if (panneauOuvert) { relire(); lireKs() } else tunnelsLus = false }
    onMasqueChanged: if (!masque) lireKs()
    property bool tunnelsLus: false               // la liste complète (panneau ouvert) a été lue
    Component.onCompleted: if (voulu) relire()

    Process {
        id: lecture
        command: [v.bin + "nc-vpn", "etat-json"]
        stdout: StdioCollector {
            onStreamFinished: {
                var d = null
                try { d = JSON.parse(text) } catch (e) { d = null }
                if (d && d.disponible === true && Array.isArray(d.connexions)) {
                    v.connexions = d.connexions.filter(c => c && typeof c.uuid === "string")
                    v.actives = Array.isArray(d.actives) ? d.actives.filter(c => c && typeof c.uuid === "string") : []
                    v.disponible = true
                } else {
                    v.connexions = []; v.actives = []; v.disponible = false
                }
                v.lu = true; v.tunnelsLus = true
            }
        }
    }

    function lireKs() { if (panneauOuvert && disponible && !masque && !lectureKs.running) lectureKs.running = true }
    onDisponibleChanged: if (disponible) lireKs()
    Process {
        id: lectureKs
        command: [v.bin + "nc-vpn", "killswitch", "etat-json"]
        stdout: StdioCollector {
            onStreamFinished: {
                var d = null
                try { d = JSON.parse(text) } catch (e) { d = null }
                if (d && typeof d === "object") {
                    v.ksInstalle = d.installe === true
                    v.ksVoulu = d.voulu === true
                    v.ksActif = d.actif === true ? true : (d.actif === false ? false : null)
                    v.ksRefus = typeof d.refus === "string" ? d.refus.slice(0, 240) : ""
                    v.ksLimites = Array.isArray(d.limites) ? d.limites.filter(x => typeof x === "string").map(x => x.slice(0, 240)).slice(0, 8) : []
                }
            }
        }
    }

    // L'application Mullvad pour le panneau : installée, connectée, pays (deux lettres), relais, « connecté au compte » (oui, non, inconnu)
    Process {
        id: lectureMullvad
        command: [v.bin + "nc-vpn", "mullvad", "etat-json"]
        stdout: StdioCollector {
            onStreamFinished: {
                var d = null
                try { d = JSON.parse(text) } catch (e) { d = null }
                if (d && d.installe === true)
                    v.mullvad = { installe: true, connecte: d.connecte === true,
                                  pays: typeof d.pays === "string" && /^[A-Z]{2}$/.test(d.pays) ? d.pays : "",
                                  hote: typeof d.hote === "string" ? d.hote.slice(0, 40) : "",
                                  compte: d.compte === true ? true : (d.compte === false ? false : null) }
                else v.mullvad = { installe: false, connecte: false, pays: "", hote: "", compte: null }
            }
        }
    }
    // `mullvad status listen` : un événement de l'application = une relecture après 600 ms de calme ; son texte est ignoré
    Process {
        id: ecouteMullvad
        command: ["mullvad", "status", "listen"]
        running: Etat.ecranVu && v.mullvadInstalle && (v.panneauOuvert || v.indActif)
        stdout: SplitParser { onRead: ligne => attente.restart() }
    }

    // Événements de NetworkManager (connexion montée, coupée, ajoutée) : une relecture après 600 ms de calme
    Process {
        id: moniteur
        command: ["nmcli", "monitor"]
        running: v.veille
        stdout: SplitParser { onRead: ligne => attente.restart() }
    }
    Timer { id: attente; interval: 600; onTriggered: v.relire() }

    // IP publique : à l'ouverture du panneau et quand les tunnels changent (panneau ouvert), jamais en partage d'écran
    readonly property bool ipAutorisee: ipVoulue && panneauOuvert && !masque && Etat.ecranVu && lu && tunnelsLus && disponible
    onIpAutoriseeChanged: if (!ipAutorisee) ip = ""; else demanderIp()
    onSignatureChanged: if (ipAutorisee) demanderIp()
    property string signatureIp: ""               // les tunnels au moment de la demande : changés pendant la réponse, une nouvelle demande
    function demanderIp() { if (!ipAutorisee || ipProc.running) return; signatureIp = signature; ipProc.running = true }
    Process {
        id: ipProc
        command: [v.bin + "nc-vpn", "ip-publique"]
        stdout: StdioCollector {
            onStreamFinished: {
                var d = null
                try { d = JSON.parse(text) } catch (e) { d = null }
                v.ip = d && typeof d.ip === "string" && v.ipAutorisee ? d.ip : ""
            }
        }
        onExited: if (v.ipAutorisee && v.signatureIp !== v.signature) v.demanderIp()
    }

    // ── Actions (une à la fois) ──
    Process {
        id: agir
        stderr: StdioCollector { onStreamFinished: v.erreur = text.trim().split("\n")[0].slice(0, 240) }
        onExited: { var ks = v.cible === "killswitch"; v.cible = ""; v.relire(); if (ks) v.lireKs() }
    }
    function lancer(args, cible) {
        if (agir.running) return
        erreur = ""; v.cible = cible
        agir.command = [bin + "nc-vpn"].concat(args)
        agir.running = true
    }
    function connecter(uuid) { lancer(["connecter", uuid], uuid) }
    function deconnecter(uuid) { lancer(["deconnecter", uuid], uuid) }
    function toutDeconnecter() { lancer(["tout-deconnecter"], "tout") }
    function killswitchActiver() { if (!masque) lancer(["killswitch", "activer"], "killswitch") }
    function killswitchDesactiver() { if (!masque) lancer(["killswitch", "desactiver"], "killswitch") }
    function mullvadConnecter() { lancer(["mullvad", "connecter"], "mullvad") }
    function mullvadDeconnecter() { lancer(["mullvad", "deconnecter"], "mullvad") }
    function mullvadPays(cc) { if (/^[a-z]{2}$/.test(cc)) lancer(["mullvad", "pays", cc], "mullvad") }

    // ── Importer un fichier : le sélecteur de zenity est une fenêtre à part, le panneau se ferme avant (il tient le clavier) ──
    property string fichierChoisi: ""
    Process {
        id: choix
        command: ["sh", "-c", "command -v zenity >/dev/null 2>&1 || exit 127; exec zenity \"$@\"", "sh", "--file-selection",
                  "--title=" + Reglages.t("Importer une connexion VPN (.ovpn ou .conf)", "Import a VPN connection (.ovpn or .conf)"),
                  "--file-filter=" + Reglages.t("Connexions VPN", "VPN connections") + " | *.ovpn *.OVPN *.conf *.CONF"]
        stdout: StdioCollector { onStreamFinished: v.fichierChoisi = text.trim().split("\n")[0] }
        onExited: code => {
            if (code === 127) v.notifier(Reglages.t("Le sélecteur de fichier (zenity) n'est pas installé. En terminal : nc-vpn importer FICHIER.",
                                                    "The file picker (zenity) isn't installed. In a terminal: nc-vpn importer FILE."))
            else if (code === 0 && v.fichierChoisi !== "") v.importer(v.fichierChoisi)
            v.fichierChoisi = ""
        }
    }
    function choisirFichier() { if (!choix.running && !importation.running) choix.running = true }
    function notifier(texte) {
        Quickshell.execDetached(["notify-send", "-a", "VPN", "--", Reglages.t("VPN", "VPN"), String(texte).slice(0, 300)])
    }
    Process {
        id: importation
        stdout: StdioCollector { id: sortieImport }
        stderr: StdioCollector { id: erreurImport }
        onExited: code => {
            var t = (code === 0 ? sortieImport.text : erreurImport.text).trim().split("\n")[0]
            v.notifier(t !== "" ? t : (code === 0 ? Reglages.t("Connexion importée.", "Connection imported.") : Reglages.t("Import impossible.", "Import failed.")))
            v.relire()
        }
    }
    function importer(chemin) {
        if (importation.running || typeof chemin !== "string" || chemin === "" || chemin.charAt(0) === "-") return
        importation.command = [bin + "nc-vpn", "importer", chemin]
        importation.running = true
    }
}
