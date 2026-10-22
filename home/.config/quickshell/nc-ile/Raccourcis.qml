pragma Singleton
// Raccourcis clavier : la seule logique d'édition, partagée par la page « Raccourcis » des réglages (Parametres.qml)
// et la fiche des raccourcis (Fiche.qml, Super + /). Chaque changement passe par « nc-reglages raccourci JSON »
// (changer, desactiver, reactiver, origine, retirer, renommer, ajouter).
// Capture des nouvelles touches : Hyprland en mode « nc-capture » (sans raccourcis) le temps de les taper, 20 s au
// plus ; finCapture() rend toujours les raccourcis à Hyprland, même quand la capture est abandonnée.
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: rac
    readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
    property var capture: null                      // le raccourci dont on attend les nouvelles touches
    property var file: []                           // écritures en attente, une par une
    readonly property bool occupe: ecriture.running || file.length > 0
    property string message: ""
    property bool erreur: false
    // Le catalogue des raccourcis, gardé en mémoire : la fiche a ses lignes dès sa première image (lu au démarrage de
    // l'île, relu à chaque ouverture de la fiche et après chaque écriture)
    property var lignes: []
    function relire() { if (!lecture.running) lecture.running = true }
    onEcrit: relire()
    Process {
        id: lecture
        command: [rac.bin + "nc-reglages", "catalogue"]
        stdout: StdioCollector {
            onStreamFinished: { try { let l = JSON.parse(text).filter(r => r.genre === "raccourci"); if (l.length) rac.lignes = l } catch (e) {} }
        }
    }
    signal ecrit()                                  // une écriture finie : relire le catalogue
    signal captureFinie()                           // capture terminée ou abandonnée : rendre le focus

    function commande(args) { file.push(args); file = file; suivant() }
    function suivant() {
        if (ecriture.running || !file.length) return
        ecriture.command = file.shift(); file = file
        ecriture.running = true
    }
    // Un raccourci : changer (touches), desactiver, reactiver, origine, retirer, renommer (nom) — nc-reglages raccourci
    function raccourci(r, action, touches, nom) {
        commande([bin + "nc-reglages", "raccourci", JSON.stringify({ action: action, ids: r.ids, origs: r.origs,
                  nom: nom !== undefined ? nom : r.nom, mien: r.mien, touches: touches || "" })])
    }
    // Un raccourci à toi : cible = une appli (firefox), « bureau N », « ile PAGE » ou une commande (comme nc-raccourci)
    function ajouter(touches, cible, nom) {
        commande([bin + "nc-reglages", "raccourci", JSON.stringify({ action: "ajouter", touches: touches, cible: cible, nom: nom || "" })])
    }
    // ↺ : le raccourci d'origine, ou réactivé
    function remettre(r) {
        if (!r || r.genre !== "raccourci" || !r.modifie) return
        if (r.desactive) raccourci(r, "reactiver")
        else if (r.mien === "") raccourci(r, "origine")
    }
    // − : désactiver un raccourci de la config, retirer l'un des tiens
    function supprimer(r) {
        if (!r || r.genre !== "raccourci") return
        if (r.mien !== "") raccourci(r, "retirer")
        else if (!r.desactive) raccourci(r, "desactiver")
    }
    function capturer(r) {
        if (!r || !r.modifiable) return false
        capture = r
        Quickshell.execDetached([bin + "nc-reglages", "capture"])
        return true
    }
    // Toujours appelée en fin de capture (touches tapées, Échap, fenêtre fermée, 20 s écoulées) : Hyprland retrouve ses
    // raccourcis ; touches vides = abandon
    function finCapture(touches) {
        var r = capture
        if (!r) return
        capture = null
        Quickshell.execDetached([bin + "nc-reglages", "capture", "fin"])
        captureFinie()
        if (touches && r.ajout) ajouter(touches, r.ajout.cible, r.ajout.nom)      // capture d'un nouveau raccourci
        else if (touches) raccourci(r, "changer", touches)
    }
    Timer { running: !!rac.capture; interval: 20000; onTriggered: rac.finCapture("") }   // comme le retour automatique de Hyprland
    // Une touche du clavier -> « Super+Maj+T » (noms de nc-raccourci) ; "" pour un modificateur seul ; "annuler" pour Échap
    function combinaison(event) {
        var k = event.key
        if ([Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_Super_L, Qt.Key_Super_R, Qt.Key_AltGr, Qt.Key_CapsLock].indexOf(k) >= 0) return ""
        var mods = []
        if (event.modifiers & Qt.MetaModifier) mods.push("Super")
        if (event.modifiers & Qt.ControlModifier) mods.push("Ctrl")
        if (event.modifiers & Qt.AltModifier) mods.push("Alt")
        if (event.modifiers & Qt.ShiftModifier) mods.push("Maj")
        if (k === Qt.Key_Escape && !mods.length) return "annuler"
        var t = "", sc = event.nativeScanCode
        var noms = {}
        noms[Qt.Key_Return] = "Entrée"; noms[Qt.Key_Enter] = "Entrée"; noms[Qt.Key_Space] = "Espace"; noms[Qt.Key_Tab] = "Tab"
        noms[Qt.Key_Escape] = "Échap"; noms[Qt.Key_Print] = "Impr"; noms[Qt.Key_Delete] = "Suppr"
        noms[Qt.Key_Left] = "gauche"; noms[Qt.Key_Right] = "droite"; noms[Qt.Key_Up] = "haut"; noms[Qt.Key_Down] = "bas"
        if (sc >= 10 && sc <= 19) t = String((sc - 9) % 10)           // rangée des chiffres, quelle que soit la disposition
        else if (k >= Qt.Key_A && k <= Qt.Key_Z) t = String.fromCharCode(k)
        else if (k >= Qt.Key_0 && k <= Qt.Key_9) t = String.fromCharCode(k)
        else if (k >= Qt.Key_F1 && k <= Qt.Key_F12) t = "F" + (k - Qt.Key_F1 + 1)
        else t = noms[k] || ""
        if (!t) return "?"
        if (!mods.length && !/^F\d+$/.test(t)) return "?"
        return mods.concat([t]).join("+")
    }
    Process {
        id: ecriture
        stdout: StdioCollector { onStreamFinished: { rac.message = text.trim().split("\n").pop() || ""; rac.erreur = false } }
        stderr: StdioCollector { onStreamFinished: if (text.trim()) { rac.message = text.trim().split("\n").pop(); rac.erreur = true } }
        onExited: (code, status) => {
            if (code !== 0 && !rac.erreur) { rac.message = Reglages.t("Raccourci refusé.", "Shortcut rejected."); rac.erreur = true }
            rac.ecrit(); rac.suivant()
        }
    }
}
