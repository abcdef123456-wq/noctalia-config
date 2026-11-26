// Bouton / pastille réutilisable de la fenêtre des réglages (Parametres.qml) :
// s'adapte automatiquement au thème actif (rayon, bordures, accents, état danger).
import QtQuick

Rectangle {
    id: bouton
    property string texte: ""
    property bool actif: false
    property bool petit: false
    property bool clavier: false
    property bool danger: false
    signal clic()

    width: etiquette.implicitWidth + (petit ? 20 : 28)
    height: petit ? 30 : 34
    radius: Couleurs.rayon(petit ? 10 : 12, width, height)
    color: danger
        ? (zp.containsMouse ? Qt.lighter(Couleurs.rouge, 1.08) : Couleurs.rouge)
        : (clavier ? Couleurs.accent
        : (actif ? Couleurs.accent
        : (zp.containsMouse ? Couleurs.gris3 : Couleurs.gris2)))
    border.width: clavier ? 2 : (actif || danger ? 0 : 1)
    border.color: clavier ? Couleurs.texte : Couleurs.bordureSubtile
    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 110 } }

    Texte {
        id: etiquette
        anchors.centerIn: parent
        text: bouton.texte
        font.pixelSize: bouton.petit ? 12 : 13
        font.weight: (bouton.actif || bouton.danger || bouton.clavier) ? Font.DemiBold : Font.Medium
        color: (bouton.danger || bouton.actif || bouton.clavier) ? Couleurs.surAccent : Couleurs.texte
    }
    MouseArea {
        id: zp
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: bouton.clic()
    }
    Accessible.role: Accessible.Button
    Accessible.name: bouton.texte
}
