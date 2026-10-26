// Carte de confirmation du mode graphique (ModeGraphique.qml) : l'île fermée s'étire en carte, comme pour une demande
// de Claude Code. « Passer en mode Dédiée ? », ce qui va se passer (redémarrage, dans le BIOS sur la plupart des
// Lenovo), puis [Annuler] et [Redémarrer dans le BIOS] ; rien n'est lancé avant ce dernier. Sans démarrage direct dans
// le BIOS, la carte explique seulement la touche à presser, avec un seul bouton qui ferme.
// Fichier à part (pas un composant interne d'Ile.qml) : le rechargement à chaud de Quickshell ne connaît pas les
// nouveaux composants internes d'un fichier déjà chargé.
import QtQuick

Item {
    id: c
    implicitHeight: col.y + col.implicitHeight + 16

    // En-tête : icône et « Mode graphique · Hybride » (le mode actuel)
    Row {
        x: 18; y: 14; spacing: 8
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "developer_board"; taille: 16; color: Couleurs.texteSec }
        Texte {
            anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.pixelSize: 12
            text: Reglages.t("Mode graphique · ", "Graphics mode · ") + ModeGraphique.nom(ModeGraphique.mode)
        }
    }
    Column {
        id: col
        x: 18; y: 40; width: c.width - 36; spacing: 6
        Texte {
            objectName: "nc-gpu-titre"
            width: parent.width; text: ModeGraphique.titre; font.pixelSize: 15; font.weight: Font.DemiBold
            wrapMode: Text.Wrap; maximumLineCount: 2
        }
        Texte {
            objectName: "nc-gpu-texte"
            width: parent.width; text: ModeGraphique.texte; font.pixelSize: 13; color: Couleurs.texteDoux
            wrapMode: Text.Wrap; maximumLineCount: 4; elide: Text.ElideNone
        }
        Texte {
            objectName: "nc-gpu-avertissement"
            visible: ModeGraphique.avertissement !== ""
            width: parent.width; text: ModeGraphique.avertissement; font.pixelSize: 12; color: Couleurs.texteDoux
            wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideNone
        }
        Item { width: 1; height: 6 }
        // Annuler · Redémarrer (le bouton principal, en clair sur le fond de l'île, à droite comme sur iPhone)
        Row {
            anchors.right: parent.right; spacing: 8
            Repeater {
                model: ModeGraphique.aConfirmer
                       ? [{ nom: "nc-gpu-annuler", texte: Reglages.t("Annuler", "Cancel"), principal: false },
                          { nom: "nc-gpu-confirmer", texte: ModeGraphique.bouton, principal: true }]
                       : [{ nom: "nc-gpu-annuler", texte: Reglages.t("Compris", "Got it"), principal: true }]
                Rectangle {
                    id: b
                    required property var modelData
                    objectName: modelData.nom
                    width: Math.max(96, lb.implicitWidth + 30); height: 34; radius: 17
                    color: modelData.principal ? (zb.containsMouse ? Couleurs.texteDoux : Couleurs.texte)
                                               : (zb.containsMouse ? Couleurs.gris3 : Couleurs.gris2)
                    scale: zb.pressed ? 0.95 : 1
                    Behavior on scale { enabled: !Reglages.sobre; SpringAnimation { spring: 6; damping: 0.45 } }
                    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
                    Texte {
                        id: lb; anchors.centerIn: parent; text: b.modelData.texte
                        font.pixelSize: 13; font.weight: Font.DemiBold
                        color: b.modelData.principal ? Couleurs.fond : Couleurs.texte
                    }
                    MouseArea {
                        id: zb; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: b.modelData.nom === "nc-gpu-confirmer" ? ModeGraphique.confirmer() : ModeGraphique.annuler()
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData.texte
                }
            }
        }
    }
}
