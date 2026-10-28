// Le lanceur (Code.qml, Super + X) qui sort de la pilule de l'île : le panneau part de la place, de la taille, du rayon et de la
// couleur EXACTS de la pilule, grandit avec un ressort jusqu'à sa taille, et la pilule se cache le temps de l'animation ; à la
// fermeture, l'inverse. Réglage ILE_LANCEUR_FONDU (non par défaut). Aucune animation en boucle : un ressort à l'ouverture, un à
// la fermeture, un garde-fou qui ne tire qu'une fois.
// Ouverture classique (actif reste faux) si : réglage non, animations réduites, partage d'écran, pas d'île sur cet écran, ou
// pilule pas au repos (île ouverte, bannière, carte). Le clavier et le focus ne dépendent pas de cette animation.
// Le Spotlight (Recherche.qml) n'en a pas besoin : il est déjà la pilule elle-même, qui grandit.
// Fichier à part : jamais un « component » dans un .qml existant (rechargement à chaud de qs).
// Idée seule, code à moi : ActivSpot (GPL v3) n'est pas repris.
import QtQuick

QtObject {
    id: f
    property string ecran: ""               // écran du lanceur
    property real largeurEcran: 0
    property bool actif: false              // l'animation tourne pour ce lanceur (décidé une fois, à l'ouverture)
    property bool fermeture: false
    property bool anime: false
    property bool cache: false              // la pilule est cachée par ce lanceur
    property real p: 1                      // 0 = la pilule, 1 = le lanceur à sa taille (peut dépasser 1 : rebond du ressort)
    // La pilule au moment de l'ouverture (copie : rien ne suit ensuite)
    property real x0: 0
    property real y0: 0
    property real w0: 0
    property real h0: 0
    property real r0: 0
    property color couleur0: "transparent"
    signal termine()

    readonly property real q: Math.max(0, p)
    function mix(a, b) { return a + (b - a) * q }
    // De la couleur de la pilule à « vers » (alpha compris)
    function couleurVers(vers) {
        var t = Math.min(1, q), a = couleur0
        return Qt.rgba(a.r + (vers.r - a.r) * t, a.g + (vers.g - a.g) * t, a.b + (vers.b - a.b) * t, a.a + (vers.a - a.a) * t)
    }

    // Vrai si l'animation part ; faux = ouverture classique
    function demarrer() {
        if (actif || Reglages.val("ILE_LANCEUR_FONDU", "non") !== "oui" || Reglages.sobre) return false
        if (Partage.silence || Partage.indicateur || Partage.sessions > 0) return false
        var it = Etat.pilules[ecran]
        if (!it || !it.auRepos || Etat.lanceurFondu !== "" || largeurEcran <= 0) return false
        w0 = it.width; h0 = it.height; r0 = it.radius; y0 = it.y; couleur0 = it.color
        x0 = Math.round((largeurEcran - w0) / 2)
        fermeture = false; anime = false; p = 0; actif = true
        Qt.callLater(lancerOuverture)
        return true
    }
    function lancerOuverture() {
        if (!actif || fermeture) return
        anime = true
        p = 1
    }
    // Vrai si l'animation prend la fermeture en charge (« termine » vient à la fin) ; faux = fermer tout de suite
    function fermer() {
        if (!actif) return false
        if (fermeture) return true
        fermeture = true; anime = true
        if (p <= 0.001) { finir(); return true }
        p = 0
        garde.restart()
        return true
    }
    function liberer() {
        if (Etat.lanceurProprio === f) { Etat.lanceurFondu = ""; Etat.lanceurProprio = null }
        cache = false
    }
    function finir() {
        if (!actif) return
        garde.stop()
        liberer()                           // la pilule revient d'abord, sous le panneau : jamais un instant sans rien
        actif = false
        termine()
    }

    // La pilule se cache dès que le panneau la dépasse (jusque-là elle le recouvre, de la même couleur)
    onPChanged: if (actif && !cache && !fermeture && p > 0.02) {
        Etat.lanceurProprio = f; Etat.lanceurFondu = ecran; cache = true
    }
    Behavior on p {
        enabled: f.anime
        SpringAnimation {
            spring: 3.4; damping: 0.34; epsilon: 0.001
            onRunningChanged: if (!running && f.fermeture) f.finir()
        }
    }
    // Filet si le ressort ne s'arrête pas : une seule fois, jamais en boucle
    property Timer garde: Timer { interval: 700; repeat: false; onTriggered: f.finir() }
    Component.onDestruction: liberer()
}
