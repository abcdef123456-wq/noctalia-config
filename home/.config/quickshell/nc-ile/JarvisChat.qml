// Petite fenêtre de chat JARVIS (Super + Maj + A, nc-jarvis chat, application « JARVIS Chat ») : une conversation
// vierge à chaque ouverture, dans le style de l'île (orbe, en-tête J.A.R.V.I.S., micro, Markdown et LaTeX), envoyée par
// AssistantEtat comme le chat de l'île. La session moteur reste celle de l'île, du cockpit, de Telegram et de Discord ;
// « Nouvelle conversation » la remet à zéro (le /reset existant) et repart d'une fenêtre vide.
// Fenêtre flottante ordinaire de Hyprland (règle jarvis-chat : centrée, 420 x 560) : Super + Ctrl + P l'épingle sur
// tous les bureaux comme n'importe quelle fenêtre ; l'île ne la ferme pas. Entrée envoie, Échap ferme ; le bouton
// d'agrandissement et Super + Ctrl + A ouvrent le cockpit complet.
import QtQuick
import Quickshell

FloatingWindow {
    id: fen
    title: "JARVIS Chat"
    visible: false
    implicitWidth: 420; implicitHeight: 560; minimumSize: Qt.size(340, 400)
    color: Couleurs.fond
    readonly property var page: chat
    property bool reinit: false             // « Nouvelle conversation » en cours : la fenêtre se vide à la réponse

    function afficher(nom) {
        surEcran(nom)
        if (!visible) vider()               // déjà ouverte : seulement ramenée devant, la conversation en cours reste
        visible = true
        Qt.callLater(chat.focaliser)
    }
    function surEcran(nom) {
        var ecrans = Quickshell.screens
        for (var i = 0; i < ecrans.length; i++) if (ecrans[i].name === nom) { screen = ecrans[i]; return }
    }
    // La fenêtre repart vide ; l'historique de l'île reste dans l'île (même liste, messages plus anciens masqués ici)
    function vider() { chat.depuis = AssistantEtat.dernierId; chat.historiqueOuvert = false }
    function nouvelle() { if (AssistantEtat.enCours || AssistantEtat.reglagesEnCours) return; reinit = true; AssistantEtat.resetSession() }
    function cockpit() { Quickshell.execDetached([AssistantEtat.bin + "nc-jarvis", "tableau"]) }
    function close() { visible = false }
    onClosed: close()
    Connections {
        target: AssistantEtat
        function onEnCoursChanged() { if (!AssistantEtat.enCours && fen.reinit) { fen.reinit = false; if (!AssistantEtat.erreur) fen.vider() } }
    }
    Shortcut { sequence: "Escape"; enabled: fen.visible && !chat.propositionsVisibles; onActivated: { if (fen.ileOuverte) fen.fermerIle(); else fen.close() } }
    property bool ileOuverte: false                  // l'île est ouverte (shell.qml) : Échap la ferme d'abord
    signal fermerIle()

    Item {
        anchors.fill: parent
        // Barre de la fenêtre : nom, nouvelle conversation, cockpit complet, fermer
        Item {
            id: barre
            width: parent.width; height: 46
            Row {
                anchors.left: parent.left; anchors.leftMargin: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 10
                Etincelle { anchors.verticalCenter: parent.verticalCenter; taille: 22; agent: "assistant"; tourne: fen.visible && AssistantEtat.enCours }
                Texte { anchors.verticalCenter: parent.verticalCenter; text: "JARVIS"; font.weight: Font.Bold; font.letterSpacing: 2 }
                Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Chat", "Chat"); secondaire: true }
            }
            Row {
                anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter; spacing: 6
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
                    onClic: fen.cockpit()
                }
                AssistantCommande {
                    rond: true; width: 30; height: 30; icone: "close"
                    aide: Reglages.t("Fermer · Échap", "Close · Esc")
                    onClic: fen.close()
                }
            }
        }
        Assistant {
            id: chat
            fenetre: true
            anchors.top: barre.bottom; anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
            anchors.leftMargin: 14; anchors.rightMargin: 14; anchors.bottomMargin: 14
            animationsActives: fen.visible
        }
    }
}
