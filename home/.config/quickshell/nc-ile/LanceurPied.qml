// Pied du lanceur (Recherche.qml) : filet, aide clavier à gauche, nombre de résultats à droite
import QtQuick

Item {
    id: p
    property int total: 0
    height: 41
    Rectangle { x: 18; width: p.width - 36; height: 1; color: Qt.alpha(Couleurs.voile, 0.16) }
    Row {
        x: 20; y: 13; spacing: 6
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "unfold_more"; taille: 14; color: Couleurs.texteSec }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Naviguer  ·  Tab Espace", "Navigate  ·  Tab Space"); font.pixelSize: 11; secondaire: true }
    }
    Texte {
        objectName: "nc-lanceur-compteur"
        anchors.right: parent.right; anchors.rightMargin: 20; y: 13
        text: p.total + " " + (p.total > 1 ? Reglages.t("résultats", "results") : Reglages.t("résultat", "result"))
        font.pixelSize: 11; font.features: ({ "tnum": 1 }); secondaire: true
    }
}
