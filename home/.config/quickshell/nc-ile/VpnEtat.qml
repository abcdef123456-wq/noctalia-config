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
// Réglages (nc-reglages → Île) : VPN_INDICATEUR (oui : bouclier dans la pilule quand un tunnel est monté), VPN_IP_PUBLIQUE (non),
// VPN_IP_SERVICE (vide).
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: v

    readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
    property bool panneauOuvert: false            // posé par Vpn.qml
    property bool disponible: false
    property bool lu: false
    property var connexions: []                   // [{uuid, nom, type, active, interface}]
    property var actives: []
    property string erreur: ""                    // dernier message de nc-vpn (texte brut)
    property string cible: ""                     // uuid en cours d'action ("tout" pour tout-deconnecter)
    property string ip: ""

    readonly property bool actif: disponible && actives.length > 0
    readonly property bool indicateur: actif && Reglages.val("VPN_INDICATEUR", "oui") !== "non"
    readonly property bool masque: Partage.silence
    readonly property bool ipVoulue: Reglages.val("VPN_IP_PUBLIQUE", "non") === "oui"
                                     && String(Reglages.val("VPN_IP_SERVICE", "")).indexOf("https://") === 0
    // Une signature des tunnels montés : l'IP n'est redemandée que si elle change
    readonly property string signature: actives.map(c => c.uuid).sort().join(",")
    readonly property bool veille: Etat.ecranVu && disponible && (panneauOuvert || (connexions.length > 0 && Reglages.val("VPN_INDICATEUR", "oui") !== "non"))
    readonly property bool voulu: Etat.ecranVu && (panneauOuvert || Reglages.val("VPN_INDICATEUR", "oui") !== "non")

    function relire() { if (!lecture.running) lecture.running = true }
    onVouluChanged: if (voulu) relire()           // premier relevé, et relevé au réveil de l'écran
    onPanneauOuvertChanged: if (panneauOuvert) relire()
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
                v.lu = true
            }
        }
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
    readonly property bool ipAutorisee: ipVoulue && panneauOuvert && !masque && Etat.ecranVu && lu && disponible
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
        onExited: { v.cible = ""; v.relire() }
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
