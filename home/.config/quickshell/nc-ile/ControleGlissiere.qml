// Glissière tactile du Centre de contrôle (volume, luminosité, mixeur audio) :
// icône cliquable, piste épaisse façon macOS / Material 3 / Brutaliste adaptée à chaque archétype de thème,
// glisser fluide, molette et bouton de détails optionnel.
import QtQuick

Item {
    id: glissiere
    property string icone: "volume_up"
    property string titre: ""
    property real valeur: 0.5
    property bool muet: false
    property bool aDetails: false
    property bool compact: false
    signal changer(real v)
    signal basculerMuet()
    signal ouvrirDetails()

    readonly property bool estBrut: Couleurs.styleBrut || Couleurs.styleTerminal
    readonly property bool estEditorial: Couleurs.styleEditorial
    readonly property bool estNeon: Couleurs.styleNeon
    readonly property real niveau: muet ? 0 : Math.max(0, Math.min(1, valeur))
    implicitHeight: compact ? 32 : 40
    function ajuster(pas) { changer(Math.max(0, Math.min(1, valeur + pas))) }

    // Bouton icône (ex. couper le son)
    Rectangle {
        id: boutonIco
        anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
        width: glissiere.compact ? 26 : 32
        height: width
        radius: Couleurs.rayon(glissiere.estBrut ? 2 : width / 2, width, height)
        color: zIco.contientPointeur ? Couleurs.accentDoux
             : (glissiere.estEditorial ? "transparent" : Qt.alpha(Couleurs.voile, Couleurs.sombre ? 0.07 : 0.06))
        border.width: (glissiere.estBrut || glissiere.estEditorial) ? 1 : 0
        border.color: zIco.contientPointeur ? Couleurs.accent : Couleurs.bordureSubtile
        Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 110 } }

        Ico {
            anchors.centerIn: parent
            nom: glissiere.icone
            taille: glissiere.compact ? 15 : 17
            color: glissiere.muet ? Couleurs.texteSec : Couleurs.accent
        }
        ControleAction {
            id: zIco
            anchors.fill: parent
            text: glissiere.titre
            onClicked: glissiere.basculerMuet()
        }
    }

    // Piste interactive (épaisse capsule façon Apple/M3, ou rail net sur Brutaliste/Terminal/Éditorial)
    Item {
        id: pisteZone
        anchors.left: boutonIco.right; anchors.leftMargin: 10
        anchors.right: pct.left; anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        height: glissiere.compact ? 24 : 30
        activeFocusOnTab: true
        Accessible.role: Accessible.Slider
        Accessible.name: glissiere.titre
        Accessible.description: pct.text
        Keys.onLeftPressed: glissiere.ajuster(-0.05)
        Keys.onRightPressed: glissiere.ajuster(0.05)
        Keys.onDownPressed: glissiere.ajuster(-0.05)
        Keys.onUpPressed: glissiere.ajuster(0.05)
        Keys.onPressed: event => {
            if (event.key === Qt.Key_Home) glissiere.changer(0)
            else if (event.key === Qt.Key_End) glissiere.changer(1)
            else return
            event.accepted = true
        }

        Rectangle {
            id: fondPiste
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width
            height: glissiere.estEditorial ? 4 : (glissiere.estBrut ? 10 : (glissiere.compact ? 10 : 14))
            radius: Couleurs.rayon(glissiere.estBrut ? 2 : height / 2, width, height)
            color: Qt.alpha(Couleurs.voile, Couleurs.sombre ? 0.11 : 0.10)
            border.width: pisteZone.activeFocus ? 2 : (glissiere.estBrut ? 1 : 0)
            border.color: pisteZone.activeFocus ? Couleurs.accent : Couleurs.bordureSubtile

            Rectangle {
                width: Math.max(glissiere.niveau > 0.01 ? height : 0, parent.width * glissiere.niveau)
                height: parent.height
                radius: parent.radius
                color: glissiere.muet ? Couleurs.gris4 : (glissiere.estNeon || glissiere.estBrut ? Couleurs.accent : Couleurs.jauge)
                Behavior on width { enabled: !dragPiste.pressed && !Reglages.sobre; NumberAnimation { duration: 80; easing.type: Easing.OutCubic } }
            }
        }

        // Curseur tactile (discret sur piste épaisse, net sur Editorial/Brut)
        Rectangle {
            id: curseur
            x: Math.max(0, Math.min(parent.width - width, parent.width * glissiere.niveau - width / 2))
            anchors.verticalCenter: parent.verticalCenter
            width: dragPiste.pressed || dragPiste.containsMouse
                   ? (glissiere.estBrut ? 12 : 18)
                   : (glissiere.estEditorial ? 14 : (glissiere.estBrut ? 10 : 16))
            height: glissiere.estBrut ? 16 : width
            radius: Couleurs.rayon(glissiere.estBrut ? 2 : width / 2, width, height)
            color: Couleurs.sombre ? "#ffffff" : Couleurs.fond
            border.width: 2
            border.color: glissiere.muet ? Couleurs.gris4 : Couleurs.accent
            Behavior on width { enabled: !Reglages.sobre; NumberAnimation { duration: 90 } }
        }

        MouseArea {
            id: dragPiste
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            function appliquer(mx) {
                if (width <= 0) return
                glissiere.changer(Math.max(0, Math.min(1, mx / width)))
            }
            onPressed: m => { pisteZone.forceActiveFocus(Qt.MouseFocusReason); appliquer(m.x) }
            onPositionChanged: m => { if (pressed) appliquer(m.x) }
            onWheel: w => {
                glissiere.ajuster(w.angleDelta.y > 0 ? 0.05 : -0.05)
                w.accepted = true
            }
        }
    }

    Texte {
        id: pct
        anchors.right: boutonDetails.visible ? boutonDetails.left : parent.right
        anchors.rightMargin: boutonDetails.visible ? 4 : 0
        anchors.verticalCenter: parent.verticalCenter
        width: 36
        horizontalAlignment: Text.AlignRight
        text: Math.round(glissiere.niveau * 100) + "%"
        secondaire: glissiere.muet
        font.pixelSize: glissiere.estBrut ? 11 : 12
        font.weight: Font.DemiBold
        font.features: ({ "tnum": 1 })
    }

    Rectangle {
        id: boutonDetails
        visible: glissiere.aDetails
        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
        width: 26; height: 26
        radius: Couleurs.rayon(glissiere.estBrut ? 2 : 13, width, height)
        color: zDet.contientPointeur ? Couleurs.accentDoux : "transparent"
        Ico { anchors.centerIn: parent; nom: "chevron_right"; taille: 17; color: zDet.contientPointeur ? Couleurs.accent : Couleurs.texteSec }
        ControleAction {
            id: zDet
            anchors.fill: parent
            text: Reglages.t("Détails : ", "Details: ") + glissiere.titre
            onClicked: glissiere.ouvrirDetails()
        }
    }
}
