pragma Singleton
// État des tunnels VPN et WireGuard de NetworkManager pour l'île (panneau Vpn.qml, bouclier de la pilule).
// Fenêtre « Réseau privé » (Vpn.qml) : tunnels (NetworkManager + application Mullvad), modèle des fournisseurs (Proton et Nord : bientôt),
// pays de Mullvad (nc-vpn mullvad pays-json, lus une fois panneau ouvert) ; débits dans VpnDebit.qml (fenêtre ouverte et écran allumé).
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
    property bool ksLu: false                     // l'état a été lu au moins une fois (avant, on ne dit pas « pas installé »)
    property bool ksVoulu: false
    property var ksActif: null                    // true, false ou null (inconnu)
    property string ksRefus: ""                   // pourquoi on ne peut pas l'activer maintenant (texte brut de nc-vpn)
    property var ksLimites: []

    // Les pays de l'application Mullvad (nc-vpn mullvad pays-json), lus une fois, panneau ouvert : [{cc, nom}]
    property var mullvadPays: []
    property bool mullvadPaysLus: false
    property var suites: []                       // actions à lancer l'une après l'autre (arguments de nc-vpn), une à la fois
    // Nord et Proton d'après « nc-vpn fournisseurs-json » (contrat 1), lecture tolérante : commande absente ou réponse illisible = {}
    // {id: {id, nom, etat, message, pays: [{cc, nom}], paysActif, connecte, peutLogin}}
    property var externe: ({})
    // L'heure (secondes) tenue par VpnDebit.qml, seulement fenêtre ouverte et écran allumé ; sert à la durée de connexion
    property real maintenant: 0

    // Tous les tunnels RÉELLEMENT montés : ceux de NetworkManager puis l'application Mullvad si elle est connectée
    //   {id, uuid (vide pour Mullvad), nom, fournisseur, pays, serveur, interface, depuis (0 si inconnu), mullvad}
    readonly property var tunnels: {
        var l = actives.map(c => ({ id: c.uuid, uuid: c.uuid, nom: String(c.nom || ""), fournisseur: typeof c.fournisseur === "string" ? c.fournisseur.slice(0, 40) : "",
                                    pays: typeof c.pays === "string" && /^[A-Z]{2}$/.test(c.pays) ? c.pays : "",
                                    serveur: String(c.nom || ""),
                                    interface: typeof c.interface === "string" && /^[A-Za-z0-9_.-]{1,15}$/.test(c.interface) && c.interface !== ".." ? c.interface : "",
                                    depuis: typeof c.depuis === "number" ? c.depuis : 0, mullvad: false }))
        for (var id of ["nord", "proton"]) {
            var x = externe[id]
            // Proton : sa connexion « ProtonVPN … » est déjà dans les tunnels de NetworkManager ci-dessus (pas de doublon)
            if (x && x.connecte && !(id === "proton" && actives.some(c => c.fournisseur === "Proton VPN")))
                l.push({ id: "ext:" + id, uuid: "", nom: x.nom, fournisseur: x.nom, pays: x.paysActif, serveur: "", interface: "",
                         depuis: 0, mullvad: false, externe: id })
        }
        if (mullvad.connecte)
            l.push({ id: "mullvad", uuid: "", nom: "Mullvad", fournisseur: "Mullvad", pays: mullvad.pays, serveur: mullvad.hote,
                     interface: "wg0-mullvad", depuis: 0, mullvad: true })
        return l
    }
    // Le modèle des fournisseurs du panneau : {id, fournisseur, etat: absent | sans_compte | pilote_appli | pret, bientot, pays: [{cc, nom}]}.
    // « pilote_appli » : Proton sans sa CLI (ou avec l'application ouverte), qui se pilote dans son application (pas de pays chez nous ; le bouton l'ouvre).
    // Proton et Nord : « bientôt » tant que nc-vpn ne répond pas ; CyberGhost seulement si un profil de ce nom existe.
    readonly property var fournisseurs: {
        var l = [fiche("proton", "Proton VPN"), fiche("nord", "NordVPN"),
                 { id: "mullvad", fournisseur: "Mullvad", bientot: false, peutLogin: false, message: "",
                   etat: !mullvadInstalle ? "absent" : (mullvad.compte === false ? "sans_compte" : "pret"), pays: mullvadPays }]
        if (connexions.some(c => c.fournisseur === "CyberGhost"))
            l.push({ id: "cyberghost", fournisseur: "CyberGhost", etat: "pret", bientot: false, peutLogin: false, message: "", pays: [] })
        return l
    }
    // Nord ou Proton : « bientôt » tant que nc-vpn ne sait pas les lire, sinon l'état donné par nc-vpn
    function fiche(id, nom) {
        var x = externe[id]
        if (!x) return { id: id, fournisseur: nom, etat: "absent", bientot: true, peutLogin: false, message: "", pays: [] }
        return { id: id, fournisseur: x.nom, etat: x.etat, bientot: false, peutLogin: x.peutLogin, message: x.message, pays: x.pays,
                 connecte: x.connecte, probleme: x.probleme }
    }
    // « 🇫🇷 » pour « FR » ; vide si le code n'est pas deux lettres majuscules
    function drapeauDe(cc) {
        return /^[A-Z]{2}$/.test(cc) ? String.fromCodePoint(0x1F1E6 + cc.charCodeAt(0) - 65, 0x1F1E6 + cc.charCodeAt(1) - 65) : ""
    }

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

    function lireExterne() { if (panneauOuvert && !lectureExterne.running) lectureExterne.running = true }
    Process {
        id: lectureExterne
        command: [v.bin + "nc-vpn", "fournisseurs-json"]
        stdout: StdioCollector {
            onStreamFinished: {
                var d = null
                try { d = JSON.parse(text) } catch (e) { d = null }
                var res = {}
                if (d && d.contrat === 1 && Array.isArray(d.fournisseurs)) {
                    d.fournisseurs.forEach(x => {
                        if (!x || (x.id !== "nord" && x.id !== "proton") || ["absent", "sans_compte", "pilote_appli", "pret"].indexOf(x.etat) < 0) return
                        var pays = x.etat === "pret" && Array.isArray(x.pays)
                            ? x.pays.filter(q => q && typeof q.code === "string" && /^[A-Za-z]{2}$/.test(q.code) && typeof q.nom === "string")
                                    .map(q => ({ cc: q.code.toUpperCase(), nom: q.nom.slice(0, 40) })).slice(0, 150) : []
                        res[x.id] = { id: x.id, nom: typeof x.nom === "string" && x.nom !== "" ? x.nom.slice(0, 40) : (x.id === "nord" ? "NordVPN" : "Proton VPN"),
                                      etat: x.etat, message: typeof x.message === "string" ? x.message.slice(0, 300) : "", pays: pays,
                                      paysActif: typeof x.pays_actif === "string" && /^[A-Za-z]{2}$/.test(x.pays_actif) ? x.pays_actif.toUpperCase() : "",
                                      connecte: x.connecte === true, peutLogin: x.peut_login === true,
                                      probleme: typeof x.probleme === "string" ? x.probleme.slice(0, 20) : "" }
                    })
                }
                v.externe = res
            }
        }
    }

    function relire() {
        lireExterne()
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
    onPanneauOuvertChanged: { if (panneauOuvert) { relire(); lireKs(); lirePays() } else tunnelsLus = false }
    onMullvadInstalleChanged: { lirePays(); if (panneauOuvert && mullvadInstalle && !lectureMullvad.running) lectureMullvad.running = true }
    function lirePays() { if (panneauOuvert && mullvadInstalle && !mullvadPaysLus && !lecturePays.running) lecturePays.running = true }
    Process {
        id: lecturePays
        command: [v.bin + "nc-vpn", "mullvad", "pays-json"]
        stdout: StdioCollector {
            onStreamFinished: {
                var d = null
                try { d = JSON.parse(text) } catch (e) { d = null }
                v.mullvadPays = d && Array.isArray(d.pays)
                    ? d.pays.filter(x => x && typeof x.cc === "string" && /^[A-Z]{2}$/.test(x.cc) && typeof x.nom === "string")
                             .map(x => ({ cc: x.cc, nom: x.nom.slice(0, 40) })).slice(0, 150) : []
                v.mullvadPaysLus = true
            }
        }
    }
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
                if (!d || typeof d !== "object") { v.ksActif = null }          // illisible : état inconnu, jamais l'ancien
                else {
                    v.ksInstalle = d.installe === true
                    v.ksLu = true
                    v.ksVoulu = d.voulu === true
                    v.ksActif = d.actif === true ? true : (d.actif === false ? false : null)
                    v.ksRefus = typeof d.refus === "string" ? d.refus.slice(0, 240) : ""
                    v.ksLimites = Array.isArray(d.limites) ? d.limites.filter(x => typeof x === "string").map(x => x.slice(0, 240)).slice(0, 8) : []
                }
            }
        }
    }

    // Poser l'assistant root : nc-assistant-install ouvre une fenêtre kitty qui lance seulement l'étape kill switch d'install.sh
    // (la question, le mot de passe et la sortie y sont) ; le processus finit quand la fenêtre est fermée, alors on relit l'état.
    // Dépôt ou kitty introuvable : la commande à taper à la main arrive en notification.
    property bool installationEnCours: installeur.running
    Process {
        id: installeur
        command: [v.bin + "nc-assistant-install", "killswitch"]
        stderr: StdioCollector { id: erreurInstalleur }
        onExited: code => {
            if (code !== 0) v.notifier(erreurInstalleur.text.trim().split("\n")[0] || Reglages.t("Installation de l'assistant impossible.", "Couldn't install the helper."))
            v.lireKs()
        }
    }
    function installerAssistant() { if (!installeur.running && !masque) installeur.running = true }

    // Relecture de l'état du kill switch toutes les 10 s : SEULEMENT panneau ouvert, écran allumé, hors partage d'écran
    Timer { interval: 10000; repeat: true; running: v.panneauOuvert && v.disponible && !v.masque && Etat.ecranVu; onTriggered: v.lireKs() }

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
        onExited: code => {
            var ks = v.cible === "killswitch"; v.cible = ""
            var suivante = v.suites.length > 0 ? v.suites[0] : null
            if (suivante) {
                v.suites = v.suites.slice(1)
                if (code === 0 || suivante.toujours) { v.lancer(suivante.args, suivante.cible); return }    // pays choisi : on connecte ; tout couper : on continue
            }
            v.suites = []
            v.relire(); if (ks) v.lireKs()
        }
    }
    function lancer(args, cible) {
        if (agir.running) return
        erreur = ""; v.cible = cible
        agir.command = [bin + "nc-vpn"].concat(args)
        agir.running = true
    }
    function connecter(uuid) { lancer(["connecter", uuid], uuid) }
    function deconnecter(uuid) { lancer(["deconnecter", uuid], uuid) }
    // Tout couper : les tunnels de NetworkManager, puis l'application Mullvad si elle est montée, puis Nord et Proton prêts (par leur CLI ;
    // Proton qui se pilote dans son appli n'est jamais ouvert pour ça : son tunnel NetworkManager est déjà coupé plus haut)
    function toutDeconnecter() {
        if (agir.running) return
        if (actives.length === 0) {
            var file0 = []
            if (mullvad.connecte) file0.push({ args: ["mullvad", "deconnecter"], cible: "mullvad", toujours: true })
            for (var i0 of ["nord", "proton"])
                if (externe[i0] && externe[i0].connecte && externe[i0].etat === "pret") file0.push({ args: ["fournisseur", i0, "deconnecter"], cible: "ext:" + i0, toujours: true })
            if (file0.length === 0) return
            suites = file0.slice(1)
            lancer(file0[0].args, file0[0].cible)
            return
        }
        var file = []
        if (mullvad.connecte) file.push({ args: ["mullvad", "deconnecter"], cible: "mullvad", toujours: true })
        for (var id of ["nord", "proton"])
            if (externe[id] && externe[id].connecte && externe[id].etat === "pret") file.push({ args: ["fournisseur", id, "deconnecter"], cible: "ext:" + id, toujours: true })
        suites = file
        lancer(["tout-deconnecter"], "tout")
    }
    function killswitchActiver() { if (!masque) lancer(["killswitch", "activer"], "killswitch") }
    function killswitchDesactiver() { if (!masque) lancer(["killswitch", "desactiver"], "killswitch") }
    function mullvadConnecter() { lancer(["mullvad", "connecter"], "mullvad") }
    function mullvadDeconnecter() { lancer(["mullvad", "deconnecter"], "mullvad") }
    // Nord et Proton (nc-vpn fournisseur ID connecter CC | deconnecter | login)
    function fournisseurVers(id, cc) {
        if ((id === "nord" || id === "proton") && /^[A-Z]{2}$/.test(cc)) lancer(["fournisseur", id, "connecter", cc], "ext:" + id)
    }
    function fournisseurDeconnecter(id) { if (id === "nord" || id === "proton") lancer(["fournisseur", id, "deconnecter"], "ext:" + id) }
    function fournisseurLogin(id) { if (id === "nord" || id === "proton") lancer(["fournisseur", id, "login"], "ext:" + id) }
    // Un pays de la liste : choisir le pays puis connecter (Connecter, ou Changer si Mullvad est déjà monté)
    function mullvadVers(cc) {
        if (!/^[A-Z]{2}$/.test(cc) || agir.running) return
        suites = [{ args: ["mullvad", "connecter"], cible: "mullvad", toujours: false }]
        lancer(["mullvad", "pays", cc.toLowerCase()], "mullvad")
    }

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
