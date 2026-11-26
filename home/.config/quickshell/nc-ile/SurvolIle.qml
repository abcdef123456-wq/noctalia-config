// Île survolée (Ile.qml, ILE_SURVOL) : la loupe au bout de la ligne et, pendant une musique, la progression du morceau
// en dessous. Le survol n'ouvre rien : seul un clic sur la loupe (ou Super + R) ouvre la recherche, depuis l'île.
// Fondu seulement (durée courte de Mouvement.qml) : la taille de l'île suit déjà ses ressorts, rien n'est recalculé
// image par image ici.
import QtQuick

Item {
    id: s
    property bool montre: false
    property int ligne: 30
    property var mouv: ({ actif: false, dureeCourte: 0, courbe: Easing.OutCubic })
    readonly property bool musique: Etat.aMusique && Etat.lecteur !== null && Etat.lecteur.length > 0
    // Ce que l'île prend en plus au survol (Ile.qml) : 20 px de chaque côté (le contenu reste centré, la loupe à
    // droite), la ligne de la progression en dessous
    readonly property real largeurEnPlus: 40
    readonly property real hauteurEnPlus: musique ? 36 : 0
    // Sur la loupe ? (coordonnées de l'île, comme Compact.surVpn)
    function surLoupe(x, y) {
        if (!montre) return false
        var p = s.parent.mapToItem(loupe, x, y)
        return p.x >= -8 && p.x <= loupe.width + 8 && p.y >= -8 && p.y <= loupe.height + 8
    }
    function temps(t) {
        t = Math.max(0, Math.floor(t || 0))
        return Math.floor(t / 60) + ":" + String(t % 60).padStart(2, "0")
    }

    opacity: montre ? 1 : 0
    visible: opacity > 0.01
    Behavior on opacity { enabled: s.mouv.actif; NumberAnimation { duration: s.mouv.dureeCourte; easing.type: s.mouv.courbe } }

    Ico {
        id: loupe
        objectName: "nc-ile-loupe"
        x: s.width - width - 12
        y: (s.ligne - height) / 2
        nom: "search"; taille: 17; color: Couleurs.texteDoux
        Accessible.role: Accessible.Button
        Accessible.name: Reglages.t("Rechercher", "Search")
    }

    // Progression du morceau : rail, temps écoulé et durée ; la position est relue chaque seconde tant qu'on la montre
    Item {
        id: progression
        objectName: "nc-ile-progression"
        visible: s.musique
        x: 14; y: s.ligne + 2
        width: s.width - 28; height: 28
        readonly property real f: s.musique ? Math.max(0, Math.min(1, Etat.lecteur.position / Etat.lecteur.length)) : 0
        Rectangle {
            id: rail
            width: parent.width; height: 3; radius: Couleurs.rayon(1.5, width, height); color: Couleurs.gris3
            Rectangle { width: rail.width * progression.f; height: parent.height; radius: parent.radius; color: Couleurs.jauge }
        }
        Texte { y: 8; text: s.temps(s.musique ? Etat.lecteur.position : 0); secondaire: true; font.pixelSize: 10; font.features: { "tnum": 1 } }
        Texte { y: 8; anchors.right: parent.right; text: s.temps(s.musique ? Etat.lecteur.length : 0); secondaire: true; font.pixelSize: 10; font.features: { "tnum": 1 } }
    }
    Timer {
        interval: 1000; repeat: true; triggeredOnStart: true
        running: s.montre && s.musique && Etat.joue
        onTriggered: if (Etat.lecteur) Etat.lecteur.positionChanged()
    }
}
