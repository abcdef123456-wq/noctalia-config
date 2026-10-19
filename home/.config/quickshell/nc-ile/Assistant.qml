import QtQuick

Item {
    id: page
    property bool dansDashboard: false
    property bool animationsActives: true
    function defiler(dy) { return defil.defiler(dy) }
    function bas() { Qt.callLater(() => { defil.cible = Math.max(0, defil.contentHeight - defil.height); defil.contentY = defil.cible }) }
    Component.onCompleted: bas()
    Connections { target: AssistantEtat; function onMessagesChanged() { page.bas() } }

    component Bouton: Rectangle {
        id: b
        property string icone
        property string aide
        signal clic()
        width: 32; height: 32; radius: 12
        color: zone.containsMouse ? Couleurs.gris3 : Couleurs.gris2
        opacity: enabled ? 1 : 0.4
        Ico { anchors.centerIn: parent; nom: b.icone; taille: 18; color: Couleurs.texte }
        MouseArea { id: zone; anchors.fill: parent; hoverEnabled: true; onClicked: b.clic() }
        Accessible.role: Accessible.Button
        Accessible.name: aide
        Accessible.onPressAction: clic()
    }

    Item {
        id: tete
        width: parent.width; height: 36
        Row {
            anchors.verticalCenter: parent.verticalCenter; spacing: 8
            Etincelle { taille: 28; agent: "assistant"; tourne: page.animationsActives && AssistantEtat.enCours }
            Texte { anchors.verticalCenter: parent.verticalCenter; text: "JARVIS"; font.pixelSize: 20; font.weight: Font.Bold }
        }
        Row {
            anchors.right: parent.right; spacing: 6
            Bouton { visible: !page.dansDashboard; icone: "open_in_full"; aide: Reglages.t("Ouvrir le cockpit JARVIS", "Open JARVIS dashboard"); onClic: AssistantEtat.ouvrirDashboard() }
            Bouton { icone: "delete_sweep"; aide: Reglages.t("Effacer l’affichage local", "Clear local display")
                     enabled: !AssistantEtat.enCours && AssistantEtat.messages.length > 0; onClic: AssistantEtat.effacer() }
            Bouton { icone: "settings"; aide: Reglages.t("Configurer la connexion", "Configure connection"); onClic: AssistantEtat.configurer() }
        }
    }
    Defilement {
        id: defil
        anchors.top: tete.bottom; anchors.topMargin: 12
        anchors.bottom: statut.top; anchors.bottomMargin: 10
        width: parent.width
        contentHeight: liste.implicitHeight
        Column {
            id: liste
            width: parent.width; spacing: 10
            Texte {
                width: parent.width; visible: AssistantEtat.messages.length === 0
                text: Reglages.t("Que veux-tu faire ?\nÉcris à ton assistant ici. La roue dentée permet de configurer sa connexion.",
                                 "What would you like to do?\nWrite to your assistant here. Use the cog to configure its connection.")
                wrapMode: Text.Wrap; elide: Text.ElideNone; secondaire: true; textFormat: Text.PlainText
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
                        Texte { text: modelData.role === "vous" ? Reglages.t("Toi", "You") : "Assistant"; font.weight: Font.DemiBold; secondaire: true }
                        TextEdit {
                            width: parent.width; height: contentHeight
                            text: modelData.texte; textFormat: TextEdit.PlainText
                            readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                            color: Couleurs.texte; selectionColor: Couleurs.accent
                            font.family: "Adwaita Sans"; font.pixelSize: 13
                        }
                    }
                }
            }
        }
    }
    Texte {
        id: statut
        anchors.bottom: saisie.top; anchors.bottomMargin: 8
        width: parent.width
        text: AssistantEtat.enCours ? Reglages.t("Réflexion en cours…", "Thinking…") : AssistantEtat.erreur
        color: AssistantEtat.erreur ? Couleurs.rouge : Couleurs.texteSec
        textFormat: Text.PlainText; wrapMode: Text.Wrap; elide: Text.ElideRight; maximumLineCount: 4
        height: text ? (AssistantEtat.erreur ? 64 : 20) : 0
    }
    Rectangle {
        id: saisie
        anchors.bottom: parent.bottom
        width: parent.width; height: 48; radius: 16; color: Couleurs.gris2
        border.width: entree.activeFocus ? 1 : 0; border.color: Couleurs.accent
        TextInput {
            id: entree
            objectName: "nc-assistant-input"
            anchors.left: parent.left; anchors.leftMargin: 14
            anchors.right: envoi.left; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
            text: AssistantEtat.brouillon
            onTextEdited: AssistantEtat.brouillon = text
            maximumLength: 8000; clip: true; selectByMouse: true
            color: Couleurs.texte; selectionColor: Couleurs.accent
            font.family: "Adwaita Sans"; font.pixelSize: 13
            onAccepted: AssistantEtat.envoyer()
            Texte { anchors.fill: parent; visible: !entree.text && !entree.activeFocus
                    text: Reglages.t("Écris ta question…", "Ask a question…"); secondaire: true }
        }
        Bouton {
            id: envoi
            anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter
            icone: "arrow_upward"; aide: Reglages.t("Envoyer", "Send")
            enabled: !AssistantEtat.enCours && AssistantEtat.brouillon.trim().length > 0
            onClic: AssistantEtat.envoyer()
        }
    }
}
