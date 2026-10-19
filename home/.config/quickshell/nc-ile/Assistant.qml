import QtQuick

Item {
    id: page
    property bool dansDashboard: false
    property bool animationsActives: true
    property bool historiqueOuvert: dansDashboard
    property bool ecouteVocale: false
    property string information: ""
    readonly property color cyan: Couleurs.accent
    readonly property color corail: Couleurs.rouge
    readonly property color teinteEtat: (AssistantEtat.erreur || ecouteVocale) ? corail : cyan
    readonly property var derniereReponse: AssistantEtat.messages.slice().reverse().find(m => m.role === "assistant")
    readonly property var modelesDefaut: [
        {id: "flash", name: "Flash", icone: "bolt", engine: "agy"},
        {id: "high", name: "High", icone: "psychology", engine: "agy"},
        {id: "sonnet", name: "Sonnet", icone: "auto_awesome", engine: "claude"},
        {id: "gpt-5", name: "GPT-5", icone: "smart_toy", engine: "codex"}
    ]
    property string modeleChoisiLocal: "flash"

    function iconeModele(item, idx) {
        if (item.icone) return item.icone
        var s = ((item.id || "") + " " + (item.name || "")).toLowerCase()
        if (s.indexOf("flash") >= 0 || s.indexOf("fast") >= 0 || s.indexOf("mini") >= 0) return "bolt"
        if (s.indexOf("high") >= 0 || s.indexOf("pro") >= 0 || s.indexOf("opus") >= 0 || s.indexOf("reason") >= 0) return "psychology"
        if (s.indexOf("sonnet") >= 0 || s.indexOf("claude") >= 0) return "auto_awesome"
        if (s.indexOf("gpt") >= 0 || s.indexOf("codex") >= 0 || s.indexOf("o3") >= 0 || s.indexOf("o4") >= 0) return "smart_toy"
        return ["bolt", "psychology", "auto_awesome", "smart_toy"][idx % 4]
    }
    function defiler(dy) {
        if (AssistantEtat.reglagesOuverts) return reglagesRapides.defiler(dy)
        return (dansDashboard || historiqueOuvert) ? defil.defiler(dy) : false
    }
    function bas() { Qt.callLater(() => { defil.cible = Math.max(0, defil.contentHeight - defil.height); defil.contentY = defil.cible }) }
    function reglages() { information = ""; ecouteVocale = false; AssistantEtat.ouvrirReglages() }
    function voix() {
        ecouteVocale = false
        information = Reglages.t("Dictée et sortie vocale non configurées sur ce client.", "Dictation and voice output are not configured on this client.")
    }
    Component.onCompleted: bas()
    onDansDashboardChanged: if (dansDashboard) historiqueOuvert = true
    Connections { target: AssistantEtat; function onMessagesChanged() { page.information = ""; page.ecouteVocale = false; page.bas() } }
    onHistoriqueOuvertChanged: if (historiqueOuvert) bas()

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
                    visible: !page.dansDashboard && (AssistantEtat.messages.length > 0 || page.historiqueOuvert)
                    rond: true; width: 32; height: 32; icone: "forum"
                    choisi: page.historiqueOuvert; aide: Reglages.t("Afficher la conversation", "Show conversation")
                    onClic: { if (AssistantEtat.reglagesOuverts) AssistantEtat.ouvrirReglages(); page.historiqueOuvert = !page.historiqueOuvert }
                }
                AssistantCommande {
                    visible: !page.dansDashboard
                    rond: true; width: 32; height: 32; icone: "volume_off"
                    aide: Reglages.t("Sortie vocale désactivée", "Voice output disabled")
                    onClic: page.voix()
                }
                AssistantCommande {
                    rond: true; width: 32; height: 32; icone: page.dansDashboard ? "delete_sweep" : "restart_alt"
                    aide: Reglages.t("Effacer l’affichage local", "Clear local display")
                    enabled: !AssistantEtat.enCours && (AssistantEtat.messages.length > 0 || page.historiqueOuvert || !!AssistantEtat.erreur)
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
            anchors.bottom: page.dansDashboard ? statutDashboard.top : resume.top; anchors.bottomMargin: 8
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
                    else if (AssistantEtat.messages.length > 0 || AssistantEtat.erreur) page.historiqueOuvert = true
                }
            }

            Defilement {
                id: defil
                anchors.fill: parent; visible: page.dansDashboard || page.historiqueOuvert
                interactive: page.dansDashboard
                contentHeight: liste.implicitHeight
                Column {
                    id: liste
                    width: parent.width; spacing: 10
                    Texte {
                        width: parent.width; visible: !AssistantEtat.messages.length
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
            visible: !page.dansDashboard && !AssistantEtat.reglagesOuverts
            anchors.bottom: modeles.top; anchors.bottomMargin: 10
            width: parent.width; height: 38
            readonly property string libelleStatut: AssistantEtat.enCours
                ? Reglages.t("Traitement de votre requête...", "Processing your request...")
                : (page.ecouteVocale
                    ? Reglages.t("À votre écoute... Cliquez sur l'orbe pour valider", "Listening... Click the orb to confirm")
                    : (AssistantEtat.erreur
                        ? ("« " + AssistantEtat.erreur + " »")
                        : (page.information || (page.derniereReponse ? ("« " + AssistantEtat.apercu(page.derniereReponse.texte) + " »") : Reglages.t("Comment puis-je vous aider ?", "How can I help you?")))))
            Row {
                anchors.centerIn: parent; spacing: 8
                width: Math.min(parent.width, iconeStatut.width + 8 + texteStatut.implicitWidth)
                Rectangle {
                    id: iconeStatut
                    anchors.verticalCenter: parent.verticalCenter
                    width: 20; height: 20; radius: 10
                    color: page.ecouteVocale || AssistantEtat.erreur ? Qt.alpha(page.corail, 0.22) : page.cyan
                    Ico {
                        anchors.centerIn: parent; taille: 13
                        nom: AssistantEtat.enCours ? "psychology" : (page.ecouteVocale ? "graphic_eq" : (AssistantEtat.erreur || page.derniereReponse ? "chat_bubble" : "auto_awesome"))
                        color: page.ecouteVocale || AssistantEtat.erreur ? page.corail : Couleurs.surAccent
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

        // Carte MODÈLE IA dans la Dynamic Island uniquement (reproduisant le design de l'image jointe avec les couleurs du terminal)
        Rectangle {
            id: modeles
            visible: !page.dansDashboard && !AssistantEtat.reglagesOuverts
            anchors.bottom: saisie.top; anchors.bottomMargin: 12
            width: parent.width; height: 128; radius: 18
            color: Couleurs.carte; border.width: 1; border.color: Couleurs.gris3
            Row {
                x: 12; y: 10; spacing: 6
                Ico { anchors.verticalCenter: parent.verticalCenter; nom: "tune"; taille: 15; color: page.cyan }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: Reglages.t("MODÈLE IA", "AI MODEL")
                    color: Couleurs.texte; font.family: "Adwaita Sans"; font.pixelSize: 12; font.weight: Font.Bold
                }
            }
            Text {
                anchors.right: parent.right; anchors.rightMargin: 14; y: 10
                text: AssistantEtat.reglagesModifies ? Reglages.t("À APPLIQUER", "PENDING") : (AssistantEtat.effort || "LOW").toUpperCase()
                color: page.cyan; font.family: "Adwaita Sans"; font.pixelSize: 12; font.weight: Font.Bold
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: page.reglages() }
            }
            Row {
                id: choix
                x: 10; y: 38; width: parent.width - 20; spacing: 8
                readonly property var listeModeles: AssistantEtat.modeles.length ? AssistantEtat.modeles.slice(0, 4) : page.modelesDefaut
                Repeater {
                    model: choix.listeModeles
                    Rectangle {
                        id: option
                        required property var modelData
                        required property int index
                        readonly property bool estBackend: AssistantEtat.modeles.length > 0
                        readonly property bool choisi: estBackend
                            ? (AssistantEtat.reglagesDisponibles && !AssistantEtat.reglagesModifies && AssistantEtat.modele === modelData.id)
                            : (page.modeleChoisiLocal === modelData.id)
                        width: (choix.width - 8 * (Math.max(1, choix.listeModeles.length) - 1)) / Math.max(1, choix.listeModeles.length)
                        height: 38; radius: 11
                        color: choisi ? page.cyan : (zone.containsMouse ? Couleurs.gris3 : Couleurs.gris2)
                        border.width: 1
                        border.color: choisi ? page.cyan : Couleurs.gris3
                        enabled: !AssistantEtat.enCours && !AssistantEtat.reglagesEnCours
                        Row {
                            anchors.centerIn: parent; spacing: 5
                            Ico {
                                anchors.verticalCenter: parent.verticalCenter
                                nom: page.iconeModele(option.modelData, option.index); taille: 15
                                color: option.choisi ? Couleurs.surAccent : Couleurs.texteDoux
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                width: Math.min(implicitWidth, option.width - 30)
                                text: option.modelData.name || option.modelData.id
                                color: option.choisi ? Couleurs.surAccent : Couleurs.texte
                                font.family: "Adwaita Sans"; font.pixelSize: 12; font.weight: Font.Bold
                                elide: Text.ElideRight; textFormat: Text.PlainText
                            }
                        }
                        function ouvrir() {
                            page.modeleChoisiLocal = modelData.id
                            if (!AssistantEtat.reglagesDisponibles) {
                                if (modelData.engine) AssistantEtat.choisirMoteur(modelData.engine)
                                page.reglages()
                                return
                            }
                            if (estBackend) {
                                AssistantEtat.modele = modelData.id
                                AssistantEtat.effort = ""
                            } else if (modelData.engine) {
                                AssistantEtat.choisirMoteur(modelData.engine)
                            }
                            AssistantEtat.reglagesOuverts = true
                        }
                        MouseArea { id: zone; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: option.ouvrir() }
                        activeFocusOnTab: true
                        Keys.onReturnPressed: ouvrir()
                        Keys.onSpacePressed: ouvrir()
                        Accessible.role: Accessible.Button
                        Accessible.name: modelData.name || modelData.id
                        Accessible.onPressAction: ouvrir()
                    }
                }
            }
            Row {
                x: 10; y: 86; width: parent.width - 20; spacing: 8
                AssistantCommande {
                    height: 30; icone: "bolt"
                    texte: "Effort: " + (AssistantEtat.effort || "LOW").toUpperCase()
                    aide: Reglages.t("Niveau de réflexion", "Reasoning effort")
                    onClic: page.reglages()
                }
                AssistantCommande {
                    height: 30; icone: "volume_off"
                    texte: Reglages.t("Voix: OFF", "Voice: OFF")
                    onClic: page.voix()
                }
                AssistantCommande {
                    height: 30; icone: "folder"
                    texte: AssistantEtat.moteurCourant.name || "ReconForge"
                    aide: Reglages.t("Moteur, modèle et connexion", "Engine, model and connection")
                    onClic: page.reglages()
                }
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
                    onAccepted: AssistantEtat.envoyer()
                    Text {
                        anchors.fill: parent; visible: !entree.text
                        text: page.dansDashboard ? Reglages.t("Écris ta question…", "Ask a question…") : Reglages.t("Demander ou dicter à JARVIS...", "Ask or dictate to JARVIS...")
                        font: entree.font
                        color: Couleurs.texteSec
                        elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
                    }
                }
            }
            AssistantCommande {
                id: micro
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
                anchors.right: parent.right
                rond: true; width: 46; height: 46
                icone: AssistantEtat.enCours ? "stop" : "arrow_upward"
                alerte: AssistantEtat.enCours
                choisi: !AssistantEtat.enCours && AssistantEtat.brouillon.trim().length > 0
                aide: AssistantEtat.enCours ? Reglages.t("Traitement en cours", "Request in progress") : Reglages.t("Envoyer", "Send")
                enabled: !AssistantEtat.enCours && !AssistantEtat.reglagesEnCours && AssistantEtat.brouillon.trim().length > 0
                onClic: AssistantEtat.envoyer()
            }
        }
    }
}
