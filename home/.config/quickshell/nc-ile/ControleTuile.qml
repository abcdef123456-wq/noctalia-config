// Tuile d'action rapide du Centre de contrôle : bascule au clic, détail optionnel au chevron ou clic droit.
// S'adapte au style du thème actif (Couleurs.familleTheme, rayon, bordure, accents).
import QtQuick

Rectangle {
    id: tuile
    property string icone: "tune"
    property string titre: ""
    property string sousTitre: ""
    property bool actif: false
    property color couleurActive: Couleurs.accent
    property bool aDetails: false
    property bool compact: false
    signal basculer()
    signal ouvrirDetails()

    readonly property bool estBrut: Couleurs.familleTheme === "brut" || Couleurs.forme === "cadre"
    readonly property bool survol: zonePrincipale.containsMouse || (aDetails && zoneDetails.containsMouse)

    implicitHeight: compact ? 48 : 62
    radius: Couleurs.rayon(compact ? 14 : 16, width, height)
    color: actif
        ? (estBrut ? Qt.alpha(couleurActive, 0.22) : (survol ? Qt.lighter(couleurActive, 1.06) : couleurActive))
        : (survol ? Couleurs.carteSurvol : Couleurs.carte)
    border.width: actif ? (estBrut ? Couleurs.epaisseurBordureCarte : 0) : 1
    border.color: actif ? couleurActive : Couleurs.bordureSubtile

    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 130 } }

    readonly property color couleurTexte: actif
        ? (estBrut ? Couleurs.texte : (Qt.colorEqual(couleurActive, Couleurs.accent) ? Couleurs.surAccent : Couleurs.surCouleur))
        : Couleurs.texte
    readonly property color couleurSecondaire: actif
        ? (estBrut ? couleurActive : Qt.alpha(couleurTexte, 0.82))
        : Couleurs.texteSec

    // Zone principale : bascule l'état (clic droit : ouvre les détails si présents)
    MouseArea {
        id: zonePrincipale
        anchors.top: parent.top; anchors.bottom: parent.bottom; anchors.left: parent.left
        anchors.right: boutonDetails.visible ? boutonDetails.left : parent.right
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: m => {
            if (m.button === Qt.RightButton && tuile.aDetails) tuile.ouvrirDetails()
            else tuile.basculer()
        }
    }

    // Badge d'icône
    Rectangle {
        id: badge
        x: tuile.compact ? 10 : 12
        anchors.verticalCenter: parent.verticalCenter
        width: tuile.compact ? 28 : 34
        height: width
        radius: Couleurs.estCarre ? Couleurs.rayon(8, width, height) : width / 2
        color: tuile.actif
            ? (tuile.estBrut ? tuile.couleurActive : Qt.alpha(tuile.couleurTexte, 0.18))
            : Couleurs.gris2
        Ico {
            anchors.centerIn: parent
            nom: tuile.icone
            taille: tuile.compact ? 16 : 18
            color: tuile.actif
                ? (tuile.estBrut ? Couleurs.surAccent : tuile.couleurTexte)
                : Couleurs.texte
        }
    }

    Column {
        anchors.left: badge.right; anchors.leftMargin: 10
        anchors.right: boutonDetails.visible ? boutonDetails.left : parent.right
        anchors.rightMargin: boutonDetails.visible ? 4 : 10
        anchors.verticalCenter: parent.verticalCenter
        spacing: 1

        Texte {
            width: parent.width
            text: tuile.titre
            font.pixelSize: tuile.compact ? 12 : 13
            font.weight: Font.DemiBold
            color: tuile.couleurTexte
        }
        Texte {
            width: parent.width
            visible: tuile.sousTitre !== ""
            text: tuile.sousTitre
            font.pixelSize: 11
            color: tuile.couleurSecondaire
        }
    }

    // Bouton chevron pour ouvrir la sous-vue détaillée
    Item {
        id: boutonDetails
        visible: tuile.aDetails
        anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom
        width: 30

        Rectangle {
            anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
            width: 1; height: parent.height - 20
            color: tuile.actif ? Qt.alpha(tuile.couleurTexte, 0.22) : Couleurs.separateur
        }
        Ico {
            anchors.centerIn: parent
            nom: "chevron_right"
            taille: 17
            color: tuile.couleurSecondaire
            opacity: zoneDetails.containsMouse ? 1 : 0.78
        }
        MouseArea {
            id: zoneDetails
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: tuile.ouvrirDetails()
        }
        Accessible.role: Accessible.Button
        Accessible.name: Reglages.t("Détails : ", "Details: ") + tuile.titre
    }

    Accessible.role: Accessible.Button
    Accessible.name: tuile.titre + (tuile.sousTitre !== "" ? " · " + tuile.sousTitre : "")
    Accessible.checkable: true
    Accessible.checked: tuile.actif
}
