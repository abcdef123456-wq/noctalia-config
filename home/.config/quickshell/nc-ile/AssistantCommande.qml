import QtQuick

Rectangle {
    id: bouton
    property string texte: ""
    property string icone: ""
    property string aide: texte
    property color accent: Couleurs.accent
    property bool choisi: false
    property bool contour: false
    property bool alerte: false
    property bool rond: false
    property bool occupe: false
    property bool animationsActives: true
    signal clic()
    implicitWidth: rond ? 36 : libelle.implicitWidth + 24
    implicitHeight: rond ? 36 : 30
    radius: rond ? width / 2 : 10
    color: alerte ? Couleurs.rouge : (choisi ? accent : (contour ? Qt.alpha(accent, zone.containsMouse ? 0.28 : 0.18) : (zone.containsMouse ? Couleurs.gris3 : Couleurs.gris2)))
    border.width: activeFocus || choisi || contour || alerte ? (contour ? 1.5 : 1) : 1
    border.color: alerte ? Qt.lighter(Couleurs.rouge, 1.15) : (activeFocus || choisi || contour ? accent : Couleurs.gris3)
    opacity: enabled || occupe ? 1 : 0.45
    activeFocusOnTab: true
    Row {
        id: libelle
        anchors.centerIn: parent; spacing: 5
        Ico {
            visible: bouton.icone !== "" && !bouton.occupe; nom: bouton.icone; taille: bouton.rond && bouton.width >= 42 ? 20 : 16
            color: bouton.alerte ? Couleurs.surCouleur : (bouton.choisi ? Couleurs.surAccent : (bouton.contour ? bouton.accent : (bouton.icone === "volume_off" ? Couleurs.texteSec : bouton.accent)))
        }
        Text {
            visible: bouton.texte !== ""; text: bouton.texte
            font.family: "Adwaita Sans"; font.pixelSize: 12; font.weight: Font.DemiBold
            color: bouton.alerte ? Couleurs.surCouleur : (bouton.choisi ? Couleurs.surAccent : Couleurs.texte)
        }
    }
    Item {
        id: attente
        objectName: "nc-assistant-button-spinner"
        anchors.centerIn: parent; width: 22; height: 22
        visible: bouton.occupe
        readonly property bool anime: visible && bouton.animationsActives && bouton.opacity > 0.01 && Reglages.val("EFFETS", "tous") !== "aucun"
        Ico { anchors.centerIn: parent; nom: "progress_activity"; taille: 22; color: bouton.accent }
        RotationAnimator on rotation { from: 0; to: 360; duration: 900; loops: Animation.Infinite; running: attente.anime }
    }
    MouseArea { id: zone; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bouton.clic() }
    Keys.onReturnPressed: clic()
    Keys.onSpacePressed: clic()
    Accessible.role: Accessible.Button
    Accessible.name: aide
    Accessible.onPressAction: clic()
}
