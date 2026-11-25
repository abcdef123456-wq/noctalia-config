// Tiroir de chat JARVIS (Super + Maj + A, nc-jarvis chat, application « JARVIS Chat ») : une conversation vierge à
// chaque ouverture, émergeant de la pilule de l'île (LanceurFondu bidirectionnel, 100 % réversible sans saut) dans le
// style de l'île (orbe, en-tête J.A.R.V.I.S., micro, Markdown et LaTeX), envoyée par AssistantEtat comme le chat de
// l'île. Mode éphémère par défaut (clic dehors ou Échap referme) ; le bouton Épingler passe en calque Top avec masque
// restreint à la carte pour travailler dans les fenêtres dessous. Le bouton d'agrandissement et Super + Ctrl + A
// ouvrent le cockpit complet.
import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland

PanelWindow {
    id: fen
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    color: "transparent"
    visible: false
    WlrLayershell.namespace: "nc-jarvis-chat"
    WlrLayershell.layer: coucheVoulue
    WlrLayershell.keyboardFocus: focusVoulu
    mask: Region { item: fen.itemMasque }

    readonly property string title: Reglages.t("JARVIS Chat", "JARVIS Chat")
    readonly property var page: chat
    readonly property bool selecteurActif: AssistantEtat.selecteurOuvert
    readonly property bool verre: Reglages.val("FENETRES_FLOU", "oui") !== "non" && !Reglages.sobre
    property bool epingle: false
    property bool ouvert: false
    property bool reinit: false             // « Nouvelle conversation » en cours : la fenêtre se vide à la réponse
    property bool ileOuverte: false         // l'île est ouverte (shell.qml) : Échap la ferme d'abord
    signal fermerIle()

    property string ecranCible: ""
    property string ecranEnAttente: ""
    property string modeEnAttente: ""

    readonly property string nomEcranActif: ecranCible !== "" ? ecranCible : (screen ? screen.name : "")
    readonly property real largeurEcran: screen ? screen.width : 1600
    readonly property real hauteurEcran: screen ? screen.height : 1000
    readonly property var mouv: Mouvement.pourEcran(nomEcranActif)
    readonly property real largeurCible: Math.min(460, Math.max(320, largeurEcran - 32))
    readonly property real hauteurCible: Math.min(580, Math.max(360, hauteurEcran - 80))
    readonly property real xCible: Math.round((largeurEcran - largeurCible) / 2)
    readonly property real yCible: Math.max(54, (parseInt(Reglages.val("ILE_Y", "9")) || 9) + 45)
    readonly property real contenuOpacite: fondu.actif ? Math.max(0, Math.min(1, (fondu.p - 0.25) / 0.55)) : (ouvert ? 1 : 0)

    readonly property int coucheVoulue: epingle ? WlrLayer.Top : WlrLayer.Overlay
    readonly property int focusVoulu: !ouvert || !visible ? WlrKeyboardFocus.None
                                      : (epingle || selecteurActif ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.Exclusive)
    readonly property Item itemMasque: (!visible || !ouvert) ? vide : (epingle || selecteurActif ? carte : fondClic)

    readonly property rect rectCarte: {
        if (fondu.actif) {
            return Qt.rect(
                fondu.mix(fondu.x0, xCible),
                fondu.mix(fondu.y0, yCible),
                Math.max(10, fondu.mix(fondu.w0, largeurCible)),
                Math.max(10, fondu.mix(fondu.h0, hauteurCible))
            )
        }
        return Qt.rect(xCible, yCible, largeurCible, hauteurCible)
    }

    LanceurFondu {
        id: fondu
        exigeReglage: false
        ecran: fen.nomEcranActif
        largeurEcran: fen.largeurEcran
        onTermine: fen.acheverFermeture()
        onActifChanged: fen.publierEmprise()
    }

    function resoudreEcran(nom) {
        if (nom && nom !== "") return nom
        if (Hyprland.focusedMonitor && Hyprland.focusedMonitor.name) return Hyprland.focusedMonitor.name
        return Quickshell.screens.length ? Quickshell.screens[0].name : ""
    }
    function surEcran(nom) {
        var ecrans = Quickshell.screens
        for (let i = 0; i < ecrans.length; i++) if (ecrans[i].name === nom) { screen = ecrans[i]; return }
    }
    function preparerVierge() {
        vider()
        AssistantEtat.suiteParIA = false
        AssistantEtat.lireQuiChat()
    }
    function preparerEchange() {
        chat.depuis = Math.max(0, AssistantEtat.idEchange - 1)
        chat.historiqueOuvert = false
    }
    function publierEmprise() {
        if (!ecranCible) return
        if (visible && (ouvert || fondu.actif)) Etat.definirEmpriseExterne(ecranCible, rectCarte)
        else Etat.effacerEmpriseExterne(ecranCible)
    }
    function verifierRelachePilule() {
        if (fondu.actif && !fondu.fermeture && !fondu.piluleRelachee && (epingle || rectCarte.y > fondu.y0 + fondu.h0 + 4))
            fondu.relacherPilule()
    }
    onRectCarteChanged: { publierEmprise(); verifierRelachePilule() }
    onEpingleChanged: verifierRelachePilule()
    onVisibleChanged: publierEmprise()
    onOuvertChanged: publierEmprise()

    function ouvrirSur(nom, mode) {
        var cible = resoudreEcran(nom)
        var m = mode === "echange" ? "echange" : "vierge"
        if (visible) {
            if (ecranCible === cible) {
                ecranEnAttente = ""; modeEnAttente = ""
                if (fondu.actif && fondu.fermeture) {
                    ouvert = true
                    if (m === "echange") preparerEchange()
                    fondu.demarrer()
                    publierEmprise()
                    Qt.callLater(chat.focaliser)
                    return
                }
                if (m === "echange") {
                    preparerEchange()
                    Qt.callLater(chat.focaliser)
                }
                return
            }
            // Ne jamais muter PanelWindow.screen pendant visible === true : fermer A puis rouvrir B.
            ecranEnAttente = cible
            modeEnAttente = m
            fermerTiroir()
            return
        }
        ecranEnAttente = ""; modeEnAttente = ""
        surEcran(cible)
        ecranCible = cible
        epingle = false
        ouvert = true
        if (m === "echange") preparerEchange()
        else preparerVierge()
        visible = true
        fondu.demarrer()
        publierEmprise()
        Qt.callLater(chat.focaliser)
    }
    function basculer(nom) {
        var cible = resoudreEcran(nom)
        if (visible && ecranCible === cible && ouvert && !(fondu.actif && fondu.fermeture)) {
            fermerTiroir()
            return
        }
        ouvrirSur(cible, "vierge")
    }
    function afficher(nom) { ouvrirSur(nom, "vierge") }
    // Ouverte par la notification d'une réponse de l'IA (zone de l'écran, texte, fichier…) : sur cet échange, pour continuer
    function montrerEchange(nom) { ouvrirSur(nom, "echange") }
    function fermerTiroir() {
        epingle = false
        ouvert = false
        if (!fondu.fermer()) acheverFermeture()
    }
    function acheverFermeture() {
        if (ecranCible) Etat.effacerEmpriseExterne(ecranCible)
        visible = false
        ouvert = false
        epingle = false
        if (ecranEnAttente !== "") {
            var nextEcran = ecranEnAttente
            var nextMode = modeEnAttente || "vierge"
            ecranEnAttente = ""
            modeEnAttente = ""
            Qt.callLater(function () { ouvrirSur(nextEcran, nextMode) })
        }
    }
    // Fermeture immédiate (sans ressort, annule toute file multi-écran)
    function close() {
        ecranEnAttente = ""
        modeEnAttente = ""
        fondu.annuler()
        if (ecranCible) Etat.effacerEmpriseExterne(ecranCible)
        visible = false
        ouvert = false
        epingle = false
    }
    // La fenêtre repart vide ; l'historique de l'île reste dans l'île (même liste, messages plus anciens masqués ici)
    function vider() { chat.depuis = AssistantEtat.dernierId; chat.historiqueOuvert = false }
    function nouvelle() { if (AssistantEtat.enCours || AssistantEtat.reglagesEnCours) return; reinit = true; AssistantEtat.resetSession() }
    function cockpit() { Quickshell.execDetached([AssistantEtat.bin + "nc-jarvis", "tableau"]) }

    Connections {
        target: AssistantEtat
        function onEnCoursChanged() { if (!AssistantEtat.enCours && fen.reinit) { fen.reinit = false; if (!AssistantEtat.erreur) fen.vider() } }
    }
    Shortcut {
        sequence: "Escape"
        enabled: fen.visible && fen.ouvert && !chat.propositionsVisibles
        onActivated: { if (fen.ileOuverte) fen.fermerIle(); else fen.fermerTiroir() }
    }
    Component.onDestruction: { if (ecranCible) Etat.effacerEmpriseExterne(ecranCible) }

    Item { id: vide; objectName: "nc-jarvis-chat-vide"; width: 0; height: 0 }

    // Relâchement (onReleased) pour que le clic dehors ne traverse pas vers les fenêtres dessous (comme Ile.qml)
    MouseArea {
        id: fondClic
        objectName: "nc-jarvis-chat-fond"
        anchors.fill: parent
        enabled: fen.ouvert && !fen.epingle && !fen.selecteurActif
        onReleased: fen.fermerTiroir()
    }

    // Contour aux couleurs de l'île (ILE_CONTOUR : dégradé de l'accent, discret, aucun)
    Rectangle {
        x: carte.x - 1.5; y: carte.y - 1.5
        width: carte.width + 3; height: carte.height + 3
        radius: carte.radius + 1.5
        visible: Couleurs.aContour
        opacity: fondu.actif ? Math.min(1, fondu.q) : (fen.ouvert ? 1 : 0)
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[0] }
            GradientStop { position: 0.5; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[1] }
            GradientStop { position: 1; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[2] }
        }
    }

    Rectangle {
        id: carte
        objectName: "nc-jarvis-chat-carte"
        x: fen.rectCarte.x
        y: fen.rectCarte.y
        width: fen.rectCarte.width
        height: fen.rectCarte.height
        radius: fondu.actif ? fondu.mix(fondu.r0, Couleurs.rayon(22, fen.largeurCible, fen.hauteurCible))
                            : Couleurs.rayon(22, width, height)
        color: fondu.actif ? fondu.couleurVers(Qt.alpha(Couleurs.fond, fen.verre ? 0.92 : 1))
                           : Qt.alpha(Couleurs.fond, fen.verre ? 0.92 : 1)
        border.width: Couleurs.aContour ? 0 : 1
        border.color: Couleurs.gris3
        clip: true

        // Empêche les clics dans la carte d'atteindre fondClic
        MouseArea { anchors.fill: parent }

        // Taille fixe sur la géométrie cible pendant le morph : zéro relayout QTextLayout par image à 240 Hz
        Item {
            id: contenu
            width: fen.largeurCible
            height: fen.hauteurCible
            anchors.horizontalCenter: parent.horizontalCenter
            opacity: fen.contenuOpacite
            transform: Translate { y: (1 - fen.contenuOpacite) * 12 }

            // Barre du tiroir : nom, épingler, nouvelle conversation, cockpit complet, fermer
            Item {
                id: barre
                width: parent.width; height: 46
                Row {
                    anchors.left: parent.left; anchors.leftMargin: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 10
                    // JARVIS, ou l'IA du bureau qui répond quand JARVIS n'est pas relié (ou pour la suite d'une de ses réponses)
                    Etincelle { anchors.verticalCenter: parent.verticalCenter; taille: 22; agent: AssistantEtat.agentChat || "assistant"; tourne: fen.visible && fen.ouvert && AssistantEtat.enCours }
                    Texte { anchors.verticalCenter: parent.verticalCenter; text: AssistantEtat.nomChat || "JARVIS"; font.weight: Font.Bold
                            font.letterSpacing: (AssistantEtat.nomChat || "JARVIS") === "JARVIS" ? 2 : 0 }
                    Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Chat", "Chat"); secondaire: true }
                }
                Row {
                    anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                    AssistantCommande {
                        objectName: "nc-jarvis-chat-pin"
                        rond: true; width: 30; height: 30; icone: "keep"
                        choisi: fen.epingle
                        aide: fen.epingle ? Reglages.t("Détacher le tiroir (se referme au clic dehors)", "Unpin drawer (closes on click outside)")
                                          : Reglages.t("Épingler le tiroir (travailler dans les fenêtres dessous)", "Pin drawer (work in windows underneath)")
                        onClic: fen.epingle = !fen.epingle
                    }
                    AssistantCommande {
                        objectName: "nc-jarvis-chat-new"
                        rond: true; width: 30; height: 30; icone: "add_comment"
                        aide: Reglages.t("Nouvelle conversation (remet la session JARVIS à zéro)", "New conversation (resets the JARVIS session)")
                        enabled: !AssistantEtat.enCours && !AssistantEtat.reglagesEnCours
                        onClic: fen.nouvelle()
                    }
                    AssistantCommande {
                        objectName: "nc-jarvis-chat-dashboard"
                        rond: true; width: 30; height: 30; icone: "open_in_full"
                        aide: Reglages.t("Cockpit complet · Super + Ctrl + A", "Full dashboard · Super + Ctrl + A")
                        onClic: { fen.fermerTiroir(); fen.cockpit() }
                    }
                    AssistantCommande {
                        rond: true; width: 30; height: 30; icone: "close"
                        aide: Reglages.t("Fermer · Échap", "Close · Esc")
                        onClic: fen.fermerTiroir()
                    }
                }
            }
            Assistant {
                id: chat
                fenetre: true
                anchors.top: barre.bottom; anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
                anchors.leftMargin: 14; anchors.rightMargin: 14; anchors.bottomMargin: 14
                animationsActives: fen.visible && fen.ouvert
            }
        }
    }
}
