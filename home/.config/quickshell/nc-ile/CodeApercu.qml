// L'aperçu du projet choisi dans l'espace de code (Code.qml, à droite) : nom, pastilles de la branche, de l'état
// et du langage (l'état propre ou modifié demanderait git : jamais lancé ici), chemin ; les derniers commits avec leur date relative ;
// le début du README dans un voile arrondi. L'en-tête vient de la liste (tout de suite), le reste de
// nc-code --apercu-json (quelques dizaines de ms après) : rien n'est interprété, tout est en texte brut (Texte.qml).
import QtQuick

Item {
    id: a
    property var projet: null
    property var apercu: null                       // null tant que nc-code n'a pas répondu pour ce projet
    readonly property color texteSecondaire: Qt.tint(Couleurs.texteSec, Qt.alpha(Couleurs.texte, 0.35))
    readonly property var commits: apercu && Array.isArray(apercu.commits) ? apercu.commits.slice(0, 5) : []
    readonly property string etat: apercu && typeof apercu.etat === "string" ? apercu.etat : ""
    readonly property string readme: apercu && typeof apercu.readme === "string" ? apercu.readme : ""

    Column {
        id: haut
        width: parent.width; spacing: 8
        Texte { width: parent.width; height: 24; text: a.projet && a.projet.nom ? a.projet.nom : ""; font.pixelSize: 17; font.weight: Font.Bold }
        Row {
            spacing: 6
            Rectangle {
                visible: !!(a.projet && a.projet.branche)
                height: 22; width: libBranche.implicitWidth + 30; radius: 11
                color: Qt.alpha(Couleurs.accent, 0.18)
                Ico { x: 8; anchors.verticalCenter: parent.verticalCenter; nom: "fork_right"; taille: 14; color: Couleurs.accent }
                Texte { id: libBranche; x: 24; height: parent.height; text: a.projet && a.projet.branche ? a.projet.branche : ""; font.pixelSize: 11; font.weight: Font.DemiBold }
            }
            Rectangle {
                objectName: "nc-code-etat"
                visible: a.etat !== ""
                height: 22; width: libEtat.implicitWidth + 20; radius: 11
                color: Qt.alpha(a.etat === "propre" ? Couleurs.vert : Couleurs.orange, 0.18)
                Texte {
                    id: libEtat; anchors.centerIn: parent; font.pixelSize: 11; font.weight: Font.DemiBold
                    color: a.etat === "propre" ? Couleurs.vert : Couleurs.orange
                    text: a.etat === "propre" ? Reglages.t("Propre", "Clean") : Reglages.t("Modifié", "Modified")
                }
            }
            Rectangle {
                visible: !!(a.projet && a.projet.langage)
                height: 22; width: libLangage.implicitWidth + 20; radius: 11
                color: Qt.alpha(Couleurs.carte, 0.7); border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.1)
                Texte { id: libLangage; anchors.centerIn: parent; text: a.projet && a.projet.langage ? a.projet.langage : ""; font.pixelSize: 11; color: a.texteSecondaire }
            }
        }
        Texte { width: parent.width; height: 16; text: a.projet && a.projet.court ? a.projet.court : ""; secondaire: true; font.pixelSize: 12 }
        Item { width: 1; height: 4 }
        Texte {
            width: parent.width; height: 16
            text: Reglages.t("Derniers commits", "Latest commits"); font.pixelSize: 11; font.weight: Font.Bold; color: a.texteSecondaire
        }
        Texte {
            visible: a.apercu === null || a.commits.length === 0
            width: parent.width; height: 18; secondaire: true; font.pixelSize: 12
            text: a.apercu === null ? "…" : Reglages.t("Aucun commit", "No commit yet")
        }
        Repeater {
            model: a.commits
            Item {
                objectName: "nc-code-commit"
                width: haut.width; height: 20
                Rectangle { x: 2; anchors.verticalCenter: parent.verticalCenter; width: 6; height: 6; radius: 3; color: Couleurs.gris4 }
                Texte {
                    anchors.left: parent.left; anchors.leftMargin: 16; anchors.right: dateCommit.left; anchors.rightMargin: 8
                    height: parent.height; font.pixelSize: 12
                    text: modelData && modelData.message ? modelData.message : ""
                }
                Texte {
                    id: dateCommit
                    anchors.right: parent.right; height: parent.height
                    text: modelData && modelData.date ? modelData.date : ""; secondaire: true; font.pixelSize: 11
                }
            }
        }
    }
    // Le début du README, en texte brut, dans un voile du fond (autant de lignes que la place le permet)
    Rectangle {
        objectName: "nc-code-readme"
        visible: a.readme !== ""
        anchors.top: haut.bottom; anchors.topMargin: 12
        width: parent.width
        height: Math.max(0, Math.min(texteReadme.implicitHeight + 24, a.height - haut.height - 12))
        radius: 12; color: Qt.alpha(Couleurs.carte, 0.55)
        clip: true
        Texte {
            id: texteReadme
            x: 12; y: 12; width: parent.width - 24
            text: a.readme
            wrapMode: Text.Wrap; maximumLineCount: 14
            verticalAlignment: Text.AlignTop
            font.pixelSize: 12; lineHeight: 1.25
            color: a.texteSecondaire
        }
    }
}
