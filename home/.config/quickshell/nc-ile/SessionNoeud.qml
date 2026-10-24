// Bandeau de la session de confiance de JARVIS (Noeud.qml, nc-noeud, issue #21) : quand une session est ouverte,
// l'île fermée s'étire en bandeau « Session JARVIS · N actions · M:SS » avec un bouton [Arrêter]. Chaque action de la
// session est aussi notifiée par nc-noeud. Arrêter écrit un marqueur que nc-noeud relit avant l'action suivante.
// Fichier à part (pas un composant interne d'Ile.qml) : le rechargement à chaud de Quickshell ne connaît pas les
// nouveaux composants internes d'un fichier déjà chargé.
import QtQuick

Item {
    id: s
    implicitHeight: 72
    readonly property var vue: Noeud.session
    readonly property int reste: Noeud.sessionReste
    readonly property string mmss: {
        var r = reste, mn = Math.floor(r / 60), sec = r % 60
        return mn + ":" + (sec < 10 ? "0" + sec : sec)
    }

    Row {
        x: 18; y: 14; spacing: 8
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "smart_toy"; taille: 16; color: Couleurs.texteSec }
        Texte {
            anchors.verticalCenter: parent.verticalCenter; font.pixelSize: 13; font.weight: Font.DemiBold
            text: Reglages.t("Session JARVIS", "JARVIS session")
        }
    }
    Texte {
        objectName: "nc-session-reste"
        anchors.right: parent.right; anchors.rightMargin: 18; y: 16
        secondaire: true; font.pixelSize: 12
        text: s.vue ? (Number(s.vue.reste_actions) + Reglages.t(" actions · ", " actions · ") + s.mmss) : ""
    }
    Row {
        x: 18; y: 42; spacing: 8; width: parent.width - 36
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "lock"; taille: 13; color: Couleurs.texteSec }
        Texte {
            anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.pixelSize: 12
            width: Math.min(implicitWidth, s.width - 160); elide: Text.ElideRight
            text: Reglages.t("Commandes en bac à sable, sans reconfirmer", "Commands sandboxed, no reconfirming")
        }
    }
    // Bouton « Arrêter la session » (à droite, comme le bouton principal des cartes)
    Rectangle {
        objectName: "nc-session-arreter"
        anchors.right: parent.right; anchors.rightMargin: 18; y: 38
        width: Math.max(96, la.implicitWidth + 30); height: 34; radius: 17
        color: za.containsMouse ? Couleurs.gris3 : Couleurs.gris2
        scale: za.pressed ? 0.95 : 1
        Behavior on scale { enabled: !Reglages.sobre; SpringAnimation { spring: 6; damping: 0.45 } }
        Texte {
            id: la; anchors.centerIn: parent; text: Reglages.t("Arrêter", "Stop")
            font.pixelSize: 13; font.weight: Font.DemiBold; color: Couleurs.texte
        }
        MouseArea {
            id: za; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
            onClicked: Noeud.arreterSession()
        }
        Accessible.role: Accessible.Button
        Accessible.name: la.text
    }
}
