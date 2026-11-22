// Widgets du bureau (nc-reglages → Île → WIDGETS_BUREAU, « non » par défaut) : une grande horloge et la date, posées
// sur le bureau, sous les fenêtres, sans jamais prendre la souris. Même format que l'île (ILE_HEURE, date en français
// ou en anglais) et même allure (police, majuscules, rayon, couleurs du thème).
// Place : coin haut gauche, sous la barre. Le centre haut est celui de l'île, le fond animé couvre tout l'écran.
// Lisible sur fond clair comme sombre : une plaque arrondie semi-transparente aux couleurs du thème.
// Énergie : créé seulement à « oui » (shell.qml). Un seul minuteur, réglé sur la prochaine minute pile, arrêté écran
// éteint ou verrouillé et quand « Tout masquer » a caché les widgets (Etat.widgetsCaches) ; rien n'est redessiné entre deux minutes.
import QtQuick
import Quickshell
import Quickshell.Wayland

PanelWindow {
    id: b
    required property var modelData
    screen: modelData
    anchors { top: true; left: true }
    margins { top: 96; left: 48 }
    implicitWidth: plaque.width
    implicitHeight: plaque.height
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Bottom
    WlrLayershell.namespace: "nc-bureau"
    color: "transparent"
    mask: Region {}
    visible: !Etat.widgetsCaches
    readonly property Item cible: plaque               // pour outils/rendu-ile.py

    property string heure: Etat.heure
    property string date: Etat.dateLongue
    function maj() {
        Etat.majHeure()
        heure = Etat.heure; date = Etat.dateLongue
        minute.interval = Math.min(60000, 60000 - Date.now() % 60000 + 50)     // prochaine minute pile
    }
    readonly property bool vu: Etat.ecranVu && !Etat.widgetsCaches
    onVuChanged: if (vu) maj()
    Component.onCompleted: maj()
    // Un changement de format (ILE_HEURE) se voit tout de suite
    readonly property string format: Reglages.val("ILE_HEURE", "24")
    onFormatChanged: maj()

    Timer { id: minute; interval: 60000; repeat: true; running: b.vu; onTriggered: b.maj() }

    Rectangle {
        id: plaque
        width: col.implicitWidth + 64; height: col.implicitHeight + 44
        radius: Couleurs.rayon(36, width, height)
        color: Qt.rgba(Couleurs.carte.r, Couleurs.carte.g, Couleurs.carte.b, 0.62 * Couleurs.verre)
        border.width: Couleurs.epaisseur > 0 ? 1 : 0
        border.color: Couleurs.aContour ? Couleurs.accent : Qt.rgba(1, 1, 1, 0.14)
        Column {
            id: col
            anchors.centerIn: parent; spacing: 2
            Texte { objectName: "bureauHeure"; anchors.horizontalCenter: parent.horizontalCenter; text: b.heure; font.pixelSize: 88; font.weight: Font.Light }
            Texte { objectName: "bureauDate"; anchors.horizontalCenter: parent.horizontalCenter; text: b.date; secondaire: true; font.pixelSize: 22 }
        }
    }
}
