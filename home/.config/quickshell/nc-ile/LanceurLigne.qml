// Ligne de résultat du lanceur (Recherche.qml), 42 px : icône 26 px, titre, sous-titre et aide à droite. Choisie : fond
// teinté, filet d'accent et repère de 2 px. Suppression demandée : la question sur la ligne même, en rouge.
import QtQuick

Rectangle {
    id: ligne
    required property var modelData
    required property int index
    property bool choisi: false
    property bool confirme: false
    readonly property bool supprimable: !!modelData.suppr
    signal survol(var point)              // position dans la fenêtre : la sélection ne suit que si la souris a bougé
    signal valider(bool nouveau)
    signal clicDroit()
    signal supprimer()
    radius: Couleurs.rayon(8, width, height)
    // En confirmation : le fond de l'île à peine teinté de rouge (le texte rouge y garde son contraste)
    color: confirme ? Qt.tint(Couleurs.fond, Qt.alpha(Couleurs.rouge, 0.14)) : choisi ? Couleurs.gris2 : "transparent"
    border.width: choisi && !confirme ? 1 : 0
    border.color: Qt.alpha(Couleurs.accent, 0.48)
    Rectangle {
        visible: ligne.choisi && !ligne.confirme
        x: 6; anchors.verticalCenter: parent.verticalCenter
        width: 2; height: 16; radius: Couleurs.rayon(1, width, height); color: Couleurs.texte
    }
    Item {
        id: ic
        x: 13; anchors.verticalCenter: parent.verticalCenter
        width: 26; height: 26
        Image {
            id: img
            anchors.fill: parent
            source: (ligne.modelData.icone || "").toLowerCase().endsWith(".jxl") ? "" : (ligne.modelData.icone || "")
            sourceSize: Qt.size(52, 52)
            visible: status === Image.Ready
        }
        Ico { anchors.centerIn: parent; nom: ligne.modelData.glyphe || "search"; taille: 20; color: Couleurs.texteDoux; visible: img.status !== Image.Ready && !ligne.modelData.emoji }
        Texte { objectName: "nc-spotlight-emoji"; anchors.centerIn: parent; visible: !!ligne.modelData.emoji; text: ligne.modelData.emoji || ""; font.pixelSize: 22 }
    }
    Texte {
        visible: !ligne.confirme
        anchors.left: ic.right; anchors.leftMargin: 5; anchors.verticalCenter: parent.verticalCenter
        width: parent.width - 44 - sous.width - 24 - (moins.visible ? 32 : 0)
        textFormat: Text.PlainText      // titres et sous-titres viennent du bilan, de systemctl, des fenêtres : jamais du HTML
        text: ligne.modelData.titre; font.pixelSize: 14; font.weight: Font.Medium
    }
    Texte {
        id: sous
        visible: !ligne.confirme
        anchors.right: parent.right; anchors.rightMargin: moins.visible ? 12 + 22 + 10 : 12; anchors.verticalCenter: parent.verticalCenter
        width: Math.min(implicitWidth, 190)
        textFormat: Text.PlainText
        text: ligne.modelData.sous + (ligne.choisi ? "  ·  " + (ligne.modelData.aide || "↵") : ""); secondaire: true; font.pixelSize: 12
        horizontalAlignment: Text.AlignRight
    }
    Texte {
        objectName: "nc-spotlight-confirmation"
        visible: ligne.confirme
        anchors.left: ic.right; anchors.leftMargin: 5; anchors.right: parent.right; anchors.rightMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        text: ligne.confirme ? ligne.modelData.suppr.libelle + "  " + Reglages.t("↵ oui · Échap non", "↵ yes · Esc no") : ""
        color: Couleurs.rouge; font.pixelSize: 14; font.weight: Font.DemiBold
    }
    // Clic droit sur une appli : l'épingler au dock, ou l'en retirer
    MouseArea {
        id: zoneLigne
        objectName: "nc-spotlight-zone"
        anchors.fill: parent; hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        // pas onEntered : la souris immobile sous une liste qui bouge ne vole pas la sélection
        onPositionChanged: e => ligne.survol(zoneLigne.mapToItem(null, e ? e.x : 0, e ? e.y : 0))
        onClicked: e => {
            if (e.button === Qt.RightButton) ligne.clicDroit()
            else ligne.valider((e.modifiers & Qt.ControlModifier) !== 0)
        }
    }
    // − : la même suppression, à la souris (au survol ou sur la ligne choisie) ; rouge seulement au survol
    Rectangle {
        id: moins
        objectName: "nc-spotlight-moins"
        readonly property bool montre: ligne.supprimable && !ligne.confirme && (ligne.choisi || zoneLigne.containsMouse || zMoins.containsMouse)
        opacity: montre ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { enabled: !Reglages.sobre; NumberAnimation { duration: 120 } }
        anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
        width: 22; height: 22; radius: width / 2
        color: zMoins.containsMouse ? Couleurs.carteSurvol : Couleurs.carte
        border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.28)
        Texte { anchors.centerIn: parent; text: "−"; font.pixelSize: 16; font.weight: Font.Bold
                color: zMoins.containsMouse ? Couleurs.rouge : Couleurs.texte }
        MouseArea {
            id: zMoins
            anchors.fill: parent; anchors.margins: -4; hoverEnabled: true
            enabled: moins.montre
            onClicked: ligne.supprimer()
        }
    }
}
