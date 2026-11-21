// Fenêtre « Cloud JARVIS » (IPC `cloud` de shell.qml, recherche de l'île, `nc-cloud fenetre`). Une VRAIE fenêtre
// (FloatingWindow), titre exact « Cloud JARVIS » dans les deux langues : les règles de Hyprland la reconnaissent à ce titre
// (regles.lua, automatismes.lua). On y parcourt le drive ; un clic choisit une entrée et montre ses actions SOUS son nom
// (la ligne grandit vers le bas : le point cliqué ne bouge pas), un double-clic l'ouvre (dossier : on y entre ; fichier :
// nc-cloud ouvrir). Créer un dossier ou un fichier vide, télécharger, renommer, déplacer (« Déplacer ici »), supprimer
// après une question sur la ligne (un dossier : d'abord l'aperçu de ce qui partirait). Chaque action seulement si le
// serveur annonce sa capacité. Envoyer : fichiers déposés sur l'île ou « Importer des fichiers… » (le sélecteur du
// portail), puis « Envoyer ici » ; la liste des envois (progression, conflit, reprise) survit au panneau fermé.
// Tout vient de CloudEtat.qml (nc-cloud --json) ; rien ne tourne panneau fermé, sauf un envoi lancé. Échap
// annule la question, le renommage ou le déplacement en cours, sinon ferme. Une entrée glissée (aperçu sous le pointeur)
// se dépose sur un dossier de la liste, ou sur ↑ pour la remonter d'un cran sans quitter le dossier. Verre comme Garmin.
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
    function finirGlisser() {
        if (fantome.Drag.active) fantome.Drag.cancel()
        fantome.Drag.active = false
        fantome.entree = null
    }
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

        // L'aperçu sous le pointeur pendant un glisser (Drag interne au panneau : rien ne sort de la fenêtre)
        // La page relue pendant un glisser (Actualiser, autre dossier) : le glisser est annulé
        Connections { target: CloudEtat; function onEntreesChanged() { cloud.finirGlisser() } }
        Rectangle {
            id: fantome
            objectName: "nc-cloud-fantome"
            property var entree: null
            z: 10
            visible: Drag.active
            width: Math.min(260, nomFantome.implicitWidth + 50); height: 34; radius: 17
            color: Couleurs.carteSurvol; border.width: 1; border.color: Couleurs.accent; opacity: 0.94
            Drag.keys: ["nc-cloud-entree"]
            Drag.hotSpot.x: 16; Drag.hotSpot.y: 17
            Ico { x: 12; anchors.verticalCenter: parent.verticalCenter; taille: 16
                  nom: fantome.entree && fantome.entree.kind === "file" ? "description" : "folder"; color: Couleurs.accent }
            Texte { id: nomFantome; x: 36; anchors.verticalCenter: parent.verticalCenter; width: Math.min(implicitWidth, 210)
                    elide: Text.ElideMiddle; text: fantome.entree ? fantome.entree.name : "" }
        }

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

                // Trop étroit pour le titre et les boutons sur une ligne (420 px) : les boutons passent dessous
                Item {
                    objectName: "nc-cloud-entete"
                    readonly property bool serre: titreEntete.x + titreEntete.implicitWidth + 16 + boutonsEntete.implicitWidth > width
                    width: parent.width; height: serre ? 34 + 8 + boutonsEntete.implicitHeight : 34
                    Ico { id: ico; y: (34 - height) / 2; nom: "cloud"; taille: 26; color: Couleurs.accent }
                    Column {
                        id: titreEntete
                        objectName: "nc-cloud-titre"
                        y: (34 - height) / 2; x: 36
                        Texte { text: "Cloud JARVIS"; font.pixelSize: 20; font.weight: Font.DemiBold }
                        Texte { objectName: "nc-cloud-quota"; visible: cloud.quota !== ""; text: cloud.quota; secondaire: true; font.pixelSize: 11 }
                    }
                    Row {
                        id: boutonsEntete
                        objectName: "nc-cloud-boutons-entete"
                        y: parent.serre ? 42 : (34 - height) / 2; anchors.right: parent.right; spacing: 8
                        CloudBouton { visible: cloud.pret && CloudEtat.fichiersPossible; objectName: "nc-cloud-fichiers"
                                      texte: Reglages.t("Ouvrir dans Fichiers", "Open in Files"); enabled: !CloudEtat.occupe
                                      onClic: CloudEtat.ouvrirFichiers() }
                        CloudBouton { visible: cloud.pret; objectName: "nc-cloud-actualiser"; texte: Reglages.t("Actualiser", "Refresh")
                                      enabled: !CloudEtat.occupe; onClic: CloudEtat.actualiser() }
                        BoutonReglages { section: "Cloud JARVIS" }
                        CloudBouton { texte: Reglages.t("Fermer", "Close"); onClic: cloud.fermer() }
                    }
                }

                // Récents : les 5 derniers fichiers envoyés ou ouverts par CE PC (liste locale) ; un clic l'ouvre
                Column {
                    objectName: "nc-cloud-recents"
                    visible: cloud.pret && CloudEtat.recents.length > 0
                    width: parent.width; spacing: 6
                    Item {
                        width: parent.width; height: 26
                        Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Récents", "Recent"); secondaire: true; font.pixelSize: 12 }
                        CloudBouton { objectName: "nc-cloud-effacer-recents"; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                      texte: Reglages.t("Effacer les récents", "Clear recent"); enabled: !CloudEtat.occupe
                                      onClic: CloudEtat.effacerRecents() }
                    }
                    Flow {
                        width: parent.width; spacing: 6
                        Repeater {
                            model: CloudEtat.recents
                            CloudBouton {
                                required property var modelData
                                required property int index
                                objectName: "nc-cloud-recent-" + index
                                texte: modelData.nom.length > 32 ? modelData.nom.slice(0, 31) + "…" : modelData.nom
                                enabled: !CloudEtat.occupe
                                onClic: CloudEtat.ouvrirRecent(index)
                            }
                        }
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

                // Où on est : un bouton par dossier, du cloud au dossier courant ; ↑ remonte, et reçoit une entrée glissée
                Flow {
                    visible: cloud.pret
                    width: parent.width; spacing: 6
                    CloudBouton {
                        id: parentBouton
                        objectName: "nc-cloud-parent"
                        visible: CloudEtat.chemin.length > 1
                        texte: "↑"
                        border.width: cibleParent.containsDrag ? 2 : 0; border.color: Couleurs.accent
                        onClic: CloudEtat.remonter(CloudEtat.chemin.length - 2)
                        Accessible.name: Reglages.t("Dossier parent", "Parent folder")
                        DropArea {
                            id: cibleParent
                            objectName: "nc-cloud-cible-parent"
                            anchors.fill: parent
                            keys: ["nc-cloud-entree"]
                            readonly property string vers: CloudEtat.chemin.length > 1 ? CloudEtat.chemin[CloudEtat.chemin.length - 2].id : ""
                            onEntered: drag => { if (!CloudEtat.deposable(fantome.entree, vers)) drag.accepted = false }
                            onDropped: drop => { if (CloudEtat.deposable(fantome.entree, vers)) { drop.accept(Qt.MoveAction); CloudEtat.deplacerVers(fantome.entree, vers) } }
                        }
                    }
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

                // Envoyer : le sélecteur de fichiers du bureau (portail), ou des fichiers déposés sur l'île fermée
                Flow {
                    visible: cloud.pret && !CloudEtat.deplacement
                    width: parent.width; spacing: 8
                    CloudBouton {
                        objectName: "nc-cloud-importer"
                        texte: CloudEtat.choixOuvert ? Reglages.t("Sélecteur ouvert…", "Picker open…") : Reglages.t("Importer des fichiers…", "Import files…")
                        enabled: !CloudEtat.choixOuvert
                        onClic: if (enabled) CloudEtat.choisirFichiers()
                    }
                    Texte {
                        objectName: "nc-cloud-choix-erreur"
                        visible: CloudEtat.choixErreur !== ""
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.min(implicitWidth, contenu.width); wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 12
                        text: CloudEtat.choixErreur
                    }
                }
                Rectangle {
                    objectName: "nc-cloud-recus"
                    visible: cloud.pret && CloudEtat.recus.length > 0
                    width: parent.width; height: recus.implicitHeight + 20; radius: 14
                    color: Couleurs.carte; border.width: 1; border.color: Couleurs.accent
                    Column {
                        id: recus
                        x: 14; y: 10; width: parent.width - 28; spacing: 8
                        Texte {
                            objectName: "nc-cloud-recus-liste"
                            width: parent.width; wrapMode: Text.Wrap
                            text: Reglages.t(CloudEtat.recus.length + " fichier(s) reçu(s) :", CloudEtat.recus.length + " file(s) received:")
                        }
                        // Chaque fichier : son chemin complet (texte brut, coupé au milieu) et sa taille ; caché en orange, protégé en rouge
                        Repeater {
                            model: CloudEtat.recus
                            Item {
                                required property string modelData
                                required property int index
                                readonly property var ex: CloudEtat.examen[modelData]
                                width: recus.width; height: Math.max(18, cheminRecu.implicitHeight)
                                // Le chemin en entier (texte brut, à la ligne n'importe où) : deux chemins qui ne diffèrent
                                // qu'au milieu restent distincts
                                Texte {
                                    id: cheminRecu
                                    objectName: "nc-cloud-recu-" + index
                                    width: parent.width - tailleRecu.implicitWidth - 10; wrapMode: Text.WrapAnywhere; font.pixelSize: 12
                                    text: CloudEtat.court(parent.modelData)
                                    color: parent.ex && parent.ex.refus ? Couleurs.rouge : parent.ex && parent.ex.cache ? Couleurs.orange : Couleurs.texte
                                }
                                Texte {
                                    id: tailleRecu
                                    objectName: "nc-cloud-recu-info-" + index
                                    anchors.right: parent.right; secondaire: true; font.pixelSize: 12
                                    text: !parent.ex ? "…" : parent.ex.refus ? Reglages.t("ne partira pas", "won't be sent")
                                          : (parent.ex.cache ? Reglages.t("fichier caché · ", "hidden file · ") : "") + cloud.taille(parent.ex.taille)
                                }
                            }
                        }
                        Texte {
                            visible: CloudEtat.recus.some(f => CloudEtat.examen[f] && CloudEtat.examen[f].refus)
                            width: parent.width; wrapMode: Text.Wrap; color: Couleurs.rouge; font.pixelSize: 12
                            text: CloudEtat.recus.map(f => CloudEtat.examen[f] && CloudEtat.examen[f].refus).filter(x => !!x).join(" ")
                        }
                        Texte {
                            width: parent.width; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 12
                            text: Reglages.t("Vers : ", "To: ") + CloudEtat.chemin[CloudEtat.chemin.length - 1].nom
                                  + (CloudEtat.recusRefus !== "" ? " · " + CloudEtat.recusRefus : "")
                        }
                        Row {
                            spacing: 8
                            CloudBouton { objectName: "nc-cloud-envoyer-ici"; principal: true
                                          texte: CloudEtat.recusCaches ? Reglages.t("Envoyer quand même", "Upload anyway") : Reglages.t("Envoyer ici", "Upload here")
                                          enabled: CloudEtat.examenPret && CloudEtat.aEnvoyer.length > 0
                                          onClic: if (enabled) CloudEtat.envoyerIci() }
                            CloudBouton { objectName: "nc-cloud-recus-vider"; texte: Reglages.t("Retirer", "Remove"); onClic: CloudEtat.viderRecus() }
                        }
                    }
                }
                // Une note : un texte glissé sur l'île, en aperçu (texte brut), puis « Enregistrer la note » dans « Notes »
                Rectangle {
                    objectName: "nc-cloud-note"
                    visible: cloud.pret && (CloudEtat.note !== "" || CloudEtat.noteRefus !== "" || CloudEtat.noteMessage !== "")
                    width: parent.width; height: colNote.implicitHeight + 20; radius: 14
                    color: Couleurs.carte; border.width: CloudEtat.note !== "" ? 1 : 0; border.color: Couleurs.accent
                    Column {
                        id: colNote
                        x: 14; y: 10; width: parent.width - 28; spacing: 8
                        Texte {
                            visible: CloudEtat.note !== ""
                            text: Reglages.t("Note pour le dossier « Notes » :", "Note for the “Notes” folder:"); font.weight: Font.DemiBold
                        }
                        Texte {
                            objectName: "nc-cloud-note-apercu"
                            visible: CloudEtat.note !== ""
                            width: parent.width; wrapMode: Text.Wrap; maximumLineCount: 5; elide: Text.ElideRight; secondaire: true
                            text: CloudEtat.note.slice(0, 600)
                        }
                        Texte {
                            objectName: "nc-cloud-note-message"
                            visible: CloudEtat.noteRefus !== "" || CloudEtat.noteMessage !== ""
                            width: parent.width; wrapMode: Text.Wrap; font.pixelSize: 12
                            color: CloudEtat.noteRefus !== "" ? Couleurs.rouge : Couleurs.texteSec
                            text: CloudEtat.noteRefus || CloudEtat.noteMessage
                        }
                        Row {
                            spacing: 8
                            CloudBouton { objectName: "nc-cloud-note-enregistrer"; visible: CloudEtat.note !== ""; principal: true
                                          texte: CloudEtat.noteEnCours ? Reglages.t("Enregistrement…", "Saving…") : Reglages.t("Enregistrer la note", "Save note")
                                          enabled: !CloudEtat.noteEnCours; onClic: if (enabled) CloudEtat.enregistrerNote() }
                            CloudBouton { texte: CloudEtat.note !== "" ? Reglages.t("Retirer", "Remove") : Reglages.t("Fermer", "Close")
                                          enabled: !CloudEtat.noteEnCours; onClic: CloudEtat.oublierNote() }
                        }
                    }
                }
                Column {
                    objectName: "nc-cloud-envois"
                    visible: cloud.pret && CloudEtat.envois.length > 0
                    width: parent.width; spacing: 6
                    Item {
                        width: parent.width; height: 30
                        Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Envois", "Uploads"); font.weight: Font.DemiBold }
                        Row {
                            anchors.right: parent.right; spacing: 8
                            CloudBouton { objectName: "nc-cloud-envois-annuler"; visible: CloudEtat.envoie; danger: true
                                          texte: Reglages.t("Annuler l'envoi", "Cancel upload"); onClic: CloudEtat.annulerEnvois() }
                            CloudBouton { objectName: "nc-cloud-effacer-termines"; texte: Reglages.t("Effacer les terminés", "Clear finished")
                                          enabled: CloudEtat.envois.some(e => CloudEtat.termines.indexOf(e.etat) >= 0)
                                          onClic: CloudEtat.effacerTermines() }
                        }
                    }
                    Repeater {
                        model: cloud.pret ? CloudEtat.envois : []
                        Rectangle {
                            id: envoi
                            required property var modelData
                            required property int index
                            objectName: "nc-cloud-envoi-" + index
                            width: parent.width; height: colEnvoi.implicitHeight + 16; radius: 12; color: Couleurs.carte
                            readonly property real part: modelData.taille > 0 ? Math.min(1, modelData.envoye / modelData.taille) : 0
                            Column {
                                id: colEnvoi
                                x: 12; y: 8; width: parent.width - 24; spacing: 6
                                Item {
                                    width: parent.width; height: 20
                                    Texte { width: parent.width - etatEnvoi.implicitWidth - 12; elide: Text.ElideMiddle; text: envoi.modelData.nom }
                                    Texte {
                                        id: etatEnvoi
                                        objectName: "nc-cloud-envoi-etat-" + envoi.index
                                        anchors.right: parent.right; secondaire: true; font.pixelSize: 12
                                        text: ({ attente: Reglages.t("En attente", "Waiting"),
                                                 en_cours: Reglages.t("Envoi… ", "Uploading… ") + Math.round(envoi.part * 100) + " %",
                                                 publie: Reglages.t("Envoyé", "Uploaded"), conflit: Reglages.t("Ce nom existe déjà", "This name already exists"),
                                                 interrompu: Reglages.t("Interrompu", "Interrupted"), annule: Reglages.t("Annulé", "Cancelled"),
                                                 echec: Reglages.t("Échec", "Failed"), refuse: Reglages.t("Refusé", "Refused"),
                                                 inconnu: Reglages.t("À vérifier", "To check") })[envoi.modelData.etat] || ""
                                    }
                                }
                                Rectangle {
                                    visible: envoi.modelData.etat === "en_cours"
                                    width: parent.width; height: 4; radius: 2; color: Couleurs.gris2
                                    Rectangle { width: parent.width * envoi.part; height: parent.height; radius: 2; color: Couleurs.accent }
                                }
                                Texte {
                                    visible: ["echec", "refuse", "inconnu"].indexOf(envoi.modelData.etat) >= 0 && envoi.modelData.message !== ""
                                    width: parent.width; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 12; text: envoi.modelData.message
                                }
                                Flow {
                                    visible: envoi.modelData.etat === "conflit" || envoi.modelData.etat === "interrompu"
                                    width: parent.width; spacing: 8
                                    CloudBouton { visible: envoi.modelData.etat === "conflit"; objectName: "nc-cloud-garder-" + envoi.index
                                                  texte: Reglages.t("Conserver les deux", "Keep both"); onClic: CloudEtat.resoudre(envoi.index, "garder") }
                                    CloudBouton { visible: envoi.modelData.etat === "conflit" && !!(envoi.modelData.actuel && envoi.modelData.actuel.revision)
                                                  && envoi.modelData.actuel.kind !== "directory"
                                                  objectName: "nc-cloud-remplacer-envoi-" + envoi.index
                                                  texte: Reglages.t("Remplacer", "Replace"); onClic: CloudEtat.resoudre(envoi.index, "remplacer") }
                                    CloudBouton { visible: envoi.modelData.etat === "conflit"; objectName: "nc-cloud-annuler-envoi-" + envoi.index
                                                  texte: Reglages.t("Annuler", "Cancel"); onClic: CloudEtat.resoudre(envoi.index, "annuler") }
                                    CloudBouton { visible: envoi.modelData.etat === "interrompu"; principal: true; objectName: "nc-cloud-reprendre-" + envoi.index
                                                  texte: Reglages.t("Reprendre / vérifier", "Resume / check"); onClic: CloudEtat.reprendre(envoi.index) }
                                }
                            }
                        }
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
                            border.width: cibleLigne.containsDrag ? 2 : (choisie ? 1 : 0); border.color: Couleurs.accent
                            // Un clic choisit, un double-clic ouvre ; les actions s'ajoutent SOUS le nom, la ligne ne bouge pas.
                            // Glisser (au-delà du seuil de Qt) : l'aperçu suit le pointeur ; lâché sur un dossier ou sur ↑, on déplace
                            MouseArea { id: zoneLigne; objectName: "nc-cloud-zone-" + ligne.modelData.id
                                        anchors.fill: parent; hoverEnabled: true; z: -1; cursorShape: Qt.PointingHandCursor
                                        readonly property bool glissable: CloudEtat.peutDeplacer && !!ligne.modelData.revision
                                                                          && !ligne.renommage && !CloudEtat.deplacement
                                        drag.target: glissable ? fantome : null
                                        preventStealing: glissable          // le défilement par la molette reste
                                        // La MouseArea retient la place de sa cible avant onPressed : l'aperçu est recalé sous le pointeur
                                        // à chaque mouvement (après le sien)
                                        function placer(m) { var p = zoneLigne.mapToItem(fantome.parent, m.x, m.y); fantome.x = p.x - 16; fantome.y = p.y - 17 }
                                        onPressed: m => placer(m)
                                        onPositionChanged: m => { if (drag.active) placer(m) }
                                        // Qt émet released AVANT de couper le glisser : seul un vrai relâchement dépose. Une saisie
                                        // perdue (canceled) coupe le glisser sans relâchement : il est annulé, rien ne bouge
                                        onReleased: if (drag.active && fantome.Drag.active) { fantome.Drag.drop(); cloud.finirGlisser() }
                                        drag.onActiveChanged: {
                                            if (drag.active) { fantome.entree = ligne.modelData; fantome.Drag.active = true; return }
                                            cloud.finirGlisser()
                                        }
                                        onClicked: CloudEtat.choisir(ligne.modelData)
                                        onDoubleClicked: CloudEtat.ouvrirEntree(ligne.modelData) }
                            DropArea {
                                id: cibleLigne
                                objectName: "nc-cloud-cible-" + ligne.modelData.id
                                anchors.fill: parent
                                keys: ["nc-cloud-entree"]
                                enabled: !ligne.fichier
                                onEntered: drag => { if (!CloudEtat.deposable(fantome.entree, ligne.modelData.id)) drag.accepted = false }
                                onDropped: drop => { if (CloudEtat.deposable(fantome.entree, ligne.modelData.id)) {
                                    drop.accept(Qt.MoveAction); CloudEtat.deplacerVers(fantome.entree, ligne.modelData.id) } }
                            }
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
