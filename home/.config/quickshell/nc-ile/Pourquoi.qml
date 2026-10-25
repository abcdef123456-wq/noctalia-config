// « Pourquoi ça se vide ? » de la page Charge (Charge.qml) : un bouton, seulement quand le PC est sur batterie en
// décharge (propriété `actif`, donnée par la page ; sans batterie ou sur secteur, rien n'existe, pas même la place).
// Au clic : nc-conso pourquoi --json (les faits, tout de suite : 2 ou 3 phrases fixes et au plus 3 actions), puis
// nc-conso pourquoi --ia --faits - (les faits affichés, donnés sur l'entrée standard et non dans l'argv, racontés par nc-ia, si l'IA est permise ; rien n'est remesuré et
// l'île ne prend que `phrases` et l'ordre des ids : les actions affichées sont toujours celles qui seront lancées ;
// échec ou IA coupée : on garde les phrases fixes, sans message). Le texte de l'IA est affiché en texte brut (PlainText), jamais en rich text.
// Chaque action est un bouton qui dit ce qui va changer ; un clic ouvre une confirmation, et rien n'est lancé avant
// « Confirmer ». La commande lancée est celle de la liste de nc-conso (argv fixe), jamais un texte reconstruit ici.
// Après une action, les faits sont relus ; la mesure de la page (nc-conso suivre, toutes les 2 s) se rafraîchit seule.
// Fichier à part (pas un composant interne de Charge.qml) : le rechargement à chaud de Quickshell ne connaît pas les
// nouveaux composants internes d'un fichier déjà chargé.
import QtQuick
import Quickshell.Io

