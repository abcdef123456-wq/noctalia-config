// Fenêtre « Cloud JARVIS » (IPC `cloud` de shell.qml, recherche de l'île, `nc-cloud fenetre`). Une VRAIE fenêtre
// (FloatingWindow), titre exact « Cloud JARVIS » dans les deux langues : les règles de Hyprland la reconnaissent à ce titre
// (regles.lua, automatismes.lua). On y parcourt le drive ; un clic choisit une entrée et montre ses actions SOUS son nom
// (la ligne grandit vers le bas : le point cliqué ne bouge pas), un double-clic l'ouvre (dossier : on y entre ; fichier :
// nc-cloud ouvrir). Créer un dossier ou un fichier vide, télécharger, renommer, déplacer (« Déplacer ici »), supprimer
// après une question sur la ligne (un dossier : d'abord l'aperçu de ce qui partirait). Chaque action seulement si le
// serveur annonce sa capacité. Tout vient de CloudEtat.qml (nc-cloud --json) ; rien ne tourne panneau fermé. Échap
// annule la question, le renommage ou le déplacement en cours, sinon ferme. Verre comme Garmin.
import QtQuick
import Quickshell

FloatingWindow {
    id: cloud
    signal fermer()
    title: Reglages.t("Cloud JARVIS", "Cloud JARVIS")   // le même nom dans les deux langues : la règle de Hyprland vise ce titre exact
    color: "transparent"
    implicitWidth: Math.min(680, Math.round(largeurEcran * 0.92))
    implicitHeight: Math.min(Math.round(hauteurEcran * 0.85), contenu.implicitHeight + 48)
    minimumSize: Qt.size(420, 260)
    onClosed: cloud.fermer()
    onVisibleChanged: if (!visible) cloud.fermer()

    readonly property real largeurEcran: cloud.screen ? cloud.screen.width : 1600
    readonly property real hauteurEcran: cloud.screen ? cloud.screen.height : 1000
    readonly property bool verre: Reglages.val("FENETRES_FLOU", "oui") !== "non" && !Reglages.sobre
    readonly property bool pret: CloudEtat.actif && CloudEtat.associe
    property string aSupprimer: ""                // id de l'entrée dont la suppression attend sa confirmation
    property string aRenommer: ""                 // id de l'entrée en cours de renommage
    function annulerEnCours() {
        if (aSupprimer !== "") { aSupprimer = ""; CloudEtat.apercu = null; return true }
        if (aRenommer !== "") { aRenommer = ""; return true }
        if (CloudEtat.deplacement) { CloudEtat.deplacement = null; return true }
        return false
    }

    Connections { target: CloudEtat; function onRedemander(id) { cloud.aSupprimer = id } }
    Component.onCompleted: CloudEtat.panneauOuvert = true
    Component.onDestruction: CloudEtat.panneauOuvert = false

    function taille(n) {
        if (typeof n !== "number") return ""
        var u = ["o", "Kio", "Mio", "Gio", "Tio"], i = 0
        while (n >= 1024 && i < u.length - 1) { n /= 1024; i++ }
        return (i === 0 ? n : n.toFixed(1)) + " " + u[i]
    }
    readonly property string quota: typeof CloudEtat.etat.used_bytes === "number" && typeof CloudEtat.etat.quota_bytes === "number"
        ? taille(CloudEtat.etat.used_bytes) + Reglages.t(" sur ", " of ") + taille(CloudEtat.etat.quota_bytes) : ""

    Item {
        anchors.fill: parent
        focus: true
        Keys.onEscapePressed: if (!cloud.annulerEnCours()) cloud.fermer()
        // Un seul fond, plein, sans arrondi ni contour : Hyprland dessine la bordure et découpe les coins
        Rectangle { anchors.fill: parent; color: Qt.alpha(Couleurs.fond, cloud.verre ? 0.62 : 0.92) }

        Flickable {
            id: defile
            anchors.fill: parent; anchors.margins: 1
            contentWidth: width; contentHeight: contenu.implicitHeight + 48
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            flickableDirection: Flickable.VerticalFlick
            Column {
                id: contenu
                objectName: "nc-cloud-contenu"
                x: 26; y: 24; width: defile.width - 52
                spacing: 14

                Item {
                    width: parent.width; height: 34
                    Ico { id: ico; anchors.verticalCenter: parent.verticalCenter; nom: "cloud"; taille: 26; color: Couleurs.accent }
                    Column {
                        anchors.verticalCenter: parent.verticalCenter; x: 36
                        Texte { text: "Cloud JARVIS"; font.pixelSize: 20; font.weight: Font.DemiBold }
                        Texte { objectName: "nc-cloud-quota"; visible: cloud.quota !== ""; text: cloud.quota; secondaire: true; font.pixelSize: 11 }
                    }
                    Row {
                        anchors.verticalCenter: parent.verticalCenter; anchors.right: parent.right; spacing: 8
                        CloudBouton { visible: cloud.pret; objectName: "nc-cloud-actualiser"; texte: Reglages.t("Actualiser", "Refresh")
                                      enabled: !CloudEtat.occupe; onClic: CloudEtat.actualiser() }
                        BoutonReglages { section: "Cloud JARVIS" }
                        CloudBouton { texte: Reglages.t("Fermer", "Close"); onClic: cloud.fermer() }
                    }
                }

                // Coupé ou non associé : on dit quoi faire, rien n'est lancé
                Texte {
                    objectName: "nc-cloud-coupe"
                    visible: !CloudEtat.actif
                    width: parent.width; wrapMode: Text.Wrap; secondaire: true
                    text: Reglages.t("Le Cloud JARVIS est coupé : active-le dans les réglages (⚙, section Cloud JARVIS).",
                                     "The JARVIS Cloud is off: turn it on in the settings (⚙, JARVIS Cloud section).")
                }
                Texte {
                    objectName: "nc-cloud-non-associe"
                    visible: CloudEtat.actif && !CloudEtat.associe
                    width: parent.width; wrapMode: Text.Wrap; secondaire: true
                    text: Reglages.t("Ce PC n'est pas associé : associe-le dans les réglages (⚙, « Associer ce PC »).",
                                     "This PC is not paired: pair it in the settings (⚙, “Pair this PC”).")
                }

                // Où on est : un bouton par dossier, du cloud au dossier courant
                Flow {
                    visible: cloud.pret
                    width: parent.width; spacing: 6
                    Repeater {
                        model: cloud.pret ? CloudEtat.chemin : []
                        CloudBouton {
                            required property var modelData
                            required property int index
                            objectName: "nc-cloud-chemin-" + index
                            texte: (index > 0 ? "› " : "") + modelData.nom
                            principal: index === CloudEtat.chemin.length - 1
                            onClic: CloudEtat.remonter(index)
                        }
                    }
                }

                // Créer : un dossier, ou un fichier vide (par l'API d'envoi : taille 0)
                Flow {
                    visible: cloud.pret && !CloudEtat.deplacement
                    width: parent.width; spacing: 8
                    Rectangle {
                        width: 220; height: 30; radius: 15; color: Couleurs.gris2
                        border.width: 1; border.color: nomNouveau.activeFocus ? Couleurs.accent : "transparent"
                        TextInput {
                            id: nomNouveau
                            objectName: "nc-cloud-nom-dossier"
                            anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12
                            verticalAlignment: TextInput.AlignVCenter; clip: true; selectByMouse: true; maximumLength: 120
                            color: Couleurs.texte; selectionColor: Couleurs.accent; font.pixelSize: 12
                            onAccepted: creer.clic()
                            Texte { anchors.verticalCenter: parent.verticalCenter; visible: nomNouveau.text === "" && !nomNouveau.activeFocus
                                    text: Reglages.t("Nom du nouveau dossier ou fichier", "New folder or file name"); secondaire: true; font.pixelSize: 12 }
                        }
                    }
                    CloudBouton {
                        id: creer
                        objectName: "nc-cloud-creer"
                        texte: Reglages.t("Créer le dossier", "Create folder")
                        enabled: nomNouveau.text.trim() !== "" && !CloudEtat.occupe
                        onClic: if (enabled) { CloudEtat.creerDossier(nomNouveau.text); nomNouveau.text = "" }
                    }
                    CloudBouton {
                        objectName: "nc-cloud-creer-fichier"
                        texte: Reglages.t("Créer un fichier vide", "Create empty file")
                        enabled: nomNouveau.text.trim() !== "" && !CloudEtat.occupe
                        onClic: if (enabled) { CloudEtat.creerFichier(nomNouveau.text); nomNouveau.text = "" }
                    }
                }

                // Déplacer : on parcourt les dossiers (chemin ci-dessus, double-clic sur un dossier), puis « Déplacer ici »
                Rectangle {
                    objectName: "nc-cloud-deplacement"
                    visible: cloud.pret && !!CloudEtat.deplacement
                    width: parent.width; height: bandeau.implicitHeight + 20; radius: 14
                    color: Couleurs.carte; border.width: 1; border.color: Couleurs.accent
                    Column {
                        id: bandeau
                        x: 14; y: 10; width: parent.width - 28; spacing: 8
                        Texte {
                            width: parent.width; wrapMode: Text.Wrap
                            text: CloudEtat.deplacement ? Reglages.t("Déplacer « " + CloudEtat.deplacement.name + " » : va dans le dossier voulu, puis « Déplacer ici ».",
                                                                     "Move “" + CloudEtat.deplacement.name + "”: go to the folder you want, then “Move here”.") : ""
                        }
                        Row {
                            spacing: 8
                            CloudBouton { objectName: "nc-cloud-deplacer-ici"; principal: true; texte: Reglages.t("Déplacer ici", "Move here")
                                          enabled: CloudEtat.deplacementPossible && !CloudEtat.occupe; onClic: CloudEtat.deplacerIci() }
                            CloudBouton { objectName: "nc-cloud-deplacer-annuler"; texte: Reglages.t("Annuler", "Cancel"); onClic: CloudEtat.deplacement = null }
                        }
                    }
                }

                Texte {
                    objectName: "nc-cloud-erreur"
                    visible: CloudEtat.erreur !== ""
                    width: parent.width; wrapMode: Text.Wrap; color: Couleurs.rouge; text: CloudEtat.erreur
                }
                Texte {
                    objectName: "nc-cloud-message"
                    visible: CloudEtat.message !== "" && CloudEtat.erreur === ""
                    width: parent.width; wrapMode: Text.Wrap; secondaire: true; text: CloudEtat.message
                }
                Texte {
                    visible: cloud.pret && CloudEtat.occupe
                    text: Reglages.t("Un instant…", "One moment…"); secondaire: true
                }
                Texte {
                    objectName: "nc-cloud-vide"
                    visible: cloud.pret && CloudEtat.lu && CloudEtat.entrees.length === 0
                    text: Reglages.t("Dossier vide.", "Empty folder."); secondaire: true
                }

                Column {
                    visible: cloud.pret
                    width: parent.width; spacing: 6
                    Repeater {
                        model: cloud.pret ? CloudEtat.entrees : []
                        Rectangle {
                            id: ligne
                            required property var modelData
                            readonly property bool fichier: modelData.kind === "file"
                            readonly property bool choisie: CloudEtat.selection === modelData.id && !CloudEtat.deplacement
                            readonly property bool confirmer: cloud.aSupprimer === modelData.id
                            readonly property bool renommage: cloud.aRenommer === modelData.id
                            readonly property bool apercuPret: !fichier && !!CloudEtat.apercu && CloudEtat.apercu.id === modelData.id
                            objectName: "nc-cloud-entree-" + modelData.id
                            width: parent.width; height: Math.max(48, colonne.implicitHeight + 16); radius: 14
                            color: choisie || zoneLigne.containsMouse ? Couleurs.carteSurvol : Couleurs.carte
                            border.width: choisie ? 1 : 0; border.color: Couleurs.accent
                            // Un clic choisit, un double-clic ouvre ; les actions s'ajoutent SOUS le nom, la ligne ne bouge pas
                            MouseArea { id: zoneLigne; anchors.fill: parent; hoverEnabled: true; z: -1; cursorShape: Qt.PointingHandCursor
                                        onClicked: CloudEtat.choisir(ligne.modelData)
                                        onDoubleClicked: CloudEtat.ouvrirEntree(ligne.modelData) }
                            Ico { id: icoL; x: 14; y: 14; taille: 20
                                  nom: ligne.fichier ? "description" : "folder"; color: ligne.fichier ? Couleurs.texteSec : Couleurs.accent }
                            Column {
                                id: colonne
                                x: 44; y: 8; width: parent.width - x - 14; spacing: 4
                                Texte { objectName: "nc-cloud-nom-" + ligne.modelData.id; visible: !ligne.renommage; width: parent.width
                                        text: ligne.modelData.name; elide: Text.ElideMiddle; font.weight: Font.DemiBold }
                                Rectangle {
                                    visible: ligne.renommage
                                    width: Math.min(parent.width, 320); height: 28; radius: 14; color: Couleurs.gris2
                                    border.width: 1; border.color: Couleurs.accent
                                    TextInput {
                                        id: nouveauNom
                                        objectName: "nc-cloud-nouveau-nom-" + ligne.modelData.id
                                        anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12
                                        verticalAlignment: TextInput.AlignVCenter; clip: true; selectByMouse: true; maximumLength: 240
                                        color: Couleurs.texte; selectionColor: Couleurs.accent; font.pixelSize: 12
                                        onAccepted: valider.clic()
                                        Keys.onEscapePressed: cloud.aRenommer = ""
                                    }
                                }
                                Texte { visible: ligne.fichier; text: cloud.taille(ligne.modelData.size); secondaire: true; font.pixelSize: 11 }
                                Texte {
                                    objectName: "nc-cloud-question-" + ligne.modelData.id
                                    visible: ligne.confirmer; width: parent.width; wrapMode: Text.Wrap
                                    color: Couleurs.rouge; font.pixelSize: 12; font.weight: Font.DemiBold
                                    text: ligne.fichier
                                        ? Reglages.t("« " + ligne.modelData.name + " » : suppression définitive, toutes ses versions.",
                                                     "“" + ligne.modelData.name + "”: permanent deletion, all its versions.")
                                        : !ligne.apercuPret ? Reglages.t("Calcul de ce que la suppression retirerait…", "Working out what the deletion would remove…")
                                        : Reglages.t("« " + ligne.modelData.name + " » : " + CloudEtat.apercu.files + " fichier(s), " + CloudEtat.apercu.directories
                                                     + " dossier(s), " + cloud.taille(CloudEtat.apercu.size) + " : suppression définitive, toutes les versions.",
                                                     "“" + ligne.modelData.name + "”: " + CloudEtat.apercu.files + " file(s), " + CloudEtat.apercu.directories
                                                     + " folder(s), " + cloud.taille(CloudEtat.apercu.size) + ": permanent deletion, all versions.")
                                }
                                Flow {
                                    id: actions
                                    objectName: "nc-cloud-actions-" + ligne.modelData.id
                                    visible: ligne.choisie || ligne.confirmer || ligne.renommage || CloudEtat.aRemplacer === ligne.modelData.id
                                    width: parent.width; spacing: 6
                                    readonly property bool libre: !ligne.confirmer && !ligne.renommage
                                    CloudBouton { visible: actions.libre; objectName: "nc-cloud-ouvrir-" + ligne.modelData.id
                                                  texte: Reglages.t("Ouvrir", "Open"); enabled: !CloudEtat.occupe
                                                  onClic: CloudEtat.ouvrirEntree(ligne.modelData) }
                                    CloudBouton { visible: actions.libre && ligne.fichier && CloudEtat.aRemplacer !== ligne.modelData.id
                                                  objectName: "nc-cloud-telecharger-" + ligne.modelData.id
                                                  texte: Reglages.t("Télécharger", "Download"); enabled: !CloudEtat.occupe
                                                  onClic: CloudEtat.telecharger(ligne.modelData, false) }
                                    CloudBouton { visible: ligne.fichier && CloudEtat.aRemplacer === ligne.modelData.id
                                                  objectName: "nc-cloud-remplacer-" + ligne.modelData.id
                                                  texte: Reglages.t("Remplacer", "Replace"); enabled: !CloudEtat.occupe
                                                  onClic: CloudEtat.telecharger(ligne.modelData, true) }
                                    CloudBouton { visible: actions.libre && CloudEtat.peutDeplacer
                                                  objectName: "nc-cloud-renommer-" + ligne.modelData.id
                                                  texte: Reglages.t("Renommer", "Rename"); enabled: !CloudEtat.occupe
                                                  onClic: { cloud.aRenommer = ligne.modelData.id; nouveauNom.text = ligne.modelData.name; nouveauNom.forceActiveFocus(); nouveauNom.selectAll() } }
                                    CloudBouton { visible: actions.libre && CloudEtat.peutDeplacer
                                                  objectName: "nc-cloud-deplacer-" + ligne.modelData.id
                                                  texte: Reglages.t("Déplacer…", "Move…"); enabled: !CloudEtat.occupe
                                                  onClic: CloudEtat.commencerDeplacement(ligne.modelData) }
                                    // Supprimer : d'abord la question sur la ligne ; un dossier, d'abord son aperçu
                                    CloudBouton { visible: actions.libre && CloudEtat.peutSupprimer(ligne.modelData)
                                                  objectName: "nc-cloud-supprimer-" + ligne.modelData.id
                                                  texte: Reglages.t("Supprimer…", "Delete…"); enabled: !CloudEtat.occupe
                                                  onClic: { cloud.aSupprimer = ligne.modelData.id; if (!ligne.fichier) CloudEtat.demanderApercu(ligne.modelData) } }
                                    CloudBouton { visible: ligne.confirmer; danger: true
                                                  objectName: "nc-cloud-confirmer-" + ligne.modelData.id
                                                  texte: Reglages.t("Supprimer définitivement", "Delete permanently")
                                                  enabled: !CloudEtat.occupe && (ligne.fichier || ligne.apercuPret)
                                                  onClic: { cloud.aSupprimer = ""; CloudEtat.supprimer(ligne.modelData) } }
                                    CloudBouton { visible: ligne.confirmer; objectName: "nc-cloud-annuler-" + ligne.modelData.id
                                                  texte: Reglages.t("Annuler", "Cancel"); onClic: { cloud.aSupprimer = ""; CloudEtat.apercu = null } }
                                    CloudBouton { id: valider; visible: ligne.renommage; principal: true
                                                  objectName: "nc-cloud-valider-nom-" + ligne.modelData.id
                                                  texte: Reglages.t("Renommer", "Rename"); enabled: !CloudEtat.occupe && nouveauNom.text.trim() !== ""
                                                  onClic: if (enabled) { cloud.aRenommer = ""; CloudEtat.renommer(ligne.modelData, nouveauNom.text) } }
                                    CloudBouton { visible: ligne.renommage; texte: Reglages.t("Annuler", "Cancel"); onClic: cloud.aRenommer = "" }
                                }
                            }
                            Ico { visible: !ligne.fichier; anchors.right: parent.right; anchors.rightMargin: 12; y: 14
                                  nom: "chevron_right"; taille: 20; color: Couleurs.texteSec }
                        }
                    }
                }
                CloudBouton {
                    objectName: "nc-cloud-suite"
                    visible: cloud.pret && CloudEtat.suite !== ""
                    texte: Reglages.t("Afficher la suite", "Show more"); enabled: !CloudEtat.occupe
                    onClic: CloudEtat.lister(true)
                }
            }
        }
    }
}
