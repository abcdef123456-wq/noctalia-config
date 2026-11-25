// Tuile tactile du Centre de contrôle : bascule directe sur le corps + chevron vers le tiroir natif dédié.
// Adapte son esthétique à l'archétype du thème actif (Apple, Brutaliste, Terminal, Éditorial, Néon, Noctalia).
import QtQuick

Rectangle {
    id: tuile
    property string icone: "tune"
    property string titre: ""
    property string sousTitre: ""
    property bool actif: false
    property bool aDetails: false
    property bool compact: false
    property color couleurActive: Couleurs.accent
    signal basculer()
    signal ouvrirDetails()

    readonly property bool estBrut: Couleurs.styleBrut || Couleurs.styleTerminal
    readonly property bool estEditorial: Couleurs.styleEditorial
    readonly property bool estNeon: Couleurs.styleNeon
    readonly property bool pleinActif: actif && estBrut

    implicitHeight: compact ? 48 : 56
    height: implicitHeight
    radius: Couleurs.rayon(estBrut ? 3 : (compact ? 14 : 16), width, height)
    color: {
        if (pleinActif) return zm.contientPointeur ? Qt.lighter(couleurActive, 1.08) : couleurActive
        if (actif) return zm.contientPointeur ? Qt.alpha(couleurActive, Couleurs.sombre ? 0.28 : 0.20)
                                             : Qt.alpha(couleurActive, Couleurs.sombre ? (estNeon ? 0.22 : 0.17) : 0.13)
        if (estEditorial) return zm.contientPointeur ? Couleurs.surfaceDouce : "transparent"
        return zm.contientPointeur ? Couleurs.carteSurvol : Couleurs.surfaceDouce
    }
    border.width: (estBrut || estEditorial || estNeon || actif) ? Couleurs.epaisseurBordureCarte : 1
    border.color: {
        if (actif) return estBrut || estNeon ? couleurActive : Qt.alpha(couleurActive, Couleurs.sombre ? 0.45 : 0.36)
        return zm.contientPointeur ? Couleurs.accentBord : Couleurs.bordureSubtile
    }
    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
    Behavior on border.color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }

    ControleAction {
        id: zm
        objectName: "nc-controle-action"
        anchors.top: parent.top; anchors.bottom: parent.bottom; anchors.left: parent.left
        anchors.right: tuile.aDetails ? btnDetails.left : parent.right
        text: tuile.titre + (tuile.sousTitre ? " · " + tuile.sousTitre : "")
        onClicked: tuile.basculer()
    }

    // Pastille d'icône (cercle translucide sur Apple/Noctalia, bloc net sur Brutaliste/Terminal)
    Rectangle {
        id: pastilleIco
        x: tuile.compact ? 9 : 11
        anchors.verticalCenter: parent.verticalCenter
        width: tuile.compact ? 28 : 32
        height: width
        radius: Couleurs.rayon(tuile.estBrut ? 2 : width / 2, width, height)
        color: tuile.pleinActif
               ? Qt.alpha(Couleurs.surAccent, 0.18)
               : (tuile.actif ? tuile.couleurActive : (Couleurs.sombre ? Qt.alpha(Couleurs.voile, 0.08) : Qt.alpha(Couleurs.voile, 0.07)))
        Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }

        Ico {
            anchors.centerIn: parent
            nom: tuile.icone
            taille: tuile.compact ? 15 : 17
            color: tuile.pleinActif ? Couleurs.surAccent : (tuile.actif ? Couleurs.surCouleur : Couleurs.texte)
            plein: tuile.actif
        }
    }

    Column {
        anchors.left: pastilleIco.right; anchors.leftMargin: tuile.compact ? 8 : 10
        anchors.right: tuile.aDetails ? btnDetails.left : parent.right
        anchors.rightMargin: tuile.aDetails ? 2 : 10
        anchors.verticalCenter: parent.verticalCenter
        spacing: 1

        Texte {
            width: parent.width
            text: tuile.estBrut ? tuile.titre.toUpperCase() : tuile.titre
            font.pixelSize: tuile.estBrut ? 10 : (tuile.compact ? 11 : 12)
            font.weight: Font.DemiBold
            font.letterSpacing: tuile.estBrut ? 0.6 : 0
            color: tuile.pleinActif ? Couleurs.surAccent : Couleurs.texte
        }
        Texte {
            width: parent.width
            visible: tuile.sousTitre !== ""
            text: tuile.sousTitre
            font.pixelSize: 10
            secondaire: !tuile.pleinActif
            color: tuile.pleinActif ? Qt.alpha(Couleurs.surAccent, 0.85) : (tuile.actif ? Couleurs.texteDoux : Couleurs.texteSec)
        }
    }

    // Bouton chevron indépendant (ouvre la sous-vue dédiée sans basculer l'interrupteur)
    Item {
        id: btnDetails
        visible: tuile.aDetails
        anchors.top: parent.top; anchors.bottom: parent.bottom; anchors.right: parent.right
        width: 30

        Rectangle {
            anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
            width: 1; height: parent.height - 20
            color: tuile.pleinActif ? Qt.alpha(Couleurs.surAccent, 0.25) : Couleurs.separateur
        }
        Rectangle {
            anchors.centerIn: parent
            width: 22; height: 22
            radius: Couleurs.rayon(tuile.estBrut ? 2 : 11, width, height)
            color: zd.contientPointeur
                   ? (tuile.pleinActif ? Qt.alpha(Couleurs.surAccent, 0.22) : Qt.alpha(Couleurs.voile, 0.12))
                   : "transparent"
        }
        Ico {
            anchors.centerIn: parent
            nom: "chevron_right"; taille: 16
            color: tuile.pleinActif ? Couleurs.surAccent : (zd.contientPointeur ? Couleurs.texte : Couleurs.texteSec)
        }
        ControleAction {
            id: zd
            objectName: "nc-controle-details"
            anchors.fill: parent
            text: Reglages.t("Détails : ", "Details: ") + tuile.titre
            onClicked: tuile.ouvrirDetails()
        }
    }

}
