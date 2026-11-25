// Glissière horizontale du Centre de contrôle (volume, luminosité) : icône cliquable, piste fluide, pourcentage,
// accès optionnel aux détails (périphériques audio) et molette.
import QtQuick

Item {
    id: glissiere
    property string icone: "volume_up"
    property string titre: ""
    property real valeur: 0.5
    property bool muet: false
    property bool aDetails: false
    signal changer(real v)
    signal basculerMuet()
    signal ouvrirDetails()

    readonly property real niveau: muet ? 0 : Math.max(0, Math.min(1, valeur))
    implicitHeight: 38

    // Bouton icône (ex. couper le son)
    Rectangle {
        id: boutonIco
        anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
        width: 32; height: 32
        radius: Couleurs.rayon(10, width, height)
        color: zIco.containsMouse ? Couleurs.gris3 : Couleurs.gris2
        Ico {
            anchors.centerIn: parent
            nom: glissiere.icone
            taille: 17
            color: glissiere.muet ? Couleurs.texteSec : Couleurs.accent
        }
        MouseArea {
            id: zIco
            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
            onClicked: glissiere.basculerMuet()
        }
        Accessible.role: Accessible.Button
        Accessible.name: glissiere.titre
    }

    // Piste interactive
    Item {
        id: pisteZone
        anchors.left: boutonIco.right; anchors.leftMargin: 10
        anchors.right: pct.left; anchors.rightMargin: 10
        anchors.verticalCenter: parent.verticalCenter
        height: 28

        Rectangle {
            id: fondPiste
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width; height: 8
            radius: Couleurs.rayon(4, width, height)
            color: Couleurs.gris2

            Rectangle {
                width: Math.max(height, parent.width * glissiere.niveau)
                height: parent.height
                radius: Couleurs.rayon(4, width, height)
                color: glissiere.muet ? Couleurs.gris4 : Couleurs.jauge
                Behavior on width { enabled: !dragPiste.pressed && !Reglages.sobre; NumberAnimation { duration: 90; easing.type: Easing.OutCubic } }
            }
        }

        // Curseur tactile
        Rectangle {
            id: curseur
            x: Math.max(0, Math.min(parent.width - width, parent.width * glissiere.niveau - width / 2))
            anchors.verticalCenter: parent.verticalCenter
            width: dragPiste.pressed || dragPiste.containsMouse ? 16 : 14
            height: width
            radius: Couleurs.estCarre ? Couleurs.rayon(4, width, height) : width / 2
            color: Couleurs.texte
            border.width: 2
            border.color: Couleurs.accent
            Behavior on width { enabled: !Reglages.sobre; NumberAnimation { duration: 100 } }
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
            onPressed: m => appliquer(m.x)
            onPositionChanged: m => { if (pressed) appliquer(m.x) }
            onWheel: w => {
                var pas = w.angleDelta.y > 0 ? 0.05 : -0.05
                glissiere.changer(Math.max(0, Math.min(1, glissiere.valeur + pas)))
                w.accepted = true
            }
        }
    }

    Texte {
        id: pct
        anchors.right: boutonDetails.visible ? boutonDetails.left : parent.right
        anchors.rightMargin: boutonDetails.visible ? 6 : 2
        anchors.verticalCenter: parent.verticalCenter
        width: 38
        horizontalAlignment: Text.AlignRight
        text: Math.round(glissiere.niveau * 100) + Reglages.t(" %", "%")
        secondaire: glissiere.muet
        font.pixelSize: 12
        font.weight: Font.DemiBold
        font.features: ({ "tnum": 1 })
    }

    Rectangle {
        id: boutonDetails
        visible: glissiere.aDetails
        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
        width: 28; height: 28
        radius: Couleurs.rayon(10, width, height)
        color: zDet.containsMouse ? Couleurs.gris3 : "transparent"
        Ico { anchors.centerIn: parent; nom: "chevron_right"; taille: 17; color: Couleurs.texteSec }
        MouseArea {
            id: zDet
            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
            onClicked: glissiere.ouvrirDetails()
        }
        Accessible.role: Accessible.Button
        Accessible.name: Reglages.t("Détails : ", "Details: ") + glissiere.titre
    }
}
