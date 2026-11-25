// Le lanceur (Code.qml, Super + X) ou le tiroir JARVIS (JarvisChat.qml, Super + Maj + A) qui sort de la pilule de
// l'île : la carte part de la place, de la taille, du rayon et de la couleur EXACTS de la pilule, grandit avec un
// ressort (Mouvement.qml) jusqu'à sa taille, et la pilule se cache tant que la carte la recouvre ; à la fermeture,
// l'inverse, réversible à tout moment sans saut.
// Ouverture classique (actif reste faux) si : exigeReglage && ILE_LANCEUR_FONDU !== oui, animations coupées / partage
// d'écran (mouv.morphActif), pas d'île sur cet écran, ou pilule pas au repos (île ouverte, bannière, carte).
// Aucune animation en boucle : un ressort à l'ouverture, un à la fermeture, un garde-fou qui ne tire qu'une fois.
// Fichier à part : jamais un « component » dans un .qml existant (rechargement à chaud de qs).
// Idée seule, code à moi : ActivSpot (GPL v3) n'est pas repris.
import QtQuick

QtObject {
    id: f
    property string ecran: ""               // écran du lanceur
    property real largeurEcran: 0
    property bool exigeReglage: true        // Code.qml : lit ILE_LANCEUR_FONDU ; JarvisChat.qml : false (suit mouv.morphActif)
    property bool actif: false              // l'animation tourne pour ce panneau (décidé à l'ouverture)
    property bool fermeture: false
    property bool anime: false
    property bool _bascule: false
    property bool cache: false              // la pilule est cachée par ce lanceur
    property bool piluleRelachee: false     // la pilule est réapparue pendant que le tiroir est descendu ou épinglé
    property real p: 1                      // 0 = la pilule, 1 = le panneau à sa taille (peut dépasser 1 : rebond du ressort)
    // La pilule capturée (recapturée à la fermeture pour atterrir sur sa géométrie courante)
    property real x0: 0
    property real y0: 0
    property real w0: 0
    property real h0: 0
    property real r0: 0
    property color couleur0: "transparent"
    signal termine()

    readonly property var mouv: Mouvement.pourEcran(ecran)
    readonly property real q: Math.max(0, p)
    function mix(a, b) { return a + (b - a) * q }
    // De la couleur de la pilule à « vers » (alpha compris)
    function couleurVers(vers) {
        var t = Math.min(1, q), a = couleur0
        return Qt.rgba(a.r + (vers.r - a.r) * t, a.g + (vers.g - a.g) * t, a.b + (vers.b - a.b) * t, a.a + (vers.a - a.a) * t)
    }

    function capturerPilule(it) {
        w0 = it.width; h0 = it.height; r0 = it.radius; y0 = it.y; couleur0 = it.color
        x0 = Math.round((largeurEcran - w0) / 2)
    }

    // Vrai si l'animation part ou s'inverse ; faux = ouverture classique
    function demarrer() {
        if (actif) {
            if (fermeture) {
                _bascule = true
                fermeture = false
                garde.stop()
                anime = true
                p = 1
                _bascule = false
            }
            return true
        }
        if (exigeReglage && Reglages.val("ILE_LANCEUR_FONDU", "non") !== "oui") return false
        if (!mouv.morphActif) return false
        var it = Etat.pilules[ecran]
        if (!it || !it.auRepos || (Etat.lanceurFondu !== "" && Etat.lanceurProprio !== f) || largeurEcran <= 0) return false
        capturerPilule(it)
        piluleRelachee = false; fermeture = false; anime = false; p = 0; actif = true
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
        var it = Etat.pilules[ecran]
        if (it && it.auRepos && largeurEcran > 0) capturerPilule(it)
        if (p <= 0.001) { fermeture = true; finir(); return true }
        _bascule = true
        fermeture = true; anime = true
        p = 0
        _bascule = false
        if (!ressort.running && fermeture) { finir(); return true }
        garde.restart()
        return true
    }
    function relacherPilule() {
        piluleRelachee = true
        liberer()
    }
    function liberer() {
        if (Etat.lanceurProprio === f) { Etat.lanceurFondu = ""; Etat.lanceurProprio = null }
        cache = false
    }
    function annuler() {
        garde.stop()
        liberer()
        fermeture = false
        piluleRelachee = false
        anime = false
        actif = false
    }
    function finir() {
        if (!actif) return
        garde.stop()
        liberer()                           // la pilule revient d'abord, sous le panneau : jamais un instant sans rien
        fermeture = false
        piluleRelachee = false
        anime = false
        actif = false
        termine()
    }

    // La pilule se cache dès que le panneau la dépasse (jusque-là elle le recouvre, de la même couleur) ;
    // si elle a été relâchée pendant l'ouverture, elle ne se recache qu'à l'approche de l'atterrissage.
    onPChanged: {
        if (!actif) return
        if (!fermeture) {
            if (!cache && !piluleRelachee && p > 0.02) {
                Etat.lanceurProprio = f; Etat.lanceurFondu = ecran; cache = true
            }
        } else if (piluleRelachee && !cache && p > 0.02 && p < 0.25) {
            if (Etat.lanceurFondu === "" || Etat.lanceurProprio === f) {
                piluleRelachee = false
                Etat.lanceurProprio = f; Etat.lanceurFondu = ecran; cache = true
            }
        }
    }
    Behavior on p {
        enabled: f.anime
        SpringAnimation {
            id: ressort
            spring: f.mouv.raideur; damping: f.mouv.amortiL; epsilon: f.mouv.epsilonNorm
            onRunningChanged: if (!running && f.fermeture && !f._bascule) f.finir()
        }
    }
    // Filet si le ressort ne s'arrête pas : une seule fois, jamais en boucle
    property Timer garde: Timer {
        interval: Math.max(700, Math.round(900 * 100 / Math.max(50, Mouvement.vitessePct)))
        repeat: false
        onTriggered: f.finir()
    }
    Component.onDestruction: liberer()
}
