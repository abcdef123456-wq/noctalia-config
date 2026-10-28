// Une île par écran : pilule noire posée sur la barre de Noctalia (couche au-dessus), qui se déploie avec un ressort,
// comme l'île dynamique de l'iPhone. Ouverte, ses pages se suivent verticalement : d'abord les activités en cours
// (musique, minuteur, recharge, mode jeu), puis le centre de contrôle, Son, Wi-Fi, Bluetooth, Système, Calendrier.
// Points sur le bord droit, molette ou deux doigts pour descendre ; l'île prend la taille de chaque page.
// Deux activités en même temps (musique + minuteur) : la seconde dans une petite bulle à côté de la pilule.
// Seule la forme de l'île capte la souris ; un clic ailleurs, Échap, Super + C ou un clic sur la pilule la referment.
import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland

PanelWindow {
    id: fen
    required property var modelData
    screen: modelData
    readonly property bool ouverte: Etat.ecranOuvert === modelData.name

    // Recherche : la fenêtre couvre tout l'écran (invisible) pour qu'un clic à côté la referme. L'île prend alors le
    // clavier en exclusif, et Hyprland ne laisse aucun clic arriver ailleurs : une couche séparée ne les recevait pas
    // Toujours ancrée en haut seulement : en recherche, la surface prend la taille de l'écran. Changer les ancres faisait
    // disparaître l'île quelques images, et changer la géométrie pendant le ressort la faisait sauter d'un côté à l'autre :
    // pleinEcran reste donc vrai après la recherche, le temps que l'île revienne à sa taille
    anchors.top: true
    readonly property bool pleinEcran: recherche || retourRecherche.running
    onRechercheChanged: if (recherche) retourRecherche.stop(); else { retourRecherche.restart(); repos.restart() }
    Timer { id: retourRecherche; interval: 900 }
    // Hors recherche, la surface suit la taille utile de l'île, centrée en haut par Hyprland : Qt redessine toute la
    // fenêtre à chaque image, et Hyprland recompose toute la zone. Une surface de 1600 x 700 pour une pilule de
    // 200 x 30 coûtait les trois quarts de l'iGPU dès que quelque chose bougeait dans l'île (étincelle, onde, minuteur).
    // Largeur fixe de 800 (le coût est par image, pas par pixel) : une couche centrée en haut qui change de largeur est
    // recentrée par Hyprland avec une image de retard, et l'île faisait un saut de côté en se refermant (issue #13).
    // Seule la hauteur change (56 pour la pilule, 700 ouverte, en bannière ou en demande) : le bord haut reste fixe.
    // À l'ouverture, la surface grandit dans le même tour ; à la fermeture, elle ne rapetisse qu'une fois les ressorts au
    // repos (taille voulue à 0,5 près pendant 120 ms, 900 ms au plus), sinon l'île serait coupée pendant son rebond
    readonly property bool grandeVoulue: ouverte || banniere || enCarte
    readonly property bool grande: grandeVoulue || retour.running
    onGrandeVoulueChanged: if (grandeVoulue) retour.stop(); else { retour.restart(); repos.restart() }
    Timer { id: retour; interval: 900 }
    // Appelée à chaque pas des ressorts : le repos n'est constaté qu'après 120 ms sans mouvement (un ressort passe sous sa
    // cible avant de rebondir)
    function revenue() { if (retour.running || retourRecherche.running) repos.restart() }
    Timer {
        id: repos
        interval: 120
        onTriggered: if (Math.abs(ile.width - ile.cibleLargeur) <= 0.5 && Math.abs(ile.height - ile.cibleHauteur) <= 0.5) {
            retour.stop(); retourRecherche.stop()
        }
    }
    implicitWidth: pleinEcran ? modelData.width : Math.min(modelData.width, 800)
    implicitHeight: pleinEcran ? modelData.height : (grande ? 700 : 56)
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "nc-ile"
    // Recherche : le clavier va tout de suite à l'île ; sinon seulement quand on clique dedans
    WlrLayershell.keyboardFocus: recherche ? WlrKeyboardFocus.Exclusive : (ouverte ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None)
    readonly property bool recherche: ouverte && Etat.recherche
    mask: Region { item: fen.recherche ? fondClic : ile; Region { item: bulle } }

    // Clic hors de l'île : elle se referme. Activé un instant après l'ouverture : en recherche, l'île prend le clavier
    // en même temps, et Hyprland annulait la prise aussitôt (l'île se refermait seule)
    HyprlandFocusGrab {
        windows: [fen]
        // Ouverte au survol : pas de prise tant qu'on n'a pas cliqué dedans (elle garderait le pointeur, et l'île ne
        // saurait plus quand il en sort)
        active: fen.ouverte && prise.prete && !Etat.parSurvol
        onCleared: Etat.fermer()
    }
    Timer {
        id: prise
        property bool prete: false
        interval: 120
        onTriggered: prete = true
    }
    onOuverteChanged: { prise.prete = false; if (ouverte) prise.restart() }

    // Taille de chaque page
    function adaptee(nom, mini) { return Qt.size(432, Math.max(mini, Math.min(580, (Etat.hauteurs[nom] || mini) + 32))) }
    readonly property var tailles: ({
        musique: Qt.size(430, 214), minuteur: Qt.size(430, Etat.minuteurFin > 0 ? 150 : 334), charge: adaptee("charge", 140),
        jeu: Qt.size(432, 250), centre: adaptee("centre", 494), son: adaptee("son", 300), reseau: adaptee("reseau", 260),
        bluetooth: adaptee("bluetooth", 220), notifications: adaptee("notifications", 200), systeme: Qt.size(432, 600), sante: adaptee("sante", 300), calendrier: adaptee("calendrier", 410),
        claude: adaptee("claude", 180), assistant: Qt.size(Math.min(480, modelData.width - 32), Math.min(620, modelData.height - 80)), meteo: Qt.size(432, 330), presse: adaptee("presse", 200),
        fenetres: adaptee("fenetres", 160), appel: adaptee("appel", 150), terminal: adaptee("terminal", 150), resume: adaptee("resume", 170), concentration: adaptee("concentration", 260)
    })
    readonly property size taille: recherche ? Qt.size(680, spot.hauteurVoulue) : (tailles[Etat.vueActive] || tailles.centre)
    readonly property bool points: Etat.vues.length > 1 && !recherche
    // Notification en cours : l'île fermée s'étire en bannière (sur l'écran actif seulement)
    // Confirmation du mode graphique (ModeGraphique.qml, ConfirmationGpu.qml) : c'est toi qui l'as demandée, elle passe
    // avant tout le reste
    readonly property bool confirmGpu: !ouverte && ModeGraphique.demande
        && (!Hyprland.focusedMonitor || Hyprland.focusedMonitor.name === modelData.name)
    readonly property int hauteurGpu: chargeurGpu.item ? Math.ceil(chargeurGpu.item.implicitHeight) : 176
    // JARVIS qui veut agir sur ce PC (Noeud.qml, ConfirmationNoeud.qml, nc-noeud) : rien n'est fait sans ta réponse,
    // elle passe avant les demandes des agents et les notifications
    readonly property bool confirmNoeud: !ouverte && !confirmGpu && Noeud.demande !== null
        && (!Hyprland.focusedMonitor || Hyprland.focusedMonitor.name === modelData.name)
    readonly property int hauteurNoeud: chargeurNoeud.item ? Math.ceil(chargeurNoeud.item.implicitHeight) : 190
    // Demande de Claude Code (autoriser, question) : l'île s'étire en bannière, avant les notifications
    readonly property bool demandeClaude: !ouverte && !confirmGpu && !confirmNoeud && Agents.demande !== null
        && (!Hyprland.focusedMonitor || Hyprland.focusedMonitor.name === modelData.name)
    readonly property int hauteurDemande: Agents.demande && Agents.demande.genre === "question"
                                          ? 78 + 40 * Math.ceil((Agents.demande.options || []).length / 2) : 146
    // Session de confiance de JARVIS en cours (Noeud.qml, SessionNoeud.qml) : un bandeau avec « Arrêter la session »,
    // sous les cartes de confirmation et les demandes (il est persistant, pas urgent)
    readonly property bool sessionNoeud: !ouverte && !confirmGpu && !confirmNoeud && !demandeClaude && Noeud.sessionActive
        && (!Hyprland.focusedMonitor || Hyprland.focusedMonitor.name === modelData.name)
    readonly property int hauteurSession: chargeurSession.item ? Math.ceil(chargeurSession.item.implicitHeight) : 72
    // L'île fermée étirée en carte à boutons (demande de Claude Code, de JARVIS ou confirmation du mode graphique)
    readonly property bool enCarte: demandeClaude || confirmGpu || confirmNoeud || sessionNoeud
    readonly property bool banniere: !ouverte && !enCarte && Notifs.banniere !== null
        && (!Hyprland.focusedMonitor || Hyprland.focusedMonitor.name === modelData.name)
    readonly property int hauteurBanniere: (Notifs.banniere && Notifs.banniere.body !== "" ? 92 : 74)
                                           + (Notifs.boutons(Notifs.banniere).length > 0 ? 36 : 0)

    // Point d'activité du micro (orange) ou de la caméra (vert), à droite de la pilule, comme sur iPhone
    // Spotlight : clic n'importe où à côté = fermer (sous l'île, qui garde ses propres clics)
    Item {
        id: fondClic
        anchors.fill: parent
        MouseArea {
            anchors.fill: parent
            enabled: fen.recherche
            acceptedButtons: Qt.AllButtons
            // Fermée au relâchement : le clic entier reste ici. Fermée à l'appui, le relâchement tombait sur ce qu'il y a
            // dessous (un bouton de la barre, une fenêtre…) et le déclenchait
            onReleased: Etat.fermer()
        }
    }
    Rectangle {
        id: pointPrive
        readonly property bool montre: !fen.ouverte && !fen.banniere && !fen.enCarte && (Etat.microActif || Etat.cameraActive)
        x: ile.x + ile.width + (bulle.montre ? 44 : 9)
        y: 9 + 15 - height / 2
        width: 8; height: 8; radius: 4
        color: Etat.cameraActive ? Couleurs.vert : Couleurs.orange
        opacity: montre ? 1 : 0
        visible: opacity > 0.01
        Behavior on opacity { NumberAnimation { duration: 250 } }
        Behavior on x { SpringAnimation { spring: 3.4; damping: 0.36 } }
    }

    // Bulle de la seconde activité (minuteur pendant la musique), comme l'île scindée de l'iPhone
    Rectangle {
        id: bulle
        // Minuteur, sinon Claude Code qui travaille (étincelle), sinon une commande longue du terminal, pendant la musique
        readonly property bool minuteur: Etat.minuteurFin > 0
        readonly property bool agent: !minuteur && Agents.travaille
        readonly property bool terminal: !minuteur && !agent && Terminal.enCours
        readonly property bool montre: !fen.ouverte && !fen.banniere && !fen.enCarte && Etat.aMusique && !Appel.enCours
                                       && (minuteur || Agents.travaille || Terminal.enCours) && Etat.activiteType === ""
        x: ile.x + ile.width + (montre ? 7 : -30)
        y: 9; width: 30; height: 30; radius: 15
        color: Couleurs.fond
        opacity: montre ? 1 : 0
        visible: opacity > 0.01
        Behavior on x { SpringAnimation { spring: 3.4; damping: 0.36 } }
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Canvas {
            anchors.fill: parent
            visible: bulle.minuteur
            property real f: Etat.minuteurDuree > 0 ? Etat.minuteurReste * 1000 / Etat.minuteurDuree : 0
            onFChanged: requestPaint()
            onPaint: {
                var c = getContext("2d"); c.reset(); c.lineWidth = 2.5; c.lineCap = "round"
                c.strokeStyle = String(Couleurs.orange); c.beginPath(); c.arc(15, 15, 11, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * f); c.stroke()
            }
        }
        Ico { anchors.centerIn: parent; nom: "timer"; taille: 13; color: Couleurs.orange; visible: bulle.minuteur }
        Ico { anchors.centerIn: parent; nom: "terminal"; taille: 14; color: Couleurs.accentClair; visible: bulle.terminal }
        Etincelle { anchors.centerIn: parent; taille: 15; tourne: bulle.montre && bulle.agent; visible: bulle.agent
                    agent: Agents.agent(Agents.principale) }
        MouseArea { anchors.fill: parent; onClicked: { Etat.basculer(fen.modelData.name, false); Etat.aller(bulle.minuteur ? "minuteur" : (bulle.terminal ? "terminal" : "claude")) } }
    }

    // Contour de l'île ouverte : le dégradé de la bordure des fenêtres (comme une fenêtre active), dessiné derrière
    // l'île et dépassant de son épaisseur ; pilule fermée : sans contour, couleur du terminal (voir Couleurs.qml)
    Rectangle {
        id: cadre
        readonly property real e: (fen.ouverte || fen.banniere || fen.enCarte) && Couleurs.aContour ? 2 : 0
        x: ile.x - e; y: ile.y - e
        width: ile.width + 2 * e; height: ile.height + 2 * e
        radius: ile.radius + e
        visible: e > 0
        opacity: e > 0 ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 220 } }
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[0] }
            GradientStop { position: 0.5; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[1] }
            GradientStop { position: 1; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[2] }
        }
    }

    Rectangle {
        id: ile
        anchors.horizontalCenter: parent.horizontalCenter
        y: 9                                        // centrée dans la barre (barre à 6 du bord, 36 de haut)
        // Tailles voulues (le ressort y mène width et height) : lues par fen.revenue()
        readonly property real cibleLargeur: fen.ouverte ? fen.taille.width : (fen.enCarte ? 460 : (fen.banniere ? 440 : compact.largeur))
        readonly property real cibleHauteur: fen.ouverte ? fen.taille.height : (fen.confirmGpu ? fen.hauteurGpu : (fen.confirmNoeud ? fen.hauteurNoeud
                                                   : (fen.demandeClaude ? fen.hauteurDemande : (fen.sessionNoeud ? fen.hauteurSession
                                                   : (fen.banniere ? fen.hauteurBanniere : 30)))))
        width: cibleLargeur
        height: cibleHauteur
        radius: fen.ouverte ? (fen.recherche ? 28 : 42) : (fen.banniere || fen.enCarte ? 32 : 15)
        color: Couleurs.fond

        // Survol (nc-reglages → Île → Ouvrir au survol) : l'île s'ouvre quand le curseur s'attarde sur la pilule, et se
        // referme quand il en sort, sauf si tu as cliqué dedans (elle reste alors ouverte comme après un clic)
        HoverHandler {
            id: survol
            enabled: Reglages.val("ILE_SURVOL", "oui") !== "non"
            onHoveredChanged: if (hovered) { sortieSurvol.stop(); attenteSurvol.restart() } else { attenteSurvol.stop(); sortieSurvol.restart() }
        }
        Timer {
            id: attenteSurvol
            interval: 280                           // juste passer dessus (vers la barre) ne l'ouvre pas
            onTriggered: if (survol.hovered && Etat.ecranOuvert === "" && !fen.banniere && !fen.enCarte && !Etat.enregistre) {
                Etat.basculer(fen.modelData.name, false)
                Etat.parSurvol = true
            }
        }
        Timer {
            id: sortieSurvol
            interval: 450
            onTriggered: if (!survol.hovered && fen.ouverte && Etat.parSurvol && !Etat.recherche) Etat.fermer()
        }
        Behavior on color { ColorAnimation { duration: 260 } }
        clip: true

        // Ressort façon iOS : rapide, avec un léger rebond ; le rayon suit sans à-coup. Bannières en pause (nc-session
        // capture l'aperçu d'une session, Notifs.enPause) : l'île revient en pilule d'un coup, sans animation
        Behavior on width { enabled: !Notifs.enPause && !Partage.silence; SpringAnimation { spring: 3.4; damping: 0.34; epsilon: 0.25 } }
        Behavior on height { enabled: !Notifs.enPause && !Partage.silence; SpringAnimation { spring: 3.4; damping: 0.36; epsilon: 0.25 } }
        Behavior on radius { enabled: !Notifs.enPause && !Partage.silence; NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }
        onWidthChanged: fen.revenue()
        onHeightChanged: fen.revenue()

        Compact {
            id: compact
            anchors.centerIn: parent
            width: parent.width
            opacity: fen.ouverte || fen.banniere || fen.enCarte ? 0 : 1
            Behavior on opacity { enabled: !Notifs.enPause && !Partage.silence; NumberAnimation { duration: fen.ouverte || fen.banniere || fen.enCarte ? 90 : 220; easing.type: Easing.OutCubic } }
        }

        // Spotlight : longue capsule de recherche
        // Chargés seulement quand ils servent (mémoire), gardés le temps de l'animation de fermeture
        Loader {
            id: spot
            readonly property int hauteurVoulue: item ? item.hauteurVoulue : 56
            // Travail en cours après la fermeture (appli lancée suivie…) : reste chargé. Recopié par un signal, pas lu
            // directement sur item (active dépendrait de item, qui dépend de active : boucle de liaisons)
            property bool occupe: false
            anchors.fill: parent
            active: fen.recherche || garderSpot.running || occupe
            sourceComponent: Recherche {
                actif: fen.recherche
                opacity: fen.recherche && ile.width > 560 ? 1 : 0
                visible: opacity > 0.01
                Behavior on opacity { NumberAnimation { duration: fen.recherche ? 160 : 70; easing.type: Easing.OutCubic } }
            }
        }
        Connections {
            target: spot.item
            ignoreUnknownSignals: true
            function onOccupeChanged() { spot.occupe = spot.item ? spot.item.occupe : false }
        }
        Timer { id: garderSpot; interval: 400 }
        Connections { target: fen; function onRechercheChanged() { if (!fen.recherche) garderSpot.restart() } }

        Loader {
            anchors.fill: parent
            active: fen.banniere || (garderBanniere.running && !Notifs.enPause && !Partage.silence)    // en pause ou écran partagé : retirée tout de suite
            sourceComponent: Banniere {
                opacity: fen.banniere && ile.height > fen.hauteurBanniere * 0.7 ? 1 : 0
                visible: opacity > 0.01
                Behavior on opacity { NumberAnimation { duration: fen.banniere ? 180 : 90; easing.type: Easing.OutCubic } }
            }
        }
        Timer { id: garderBanniere; interval: 400 }
        Loader {
            anchors.fill: parent
            active: fen.demandeClaude || garderDemande.running
            sourceComponent: DemandeClaude {
                opacity: fen.demandeClaude && ile.height > fen.hauteurDemande * 0.7 ? 1 : 0
                visible: opacity > 0.01
                Behavior on opacity { NumberAnimation { duration: fen.demandeClaude ? 180 : 90; easing.type: Easing.OutCubic } }
            }
        }
        Timer { id: garderDemande; interval: 400 }
        // Confirmation du mode graphique (ConfirmationGpu.qml), gardée le temps de la fermeture
        Loader {
            id: chargeurGpu
            anchors.fill: parent
            active: fen.confirmGpu || garderGpu.running
            sourceComponent: ConfirmationGpu {
                opacity: fen.confirmGpu && ile.height > fen.hauteurGpu * 0.7 ? 1 : 0
                visible: opacity > 0.01
                Behavior on opacity { enabled: !Reglages.sobre; NumberAnimation { duration: fen.confirmGpu ? 180 : 90; easing.type: Easing.OutCubic } }
            }
        }
        Timer { id: garderGpu; interval: 400 }
        // Confirmation d'une action de JARVIS sur ce PC (ConfirmationNoeud.qml), gardée le temps de la fermeture
        Loader {
            id: chargeurNoeud
            anchors.fill: parent
            active: fen.confirmNoeud || garderNoeud.running
            sourceComponent: ConfirmationNoeud {
                opacity: fen.confirmNoeud && ile.height > fen.hauteurNoeud * 0.7 ? 1 : 0
                visible: opacity > 0.01
                Behavior on opacity { enabled: !Reglages.sobre; NumberAnimation { duration: fen.confirmNoeud ? 180 : 90; easing.type: Easing.OutCubic } }
            }
        }
        Timer { id: garderNoeud; interval: 400 }
        // Bandeau de la session de confiance de JARVIS (SessionNoeud.qml), gardé le temps de la fermeture
        Loader {
            id: chargeurSession
            anchors.fill: parent
            active: fen.sessionNoeud || garderSession.running
            sourceComponent: SessionNoeud {
                opacity: fen.sessionNoeud && ile.height > fen.hauteurSession * 0.7 ? 1 : 0
                visible: opacity > 0.01
                Behavior on opacity { enabled: !Reglages.sobre; NumberAnimation { duration: fen.sessionNoeud ? 180 : 90; easing.type: Easing.OutCubic } }
            }
        }
        Timer { id: garderSession; interval: 400 }
        Connections { target: fen; function onSessionNoeudChanged() { if (!fen.sessionNoeud) garderSession.restart() } }
        Connections { target: fen; function onConfirmNoeudChanged() { if (!fen.confirmNoeud) garderNoeud.restart() } }
        Connections { target: fen; function onConfirmGpuChanged() { if (!fen.confirmGpu) garderGpu.restart() } }
        Connections { target: fen; function onDemandeClaudeChanged() { if (!fen.demandeClaude) garderDemande.restart() } }
        Connections { target: fen; function onBanniereChanged() { if (!fen.banniere) garderBanniere.restart() } }

        MouseArea {
            anchors.fill: parent
            enabled: !fen.ouverte && !fen.banniere && !fen.enCarte
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            onClicked: e => e.button === Qt.RightButton ? Etat.lecturePause()
                            : (Etat.enregistre ? Etat.arreterVideo()
                               // « Bonjour » au réveil : un clic ouvre le résumé
                               : (Resume.actif && !Resume.ouvert && Etat.activiteType === "" ? Resume.ouvrir(fen.modelData.name)
                               // « Terminée » / « Échec » d'une commande longue : retour à son terminal
                               : (Etat.activiteType === "telechargement-fini" && Etat.dossierTel !== "" ? Etat.ouvrirTelechargements()
                               : (Etat.activiteType === "terminal-fini" && Terminal.fini ? Terminal.aller(Terminal.fini.pid)
                               // Un agent t'attend dans son terminal : sa question, directement
                               : (Agents.ouvrirAttente(fen.modelData.name) || Etat.basculer(fen.modelData.name, false))))))
            onWheel: w => Etat.reglerVolume(Etat.volume + (w.angleDelta.y > 0 ? 0.05 : -0.05))
        }

        // Glisser entre les pages : molette ou deux doigts, partout dans l'île (les curseurs ne prennent pas la molette)
        MouseArea {
            anchors.fill: parent
            enabled: fen.ouverte && fen.points && !fen.recherche
            acceptedButtons: Qt.NoButton
            property real cumul: 0
            property real dernier: 0         // heure du dernier événement : un trou de 200 ms = nouveau geste
            property bool geste: false       // le geste en cours a déjà servi (liste défilée ou page changée)
            onWheel: w => {
                var t = Date.now()
                if (t - dernier > 200) { geste = false; cumul = 0 }
                dernier = t
                var dy = w.pixelDelta.y !== 0 ? w.pixelDelta.y : w.angleDelta.y / 2
                // Un geste ne sert qu'une fois : il fait défiler la liste de la page d'un grand coup, ou, si la liste
                // est déjà au bout (ou qu'il n'y en a pas), change de page. L'élan du pavé tactile ne compte pas.
                if (verrou.running || geste) return
                cumul += dy
                if (Math.abs(cumul) < 30) return
                var page = pages.itemAt(Etat.vue), contenu = page ? page.contenu : null
                if (contenu && contenu.defiler && contenu.defiler(cumul)) { cumul = 0; geste = true; return }
                if (Math.abs(cumul) >= 60) {
                    Etat.changerVue(cumul > 0 ? -1 : 1)
                    cumul = 0
                    geste = true
                    verrou.restart()
                }
            }
            Timer { id: verrou; interval: 300 }
        }

        // Pages empilées : celle de la vue active est à sa place, les autres glissent hors de l'île
        Repeater {
            id: pages
            model: Etat.vues
            Item {
                id: pageIle
                readonly property var contenu: chargeur.item
                required property string modelData
                required property int index
                readonly property size t: fen.tailles[modelData] || fen.tailles.centre
                readonly property bool active: modelData === Etat.vueActive
                // Une page visitée reste prête tant que l'île est ouverte, et les deux voisines de la page affichée sont
                // préparées à l'avance, sans bloquer (asynchrone) : glisser vers elles ne fige plus l'île le temps de les
                // construire (revue PERF-02) ; tout est libéré quand l'île se ferme
                property bool dejaVue: false
                onActiveChanged: if (active) dejaVue = true
                readonly property bool voisine: Math.abs(index - Etat.vue) <= 1
                Connections { target: fen; function onOuverteChanged() { if (!fen.ouverte) pageIle.dejaVue = false } }
                x: (ile.width - t.width) / 2 + 16
                width: Math.max(0, t.width - 32 - (fen.points ? 22 : 0))
                height: t.height - 32
                y: 16 + (index - Etat.vue) * (ile.height * 0.6)
                Behavior on y { SpringAnimation { spring: 3.6; damping: 0.4 } }
                // Le contenu apparaît quand l'île a presque sa taille ; s'efface dès qu'elle se referme ou change de page
                opacity: fen.ouverte && !fen.recherche && active && ile.height > t.height * 0.72 && chargeur.status === Loader.Ready ? 1 : 0
                visible: opacity > 0.01
                Behavior on opacity { NumberAnimation { duration: fen.ouverte ? 200 : 80; easing.type: Easing.OutCubic } }
                Loader {
                    id: chargeur
                    anchors.fill: parent
                    asynchronous: true
                    active: pageIle.visible || pageIle.active || (fen.ouverte && (pageIle.dejaVue || pageIle.voisine))
                    sourceComponent: ({ concentration: pConcentration, musique: pMusique, minuteur: pMinuteur, charge: pCharge, jeu: pJeu, centre: pCentre,
                                        son: pSon, notifications: pNotifs, reseau: pReseau, bluetooth: pBluetooth, systeme: pSysteme,
                                        sante: pSante, calendrier: pCalendrier, claude: pClaude, assistant: pAssistant, meteo: pMeteo, presse: pPresse, fenetres: pFenetres,
                                        appel: pAppel, terminal: pTerminal, resume: pResume })[pageIle.modelData] || pCentre
                }
            }
        }
        Component { id: pAppel; PageAppel {} }
        Component { id: pTerminal; PageTerminal {} }
        Component { id: pResume; PageResume {} }
        Component { id: pConcentration; PageConcentration {} }
        Component { id: pMusique; Musique {} }
        Component { id: pMinuteur; Minuteur {} }
        Component { id: pCharge; Charge {} }
        Component { id: pJeu; Jeu {} }
        Component { id: pCentre; Centre {} }
        Component { id: pSon; Son {} }
        Component { id: pNotifs; PageNotifs {} }
        Component { id: pReseau; PageListe { mode: "wifi" } }
        Component { id: pBluetooth; PageListe { mode: "bluetooth" } }
        Component { id: pSysteme; Systeme {} }
        Component { id: pSante; Sante {} }
        Component { id: pCalendrier; Calendrier {} }
        Component { id: pClaude; Claude {} }
        Component { id: pAssistant; Assistant {} }
        Component { id: pMeteo; Meteo {} }
        Component { id: pPresse; Presse {} }
        Component { id: pFenetres; Fenetres {} }

        // Points de page sur le bord droit (comme le Centre de contrôle de l'iPhone)
        NavigationIle {
            anchors.right: parent.right; anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            width: 18; height: Math.max(0, Math.min(parent.height - 64, Etat.vues.length * 14))
            visible: fen.ouverte && fen.points
            pages: Etat.vues; courant: Etat.vue
            onChoisir: nom => Etat.aller(nom)
        }

        focus: fen.ouverte
        Keys.onEscapePressed: Etat.fermer()
        Keys.onUpPressed: Etat.changerVue(-1)
        Keys.onDownPressed: Etat.changerVue(1)
    
        // Clic dans l'île ouverte au survol : elle reste ouverte comme après un clic. Au-dessus de tout, le clic est
        // seulement noté puis laissé aux boutons en dessous.
        MouseArea {
            anchors.fill: parent
            enabled: Etat.parSurvol
            acceptedButtons: Qt.AllButtons
            onPressed: m => { Etat.parSurvol = false; m.accepted = false }
        }
    }
}
