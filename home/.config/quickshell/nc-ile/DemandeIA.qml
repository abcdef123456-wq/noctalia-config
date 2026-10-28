// Une demande à l'IA du bureau (nc-ia), toujours sur un clic de l'utilisateur, jamais seule.
// - Tout passe par nc-ia (nc-ia demander --usage texte --flux -) : jamais d'appel direct à une API. nc-ia n'a aucun outil
//   pour cet usage (« texte ») : il répond à partir du texte donné, rien d'autre.
// - La consigne ET les données vont sur l'entrée standard, jamais dans les arguments (un « ps » les montrerait) ;
//   les données sont bornées (maxDonnees) et la réponse aussi (maxReponse). La consigne dit que les données sont des
//   données et non des ordres.
// - Un seul appel à la fois par objet ; délai borné (delai) ; arreter() coupe l'attente.
// - IA coupée (IA_MODE=non) : lancer() ne fait rien.
// La réponse est du texte brut : la montrer dans Texte.qml (PlainText), jamais en rich text.
// Fichier à part (pas un composant interne) : le rechargement à chaud de Quickshell ne connaît pas les nouveaux
// composants internes d'un fichier déjà chargé.
import QtQuick
import Quickshell.Io

Item {
    id: d
    visible: false; width: 0; height: 0
    property bool local: false             // préférer l'IA de ce PC (nc-ia demander --local) : le texte n'en sort pas
    property int delai: 60000              // ms avant d'abandonner
    property int maxDonnees: 4096          // caractères de données envoyés au plus
    property int maxReponse: 1500          // caractères de réponse gardés au plus
    property string reponse: ""
    property string qui: ""                // l'IA qui répond
    property string erreur: ""
    property string envoi: ""              // ce qui part sur l'entrée standard
    readonly property bool enCours: proc.running

    function lancer(consigne, donnees) {
        if (proc.running || Reglages.iaCoupee) return
        reponse = ""; qui = ""; erreur = ""
        envoi = String(consigne) + "\n\n---\n" + String(donnees).slice(0, maxDonnees) + "\n---\n"
        proc.stdinEnabled = true
        proc.running = true
        tempo.restart()
    }
    function arreter() { if (proc.running) { proc.running = false } tempo.stop() }
    function vider() { arreter(); reponse = ""; qui = ""; erreur = "" }

    Timer {
        id: tempo
        interval: d.delai
        onTriggered: { if (proc.running) { proc.running = false; d.erreur = Reglages.t("Délai dépassé.", "Timed out.") } }
    }
    Process {
        id: proc
        command: [Etat.bin + "nc-ia", "demander", "--usage", "texte", "--flux"].concat(d.local ? ["--local"] : []).concat(["-"])
        onStarted: { write(d.envoi); stdinEnabled = false }
        stdout: SplitParser {
            onRead: l => {
                try {
                    let o = JSON.parse(l)
                    if (o.ia) d.qui = String(o.ia).slice(0, 60)
                    if (o.t) d.reponse = (d.reponse + o.t).slice(0, d.maxReponse)
                } catch (e) {}
            }
        }
        stderr: StdioCollector {
            onStreamFinished: if (d.reponse === "" && d.erreur === "" && text.trim() !== "") d.erreur = text.trim().split("\n")[0].slice(0, 200)
        }
        onExited: { tempo.stop(); d.envoi = ""; if (d.reponse.trim() === "" && d.erreur === "") d.erreur = Reglages.t("Pas de réponse de l'IA.", "No answer from the AI.") }
    }
}
