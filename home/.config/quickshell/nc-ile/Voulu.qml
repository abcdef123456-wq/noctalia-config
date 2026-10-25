// Réactivité des interrupteurs de l'île : un état « voulu » par clé (wifi, bluetooth, protection, halo…) qui prend le
// pas sur la mesure dès le clic, jusqu'à ce que la mesure le confirme, ou au plus `grace` ms (3 s). Une mesure
// contraire pendant la grâce ne retourne pas le bouton (pas de scintillement) ; si la commande échoue, on revient tout
// de suite à l'état réel. Les commandes sont suivies ici (code de retour) : `fini` sert à relire l'état dès leur fin.
pragma ComponentBehavior: Bound
import QtQuick
import QtQml
import Quickshell
import Quickshell.Io

Scope {
    id: v
    property int grace: 3000
    // cle -> { valeur, fin } ; remplacé en entier à chaque changement (les liaisons se réévaluent)
    property var voulus: ({})
    // Donne la mesure actuelle d'une clé (fournie par Etat) ; undefined si inconnue
    property var mesure: cle => undefined

    signal echec(string cle, int code)
    signal fini(string cle, int code)

    function voulu(cle, valeur) {
        var t = Object.assign({}, voulus)
        t[cle] = { valeur: String(valeur), fin: Date.now() + grace }
        voulus = t
    }
    // La valeur à afficher : le voulu s'il y en a un, sinon la mesure
    function valeur(cle, m) {
        var w = voulus[cle]
        return w === undefined ? m : w.valeur
    }
    function annuler(cle) {
        if (voulus[cle] === undefined) return
        var t = Object.assign({}, voulus)
        delete t[cle]
        voulus = t
    }
    // À appeler quand une mesure vient d'être relue : un voulu confirmé s'efface (un contraire est ignoré)
    function confirmer() {
        var cles = Object.keys(voulus)
        for (let i = 0; i < cles.length; i++)
            if (String(mesure(cles[i])) === voulus[cles[i]].valeur) annuler(cles[i])
    }
    function expirer() {
        var cles = Object.keys(voulus), maintenant = Date.now()
        for (let i = 0; i < cles.length; i++)
            if (maintenant >= voulus[cles[i]].fin) annuler(cles[i])
    }
    Timer { interval: 200; repeat: true; running: Object.keys(v.voulus).length > 0; onTriggered: v.expirer() }

    // ── Commandes suivies ──
    property int compteur: 0
    function lancer(cmd, cle) {
        compteur++
        // Une commande d'interrupteur qui ne finit jamais est arrêtée au bout de 30 s (code 124 : échec, retour à la mesure)
        const argv = cle ? ["timeout", "30"].concat(cmd) : cmd
        rangees.append({ ident: compteur, cmdJson: JSON.stringify(argv), cle: cle || "" })
    }
    function finCommande(ident, code) {
        var cle = ""
        for (let i = 0; i < rangees.count; i++)
            if (rangees.get(i).ident === ident) { cle = rangees.get(i).cle; break }
        if (code !== 0 && cle !== "") { annuler(cle); echec(cle, code) }
        fini(cle, code)
        Qt.callLater(retirer, ident)
    }
    function retirer(ident) {
        for (let i = 0; i < rangees.count; i++)
            if (rangees.get(i).ident === ident) { rangees.remove(i); return }
    }
    ListModel { id: rangees }
    Instantiator {
        model: rangees
        delegate: Process {
            required property int ident
            required property string cmdJson
            command: JSON.parse(cmdJson)
            running: true
            onExited: (code, statut) => v.finCommande(ident, code)
            // Binaire introuvable : le processus ne démarre pas (jamais « started » ni « exited », seulement running qui
            // retombe) : c'est un échec
            property bool demarre: false
            onStarted: demarre = true
            onRunningChanged: if (!running && !demarre) v.finCommande(ident, -1)
        }
    }
}
