// Un agent proposé par Tab dans l'espace de code (Code.qml, à droite) : nom, programme (ou « Neovim et un shell » pour
// le choix sans agent), « par défaut » pour celui de l'IA choisie. Le survol en fait le choix, un clic ouvre avec lui.
import QtQuick

Item {
    id: ligne
    property var agent: ({})
    property bool actif: false
    property bool defaut: false
    signal survol()
    signal choisir()
    width: 300; height: 46
    readonly property bool sansAgent: !agent || !agent.prog

    Rectangle {
        anchors.fill: parent; radius: 12
        color: ligne.actif ? Qt.alpha(Couleurs.accent, 0.22) : "transparent"
        Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
    }
    Ico {
        id: icone
        x: 12; anchors.verticalCenter: parent.verticalCenter
        nom: ligne.sansAgent ? "terminal" : "smart_toy"; taille: 20
        color: ligne.actif ? Couleurs.accent : Couleurs.texteSec
    }
    Texte {
        anchors.left: icone.right; anchors.leftMargin: 12; anchors.right: pastille.left; anchors.rightMargin: 8
        y: 7; height: 18
        text: ligne.agent && ligne.agent.nom ? ligne.agent.nom : ""
        font.pixelSize: 14; font.weight: Font.DemiBold
    }
    Texte {
        anchors.left: icone.right; anchors.leftMargin: 12; anchors.right: parent.right; anchors.rightMargin: 12
        y: 25; height: 16
        text: ligne.sansAgent ? Reglages.t("Neovim et un shell", "Neovim and a shell") : ligne.agent.prog
        secondaire: true; font.pixelSize: 11
    }
    Rectangle {
        id: pastille
        visible: ligne.defaut
        anchors.right: parent.right; anchors.rightMargin: 12; y: 8
        width: libDefaut.implicitWidth + 16; height: 18; radius: 9
        color: Qt.alpha(Couleurs.accent, 0.18)
        Texte { id: libDefaut; anchors.centerIn: parent; text: Reglages.t("par défaut", "default"); font.pixelSize: 10; color: Couleurs.accent }
    }
    MouseArea {
        anchors.fill: parent; hoverEnabled: true
        onEntered: ligne.survol()
        onClicked: ligne.choisir()
    }
}
