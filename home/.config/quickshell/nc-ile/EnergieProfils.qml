// Carte « Profils d'énergie poussés » de la page Santé : les profils proposés par l'IA (ou par des règles, sans IA) pour CE PC,
// l'aperçu de ce qui changerait (avant → après, en français simple), Appliquer et Revenir. Tout passe par la commande
// nc-energie (liste blanche, validateur, retour arrière) : l'île ne règle rien elle-même et ne construit aucune commande
// avec un texte venu de l'IA (seulement l'identifiant du profil, lettres, chiffres et tirets, relu par nc-energie).
// Rien ne tourne en boucle : une lecture quand la page s'affiche, puis seulement sur un clic. Sans capacité détectée ou
// sans nc-energie, la carte n'existe pas. IA_MODE=non : le bouton de l'IA est caché (les profils par règles restent).
import QtQuick
import Quickshell.Io

Module {
    id: ep
    objectName: "blocEnergie"
    radius: 18
    visible: etat.disponible === true
    height: col.implicitHeight + 24

    property bool affichee: false                        // la page Santé est vraiment affichée
    property var etat: ({ profils: [], ia: false, disponible: false, actif: null, assistant_root: false })
    property var apercu: null
    property string choisi: ""                           // identifiant du profil dont l'aperçu est ouvert
    property string message: ""
    property bool occupe: false
    readonly property var profils: etat.profils || []
    readonly property bool identifiantSur: /^[a-z0-9-]{1,40}$/.test(choisi)

    onAfficheeChanged: if (affichee) lire()
    function lire() { if (!lecteur.running) lecteur.running = true }
    function ouvrir(id) {
        if (!/^[a-z0-9-]{1,40}$/.test(id)) return
        choisi = id; apercu = null; message = ""
        relireApercu()
    }
    function relireApercu() { if (identifiantSur && !lecteurApercu.running) lecteurApercu.running = true }
    function proposer(option) {
        message = ""; occupe = true
        proposeur.command = [Etat.bin + "nc-energie", "proposer", option, "--json"]
        proposeur.running = true
    }
    function appliquer() {
        if (!identifiantSur || occupe || !apercu || !apercu.applicable) return
        message = ""; occupe = true
        var cmd = [Etat.bin + "nc-energie", "appliquer", choisi, "--oui", "--json"]
        if (apercu.demande_hz) cmd.splice(4, 0, "--oui-hz")      // la phrase de confirmation est affichée juste au-dessus du bouton
        applicateur.command = cmd
        applicateur.running = true
    }
    function revenir() {
        if (occupe) return
        message = ""; occupe = true
        retour.running = true
    }
    function fin(texte) {
        var r = {}
        try { r = JSON.parse(texte) } catch (e) { r = {} }
        occupe = false
        message = r.message || r.erreur || Reglages.t("Pas de réponse de nc-energie.", "No answer from nc-energie.")
        lire()
        relireApercu()
    }

    Process {
        id: lecteur
        command: [Etat.bin + "nc-energie", "liste", "--json"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { var r = JSON.parse(text); if (r && Array.isArray(r.profils)) ep.etat = r } catch (e) { }
            }
        }
    }
    Process {
        id: lecteurApercu
        command: [Etat.bin + "nc-energie", "apercu", ep.choisi, "--json"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var r = JSON.parse(text)
                    if (r.ok === false) { ep.apercu = null; ep.message = r.erreur || "" } else ep.apercu = r
                } catch (e) { ep.apercu = null }
            }
        }
    }
    Process {
        id: proposeur
        stdout: StdioCollector {
            onStreamFinished: {
                var r = {}
                try { r = JSON.parse(text) } catch (e) { r = {} }
                ep.occupe = false
                ep.choisi = ""; ep.apercu = null
                if (r.ok === false) ep.message = r.erreur || ""
                else ep.message = (r.source === "ia" ? Reglages.t("Profils proposés par l'IA.", "Profiles proposed by the AI.")
                                                     : Reglages.t("Profils calculés d'après ton PC.", "Profiles computed from your PC.")) + (r.raison ? " " + r.raison : "")
                ep.lire()
            }
        }
    }
    Process {
        id: applicateur
        stdout: StdioCollector { onStreamFinished: ep.fin(text) }
    }
    Process {
        id: retour
        command: [Etat.bin + "nc-energie", "revenir", "--json"]
        stdout: StdioCollector { onStreamFinished: ep.fin(text) }
    }

    Column {
        id: col
        x: 14; y: 12; width: parent.width - 28; spacing: 8
        Item {
            width: parent.width; height: 20
            Texte { anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Profils d'énergie poussés", "Advanced power profiles"); font.weight: Font.DemiBold; font.pixelSize: 14 }
            Texte {
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.pixelSize: 11
                visible: ep.etat.actif !== null && ep.etat.actif !== undefined
                text: Reglages.t("un profil est actif", "a profile is active")
            }
        }
        Texte {
            visible: ep.profils.length === 0
            width: parent.width; wrapMode: Text.WordWrap; secondaire: true; font.pixelSize: 12
            text: Reglages.t("Aucun profil pour l'instant : propose-en d'après ton PC.", "No profile yet: ask for some based on your PC.")
        }
        Repeater {
            model: ep.profils
            Rectangle {
                id: carte
                required property var modelData
                objectName: "profilPousse"
                readonly property bool ouvert: ep.choisi === modelData.id
                readonly property bool actif: ep.etat.actif === modelData.id
                width: col.width; height: ligneProfil.implicitHeight + 16; radius: 14
                color: ouvert ? Couleurs.gris3 : (zoneProfil.containsMouse ? Couleurs.gris3 : Couleurs.gris2)
                opacity: modelData.valide ? 1 : 0.5
                Behavior on color { ColorAnimation { duration: 160 } }
                Column {
                    id: ligneProfil
                    x: 12; y: 8; width: parent.width - 24; spacing: 2
                    Row {
                        spacing: 6
                        Ico { nom: carte.actif ? "bolt" : (carte.modelData.film_batterie ? "movie" : "tune"); taille: 15; color: carte.actif ? Couleurs.vert : Couleurs.texteSec; anchors.verticalCenter: parent.verticalCenter }
                        Texte { text: carte.modelData.nom; font.pixelSize: 13; font.weight: Font.DemiBold; width: Math.min(implicitWidth, ligneProfil.width - 90); anchors.verticalCenter: parent.verticalCenter }
                        Texte { visible: carte.modelData.materiel === true; text: Reglages.t("matériel", "hardware"); secondaire: true; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                    }
                    Texte {
                        width: parent.width; wrapMode: Text.WordWrap; secondaire: true; font.pixelSize: 11; elide: Text.ElideNone
                        text: carte.modelData.valide ? carte.modelData.description : Reglages.t("Plus valable sur ce PC : ", "No longer valid on this PC: ") + (carte.modelData.raison || "")
                    }
                }
                MouseArea { id: zoneProfil; anchors.fill: parent; hoverEnabled: true; enabled: carte.modelData.valide === true; onClicked: ep.ouvrir(carte.modelData.id) }
            }
        }
        // Aperçu du profil choisi : avant → après, en français simple
        Column {
            id: blocApercu
            objectName: "apercuEnergie"
            visible: ep.apercu !== null
            width: parent.width; spacing: 4
            Repeater {
                model: ep.apercu ? ep.apercu.changements : []
                Item {
                    id: ligneChg
                    required property var modelData
                    width: blocApercu.width; height: Math.max(16, texteChg.implicitHeight)
                    Texte { id: texteChg; width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: 11; elide: Text.ElideNone
                            text: ligneChg.modelData.libelle + " : " + ligneChg.modelData.avant + " → " + ligneChg.modelData.apres }
                }
            }
            Texte {
                visible: ep.apercu !== null && ep.apercu.changements.length === 0
                width: parent.width; wrapMode: Text.WordWrap; secondaire: true; font.pixelSize: 11
                text: Reglages.t("Rien à changer : ton PC est déjà dans cet état.", "Nothing to change: your PC is already in this state.")
            }
            Texte {
                visible: ep.apercu !== null && ep.apercu.demande_hz === true
                width: parent.width; wrapMode: Text.WordWrap; color: Couleurs.orange; font.pixelSize: 11; elide: Text.ElideNone
                text: ep.apercu ? ep.apercu.texte_hz : ""
            }
            Texte {
                visible: ep.apercu !== null && ep.apercu.applicable === false
                width: parent.width; wrapMode: Text.WordWrap; color: Couleurs.orange; font.pixelSize: 11; elide: Text.ElideNone
                text: ep.apercu ? ep.apercu.raison : ""
            }
            Texte {
                visible: ep.apercu !== null && ep.apercu.avertissements.length > 0
                width: parent.width; wrapMode: Text.WordWrap; secondaire: true; font.pixelSize: 10; elide: Text.ElideNone
                text: ep.apercu ? ep.apercu.avertissements.join("\n") : ""
            }
            Row {
                spacing: 8
                BoutonEnergie {
                    objectName: "boutonAppliquerEnergie"
                    texte: ep.apercu && ep.apercu.demande_hz ? Reglages.t("Confirmer : écran à 60 Hz", "Confirm: screen at 60 Hz") : Reglages.t("Appliquer", "Apply")
                    icone: "check"; teinte: Couleurs.accent; surTeinte: Couleurs.surCouleur
                    actif: !ep.occupe && ep.apercu !== null && ep.apercu.applicable === true && ep.apercu.changements.length > 0
                    onClic: ep.appliquer()
                }
                BoutonEnergie { texte: Reglages.t("Fermer", "Close"); onClic: { ep.choisi = ""; ep.apercu = null } }
            }
        }
        Texte {
            visible: ep.message !== ""
            width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: 11; elide: Text.ElideNone
            text: ep.message
        }
        Flow {
            width: parent.width; spacing: 8
            BoutonEnergie {
                objectName: "boutonRevenirEnergie"
                texte: Reglages.t("Revenir", "Revert"); icone: "undo"
                actif: !ep.occupe && ep.etat.actif !== null && ep.etat.actif !== undefined
                onClic: ep.revenir()
            }
            BoutonEnergie {
                objectName: "boutonReglesEnergie"
                texte: Reglages.t("Profils d'après mon PC", "Profiles from my PC"); icone: "tune"
                actif: !ep.occupe
                onClic: ep.proposer("--regles")
            }
            BoutonEnergie {
                objectName: "boutonIaEnergie"
                visible: ep.etat.ia === true
                texte: Reglages.t("Proposer avec l'IA", "Ask the AI"); icone: "auto_awesome"
                actif: !ep.occupe
                onClic: ep.proposer("--ia")
            }
        }
        Texte {
            width: parent.width; wrapMode: Text.WordWrap; secondaire: true; font.pixelSize: 10; elide: Text.ElideNone
            text: ep.etat.assistant_root === true
                  ? Reglages.t("Rien n'est réappliqué tout seul au démarrage. L'écran garde sa fréquence maximale sauf profil « film » confirmé.",
                               "Nothing is reapplied on its own at startup. The screen keeps its top refresh rate unless a confirmed \"movie\" profile says otherwise.")
                  : Reglages.t("Les réglages du matériel demandent l'assistant (install.sh te le propose, avec ton accord).",
                               "Hardware settings need the helper (install.sh offers it, with your consent).")
        }
    }
}
