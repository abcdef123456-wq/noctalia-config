import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: page
    property bool dansDashboard: false
    property bool fenetre: false            // petite fenêtre de chat (JarvisChat) : défilement à la molette, conversation vierge
    property int depuis: 0                  // n'afficher que les messages d'identifiant supérieur (conversation vierge)
    readonly property int nombre: depuis > 0 ? AssistantEtat.messages.filter(m => m.num > depuis).length : AssistantEtat.messages.length
    function conversation() { return AssistantEtat.messages.filter(m => m.num > depuis) }   // les messages affichés
    property bool animationsActives: true
    property bool historiqueOuvert: dansDashboard || nombre > 0
    function focaliser() { entree.forceActiveFocus(); entree.cursorPosition = entree.text.length }
    property bool ecouteVocale: false
    property string information: ""
    property bool suivreFin: true
    property int indiceSuggestion: 0
    property bool selectionExplicite: false
    property string suggestionsMasqueesPour: ""
    property var ouvrirLien: lien => Qt.openUrlExternally(lien)
    readonly property var propositions: AssistantEtat.proposerCommandes(entree.text, entree.cursorPosition)
    readonly property bool propositionsVisibles: visible && !AssistantEtat.reglagesOuverts && !AssistantEtat.enCours
        && !AssistantEtat.ecritureReglagesEnCours && entree.activeFocus && !entree.inputMethodComposing
        && propositions.length > 0 && entree.text !== suggestionsMasqueesPour
    readonly property bool animeAttente: visible && animationsActives && !AssistantEtat.reglagesOuverts
        && (dansDashboard || historiqueOuvert) && AssistantEtat.enCours && !Reglages.sobre
    readonly property color cyan: Couleurs.accent
    readonly property color corail: Couleurs.rouge
    readonly property color teinteEtat: (AssistantEtat.erreur || ecouteVocale) ? corail : cyan
    readonly property var derniereReponse: AssistantEtat.messages.slice().reverse().find(m => m.role === "assistant" && m.num > depuis)
    function chargerReglagesRapides() {
        if (visible && !dansDashboard && !historiqueOuvert && !entree.activeFocus && !AssistantEtat.brouillon
            && !AssistantEtat.reglagesDemandes && !AssistantEtat.enCours)
            AssistantEtat.lireReglages()
    }
    function defiler(dy) {
        if (AssistantEtat.reglagesOuverts) return reglagesRapides.defiler(dy)
        if (!dansDashboard && !historiqueOuvert) return false
        var bouge = defil.defiler(dy)
        if (bouge) suivreFin = defil.cible >= Math.max(0, defil.contentHeight - defil.height) - 1
        return bouge
    }
    function placerEnBas() {
        if (visible && defil.visible && suivreFin) defil.positionner(Math.max(0, defil.contentHeight - defil.height))
    }
    function bas() { suivreFin = true; Qt.callLater(placerEnBas) }
    function completer(index) {
        if (index < 0 || index >= propositions.length) return
        var p = propositions[index], suite = entree.text.slice(p.fin)
        var ajout = p.arguments && !suite ? " " : ""
        var texte = p.texte + ajout + suite
        suggestionsMasqueesPour = texte
        AssistantEtat.brouillon = texte
        entree.forceActiveFocus()
        entree.cursorPosition = p.texte.length + ajout.length
    }
    function validerSaisie() {
        if (propositionsVisibles && (selectionExplicite || !AssistantEtat.commandeComplete(entree.text))) {
            completer(indiceSuggestion)
            return
        }
        historiqueOuvert = true
        AssistantEtat.envoyer()
    }
    onPropositionsChanged: { indiceSuggestion = 0; selectionExplicite = false }
    onVisibleChanged: if (visible) { bas(); Qt.callLater(chargerReglagesRapides) }
    onAnimationsActivesChanged: if (animationsActives) bas()
    function reglages() { information = ""; ecouteVocale = false; AssistantEtat.ouvrirReglages() }
    // Haut-parleur : pas de synthèse vocale sur ce client, le bouton le dit
    function sortieVocale() {
        ecouteVocale = false
        information = Reglages.t("Sortie vocale non configurée sur ce client.", "Voice output is not configured on this client.")
    }
    // Micro : un clic enregistre (nc-dictee start), le suivant arrête et transcrit sur le serveur (nc-dictee stop) ;
    // le texte est ajouté au brouillon, sans envoi. Rien pendant une demande ni tant que nc-dictee tourne (double clic).
    function voix() {
        if (AssistantEtat.enCours || dictee.running) return
        if (ecouteVocale) {
            ecouteVocale = false
            information = Reglages.t("Transcription…", "Transcribing…")
            dictee.commande = "stop"
        } else {
            ecouteVocale = true
            information = Reglages.t("Écoute vocale…", "Listening…")
            dictee.commande = "start"
        }
        dictee.running = true
    }
    Component.onCompleted: { bas(); Qt.callLater(chargerReglagesRapides) }
    // Page détruite (île fermée) en pleine écoute : le micro ne reste pas ouvert
    Component.onDestruction: if (ecouteVocale) Quickshell.execDetached([AssistantEtat.bin + "nc-dictee", "cancel"])
    onDansDashboardChanged: if (dansDashboard) historiqueOuvert = true
    Connections {
        target: AssistantEtat
        function onMessagesChanged() {
            page.information = ""
            page.ecouteVocale = false
            if (page.nombre > 0) page.historiqueOuvert = true
            page.bas()
        }
        function onReglagesOuvertsChanged() { if (!AssistantEtat.reglagesOuverts) page.bas() }
    }
    onHistoriqueOuvertChanged: if (historiqueOuvert) bas()

    // Pastille d'un choix de JARVIS, comme les réponses à une question de Claude Code (DemandeClaude) ; fait : le choix
    // envoyé, en couleur d'accent
    component Pastille: Rectangle {
        id: pastille
        property string texte: ""
        property bool fait: false
        signal clic()
        width: Math.min(Math.max(86, lp.implicitWidth + 28), parent ? parent.width : 0); height: 32; radius: 16
        color: fait ? Couleurs.accent : (enabled && (zp.containsMouse || activeFocus) ? Couleurs.gris4 : Couleurs.gris2)
        scale: zp.pressed ? 0.94 : 1
        Behavior on scale { enabled: !Reglages.sobre; SpringAnimation { spring: 6; damping: 0.4 } }
        activeFocusOnTab: enabled
        Accessible.role: Accessible.Button
        Accessible.name: texte
        Accessible.onPressAction: if (enabled) clic()
        Keys.onReturnPressed: clic()
        Keys.onEnterPressed: clic()
        Keys.onSpacePressed: clic()
        Texte {
            id: lp
            anchors.centerIn: parent; width: Math.min(implicitWidth, pastille.width - 28)
            text: pastille.texte; font.pixelSize: 13; font.weight: Font.DemiBold
            color: pastille.fait ? Couleurs.surAccent : (pastille.enabled ? Couleurs.texte : Couleurs.texteSec)
        }
        MouseArea { id: zp; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pastille.clic() }
    }

    Item {
        id: contenu
        width: page.dansDashboard ? parent.width : Math.min(parent.width, 590)
        height: parent.height
        anchors.horizontalCenter: parent.horizontalCenter

        // En-tête : style J.A.R.V.I.S. dans la Dynamic Island uniquement, en-tête de conversation sobre dans le cockpit
        Item {
            id: tete
            width: parent.width; height: 36
            Row {
                anchors.verticalCenter: parent.verticalCenter; spacing: 10
                Etincelle {
                    visible: page.dansDashboard
                    anchors.verticalCenter: parent.verticalCenter
                    taille: 26; agent: "assistant"
                    tourne: page.animationsActives && AssistantEtat.enCours
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: page.dansDashboard ? "JARVIS" : "J.A.R.V.I.S."
                    font.family: "Adwaita Sans"; font.pixelSize: page.dansDashboard ? 20 : 19; font.weight: Font.Bold
                    color: Couleurs.texte
                }
                Rectangle {
                    visible: !page.dansDashboard
                    anchors.verticalCenter: parent.verticalCenter
                    width: badge.implicitWidth + 30; height: 26; radius: 13
                    color: Qt.alpha(page.teinteEtat, 0.16)
                    border.width: 1; border.color: Qt.alpha(page.teinteEtat, 0.35)
                    Rectangle { x: 10; anchors.verticalCenter: parent.verticalCenter; width: 7; height: 7; radius: 3.5; color: page.teinteEtat }
                    Text {
                        id: badge; x: 22; anchors.verticalCenter: parent.verticalCenter
                        text: AssistantEtat.enCours ? Reglages.t("Traitement", "Thinking")
                            : (page.ecouteVocale ? Reglages.t("Écoute vocale", "Listening")
                            : (AssistantEtat.erreur ? Reglages.t("Erreur", "Error") : Reglages.t("Prêt", "Ready")))
                        font.family: "Adwaita Sans"; font.pixelSize: 12; font.weight: Font.DemiBold; color: page.teinteEtat
                    }
                }
            }
            Row {
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 7
                AssistantCommande {
                    visible: !page.dansDashboard && (page.nombre > 0 || page.historiqueOuvert)
                    rond: true; width: 32; height: 32
                    icone: page.historiqueOuvert ? "smart_toy" : "forum"
                    choisi: page.historiqueOuvert
                    aide: page.historiqueOuvert ? Reglages.t("Afficher l'accueil JARVIS", "Show JARVIS home") : Reglages.t("Afficher la conversation", "Show conversation")
                    onClic: { if (AssistantEtat.reglagesOuverts) AssistantEtat.ouvrirReglages(); page.historiqueOuvert = !page.historiqueOuvert }
                }
                AssistantCommande {
                    visible: !page.dansDashboard
                    objectName: "nc-jarvis-voice-output"
                    rond: true; width: 32; height: 32; icone: "volume_off"
                    aide: Reglages.t("Sortie vocale désactivée", "Voice output disabled")
                    onClic: page.sortieVocale()
                }
                AssistantCommande {
                    rond: true; width: 32; height: 32; icone: "restart_alt"
                    aide: Reglages.t("Réinitialiser la session JARVIS (serveur et mémoire)", "Reset JARVIS session (server and memory)")
                    enabled: !AssistantEtat.enCours && !AssistantEtat.reglagesEnCours
                    onClic: { AssistantEtat.resetSession(); page.historiqueOuvert = true }
                }
                AssistantCommande {
                    rond: true; width: 32; height: 32; icone: "delete_sweep"
                    aide: Reglages.t("Effacer l’affichage local", "Clear local display")
                    enabled: !AssistantEtat.enCours && (page.nombre > 0 || page.historiqueOuvert || !!AssistantEtat.erreur)
                    onClic: { AssistantEtat.effacer(); if (!page.dansDashboard) page.historiqueOuvert = false }
                }
                AssistantCommande {
                    visible: page.dansDashboard
                    rond: true; width: 32; height: 32; icone: "tune"
                    choisi: AssistantEtat.reglagesOuverts
                    aide: Reglages.t("Modèle, réflexion et moteur", "Model, reasoning and engine")
                    onClic: page.reglages()
                }
                AssistantCommande {
                    visible: !page.dansDashboard
                    rond: true; width: 32; height: 32; icone: "open_in_full"
                    contour: true; aide: Reglages.t("Ouvrir le cockpit JARVIS", "Open JARVIS dashboard")
                    onClic: AssistantEtat.ouvrirDashboard()
                }
                AssistantCommande {
                    visible: !page.dansDashboard && AssistantEtat.reglagesOuverts
                    rond: true; width: 32; height: 32; icone: "close"
                    aide: Reglages.t("Fermer les réglages", "Close settings"); onClic: page.reglages()
                }
            }
        }

        AssistantReglages {
            id: reglagesRapides
            anchors.top: tete.bottom; anchors.topMargin: 12; anchors.bottom: parent.bottom
            width: parent.width; visible: AssistantEtat.reglagesOuverts
        }

        Item {
            id: accueil
            anchors.top: tete.bottom; anchors.topMargin: 10
            anchors.bottom: page.dansDashboard ? statutDashboard.top : (page.historiqueOuvert ? saisie.top : resume.top); anchors.bottomMargin: 8
            width: parent.width; visible: !AssistantEtat.reglagesOuverts

            AssistantOrbe {
                id: orbe
                visible: !page.dansDashboard && !page.historiqueOuvert
                anchors.centerIn: parent
                width: Math.max(0, Math.min(230, parent.width * 0.62, parent.height)); height: width
                anime: page.visible && page.animationsActives && !page.dansDashboard && !AssistantEtat.reglagesOuverts && !page.historiqueOuvert
                occupe: AssistantEtat.enCours; erreur: !!AssistantEtat.erreur; ecoute: page.ecouteVocale
                onClic: {
                    if (page.ecouteVocale) page.voix()
                    else if (page.nombre > 0 || AssistantEtat.erreur) page.historiqueOuvert = true
                }
            }

            Defilement {
                id: defil
                objectName: "nc-jarvis-history"
                anchors.fill: parent; visible: page.dansDashboard || page.historiqueOuvert
                interactive: page.dansDashboard || page.fenetre
                contentHeight: liste.implicitHeight
                onContentHeightChanged: if (page.suivreFin) Qt.callLater(page.placerEnBas)
                onHeightChanged: if (page.suivreFin) Qt.callLater(page.placerEnBas)
                onVisibleChanged: if (visible) page.bas()
                onMovementStarted: page.suivreFin = false
                onMovementEnded: {
                    cible = contentY
                    page.suivreFin = contentY >= Math.max(0, contentHeight - height) - 1
                }
                Column {
                    id: liste
                    width: parent.width; spacing: 10
                    Texte {
                        width: parent.width; visible: !page.nombre
                        text: page.dansDashboard
                            ? Reglages.t("Que veux-tu faire ?\nDiscute avec JARVIS (Markdown et LaTeX pris en charge), ou ouvre ses réglages rapides en haut à droite.",
                                         "What would you like to do?\nTalk to JARVIS (Markdown and LaTeX supported), or open quick settings at the top right.")
                            : Reglages.t("La conversation apparaîtra ici.", "Your conversation will appear here.")
                        color: Couleurs.texteSec
                        wrapMode: Text.Wrap; elide: Text.ElideNone
                    }
                    Repeater {
                        model: AssistantEtat.messages
                        Rectangle {
                            required property var modelData
                            visible: modelData.num > page.depuis      // fenêtre de chat : les messages d'avant son ouverture restent dans l'île
                            width: liste.width; height: corps.implicitHeight + 24; radius: 16
                            color: modelData.role === "vous" ? Couleurs.gris2 : Couleurs.carte
                            Column {
                                id: corps
                                x: 12; y: 12; width: parent.width - 24; spacing: 6
                                Texte {
                                    text: modelData.role === "vous" ? Reglages.t("Toi", "You") : "JARVIS"
                                    font.weight: Font.DemiBold
                                    color: page.dansDashboard ? Couleurs.texteSec : page.cyan
                                }
                                TextEdit {
                                    objectName: "nc-jarvis-message"
                                    width: parent.width; height: contentHeight
                                    property string brut: modelData.texte
                                    text: AssistantEtat.formater(modelData.texte)
                                    textFormat: TextEdit.MarkdownText
                                    readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                                    color: Couleurs.texte
                                    selectionColor: Couleurs.accent
                                    font.family: "Adwaita Sans"; font.pixelSize: 13
                                    onLinkActivated: lien => page.ouvrirLien(lien)
                                    HoverHandler { cursorShape: parent.hoveredLink ? Qt.PointingHandCursor : Qt.IBeamCursor }
                                }
                                // Choix proposés par JARVIS (issue #7), sous sa dernière réponse seulement et pas pendant une
                                // demande : un clic (ou Tab puis Entrée) l'envoie comme message ; ensuite, le choix fait reste
                                // marqué et les autres se grisent
                                Flow {
                                    id: choixMessage
                                    objectName: "nc-jarvis-choix"
                                    readonly property var message: modelData
                                    visible: message.role === "assistant" && (message.choix || []).length > 0 && !AssistantEtat.enCours
                                        && !!page.derniereReponse && page.derniereReponse.num === message.num
                                    width: parent.width; spacing: 8; topPadding: 4
                                    Repeater {
                                        model: choixMessage.visible ? choixMessage.message.choix : []
                                        Pastille {
                                            required property string modelData
                                            objectName: "nc-jarvis-choix-pastille"
                                            texte: modelData
                                            fait: choixMessage.message.choixFait === modelData
                                            enabled: !choixMessage.message.choixFait && !AssistantEtat.ecritureReglagesEnCours
                                            onClic: { page.historiqueOuvert = true; AssistantEtat.choisir(choixMessage.message.num, modelData) }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    Rectangle {
                        objectName: "nc-jarvis-thinking"
                        width: liste.width; height: visible ? 62 : 0; radius: 16
                        visible: AssistantEtat.enCours
                        color: Couleurs.carte
                        Accessible.role: Accessible.StaticText
                        Accessible.name: Reglages.t("JARVIS réfléchit…", "JARVIS is thinking…")
                        Column {
                            x: 12; y: 12; spacing: 10
                            Texte { text: "JARVIS"; color: page.cyan; font.weight: Font.DemiBold }
                            Row {
                                spacing: 5
                                Repeater {
                                    model: 3
                                    Rectangle {
                                        required property int index
                                        objectName: "nc-jarvis-thinking-dot"
                                        width: 5; height: 5; radius: 2.5; color: Couleurs.texte; opacity: 0.4
                                        SequentialAnimation on opacity {
                                            running: page.animeAttente; loops: Animation.Infinite
                                            PauseAnimation { duration: index * 140 }
                                            NumberAnimation { to: 1; duration: 200 }
                                            NumberAnimation { to: 0.4; duration: 360 }
                                            PauseAnimation { duration: (2 - index) * 140 }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    TextEdit {
                        width: parent.width; height: visible ? contentHeight : 0
                        visible: !page.dansDashboard && !!AssistantEtat.erreur
                        text: AssistantEtat.erreur; textFormat: TextEdit.PlainText
                        readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                        color: page.teinteEtat; selectionColor: Couleurs.accent
                        font.family: "Adwaita Sans"; font.pixelSize: 13
                    }
                }
            }
        }

        // Ligne d'état sous l'orbe dans la Dynamic Island uniquement
        Item {
            id: resume
            objectName: "nc-jarvis-status"
            visible: !page.dansDashboard && !AssistantEtat.reglagesOuverts && !page.historiqueOuvert
            anchors.bottom: modeles.top; anchors.bottomMargin: 10
            width: parent.width; height: 38
            readonly property string libelleStatut: AssistantEtat.enCours
                ? Reglages.t("Réflexion en cours…", "Thinking…")
                : (AssistantEtat.erreur ? Reglages.t("Une erreur est survenue — ouvrir la conversation", "An error occurred — open conversation")
                    : (page.information || (page.derniereReponse
                        ? Reglages.t("Réponse reçue — ouvrir la conversation", "Reply received — open conversation")
                        : Reglages.t("Comment puis-je vous aider ?", "How can I help you?"))))
            Row {
                anchors.centerIn: parent; spacing: 8
                width: Math.min(parent.width, iconeStatut.width + 8 + texteStatut.implicitWidth)
                Rectangle {
                    id: iconeStatut
                    anchors.verticalCenter: parent.verticalCenter
                    width: 22; height: 22; radius: 11
                    color: Qt.alpha(page.teinteEtat, 0.16)
                    border.width: 1; border.color: Qt.alpha(page.teinteEtat, 0.35)
                    Ico {
                        anchors.centerIn: parent; taille: 13
                        nom: AssistantEtat.enCours ? "psychology" : (page.ecouteVocale ? "graphic_eq" : (AssistantEtat.erreur || page.derniereReponse ? "chat_bubble" : "auto_awesome"))
                        color: page.teinteEtat
                    }
                }
                Text {
                    id: texteStatut
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(implicitWidth, resume.width - 32)
                    text: resume.libelleStatut
                    color: (AssistantEtat.erreur || page.ecouteVocale) ? page.corail : Couleurs.texte
                    font.family: "Adwaita Sans"; font.pixelSize: 14; font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    textFormat: Text.PlainText; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                }
            }
            MouseArea {
                anchors.fill: parent
                enabled: !!page.derniereReponse || !!AssistantEtat.erreur || page.historiqueOuvert
                cursorShape: Qt.PointingHandCursor
                onClicked: page.historiqueOuvert = !page.historiqueOuvert
            }
        }

        // Une entrée par famille ; l'effort reste un choix séparé.
        Rectangle {
            id: modeles
            visible: !page.dansDashboard && !AssistantEtat.reglagesOuverts && !page.historiqueOuvert
            anchors.bottom: saisie.top; anchors.bottomMargin: 12
            width: parent.width; height: 140; radius: 18
            color: Couleurs.carte; border.width: 1; border.color: Couleurs.gris3
            Texte {
                x: 12; y: 12; font.pixelSize: 11; font.weight: Font.Bold
                text: Reglages.t("MODÈLE IA", "AI MODEL"); secondaire: true
            }
            Row {
                anchors.right: parent.right; anchors.rightMargin: 10; y: 5; spacing: 6
                JarvisBouton {
                    objectName: "nc-jarvis-apply-model"
                    texte: Reglages.t("Appliquer", "Apply"); height: 28; primaire: true
                    visible: AssistantEtat.reglagesModifies && AssistantEtat.reglagesDisponibles
                    enabled: !AssistantEtat.enCours && !AssistantEtat.reglagesEnCours
                    onClic: AssistantEtat.appliquerReglages()
                }
                AssistantCommande {
                    rond: true; width: 28; height: 28; icone: "tune"
                    aide: Reglages.t("Moteur, modèles et connexion", "Engine, models and connection")
                    onClic: page.reglages()
                }
            }
            Row {
                id: choix
                x: 10; y: 38; width: parent.width - 20; spacing: 6
                Repeater {
                    model: AssistantEtat.famillesModeles
                    JarvisBouton {
                        required property string modelData
                        objectName: "nc-jarvis-model-" + modelData.toLowerCase()
                        width: (choix.width - 18) / 4; height: 34
                        texte: modelData
                        primaire: AssistantEtat.reglagesDisponibles && AssistantEtat.familleModele(AssistantEtat.modeleCourant) === modelData
                        enabled: AssistantEtat.reglagesDisponibles && !!AssistantEtat.moteurCourant.installed
                            && !!AssistantEtat.modelePourFamille(modelData) && !AssistantEtat.enCours && !AssistantEtat.reglagesEnCours
                        onClic: AssistantEtat.choisirFamille(modelData)
                    }
                }
            }
            Row {
                id: reflexion
                x: 10; y: 80; width: parent.width - 20; spacing: 6
                Repeater {
                    model: ["low", "medium", "high"]
                    JarvisBouton {
                        required property string modelData
                        objectName: "nc-jarvis-effort-" + modelData
                        width: (reflexion.width - 12) / 3; height: 28
                        texte: modelData
                        primaire: AssistantEtat.reglagesDisponibles && AssistantEtat.effort === modelData
                        enabled: AssistantEtat.reglagesDisponibles && AssistantEtat.modelePourEffort(modelData) !== null
                            && !AssistantEtat.enCours && !AssistantEtat.reglagesEnCours
                        onClic: AssistantEtat.choisirEffort(modelData)
                    }
                }
            }
            Texte {
                x: 12; y: 116; width: parent.width - 24; font.pixelSize: 10; secondaire: true
                text: AssistantEtat.reglagesEnCours ? Reglages.t("Chargement…", "Loading…")
                    : (!AssistantEtat.reglagesDisponibles ? Reglages.t("Configurer la connexion avec ⚙", "Configure connection with ⚙")
                    : (AssistantEtat.reglagesModifies ? Reglages.t("Choix en attente d’Appliquer", "Selection pending Apply")
                    : Reglages.t("Grisé : absent du catalogue de ce moteur", "Disabled: absent from this engine’s catalog")))
                elide: Text.ElideRight; textFormat: Text.PlainText
            }
        }

        // Ligne d'état compacte dans le cockpit plein écran
        Texte {
            id: statutDashboard
            visible: page.dansDashboard && !AssistantEtat.reglagesOuverts
            anchors.bottom: saisie.top; anchors.bottomMargin: 8
            width: parent.width
            text: AssistantEtat.enCours ? Reglages.t("Réflexion en cours…", "Thinking…") : AssistantEtat.erreur
            color: AssistantEtat.erreur ? Couleurs.rouge : Couleurs.texteSec
            textFormat: Text.PlainText; wrapMode: Text.Wrap; elide: Text.ElideRight; maximumLineCount: 4
            height: visible && text ? (AssistantEtat.erreur ? 64 : 20) : 0
        }

        // Barre de saisie
        Item {
            id: saisie
            visible: !AssistantEtat.reglagesOuverts
            anchors.bottom: parent.bottom
            width: parent.width; height: 46
            Rectangle {
                anchors.left: parent.left
                anchors.right: page.dansDashboard ? envoi.left : micro.left
                anchors.rightMargin: 8; height: parent.height
                radius: page.dansDashboard ? 16 : height / 2
                color: Couleurs.gris2
                border.width: 1
                border.color: entree.activeFocus ? Couleurs.accent : (page.dansDashboard ? "transparent" : Couleurs.gris4)
                TextInput {
                    id: entree
                    objectName: "nc-assistant-input"
                    anchors.left: parent.left; anchors.leftMargin: 16
                    anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
                    text: AssistantEtat.brouillon; onTextEdited: AssistantEtat.brouillon = text
                    maximumLength: 8000; clip: true; selectByMouse: true
                    color: Couleurs.texte
                    selectionColor: Couleurs.accent
                    font.family: "Adwaita Sans"; font.pixelSize: 13
                    onAccepted: page.validerSaisie()
                    Keys.onPressed: event => {
                        event.accepted = false
                        if (!page.propositionsVisibles || (event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))) return
                        if (event.key === Qt.Key_Down || event.key === Qt.Key_Up) {
                            let n = page.propositions.length
                            page.indiceSuggestion = (page.indiceSuggestion + (event.key === Qt.Key_Down ? 1 : -1) + n) % n
                            page.selectionExplicite = true
                            listeSuggestions.positionViewAtIndex(page.indiceSuggestion, ListView.Contain)
                        } else if (event.key === Qt.Key_Tab) page.completer(page.indiceSuggestion)
                        else if (event.key === Qt.Key_Escape) page.suggestionsMasqueesPour = text
                        else return
                        event.accepted = true
                    }
                    Text {
                        anchors.fill: parent; visible: !entree.text
                        text: page.dansDashboard ? Reglages.t("Écris ta question ou commande (/help, /reset)…", "Ask a question or command (/help, /reset)…")
                                                 : Reglages.t("Question ou commande (/reset, /help, /status)…", "Question or command (/reset, /help, /status)…")
                        font: entree.font
                        color: Couleurs.texteSec
                        elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
                    }
                }
            }
            Rectangle {
                id: suggestions
                objectName: "nc-jarvis-completions"
                visible: page.propositionsVisibles
                anchors.bottom: parent.top; anchors.bottomMargin: 6
                z: 10; width: parent.width; height: Math.min(5, page.propositions.length) * 42 + 12
                radius: 14; color: Couleurs.carte; border.width: 1; border.color: Couleurs.gris3
                ListView {
                    id: listeSuggestions
                    anchors.fill: parent; anchors.margins: 6; clip: true
                    model: page.propositions; currentIndex: page.indiceSuggestion
                    boundsBehavior: Flickable.StopAtBounds
                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        width: listeSuggestions.width; height: 42; radius: 8
                        color: index === page.indiceSuggestion ? Couleurs.gris3 : "transparent"
                        Column {
                            x: 10; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 20; spacing: 2
                            Texte { text: modelData.texte; color: page.cyan; font.weight: Font.DemiBold }
                            Texte { width: parent.width; text: modelData.description; font.pixelSize: 11; color: Couleurs.texteSec }
                        }
                        MouseArea {
                            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onEntered: { page.indiceSuggestion = parent.index; page.selectionExplicite = true }
                            onClicked: page.completer(parent.index)
                        }
                        Accessible.role: Accessible.Button
                        Accessible.name: modelData.texte + " — " + modelData.description
                        Accessible.onPressAction: page.completer(index)
                    }
                }
            }
            AssistantCommande {
                id: micro
                objectName: "nc-jarvis-mic"
                visible: !page.dansDashboard
                anchors.right: envoi.left; anchors.rightMargin: 8
                rond: true; width: 46; height: 46
                icone: page.ecouteVocale ? "stop" : "mic"
                alerte: page.ecouteVocale
                aide: Reglages.t("Dictée vocale", "Voice dictation")
                onClic: page.voix()
            }
            AssistantCommande {
                id: envoi
                objectName: "nc-jarvis-send"
                anchors.right: parent.right
                rond: true; width: 46; height: 46
                icone: "arrow_upward"
                occupe: AssistantEtat.enCours
                animationsActives: page.animationsActives
                choisi: !AssistantEtat.enCours && AssistantEtat.brouillon.trim().length > 0
                aide: AssistantEtat.enCours ? Reglages.t("Traitement en cours", "Request in progress") : Reglages.t("Envoyer", "Send")
                enabled: !AssistantEtat.enCours && !AssistantEtat.ecritureReglagesEnCours && AssistantEtat.brouillon.trim().length > 0
                onClic: { page.historiqueOuvert = true; AssistantEtat.envoyer() }
            }
        }
    }

    // Dictée : nc-dictee start | stop, une ligne de JSON en réponse ({ ok, recording } ou { ok, text } ou { ok: false, error })
    Process {
        id: dictee
        property string commande: "start"
        command: [AssistantEtat.bin + "nc-dictee", commande]
        stdout: StdioCollector {
            onStreamFinished: {
                var r = null
                try { r = JSON.parse(text) } catch (_) {}
                var erreur = r && r.error ? String(r.error).slice(0, 300) : ""
                if (dictee.commande === "start") {
                    if (!r || r.ok !== true) {
                        page.ecouteVocale = false
                        page.information = erreur || Reglages.t("Micro indisponible.", "Microphone unavailable.")
                    }
                    return
                }
                page.ecouteVocale = false
                if (r && r.ok === true && typeof r.text === "string" && r.text.trim().length) {
                    let t = r.text.trim(), b = AssistantEtat.brouillon.trim()
                    AssistantEtat.brouillon = b.length ? b + " " + t : t
                    page.information = ""
                    Qt.callLater(function() { entree.forceActiveFocus(); entree.cursorPosition = entree.text.length })
                } else {
                    page.information = erreur || Reglages.t("Transcription vide.", "Empty transcription.")
                }
            }
        }
        stderr: StdioCollector {}
    }
}