Module {
    id: p
    objectName: "pourquoi"
    property bool actif: false                       // sur batterie en décharge, page affichée
    property bool ouvert: false
    property var res: null                           // la sortie de nc-conso pourquoi
    property string phase: "faits"                   // faits (--json) puis ia (--ia)
    property bool aRelire: false
    property bool sansIa: false                      // relecture après une action : pas de nouvel appel à l'IA sans clic
    property int gen: 0                              // change à chaque ouverture, fermeture ou relecture : un vieux résultat est ignoré
    property string derniereAction: ""
    property bool faitsRecus: false                  // la lecture --json a donné un résultat valable
    property bool sorti: true                        // le processus de lecture est terminé
    property string choix: ""                        // l'id de l'action qui attend sa confirmation
    property string etatAction: ""                   // "", encours, fait, echec

    visible: actif
    radius: 18
    height: col.implicitHeight + 24
    clip: true

    onActifChanged: if (!actif) fermer()
    // Un clic sur une action : la ligne d'état de l'action d'avant disparaît, la page ne grandit pas
    onChoixChanged: if (choix !== "" && etatAction !== "encours") etatAction = ""

    // Cacher la page n'arrête PAS une action déjà partie (rtx_relancer ferme puis rouvre une appli : la tuer à mi-chemin
    // la laisserait fermée) ; elle va au bout, sans rien relancer ensuite (finAction)
    function fermer() {
        gen++
        ouvert = false; choix = ""; res = null; aRelire = false
        if (etatAction !== "encours") etatAction = ""
        lecteur.running = false
    }
    function ouvrir() { ouvert = true; res = null; if (etatAction !== "encours") etatAction = ""; sansIa = false; lancer() }
    function lancer() {
        if (lecteur.running) { aRelire = true; return }
        aRelire = false; phase = "faits"; faitsRecus = false; sorti = false
        gen++
        lecteur.running = true
    }
    // Quand la lecture est finie ET son texte reçu (dans un ordre ou dans l'autre) : l'IA après les faits, ou une relecture demandée
    function suite() {
        if (!sorti) return
        if (aRelire) { lancer(); return }
        if (phase === "faits" && ouvert && !sansIa && faitsRecus && res !== null && res.causes.length > 0) {
            phase = "ia"; sorti = false; lecteur.entree = true
            lecteur.running = true
        }
    }
    function valide(o) {
        return o !== null && typeof o === "object" && typeof o.phrases === "string" && Array.isArray(o.causes) && Array.isArray(o.actions)
    }
    function recu(texte, genLue) {
        if (!ouvert || genLue !== gen) return              // page fermée ou résultat périmé
        let o = null
        try { o = JSON.parse(texte) } catch (e) { return }
        if (phase === "ia") {
            // Seulement le texte et l'ordre : les actions restent celles qui sont affichées
            if (!res || o === null || typeof o !== "object" || o.ia !== true || typeof o.phrases !== "string" || !Array.isArray(o.ordre)) return
            const reste = res.actions.slice(), ordonnees = []
            for (let k = 0; k < o.ordre.length; k++) {
                const n = reste.findIndex(a => a.id === o.ordre[k])
                if (n >= 0) ordonnees.push(reste.splice(n, 1)[0])
            }
            res = Object.assign({}, res, { phrases: o.phrases, ia: true, actions: ordonnees.concat(reste) })
            return
        }
        if (!valide(o) || o.sur_batterie !== true) return
        // Les actions ont changé pendant qu'une confirmation était ouverte : on la ferme, rien n'est lancé sur un doute
        if (choix !== "") {
            const avant = action(choix), apres = o.actions.find(a => a.id === choix)
            if (!avant || !apres || JSON.stringify(avant) !== JSON.stringify(apres)) choix = ""
        }
        res = o
        faitsRecus = true
        suite()
    }
    readonly property var actions: res ? res.actions : []
    function action(ident) {
        for (let i = 0; i < actions.length; i++) if (actions[i].id === ident) return actions[i]
        return null
    }
    function lancerAction(a) {
        // Seulement un argv de chaînes, pris dans la liste de nc-conso (un modelData rend la liste en tableau « liste »,
        // pas en vrai tableau JS : on la recopie)
        if (etatAction === "encours") return                 // une seule action à la fois
        if (!a || !a.commande || typeof a.commande.length !== "number" || a.commande.length === 0 || typeof a.commande === "string") return
        const cmd = []
        for (let i = 0; i < a.commande.length; i++) {
            if (typeof a.commande[i] !== "string") return
            cmd.push(a.commande[i])
        }
        choix = ""; etatAction = "encours"; derniereAction = a.id
        executeur.demarre = false
        executeur.command = cmd
        executeur.running = true
    }
    function finAction(code) {
        if (!ouvert) { etatAction = ""; return }             // page cachée entre-temps : rien à afficher, rien à relancer
        etatAction = code === 0 ? "fait" : "echec"
        sansIa = true                                        // relire les faits seulement, sans nouvel appel à l'IA
        lancer()
    }

    // Les faits, puis le récit de l'IA
    Process {
        id: lecteur
        property int genDemarrage: 0                 // la génération de p, posée une seule fois au démarrage du processus
        property bool entree: false                  // IA : les faits passent par l'entrée standard (jamais dans l'argv)
        stdinEnabled: entree
        onStarted: {
            genDemarrage = p.gen
            if (entree) { write(JSON.stringify(p.res) + "\n"); entree = false }      // puis l'entrée est fermée
        }
        // Même langue que l'île (Reglages.en), pas celle du service qui a lancé qs
        environment: ({ "NC_LANGUE": Reglages.en ? "en" : "fr" })
        command: p.phase === "ia" && p.res ? [Etat.bin + "nc-conso", "pourquoi", "--ia", "--faits", "-"]
                                           : [Etat.bin + "nc-conso", "pourquoi", "--json"]
        stdout: StdioCollector { onStreamFinished: p.recu(this.text, lecteur.genDemarrage) }
        onRunningChanged: if (!running) { p.sorti = true; p.suite() }
    }
    // L'action confirmée (un seul processus à la fois)
    Process {
        id: executeur
        property bool demarre: false
        environment: ({ "NC_LANGUE": Reglages.en ? "en" : "fr" })
        onStarted: demarre = true
        onExited: (code, statut) => p.finAction(code)
        // Binaire introuvable : le processus ne démarre pas (jamais « started » ni « exited »), c'est un échec
        onRunningChanged: if (!running && !demarre && p.etatAction === "encours") p.finAction(-1)
    }

    Column {
        id: col
        x: 14; y: 12; width: parent.width - 28; spacing: 8

        // Le bouton d'entrée
        Item {
            objectName: "pourquoi-bouton"
            visible: !p.ouvert
            width: parent.width; height: 28
            Ico {
                id: icoQ
                anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                nom: "help"; taille: 20; color: Couleurs.texteSec
            }
            Texte {
                anchors.left: icoQ.right; anchors.leftMargin: 10; anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                text: Reglages.t("Pourquoi ça se vide ?", "Why is it draining?")
                font.weight: Font.DemiBold; font.pixelSize: 14
            }
            MouseArea {
                anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                onClicked: p.ouvrir()
            }
            Accessible.role: Accessible.Button
            Accessible.name: Reglages.t("Pourquoi ça se vide ?", "Why is it draining?")
        }

        // La réponse
        Texte {
            objectName: "pourquoi-texte"
            visible: p.ouvert
            width: parent.width
            textFormat: Text.PlainText
            wrapMode: Text.Wrap; maximumLineCount: 5; elide: Text.ElideRight
            text: p.res ? p.res.phrases : Reglages.t("Je regarde ce qui consomme…", "Checking what uses power…")
            color: p.res ? Couleurs.texte : Couleurs.texteSec
        }

        // Une action : un bouton qui dit ce qui va changer ; au clic, la confirmation prend sa place
        Repeater {
            model: p.ouvert ? p.actions : []
            Item {
                id: a
                required property var modelData
                objectName: "pourquoi-action"
                readonly property bool confirmation: p.choix === modelData.id
                width: col.width
                height: confirmation ? conf.implicitHeight + 20 : bouton.implicitHeight + 16
                Rectangle {
                    id: fond
                    anchors.fill: parent; radius: 16
                    color: a.confirmation ? Couleurs.gris3 : (zone.containsMouse ? Couleurs.gris3 : Couleurs.gris2)
                    opacity: p.etatAction === "encours" ? 0.5 : 1
                    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
                }
                Column {
                    id: bouton
                    visible: !a.confirmation
                    x: 14; y: 8; width: parent.width - 28; spacing: 1
                    Texte {
                        width: parent.width; text: a.modelData.libelle
                        font.weight: Font.DemiBold; font.pixelSize: 13; textFormat: Text.PlainText
                    }
                    Texte {
                        width: parent.width; text: a.modelData.detail
                        secondaire: true; font.pixelSize: 12; textFormat: Text.PlainText
                        wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                    }
                }
                MouseArea {
                    id: zone
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    enabled: !a.confirmation && p.etatAction !== "encours"
                    onClicked: p.choix = a.modelData.id
                }
                // La confirmation : Annuler · Confirmer (le bouton principal en clair, à droite, comme ConfirmationGpu)
                Column {
                    id: conf
                    objectName: "pourquoi-confirmation"
                    visible: a.confirmation
                    x: 14; y: 10; width: parent.width - 28; spacing: 6
                    Texte {
                        width: parent.width; text: a.modelData.libelle + " ?"
                        font.weight: Font.DemiBold; font.pixelSize: 13; textFormat: Text.PlainText
                        wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                    }
                    Texte {
                        width: parent.width; text: a.modelData.detail
                        color: Couleurs.texteDoux; font.pixelSize: 12; textFormat: Text.PlainText
                        wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight
                    }
                    Row {
                        anchors.right: parent.right; spacing: 8
                        Repeater {
                            model: [{ nom: "pourquoi-annuler", texte: Reglages.t("Annuler", "Cancel"), principal: false },
                                    { nom: "pourquoi-confirmer", texte: Reglages.t("Confirmer", "Confirm"), principal: true }]
                            Rectangle {
                                id: b
                                required property var modelData
                                objectName: modelData.nom
                                width: Math.max(88, lb.implicitWidth + 28); height: 32; radius: 16
                                color: modelData.principal ? (zb.containsMouse ? Couleurs.texteDoux : Couleurs.texte)
                                                           : (zb.containsMouse ? Couleurs.gris4 : Couleurs.gris3)
                                scale: zb.pressed ? 0.95 : 1
                                Behavior on scale { enabled: !Reglages.sobre; SpringAnimation { spring: 6; damping: 0.45 } }
                                Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
                                Texte {
                                    id: lb; anchors.centerIn: parent; text: b.modelData.texte
                                    font.pixelSize: 13; font.weight: Font.DemiBold
                                    color: b.modelData.principal ? Couleurs.fond : Couleurs.texte
                                }
                                MouseArea {
                                    id: zb; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: b.modelData.principal ? (p.choix === a.modelData.id ? p.lancerAction(a.modelData) : p.choix = "") : p.choix = ""
                                }
                                Accessible.role: Accessible.Button
                                Accessible.name: modelData.texte
                            }
                        }
                    }
                }
            }
        }

        // Le résultat de la dernière action
        Texte {
            objectName: "pourquoi-etat"
            visible: p.ouvert && p.etatAction !== "" && p.choix === ""        // masquée pendant une confirmation
            width: parent.width; textFormat: Text.PlainText
            secondaire: true; font.pixelSize: 12
            text: p.etatAction === "encours" ? Reglages.t("En cours…", "Working…")
                  : p.etatAction === "fait" ? Reglages.t("C'est fait.", "Done.")
                  : p.derniereAction === "rtx_relancer"
                    ? Reglages.t("Ça n'a pas marché. L'appli a pu être fermée : rouvre-la si besoin.", "That didn't work. The app may have been closed: reopen it if needed.")
                  : Reglages.t("Ça n'a pas marché. Rien d'autre n'a changé.", "That didn't work. Nothing else changed.")
        }

        // Fermer la réponse
        Item {
            visible: p.ouvert
            width: parent.width; height: 24
            Texte {
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                text: Reglages.t("Fermer", "Close"); secondaire: true; font.pixelSize: 12
            }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: p.fermer() }
            Accessible.role: Accessible.Button
            Accessible.name: Reglages.t("Fermer", "Close")
        }
    }
}
