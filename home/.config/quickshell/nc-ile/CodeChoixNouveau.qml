// Le petit choix de « Nouveau » dans l'espace de code (Code.qml, à droite) : deux lignes, « Projet vide » (taper un nom)
// et « Depuis GitHub » (la liste de tes dépôts, ou l'adresse à coller). Flèches et Entrée au clavier (gérés par Code.qml),
// survol pour choisir une ligne, un clic la lance.
import QtQuick

Column {
    id: choix
    property int selection: 0
    signal survol(int i)
    signal choisir(int i)
    spacing: 4
    Texte { width: parent.width; height: 30; text: Reglages.t("Nouveau", "New"); font.pixelSize: 17; font.weight: Font.Bold }
    Texte {
        width: parent.width; height: 24; secondaire: true; font.pixelSize: 12
        text: Reglages.t("Entrée choisit, Échap revient", "Enter picks, Esc goes back")
    }
    Repeater {
        model: [
            { objet: "nc-code-choix-vide", icone: "create_new_folder", titre: Reglages.t("Projet vide", "Empty project"),
              detail: Reglages.t("Un nom, un dossier avec git et un README", "A name, a folder with git and a README") },
            { objet: "nc-code-choix-github", icone: "download", titre: Reglages.t("Depuis GitHub", "From GitHub"),
              detail: Reglages.t("Cloner un de tes dépôts, ou ouvrir celui qui est déjà là", "Clone one of your repositories, or open the one already here") }
        ]
        Item {
            id: ligne
            objectName: modelData.objet
            width: choix.width; height: 46
            readonly property bool actif: index === choix.selection
            Rectangle {
                anchors.fill: parent; radius: 12
                color: ligne.actif ? Qt.alpha(Couleurs.accent, 0.22) : "transparent"
                Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
            }
            Ico { id: icone; x: 12; anchors.verticalCenter: parent.verticalCenter; nom: modelData.icone; taille: 20; color: ligne.actif ? Couleurs.accent : Couleurs.texteSec }
            Texte {
                anchors.left: icone.right; anchors.leftMargin: 12; anchors.right: parent.right; anchors.rightMargin: 12
                y: 7; height: 18; text: modelData.titre; font.pixelSize: 14; font.weight: Font.DemiBold
            }
            Texte {
                anchors.left: icone.right; anchors.leftMargin: 12; anchors.right: parent.right; anchors.rightMargin: 12
                y: 25; height: 16; text: modelData.detail; secondaire: true; font.pixelSize: 11
            }
            MouseArea {
                anchors.fill: parent; hoverEnabled: true
                onEntered: choix.survol(index)
                onClicked: choix.choisir(index)
            }
        }
    }
}
