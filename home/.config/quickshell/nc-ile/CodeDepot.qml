// Un dépôt de la liste « Depuis GitHub » (Code.qml, à droite) : propriétaire/dépôt, un cadenas s'il est privé, sa description
// (texte brut : Texte.qml) ; « déjà là » s'il est déjà sur le disque (Entrée l'ouvre), « dossier pris » si le dossier d'un
// clone existe déjà sans être lui (rien n'est cloné par-dessus). Le survol en fait la ligne choisie, un clic la lance.
import QtQuick

Item {
    id: ligne
    property var depot: ({})
    property bool actif: false
    signal survol()
    signal choisir()
    width: 300; height: 46

    Rectangle {
        anchors.fill: parent; radius: 12
        color: ligne.actif ? Qt.alpha(Couleurs.accent, 0.22) : "transparent"
        Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
    }
    Ico {
        id: icone
        x: 12; anchors.verticalCenter: parent.verticalCenter
        nom: ligne.depot && ligne.depot.la ? "folder_open" : "download"; taille: 20
        color: ligne.actif ? Couleurs.accent : Couleurs.texteSec
    }
    Ico {
        id: cadenas
        objectName: "nc-code-depot-cadenas"
        visible: !!(ligne.depot && ligne.depot.prive)
        anchors.left: icone.right; anchors.leftMargin: 10; y: 8
        nom: "lock"; taille: 14; color: Couleurs.texteSec
    }
    Texte {
        id: nom
        anchors.left: cadenas.visible ? cadenas.right : icone.right; anchors.leftMargin: cadenas.visible ? 4 : 12
        anchors.right: etiquette.visible ? etiquette.left : parent.right; anchors.rightMargin: etiquette.visible ? 12 : 12
        y: 7; height: 18
        text: ligne.depot && ligne.depot.nom ? ligne.depot.nom : ""
        font.pixelSize: 14; font.weight: Font.DemiBold
    }
    Texte {
        anchors.left: icone.right; anchors.leftMargin: 12; anchors.right: parent.right; anchors.rightMargin: 12
        y: 25; height: 16
        secondaire: true; font.pixelSize: 11
        text: ligne.depot && ligne.depot.description ? ligne.depot.description : ""
    }
    Rectangle {
        id: etiquette
        objectName: "nc-code-depot-etiquette"
        visible: !!(ligne.depot && (ligne.depot.la || ligne.depot.pris))
        anchors.right: parent.right; anchors.rightMargin: 12; y: 8
        width: libEtiquette.implicitWidth + 16; height: 18; radius: 9
        color: ligne.depot && ligne.depot.la ? Qt.alpha(Couleurs.accent, 0.18) : Qt.alpha(Couleurs.carte, 0.7)
        Texte {
            id: libEtiquette; anchors.centerIn: parent; font.pixelSize: 10; elide: Text.ElideNone
            text: ligne.depot && ligne.depot.la ? Reglages.t("déjà là", "already here") : Reglages.t("dossier pris", "folder taken")
            color: ligne.depot && ligne.depot.la ? Couleurs.accent : Couleurs.texteSec
        }
    }
    MouseArea {
        anchors.fill: parent; hoverEnabled: true
        onEntered: ligne.survol()
        onClicked: ligne.choisir()
    }
}
