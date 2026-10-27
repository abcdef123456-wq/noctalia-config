import QtQuick

// Une fenêtre bornée autour de la page active, même sur Recharge (140 px).
Item {
    id: navigation
    property var pages: []
    property int courant: 0
    signal choisir(string nom)
    // Nom lu par un lecteur d'écran : le libellé traduit de la page, pas son identifiant (« fenetres »)
    function libelle(nom) {
        var l = ({
            musique: ["Musique", "Music"], claude: ["Claude", "Claude"], minuteur: ["Minuteur", "Timer"], charge: ["Batterie", "Battery"],
            jeu: ["Jeu", "Game"], centre: ["Centre de contrôle", "Control Center"], assistant: ["Assistant", "Assistant"],
            notifications: ["Notifications", "Notifications"], son: ["Son", "Sound"], reseau: ["Réseau", "Network"],
            bluetooth: ["Bluetooth", "Bluetooth"], systeme: ["Système", "System"], calendrier: ["Calendrier", "Calendar"],
            meteo: ["Météo", "Weather"], presse: ["Presse-papiers", "Clipboard"], fenetres: ["Fenêtres", "Windows"],
            appel: ["Appel", "Call"], terminal: ["Terminal", "Terminal"]
        })[nom]
        return l ? Reglages.t(l[0], l[1]) : nom
    }
    clip: true
    implicitWidth: 18
    Repeater {
        model: navigation.pages
        Item {
            id: point
            required property string modelData
            required property int index
            readonly property int distance: Math.abs(index - navigation.courant)
            readonly property real bord: Math.min(y, navigation.height - y - height)
            width: navigation.width; height: 14
            y: (navigation.height - height) / 2 + (index - navigation.courant) * 14
            opacity: distance === 0 ? 1 : Math.pow(0.62, distance) * Math.max(0, Math.min(1, bord / 12))
            visible: navigation.height >= height && bord >= 0 && opacity > 0.02
            Rectangle {
                anchors.centerIn: parent
                width: 6; height: point.distance === 0 ? 14 : 6; radius: 3
                color: Couleurs.texte
            }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: navigation.choisir(point.modelData) }
            activeFocusOnTab: visible
            Keys.onReturnPressed: navigation.choisir(modelData)
            Keys.onSpacePressed: navigation.choisir(modelData)
            Accessible.role: Accessible.Button
            Accessible.name: navigation.libelle(modelData)
            Accessible.checkable: true
            Accessible.checked: distance === 0
            Accessible.onPressAction: navigation.choisir(modelData)
        }
    }
}
