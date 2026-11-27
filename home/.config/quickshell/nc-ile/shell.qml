//@ pragma UseQApplication
//@ pragma IconTheme NC
// nc-ile : l'île dynamique de noctalia-config, en Quickshell, par-dessus la barre de Noctalia.
//   qs -c nc-ile                         lancer (service : nc-ile.service)
//   qs -c nc-ile ipc call ile basculer   ouvrir / fermer sur l'écran actif, sur le centre de contrôle (Super + C)
//   qs -c nc-ile ipc call ile ouvrir     ouvrir sur ce qui se passe (musique…) ; … suivante / precedente : changer de page
//   qs -c nc-ile ipc call ile luminosite montrer la luminosité (touches de luminosité)
//   qs -c nc-ile ipc call ile page wifi  ouvrir une page : wifi, bluetooth, son, notifications, charge (Batterie)
//   qs -c nc-ile ipc call ile pageOu charge systeme   la même, avec une page de repli si elle n'existe pas
//   qs -c nc-ile ipc call ile effacerNotifications | concentration | recherche (Spotlight, Super + R)
//   qs -c nc-ile ipc call ile projection   projection sur un second écran, comme Windows + P (Super + O)
//   qs -c nc-ile ipc call ile fiche        fiche des raccourcis, éditable (Super + /)
//   qs -c nc-ile ipc call ile code         espace de code : le sélecteur de projets façon Raycast (Super + X, nc-code)
//   qs -c nc-ile ipc call ile vpn          panneau VPN : tunnels VPN et WireGuard de NetworkManager (Super + Alt + V, nc-vpn)
//   qs -c nc-ile ipc call ile themes       carrousel des thèmes : choisir l'allure du bureau (Super + Alt + T)
//   qs -c nc-ile ipc call ile garmin      panneau Santé Garmin : batterie, sommeil, stress, pas (Super + Alt + S, nc-garmin)
//   qs -c nc-ile ipc call ile cloud        panneau Cloud JARVIS : parcourir, télécharger (Super + Alt + C, nc-cloud fenetre, CLOUD_JARVIS=oui)
//   qs -c nc-ile ipc call ile aimant ZONE X Y W H   aperçu d'aimantation pendant un glisser (nc/raccourcis.lua) ; ZONE "" l'efface
//   qs -c nc-ile ipc call ile gpuMode      confirmer un changement de mode graphique (Hybride ↔ Dédiée), qui redémarre
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "DispositionPanneaux.js" as Disposition

