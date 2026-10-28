// Page « Réglages du code » de l'espace de code (Code.qml, bouton ⚙ du pied ou Ctrl + ,) : l'agent par défaut, le dossier des
// projets, le modèle d'un projet vide, la part de Neovim et lazygit. Chaque contrôle écrit par « nc-reglages set CLE VALEUR »
// (argv, une commande à la fois) : CODE_AGENT, CODE_DOSSIER, CODE_MODELE, CODE_NVIM_PART, CODE_LAZYGIT. Les valeurs affichées
// viennent de Reglages (relu dès que le fichier change). Clavier (géré par Code.qml) : Haut / Bas, Gauche / Droite, Entrée.
// Le sélecteur de dossier est celui de zenity (argv) ; la fenêtre du panneau se cache le temps qu'il est ouvert.
import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: page
    property var agents: []                         // nc-code --agents-json : [{prog, nom}]
    property int sel: 0
    property bool selecteur: false                  // le sélecteur de dossier est ouvert : Code.qml cache sa fenêtre
    signal rendreFocus()
    readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
    readonly property int nombre: 5

    readonly property string agentVal: Reglages.val("CODE_AGENT", "auto")
    readonly property string modeleVal: Reglages.val("CODE_MODELE", "vide")
    readonly property string partVal: Reglages.val("CODE_NVIM_PART", "62")
    readonly property string lazygitVal: Reglages.val("CODE_LAZYGIT", "oui")
    readonly property string dossierVal: Reglages.val("CODE_DOSSIER", "~/Projets")

    // Les choix de chaque ligne, dans l'ordre d'affichage : [{v, t}]
    readonly property var choixAgent: [{ v: "auto", t: Reglages.t("Automatique", "Automatic") }]
        .concat((agents || []).map(a => ({ v: a.prog, t: a.nom || a.prog })))
        .concat([{ v: "aucun", t: Reglages.t("Aucun", "None") }])
    readonly property var choixModele: [{ v: "vide", t: Reglages.t("Vide", "Empty") }, { v: "python", t: "Python" }, { v: "c", t: "C" },
                                        { v: "web", t: Reglages.t("Page web", "Web page") }]
    readonly property var choixPart: [{ v: "40", t: "40 %" }, { v: "50", t: "50 %" }, { v: "62", t: "62 %" }, { v: "70", t: "70 %" }, { v: "80", t: "80 %" }]
    readonly property var choixLazygit: [{ v: "oui", t: Reglages.t("Oui", "Yes") }, { v: "non", t: Reglages.t("Non", "No") }]

    function cleDe(i) { return ["CODE_AGENT", "CODE_DOSSIER", "CODE_MODELE", "CODE_NVIM_PART", "CODE_LAZYGIT"][i] || "" }
    function choixDe(i) { return i === 0 ? choixAgent : i === 2 ? choixModele : i === 3 ? choixPart : i === 4 ? choixLazygit : [] }
    function valeurDe(i) { return i === 0 ? agentVal : i === 2 ? modeleVal : i === 3 ? partVal : i === 4 ? lazygitVal : dossierVal }

    // ── Écrire : une commande nc-reglages à la fois, dans l'ordre ──
    property var file: []
    function regler(cle, valeur) {
        if (cle === "" || String(valeur) === "" || String(valeur).indexOf("\n") >= 0) return
        file = file.concat([[cle, String(valeur)]])
        suivant()
    }
    function suivant() {
        if (ecriture.running || file.length === 0) return
        var c = file[0]
        file = file.slice(1)
        ecriture.command = [bin + "nc-reglages", "set", c[0], c[1]]
        ecriture.running = true
    }
    readonly property bool occupe: ecriture.running || file.length > 0 || choix.running
    Process { id: ecriture; onExited: page.suivant() }

    // ── Clavier ──
    function bouger(d) { sel = Math.max(0, Math.min(nombre - 1, sel + d)) }
    function changer(d) {
        var l = choixDe(sel)
        if (l.length === 0) return
        var n = -1
        for (var k = 0; k < l.length; k++) if (l[k].v === valeurDe(sel)) n = k
        if (n < 0) n = d > 0 ? -1 : 0
        regler(cleDe(sel), l[(n + d + l.length) % l.length].v)
    }
    function activer() {
        if (sel === 1) choisirDossier()
        else if (sel === 4) regler("CODE_LAZYGIT", lazygitVal === "non" ? "oui" : "non")
        else changer(1)
    }

    // ── Le sélecteur de dossier (zenity, argv) ──
    property string dossierChoisi: ""
    function choisirDossier() {
        if (choix.running) return
        var d = dossierVal.indexOf("~") === 0 ? Quickshell.env("HOME") + dossierVal.slice(1) : dossierVal
        choix.command = ["sh", "-c", "command -v zenity >/dev/null 2>&1 || exit 127; exec zenity \"$@\"", "sh", "--file-selection", "--directory",
                         "--title=" + Reglages.t("Dossier des nouveaux projets", "Folder for new projects"), "--filename=" + d.replace(/\/+$/, "") + "/"]
        selecteur = true
        choix.running = true
    }
    Process {
        id: choix
        stdout: StdioCollector { onStreamFinished: page.dossierChoisi = text.trim().split("\n")[0] }
        onExited: code => {
            page.selecteur = false
            if (code === 127) Quickshell.execDetached(["notify-send", "-a", "nc-code", "--", Reglages.t("Espace de code", "Code space"),
                Reglages.t("Le sélecteur de dossier (zenity) n'est pas installé : tape le chemin dans le champ.",
                           "The folder picker (zenity) isn't installed: type the path in the field.")])
            else if (code === 0 && page.dossierChoisi.indexOf("/") === 0) page.regler("CODE_DOSSIER", page.dossierChoisi)
            page.dossierChoisi = ""
            page.rendreFocus()
        }
    }

    Flickable {
        id: defile
        anchors.fill: parent; anchors.margins: 14; anchors.topMargin: 10
        contentHeight: colonne.height; clip: true
        boundsBehavior: Flickable.StopAtBounds
        Column {
            id: colonne
            width: defile.width; spacing: 4
            Texte { width: parent.width; height: 30; text: Reglages.t("Réglages du code", "Code settings"); font.pixelSize: 17; font.weight: Font.Bold }
            Texte {
                width: parent.width; height: 22; secondaire: true; font.pixelSize: 12
                text: Reglages.t("Haut / Bas choisit, Gauche / Droite change, Échap revient à la liste.", "Up / Down picks, Left / Right changes, Esc goes back to the list.")
            }
            CodeReglageLigne {
                objectName: "nc-code-reglage-agent"; width: parent.width; choisie: page.sel === 0; onSurvol: page.sel = 0
                titre: Reglages.t("Agent par défaut", "Default agent")
                aide: Reglages.t("Celui qui s'ouvre à droite de Neovim.", "The one that opens to the right of Neovim.")
                Flow {
                    width: parent.width; spacing: 6
                    Repeater {
                        model: page.choixAgent
                        PastilleChoix {
                            required property var modelData
                            objectName: "nc-code-reglage-agent-" + (modelData.v)
                            texte: modelData.t; actif: page.agentVal === modelData.v
                            onClic: { page.sel = 0; page.regler("CODE_AGENT", modelData.v) }
                        }
                    }
                }
            }
            CodeReglageLigne {
                objectName: "nc-code-reglage-dossier"; width: parent.width; choisie: page.sel === 1; onSurvol: page.sel = 1
                titre: Reglages.t("Dossier des projets", "Projects folder")
                aide: Reglages.t("Nouveau projet et clonage y créent leur dossier.", "New projects and clones are created there.")
                Row {
                    width: parent.width; spacing: 8
                    Rectangle {
                        width: parent.width - boutonDossier.width - 8; height: 28; radius: 14
                        color: Qt.alpha(Couleurs.carte, 0.6); border.width: 1; border.color: champDossier.activeFocus ? Qt.alpha(Couleurs.accent, 0.7) : Qt.alpha(Couleurs.texte, 0.1)
                        TextInput {
                            id: champDossier
                            objectName: "nc-code-reglage-dossier-champ"
                            anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12
                            verticalAlignment: TextInput.AlignVCenter
                            color: Couleurs.texte; selectionColor: Couleurs.accent; selectedTextColor: Couleurs.surAccent
                            font.family: "Adwaita Sans"; font.pixelSize: 12; clip: true
                            text: page.dossierVal
                            onActiveFocusChanged: if (activeFocus) page.sel = 1
                            onAccepted: { var t = text.trim(); if (t !== "" && t !== page.dossierVal) page.regler("CODE_DOSSIER", t); page.rendreFocus() }
                            Keys.onEscapePressed: { text = page.dossierVal; page.rendreFocus() }
                        }
                    }
                    PastilleChoix {
                        id: boutonDossier
                        objectName: "nc-code-reglage-dossier-choisir"
                        texte: Reglages.t("Choisir…", "Choose…")
                        onClic: { page.sel = 1; page.choisirDossier() }
                    }
                }
            }
            CodeReglageLigne {
                objectName: "nc-code-reglage-modele"; width: parent.width; choisie: page.sel === 2; onSurvol: page.sel = 2
                titre: Reglages.t("Modèle d'un projet vide", "Empty project template")
                aide: Reglages.t("Les fichiers de départ, choisis d'avance dans « Nouveau projet ».", "The starting files, preselected in “New project”.")
                Flow {
                    width: parent.width; spacing: 6
                    Repeater {
                        model: page.choixModele
                        PastilleChoix {
                            required property var modelData
                            objectName: "nc-code-reglage-modele-" + modelData.v
                            texte: modelData.t; actif: page.modeleVal === modelData.v
                            onClic: { page.sel = 2; page.regler("CODE_MODELE", modelData.v) }
                        }
                    }
                }
            }
            CodeReglageLigne {
                objectName: "nc-code-reglage-part"; width: parent.width; choisie: page.sel === 3; onSurvol: page.sel = 3
                titre: Reglages.t("Place de Neovim", "Neovim's share")
                aide: Reglages.t("La part de la largeur ; l'agent prend le reste.", "The share of the width; the agent takes the rest.")
                Flow {
                    width: parent.width; spacing: 6
                    Repeater {
                        model: page.choixPart
                        PastilleChoix {
                            required property var modelData
                            objectName: "nc-code-reglage-part-" + modelData.v
                            texte: modelData.t; actif: page.partVal === modelData.v
                            onClic: { page.sel = 3; page.regler("CODE_NVIM_PART", modelData.v) }
                        }
                    }
                }
            }
            CodeReglageLigne {
                objectName: "nc-code-reglage-lazygit"; width: parent.width; choisie: page.sel === 4; onSurvol: page.sel = 4
                titre: Reglages.t("lazygit", "lazygit")
                aide: Reglages.t("Un onglet Git dans l'espace de code.", "A Git tab in the code space.")
                Flow {
                    width: parent.width; spacing: 6
                    Repeater {
                        model: page.choixLazygit
                        PastilleChoix {
                            required property var modelData
                            objectName: "nc-code-reglage-lazygit-" + modelData.v
                            texte: modelData.t; actif: page.lazygitVal === modelData.v
                            onClic: { page.sel = 4; page.regler("CODE_LAZYGIT", modelData.v) }
                        }
                    }
                }
            }
        }
    }
}
