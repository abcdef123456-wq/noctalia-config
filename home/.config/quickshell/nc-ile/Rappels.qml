pragma Singleton
// Rappels locaux (Spotlight « rappel 15h appeler le garage », « rappels ») : la liste { id, texte, due } est gardée par
// Memo (« rappels », fichier privé) et survit aux redémarrages. UN SEUL minuteur, non répétitif, visé sur la prochaine
// échéance, et armé seulement s'il y a un rappel en attente. Au tir on compare à l'heure réelle puis on réarme.
// Limite connue : le minuteur ne compte pas la veille ; un rappel échu pendant la veille s'affiche au retour de l'écran
// (Etat.ecranVu repasse à vrai : écran rallumé ou session déverrouillée).
import QtQuick
import Quickshell
import "Rappels.js" as R

Singleton {
    id: r
    property var liste: []
    property bool lance: false
    readonly property int nombre: liste.length
    readonly property bool plein: liste.length >= R.MAX_RAPPELS

    // Appelé une fois au démarrage de l'île (shell.qml) : relit la liste, montre les échus une seule fois
    function demarrer() {
        if (lance) return
        lance = true
        Memo.lire("rappels", v => {
            liste = R.valider(v).concat(liste.filter(x => !R.valider(v).some(y => y.id === x.id))).slice(0, R.MAX_RAPPELS)
            verifier()
        })
    }
    function analyser(phrase) { return R.analyser(phrase, Date.now()) }
    function quand(due) { return R.quand(due, Date.now(), Reglages.en) }
    function creer(texte, due) {
        var a = R.ajouter(liste, texte, due, Date.now())
        if (!a.ok) return false
        liste = a.liste
        garder()
        return true
    }
    function supprimer(id) { liste = R.retirer(liste, id); garder() }
    function garder() { Memo.ecrire("rappels", liste); armer() }

    // Les échus sont retirés puis montrés (une fois chacun) ; le minuteur vise ensuite la prochaine échéance
    function verifier() {
        var p = R.partager(liste, Date.now())
        if (p.dus.length) {
            liste = p.restants
            Memo.ecrire("rappels", liste)
            p.dus.forEach(x => Notifs.rappeler(x.texte))
        }
        armer()
    }
    function armer() {
        var p = R.partager(liste, Date.now())
        if (p.prochaine === null) { minuteur.stop(); return }
        minuteur.interval = R.delai(p.prochaine, Date.now())
        minuteur.restart()
    }
    Connections { target: Etat; function onEcranVuChanged() { if (Etat.ecranVu && r.lance) r.verifier() } }
    Timer { id: minuteur; repeat: false; onTriggered: r.verifier() }
}