ShellRoot {
    id: racine
    property var modelePanneaux: ({})
    property var palettePanneaux: ({})
    FileView {
        path: Quickshell.env("HOME") + "/.config/nc/panneaux.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            try {
                const modele = JSON.parse(text())
                if (Array.isArray(modele.barres)) racine.modelePanneaux = modele
            } catch (e) {
                console.warn("Réglages des panneaux illisibles : " + e)
            }
        }
        // L'ancien modèle reste affiché en cas d'erreur de lecture ; seul le retrait du fichier rend la main.
        onLoadFailed: error => { if (error === FileViewError.FileNotFound) racine.modelePanneaux = ({}) }
    }
    FileView {
        path: Quickshell.env("HOME") + "/.config/noctalia/colors.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: racine.palettePanneaux = JSON.parse(text())
        onLoadFailed: racine.palettePanneaux = {}
    }
    readonly property bool panneauxActifs: (modelePanneaux.barres?.length ?? 0) > 0
    readonly property bool bandeIle: Reglages.val("ILE_BANDE", "non") === "oui"
    readonly property Variants ecransIle: Variants {
        model: Quickshell.screens
        Ile {
            id: ile
            readonly property bool panneauxRendus: panneaux.pret
            onOuvrirThemes: { Hyprland.refreshMonitors(); racine.themesOuvert = true }
            Panneaux {
                id: panneaux
                ecran: ile.modelData
                modele: racine.modelePanneaux
                palette: racine.palettePanneaux
                obstacle: ile.obstaclePanneaux
                obstacleRepos: ile.obstaclePanneauxRepos
                empriseLive: ile.empriseLive
                empriseStable: ile.empriseStable
                reserveIleHaut: racine.panneauxActifs && racine.bandeIle ? 42 : 0
            }
        }
    }
    // Barre native : la bande optionnelle reste indépendante. En mode modulaire les réserves sont calculées par écran.
    LazyLoader {
        id: chargeurBande
        active: racine.bandeIle && !racine.panneauxActifs
        Variants {
            model: Quickshell.screens
            ReserveIle {}
        }
    }
    // Vue de toutes les fenêtres (Super + A, trois doigts vers le haut, coin actif) : chargée seulement à l'ouverture.
    // Elle utilise la capture d'écran de Quickshell, absente de certains paquets : sans elle, seule la vue manque
    // (un message le dit) ; déclarée ici directement, c'est toute l'île qui ne se chargeait plus.
    property Component composantVue: null
    property var vues: []
    // Cockpit chargé seulement à la demande ; aucune capture ni connexion de backend au démarrage.
    property var jarvisFenetre: null
    property Component composantJarvis: null
    // Tiroir de chat JARVIS (Super + Maj + A, nc-jarvis chat) : pré-chauffé en asynchrone sans bloquer l'interface
    property var jarvisChatFenetre: null
    property Component composantJarvisChat: null
    property var incubateurJarvisChat: null
    property var jarvisChatEnAttente: null
    Timer {
        id: prechauffeJarvisChat
        interval: 2500
        running: Reglages.val("IA_MODE", "auto") !== "non"
        repeat: false
        onTriggered: racine.preparerJarvisChat()
    }
    function preparerJarvisChat() {
        if (racine.jarvisChatFenetre || racine.incubateurJarvisChat) return
        if (!racine.composantJarvisChat) racine.composantJarvisChat = Qt.createComponent("JarvisChat.qml")
        if (racine.composantJarvisChat.status !== Component.Ready) {
            console.warn("Chat JARVIS indisponible : " + racine.composantJarvisChat.errorString())
            racine.jarvisChatEnAttente = null
            return
        }
        const inc = racine.composantJarvisChat.incubateObject(racine, {}, Qt.Asynchronous)
        if (!inc) return
        const finaliser = function () {
            if (inc.status === Component.Ready) {
                racine.jarvisChatFenetre = inc.object
                racine.incubateurJarvisChat = null
                racine.brancherIle(racine.jarvisChatFenetre)
                const attente = racine.jarvisChatEnAttente
                racine.jarvisChatEnAttente = null
                if (attente && racine.jarvisChatFenetre) {
                    if (attente.action === "echange") racine.jarvisChatFenetre.montrerEchange(attente.ecran)
                    else racine.jarvisChatFenetre.basculer(attente.ecran)
                }
            } else if (inc.status === Component.Error) {
                racine.incubateurJarvisChat = null
                racine.jarvisChatEnAttente = null
            }
        }
        if (inc.status !== Component.Loading) {
            finaliser()
        } else {
            racine.incubateurJarvisChat = inc
            inc.onStatusChanged = finaliser
        }
    }
    // Fenêtre « Connexion JARVIS » (nc-assistant configurer) : créée à la demande
    property var connexionFenetre: null
    property Component composantConnexion: null
    // Fenêtre « Clés des IA » (nc-ia configurer), créée à la demande
    property var clesFenetre: null
    property Component composantCles: null
    // Fenêtre des réglages (Super + Alt + , ; nc-reglages fenetre) : une fenêtre classique, créée à la demande
    property var reglagesFenetre: null
    property Component composantReglages: null
    // Raccourci d'une fenêtre-outil déjà ouverte (réglages, cockpit, chat JARVIS) : nc-fenetre outil décide — sur un
    // autre bureau ou masquée, elle vient sur le bureau affiché ; ici derrière, elle passe devant ; ici et active, elle
    // est masquée comme avec Super + H (rangée ou libre, elle garde sa forme). Introuvable dans Hyprland : fermée.
    Process {
        id: outil
        property var fenetre: null
        onExited: (code, status) => { if (code === 3 && outil.fenetre) outil.fenetre.close(); outil.fenetre = null }
    }
    // Une fenêtre-outil sait si l'île est ouverte : Échap ferme alors l'île, pas la fenêtre
    function brancherIle(fenetre) {
        if (!fenetre) return
        fenetre.ileOuverte = Qt.binding(() => Etat.ecranOuvert !== "")
        fenetre.fermerIle.connect(() => { Etat.fermer(); Etat.projection = false })
    }
    function basculerOutil(fenetre, titre) {
        if (outil.running) return
        outil.fenetre = fenetre
        outil.command = [Quickshell.env("HOME") + "/.local/bin/nc-fenetre", "outil", titre]
        outil.running = true
    }
    Connections {
        target: Etat
        function onVueFenetresChanged() {
            racine.vues.forEach(v => v.destroy())
            racine.vues = []
            if (!Etat.vueFenetres) { Etat.vueCaptures = ({}); return }
            if (!racine.composantVue) racine.composantVue = Qt.createComponent("Vue.qml")
            if (racine.composantVue.status !== Component.Ready) {
                console.warn("Vue des fenêtres indisponible : " + racine.composantVue.errorString())
                Etat.vueFenetres = false
                Quickshell.execDetached(["notify-send", "-a", Reglages.t("Vue des fenêtres", "Window Overview"),
                                         Reglages.t("Vue des fenêtres indisponible", "Window Overview unavailable"),
                                         Reglages.t("Impossible de charger la vue. Consulte le journal de nc-ile pour l'erreur détaillée.", "Couldn't load the overview. Check the nc-ile journal for the detailed error.")])
                return
            }
            racine.vues = Quickshell.screens.map(s => racine.composantVue.createObject(racine, { modelData: s }))
        }
    }
    // Projection sur un second écran (Super + O, nc-ecrans) : chargée seulement à l'ouverture
    LazyLoader {
        active: Etat.projection
        Projection {}
    }
    // Aperçu d'aimantation (nc/raccourcis.lua, pendant le glisser d'une fenêtre vers un bord ou un coin) : le cadre est
    // créé seulement tant qu'une zone est annoncée, puis 300 ms de plus pour son fondu ; rien en mémoire sinon. Zones
    // reconnues : la liste fixe ci-dessous, toute autre est ignorée ; réglage AIMANT_APERCU=non : tout est ignoré.
    readonly property var aimantZones: ["haut", "gauche", "droite", "haut-gauche", "haut-droite", "bas-gauche", "bas-droite"]
    property string aimantZone: ""
    property int aimantX: 0
    property int aimantY: 0
    property int aimantW: 0
    property int aimantH: 0
    property bool aimantCharge: false
    // L'écran qui contient le centre du rectangle (coordonnées logiques globales), sinon le premier
    readonly property var aimantEcran: Quickshell.screens.find(s => racine.aimantX + racine.aimantW / 2 >= s.x
                                                                  && racine.aimantX + racine.aimantW / 2 < s.x + s.width
                                                                  && racine.aimantY + racine.aimantH / 2 >= s.y
                                                                  && racine.aimantY + racine.aimantH / 2 < s.y + s.height) || Quickshell.screens[0]
    Timer {
        id: aimantFin
        interval: 300
        onTriggered: racine.aimantCharge = false
    }
    LazyLoader {
        id: aimantChargeur
        active: racine.aimantCharge
        AimantApercu {
            screen: racine.aimantEcran
            montre: racine.aimantZone !== ""
            rx: racine.aimantX
            ry: racine.aimantY
            rw: racine.aimantW
            rh: racine.aimantH
        }
    }
    // Fiche des raccourcis (Super + /), éditable : créée à l'ouverture, sur l'écran actif ; sans l'île Quickshell,
    // Super + / ouvre la fiche de Noctalia
    property bool ficheOuverte: false
    // Un seul Component.onCompleted par objet (deux : « Property value set multiple times », l'île ne démarre plus)
    Component.onCompleted: {
        Raccourcis.relire()          // le catalogue est prêt avant la première ouverture de la fiche
        Rappels.demarrer()           // rappels de la recherche (Rappels.qml) : relit la liste, montre les échus de l'arrêt
        racine.effacerEpingles("")   // aucune capture épinglée n'est ouverte au démarrage : leurs copies restantes sont effacées
        Chaleur.demarrer()           // veille de surchauffe (Chaleur.qml) : un « nc-ile-etat capteurs », puis deux fichiers
                                     // du noyau relus toutes les 20 s écran allumé ; rien sur une machine sans capteur
    }
    // Créée seulement une fois ses raccourcis connus : jamais une carte vide
    LazyLoader {
        id: chargeurFiche
        active: racine.ficheOuverte && Raccourcis.lignes.length > 0
        Fiche {
            screen: Quickshell.screens.find(s => Hyprland.focusedMonitor && s.name === Hyprland.focusedMonitor.name) || Quickshell.screens[0]
            // Place réservée en haut par la barre (hyprctl monitors : reserved = gauche, haut, droite, bas)
            hautReserve: { var m = Hyprland.focusedMonitor, r = m && m.lastIpcObject ? m.lastIpcObject.reserved : null
                           return r && r.length > 1 ? r[1] : Gabarit.barre }
            onFermer: racine.ficheOuverte = false
        }
    }
    // Espace de code (Super + X, nc-code) : le sélecteur de projets façon Raycast, créé à l'ouverture seulement ; sans
    // l'île, nc-code ouvre le même sélecteur dans une fenêtre kitty
    property bool codeOuvert: false
    LazyLoader {
        id: chargeurCode
        active: racine.codeOuvert
        Code {
            screen: Quickshell.screens.find(s => Hyprland.focusedMonitor && s.name === Hyprland.focusedMonitor.name) || Quickshell.screens[0]
            onFermer: racine.codeOuvert = false
        }
    }
    // Panneau VPN (Super + Alt + V, nc-vpn) : les tunnels VPN et WireGuard de NetworkManager ; créé à l'ouverture seulement
    property bool vpnOuvert: false
    LazyLoader {
        id: chargeurVpn
        active: racine.vpnOuvert
        Vpn {
            screen: Quickshell.screens.find(s => Hyprland.focusedMonitor && s.name === Hyprland.focusedMonitor.name) || Quickshell.screens[0]
            onFermer: racine.vpnOuvert = false
        }
    }
    Connections {
        target: VpnEtat
        function onOuvrirPanneau() { if (!racine.vpnOuvert) { Etat.fermer(); Hyprland.refreshMonitors(); racine.vpnOuvert = true } }
    }
    // Panneau Santé Garmin (Super + Alt + S, nc-garmin) : créé à l'ouverture seulement
    property bool garminOuvert: false
    LazyLoader {
        id: chargeurGarmin
        active: racine.garminOuvert
        Garmin {
            screen: Quickshell.screens.find(s => Hyprland.focusedMonitor && s.name === Hyprland.focusedMonitor.name) || Quickshell.screens[0]
            onFermer: racine.garminOuvert = false
        }
    }
    Connections {
        target: GarminEtat
        function onOuvrirPanneau() { if (!racine.garminOuvert) { Etat.fermer(); Hyprland.refreshMonitors(); racine.garminOuvert = true } }
    }
    function barreControlePourEcran(ecran, bord) {
        if (!ecran) return null
        const description = Hyprland.monitorFor(ecran)?.lastIpcObject?.description ?? ""
        const barres = Disposition.barresPourEcran(racine.modelePanneaux.barres ?? [], ecran.name, description)
        return Disposition.barreControle(barres, racine.modelePanneaux.widgets ?? {}, bord)
    }
    function reservesPourEcran(ecran) {
        var m = ecran ? Hyprland.monitorFor(ecran) : Hyprland.focusedMonitor
        var r = m && m.lastIpcObject ? m.lastIpcObject.reserved : null
        if (r && r.length >= 4) return { gauche: r[0], haut: r[1], droite: r[2], bas: r[3] }
        return { gauche: 0, haut: Gabarit.barre, droite: 0, bas: 0 }
    }
    function bordControlePourReserves(res) {
        if (res.bas > 0 && res.bas >= res.haut) return "bottom"
        if (res.haut > 0) return "top"
        return res.droite > res.gauche ? "right" : res.gauche > 0 ? "left" : "top"
    }
    // Panneau Centre de contrôle dédié (Super + C ; icônes de la barre ; bouton de l'île) : chargé à l'ouverture seulement
    LazyLoader {
        id: chargeurControle
        active: Etat.controleOuvert
        PanneauControle {
            id: controleFenetre
            readonly property var _ecranCible: Quickshell.screens.find(s => s.name === Etat.controleEcran)
                    || Quickshell.screens.find(s => Hyprland.focusedMonitor && s.name === Hyprland.focusedMonitor.name)
                    || Quickshell.screens[0]
            readonly property var _reserves: racine.reservesPourEcran(_ecranCible)
            screen: _ecranCible
            readonly property var _barre: racine.barreControlePourEcran(_ecranCible, Etat.controleBord)
            readonly property var _moniteur: _ecranCible ? Hyprland.monitorFor(_ecranCible)?.lastIpcObject : null
            property var _calques: ({})
            readonly property var _barreNative: !_barre && _moniteur
                ? Disposition.barreNativeControle(_calques[_ecranCible.name], _moniteur.x, _moniteur.y,
                    _ecranCible.width, _ecranCible.height, Etat.controleAncre) : null
            readonly property real _empriseBarre: _barre ? Math.ceil(_barre.thickness ?? 36) + Math.round(_barre.margin_edge ?? 0)
                : _barreNative?.emprise ?? 0
            bord: Etat.controleBord || (_barre ? _barre.position ?? "top" : _barreNative?.bord ?? racine.bordControlePourReserves(_reserves))
            gaucheReserve: Math.max(_reserves.gauche, bord === "left" ? _empriseBarre : 0)
            ancre: Etat.controleAncre
            hautReserve: Math.max(_reserves.haut, bord === "top" ? _empriseBarre : 0)
            droiteReserve: Math.max(_reserves.droite, bord === "right" ? _empriseBarre : 0)
            basReserve: Math.max(_reserves.bas, bord === "bottom" ? _empriseBarre : 0)
            onFermer: Etat.fermerControle()
            onOuvrirThemes: { Etat.fermerControle(); Hyprland.refreshMonitors(); racine.themesOuvert = true }
            Process {
                command: ["hyprctl", "-j", "layers"]
                running: !racine.panneauxActifs
                stdout: StdioCollector {
                    onStreamFinished: {
                        try { controleFenetre._calques = JSON.parse(text) }
                        catch (_) { /* Réserves du moniteur en repli. */ }
                    }
                }
            }
        }
    }
    // Carrousel des thèmes (Super + Alt + T, recherche « Thèmes ») : créé à l'ouverture seulement
    property bool themesOuvert: false
    LazyLoader {
        id: chargeurThemes
        active: racine.themesOuvert
        ChoixTheme {
            screen: Quickshell.screens.find(s => Hyprland.focusedMonitor && s.name === Hyprland.focusedMonitor.name) || Quickshell.screens[0]
            onFermer: racine.themesOuvert = false
        }
    }
    // $XDG_RUNTIME_DIR/nc-epingles ; elle est effacée à la fermeture, au remplacement et au démarrage de l'île.
    property string epingleChemin: ""
    readonly property string epingleDossier: (Quickshell.env("XDG_RUNTIME_DIR") || "") + "/nc-epingles"
    function epingler(chemin) {
        var nom = String(chemin).slice(racine.epingleDossier.length + 1)
        // seulement un fichier au nom aléatoire de nc-capture, directement dans le bon dossier
        if (!Quickshell.env("XDG_RUNTIME_DIR") || String(chemin) !== racine.epingleDossier + "/" + nom || !/^[A-Za-z0-9]{10}\.(png|jpg)$/.test(nom)) return
        racine.epingleChemin = String(chemin)
        racine.effacerEpingles(nom)
    }
    function effacerEpingles(garder) {
        if (!Quickshell.env("XDG_RUNTIME_DIR") || effaceur.running) return
        var c = ["find", racine.epingleDossier, "-maxdepth", "1", "-type", "f"]
        if (garder !== "") c.push("!", "-name", garder)
        c.push("-delete")
        effaceur.command = c
        effaceur.running = true
    }
    Process { id: effaceur }
    LazyLoader {
        id: chargeurEpingle
        active: racine.epingleChemin !== ""
        CaptureEpinglee {
            chemin: racine.epingleChemin
            screen: Quickshell.screens.find(s => Hyprland.focusedMonitor && s.name === Hyprland.focusedMonitor.name) || Quickshell.screens[0]
            onFermer: { racine.epingleChemin = ""; racine.effacerEpingles("") }
        }
    }
    // Panneau Cloud JARVIS (IPC cloud, recherche, nc-cloud fenetre) : créé à l'ouverture seulement, si CLOUD_JARVIS=oui
    property bool cloudOuvert: false
    onCloudOuvertChanged: if (cloudOuvert && !CloudEtat.actif) cloudOuvert = false
    // L'écran du panneau est celui qui a le focus À L'OUVERTURE, puis il y reste : jamais lié au moniteur actif en continu
    // (changer d'écran ne le déplace ni ne le ferme)
    property var ecranCloud: null
    function ouvrirCloud() {
        if (racine.cloudOuvert || !CloudEtat.actif) return
        Etat.fermer()
        Hyprland.refreshMonitors()
        racine.ecranCloud = Quickshell.screens.find(s => Hyprland.focusedMonitor && s.name === Hyprland.focusedMonitor.name) || Quickshell.screens[0]
        racine.cloudOuvert = true
    }
    LazyLoader {
        id: chargeurCloud
        active: racine.cloudOuvert
        CloudPanneau {
            screen: racine.ecranCloud
            onFermer: racine.cloudOuvert = false
        }
    }
    Connections {
        target: CloudEtat
        function onOuvrirPanneau() { racine.ouvrirCloud() }
        function onBasculerPanneau() {
            if (racine.cloudOuvert) racine.cloudOuvert = false
            else racine.ouvrirCloud()
        }
    }
    // Coins actifs (nc-reglages → Clavier et souris)
    Variants {
        model: Quickshell.screens
        Coins {}
    }
    // Terminal déroulant sorti : un clic sur le bureau vide à côté le range
    RangeTerminal {}
    // Fond du jour et fond de la nuit (FONDS_JOUR_NUIT) : lance nc-fond-jour-nuit aux bons moments, rien d'autre
    FondJourNuit {}
    // Rappel de débrancher quand la charge atteint le seuil (BAT_RAPPEL_80) : une fois par branchement, sans sondage
    BatRappel80 {}
    // Fond d'écran animé (nc-reglages → Fonds d'écran : aurore ou vivant) : créé seulement s'il est choisi
    Variants {
        model: ["aurore", "vivant"].indexOf(Reglages.val("FOND_ANIME", "non")) >= 0 && !Reglages.sobre ? Quickshell.screens : []
        Fond { vivant: Reglages.val("FOND_ANIME", "non") === "vivant" }
    }
    // Widgets du bureau (nc-reglages → Île → WIDGETS_BUREAU) : créés seulement à « oui » ; rallumés, ils se montrent
    // même si « Tout masquer » les avait cachés avant
    readonly property bool widgetsBureau: Reglages.val("WIDGETS_BUREAU", "non") === "oui"
    onWidgetsBureauChanged: if (widgetsBureau) Etat.widgetsCaches = false
    Variants {
        model: Reglages.val("WIDGETS_BUREAU", "non") === "oui" ? Quickshell.screens : []
        Bureau {}
    }
    // Widgets choisis par le thème (champ « widgets ») : un seul objet, ses fenêtres sont par écran ; rien en mémoire sans eux
    LazyLoader {
        active: Reglages.val("WIDGETS_BUREAU", "non") === "oui" && Reglages.val("WIDGETS_THEME", "") !== ""
        WidgetsTheme {}
    }

    IpcHandler {
        target: "ile"
        // Le réglage demandé et le modèle exporté sont relus indépendamment. Un vieux modèle ne peut pas acquitter
        // une bascule ; nc-reglages vérifie aussi les surfaces mappées avant de masquer la barre Noctalia.
        function panneauxPrets(generation: string): string {
            return racine.panneauxActifs && Quickshell.screens.length > 0
                && Reglages.val("BARRE_MODULAIRE", "non") === "oui"
                && ecransIle.instances.length === Quickshell.screens.length
                && ecransIle.instances.every(ile => ile.panneauxRendus)
                && racine.modelePanneaux.generation === generation ? generation : ""
        }
        function basculer(): void { Etat.basculer(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : (Quickshell.screens.length ? Quickshell.screens[0].name : ""), true) }
        function ouvrir(): void { Etat.basculer(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : (Quickshell.screens.length ? Quickshell.screens[0].name : ""), false) }
        function controle(): void {
            Hyprland.refreshMonitors()
            Etat.basculerControle(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : (Quickshell.screens.length ? Quickshell.screens[0].name : ""), "accueil")
        }
        function controlePage(nom: string): void {
            Hyprland.refreshMonitors()
            Etat.basculerControle(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : (Quickshell.screens.length ? Quickshell.screens[0].name : ""), nom)
        }
        // Noctalia ne transmet pas le rectangle d'un bouton IPC ; le point cliqué reste en pixels logiques globaux.
        function controleWidget(nom: string, repli: string, pointeur: string): void {
            const cible = repli ? Etat.pageOu(nom, repli) : nom
            if (!Etat.estPageControle(cible)) { page(cible); return }
            let pos
            try { pos = JSON.parse(pointeur) } catch (_) { controlePage(cible); return }
            const ecran = Quickshell.screens.find(s => pos && pos.x >= s.x && pos.x < s.x + s.width
                                                         && pos.y >= s.y && pos.y < s.y + s.height)
            if (!ecran) { controlePage(cible); return }
            Hyprland.refreshMonitors()
            Etat.basculerControle(ecran.name, cible, "", Qt.rect(pos.x - ecran.x, pos.y - ecran.y, 1, 1))
        }
        function fermer(): void { Etat.fermer(); Etat.fermerControle(); Etat.projection = false }
        function fiche(): void {                                                            // Super + /
            Etat.fermer(); Etat.fermerControle()
            if (racine.ficheOuverte && chargeurFiche.item) chargeurFiche.item.quitter()          // comme Échap
            else { Hyprland.refreshMonitors(); Raccourcis.relire(); racine.ficheOuverte = !racine.ficheOuverte }
        }
        // Espace de code (Super + X, par nc-code) : ouvre le sélecteur de projets ; déjà ouvert, le referme
        function code(): void {
            Etat.fermer(); Etat.fermerControle()
            // Déjà ouvert : il se referme comme Échap (en rétrécissant vers la pilule si ILE_LANCEUR_FONDU)
            if (racine.codeOuvert && chargeurCode.item) { chargeurCode.item.quitter(); return }
            if (!racine.codeOuvert) Hyprland.refreshMonitors()
            racine.codeOuvert = !racine.codeOuvert
        }
        // Panneau VPN (Super + Alt + V, nc-vpn) : ouvre ; déjà ouvert, le referme
        function vpn(): void {
            Etat.fermer(); Etat.fermerControle()
            if (!racine.vpnOuvert) Hyprland.refreshMonitors()
            racine.vpnOuvert = !racine.vpnOuvert
        }
        // Panneau Santé Garmin (Super + Alt + S) : ouvre ; déjà ouvert, le referme
        function garmin(): void {
            Etat.fermer(); Etat.fermerControle()
            if (!racine.garminOuvert) Hyprland.refreshMonitors()
            racine.garminOuvert = !racine.garminOuvert
        }
        // Épingle une capture (nc-capture epingler) : le chemin doit être une copie de nc-epingles
        function epingler(chemin: string): void { racine.epingler(chemin) }
        // Carrousel des thèmes (Super + Alt + T) : ouvre ; déjà ouvert, le referme
        function themes(): void {
            Etat.fermer(); Etat.fermerControle()
            if (!racine.themesOuvert) Hyprland.refreshMonitors()
            racine.themesOuvert = !racine.themesOuvert
        }
        // Panneau Cloud JARVIS (nc-cloud fenetre, recherche) : sans argument, ouvre (déjà ouvert : rien ; il ne se ferme que
        // par l'utilisateur) ; rien si CLOUD_JARVIS n'est pas à oui
        function cloud(): void { Etat.fermerControle(); racine.ouvrirCloud() }
        function pomodoro(): void { if (Etat.pomodoro) Etat.arreterMinuteur(); else Etat.lancerPomodoro() }
        function vue(): void { if (Etat.vueFenetres) vueFermer(); else vueOuvrir() }
        function vueOuvrir(): void { Etat.fermer(); Etat.fermerControle(); Etat.vueFenetres = true }
        function vuePause(oui: bool): void { Etat.vuePause = oui }      // nc-capture, le temps de choisir une zone
        // nc-session, le temps de capturer l'aperçu d'une session : aucune bannière dessus (reprise seule après 3 s)
        function bannieresPause(oui: bool): string { Notifs.pauseBannieres(oui); return "oui" }
        // Par la vue elle-même : elle va sur le bureau choisi, en grandissant
        function vueFermer(): void { if (racine.vues.length) racine.vues.slice().forEach(v => v.fermer()); else Etat.vueFenetres = false }
        // Projection (Super + O) : ouvre la fenêtre ; déjà ouverte, la referme
        function projection(): void {
            if (Etat.projection) { Etat.projection = false; return }
            Etat.fermer(); Etat.fermerControle()
            Etat.projection = true
        }
        function rechercher(texte: string): void {
            Etat.saisie = texte
            if (!Etat.recherche) recherche()
        }
        function valider(): void { Etat.validerRecherche() }
        // L'IA qui agit, sur cette demande (nc-ia organiser) : le Spotlight sur « @ », le plan demandé tout de suite
        function agirIA(demande: string, portee: string): void {
            Etat.saisie = "@ " + demande; Etat.agirAuto = true; Etat.agirPortee = portee
            if (!Etat.recherche) recherche()
        }
        function recherche(): void { Etat.chercher(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : (Quickshell.screens.length ? Quickshell.screens[0].name : "")) }
        function suivante(): void { Etat.changerVue(1) }
        function precedente(): void { Etat.changerVue(-1) }
        // Mode graphique (nc-reglages → Énergie, nc-gpu-mode) : la carte de confirmation, vers l'autre mode ou vers
        // celui-ci (hybride, dediee) ; rien ne redémarre avant son bouton
        function gpuMode(): void { Etat.fermer(); ModeGraphique.demander("") }
        function gpuModeVers(cible: string): void { Etat.fermer(); ModeGraphique.demander(cible) }
        // JARVIS veut agir sur ce PC (nc-noeud) : la demande est relue, la carte de confirmation s'ouvre (ou se ferme si
        // la demande est partie) ; « oui » dit à nc-noeud que l'île est là pour répondre
        function noeud(): string { Noeud.relire(); return "oui" }
        // Aperçu d'aimantation : ZONE de la liste fixe (aimantZones) ou "" pour l'effacer ; le rectangle est en pixels logiques
        function aimant(zone: string, x: int, y: int, w: int, h: int): void {
            if (Reglages.val("AIMANT_APERCU", "oui") === "non") return
            if (zone === "") {
                racine.aimantZone = ""
                if (racine.aimantCharge) aimantFin.restart()
                return
            }
            if (racine.aimantZones.indexOf(zone) < 0 || w <= 0 || h <= 0 || Math.abs(x) > 100000 || Math.abs(y) > 100000 || w > 100000 || h > 100000) return
            racine.aimantX = x; racine.aimantY = y; racine.aimantW = w; racine.aimantH = h
            racine.aimantZone = zone
            aimantFin.stop()
            racine.aimantCharge = true
        }
        function luminosite(): void { Etat.lireLuminosite(true) }
        function volume(): void { Etat.activite("volume") }
        function media(): void {}
        function notifications(): void {
            if (Couleurs.themeActif === "sakura") { page("notifications"); return }
            Etat.basculer(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : (Quickshell.screens.length ? Quickshell.screens[0].name : ""), true)
            Etat.aller("notifications")
        }
        function effacerNotifications(): void { Notifs.toutEffacer() }
        function concentration(): void { Notifs.basculerConcentration() }
        function concentrationRegler(actif: bool): void { Notifs.concentration = actif }   // mode jeu
        function concentrationEtat(): string { return Notifs.concentration ? "oui" : "non" }
        function cafeRegler(actif: bool): void { Etat.cafeRegler(actif) }   // mode Présentation
        function cafeEtat(): string { return Etat.cafe ? "oui" : "non" }
        // Ouvre une page : sur l'île si elle y est activée, sinon dans le panneau Centre de contrôle si c'est un outil rapide
        function page(nom: string): void {
            var cible = nom === "wifi" ? "reseau" : nom
            if (Etat.estPageControle(cible)) { controlePage(cible); return }
            if (Etat.vues.indexOf(cible) >= 0) {
                if (cible === "assistant" && racine.jarvisFenetre) racine.jarvisFenetre.close()
                if (Etat.ecranOuvert !== "" && !Etat.recherche && Etat.vueActive === cible) { Etat.fermer(); return }
                if (Couleurs.themeActif === "sakura" && (cible === "notifications" || cible === "musique")) {
                    const ecran = Etat.ecranOuvert || Hyprland.focusedMonitor?.name || Quickshell.screens[0]?.name || ""
                    Etat.ouvrirContexteSakura(ecran, cible)
                    return
                }
                if (Etat.ecranOuvert === "") basculer()
                Etat.aller(cible)
                return
            }
        }
        // Notification d'un agent qui t'attend, cliquée (« Voir », nc-claude) : l'île sur sa question, jamais refermée
        // (sa demande avec ses choix, sinon sa session en tête de la page des agents, avec le texte entier)
        // « non » : page des agents coupée dans les réglages, nc-claude va alors sur le terminal
        function agent(session: string): string {
            if (!Reglages.pageActive("claude")) return "non"
            if (Etat.ecranOuvert === "") basculer()
            Agents.montrer(session)
            return "oui"
        }
        // La même, avec une page de repli si celle-ci n'existe pas (coupée dans les réglages, PC sans batterie…)
        function pageOu(nom: string, repli: string): void {
            page(Etat.pageOu(nom, repli))
        }
        function jarvis(): void {
            if (racine.jarvisChatFenetre && racine.jarvisChatFenetre.visible && !racine.jarvisChatFenetre.epingle)
                racine.jarvisChatFenetre.fermerTiroir()
            if (racine.jarvisFenetre && racine.jarvisFenetre.visible) { racine.basculerOutil(racine.jarvisFenetre, "JARVIS"); return }
            Etat.fermer()
            if (!racine.jarvisFenetre) {
                if (!racine.composantJarvis) racine.composantJarvis = Qt.createComponent("Jarvis.qml")
                if (racine.composantJarvis.status !== Component.Ready) {
                    console.warn("Cockpit JARVIS indisponible : " + racine.composantJarvis.errorString())
                    return
                }
                racine.jarvisFenetre = racine.composantJarvis.createObject(racine)
                racine.brancherIle(racine.jarvisFenetre)
            }
            if (racine.jarvisFenetre) {
                racine.jarvisFenetre.afficher(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "")
            }
        }
        function jarvisFermer(): void { if (racine.jarvisFenetre) racine.jarvisFenetre.close() }
        // Tiroir de chat JARVIS : bascule réversible depuis la pilule de l'île (ou mis en attente pendant le pré-chauffage)
        function jarvisChat(): void {
            const ecran = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : ""
            if (racine.jarvisChatFenetre) { racine.jarvisChatFenetre.basculer(ecran); return }
            racine.jarvisChatEnAttente = { action: "basculer", ecran: ecran }
            racine.preparerJarvisChat()
        }
        // Une réponse de l'IA du bureau (nc-ia : fichier d'échange privé), versée dans la conversation
        function iaReponse(chemin: string): void { AssistantEtat.recevoirReponse(chemin) }
        // Notification de cette réponse cliquée : le tiroir de chat, sur l'échange
        function chatReponse(): void {
            const ecran = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : ""
            if (racine.jarvisChatFenetre) { racine.jarvisChatFenetre.montrerEchange(ecran); return }
            racine.jarvisChatEnAttente = { action: "echange", ecran: ecran }
            racine.preparerJarvisChat()
        }
        function jarvisChatFermer(): void {
            racine.jarvisChatEnAttente = null
            if (racine.jarvisChatFenetre) racine.jarvisChatFenetre.close()
        }
        // Réglages en fenêtre : déjà ouverte, le même appel la ramène ici, la met devant ou la range (basculerOutil)
        function reglages(): void {
            if (racine.reglagesFenetre && racine.reglagesFenetre.visible) { racine.basculerOutil(racine.reglagesFenetre, Reglages.t("Réglages du bureau", "Desktop settings")); return }
            if (!racine.reglagesFenetre) {
                if (!racine.composantReglages) racine.composantReglages = Qt.createComponent("Parametres.qml")
                if (racine.composantReglages.status !== Component.Ready) {
                    console.warn("Fenêtre des réglages indisponible : " + racine.composantReglages.errorString())
                    return
                }
                racine.reglagesFenetre = racine.composantReglages.createObject(racine)
                racine.brancherIle(racine.reglagesFenetre)
            }
            if (racine.reglagesFenetre) racine.reglagesFenetre.afficher(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "")
        }
        function reglagesFermer(): void { if (racine.reglagesFenetre) racine.reglagesFenetre.close() }
        // Réglages ouverts sur une recherche (réponses du Spotlight) : la fenêtre vient au premier plan, recherche tapée
        function reglagesChercher(texte: string): void {
            if (!racine.reglagesFenetre || !racine.reglagesFenetre.visible) reglages()
            if (racine.reglagesFenetre) racine.reglagesFenetre.chercherTexte(texte)
        }
        // Réglages ouverts sur une section (nc-reglages fenetre SECTION : Raccourcis, Nouveautés…), nom tel qu'affiché
        function reglagesSection(nom: string): void {
            if (!racine.reglagesFenetre || !racine.reglagesFenetre.visible) reglages()
            if (racine.reglagesFenetre) racine.reglagesFenetre.allerSection(nom)
        }
        // Connexion à JARVIS en graphique (adresse, clé, test) ; déjà ouverte : ramenée ici, mise devant ou rangée
        // Fenêtre « Clés des IA » (nc-ia configurer, réglages → Clés d'API des IA)
        function clesIA(): void {
            if (racine.clesFenetre && racine.clesFenetre.visible) { racine.basculerOutil(racine.clesFenetre, Reglages.t("Clés des IA", "AI keys")); return }
            if (!racine.clesFenetre) {
                if (!racine.composantCles) racine.composantCles = Qt.createComponent("ClesIA.qml")
                if (racine.composantCles.status !== Component.Ready) {
                    console.warn("Fenêtre des clés des IA indisponible : " + racine.composantCles.errorString())
                    return
                }
                racine.clesFenetre = racine.composantCles.createObject(racine)
                racine.brancherIle(racine.clesFenetre)
            }
            if (racine.clesFenetre) racine.clesFenetre.afficher(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "")
        }
        function connexionJarvis(): void {
            if (racine.connexionFenetre && racine.connexionFenetre.visible) { racine.basculerOutil(racine.connexionFenetre, Reglages.t("Connexion JARVIS", "JARVIS connection")); return }
            if (!racine.connexionFenetre) {
                if (!racine.composantConnexion) racine.composantConnexion = Qt.createComponent("ConnexionJarvis.qml")
                if (racine.composantConnexion.status !== Component.Ready) {
                    console.warn("Fenêtre de connexion JARVIS indisponible : " + racine.composantConnexion.errorString())
                    return
                }
                racine.connexionFenetre = racine.composantConnexion.createObject(racine)
                racine.brancherIle(racine.connexionFenetre)
            }
            if (racine.connexionFenetre) racine.connexionFenetre.afficher(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "")
        }
    }
}
