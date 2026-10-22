// Fiche des raccourcis (Super + /), éditable sur place : la même fiche que celle de Noctalia (sections de nc-keys, trois
// ou quatre colonnes selon la place), dans le cadre du carrousel des fonds (Gabarit.qml), en verre aux couleurs du
// bureau. Créée seulement une fois ses raccourcis connus (gardés par Raccourcis.qml : jamais une carte vide). Le fondu
// d'entrée et de sortie est celui de Hyprland (animations des couches), qui fond le flou et la carte ensemble ; la carte
// y ajoute un léger zoom à l'entrée. « Modifier » passe en mode édition, comme le
// Centre de contrôle de l'iPhone : l'interrupteur éteint ou rallume un raccourci de la config (éteint, il reste dans la
// fiche, grisé), − supprime l'un des tiens (ceux de la config ne se suppriment pas), un toucher sur les touches attend
// la nouvelle combinaison, le nom de l'un des tiens se renomme, ↺ remet celui de la config. « + Ajouter », dans l'en-tête
// et toujours là, crée un raccourci (une appli, « bureau N », « ile PAGE » ou une commande) ; si l'IA est permise
// (nc-ia actif), il peut aussi être décrit en mots : l'IA propose (nc-ia raccourci), on corrige, rien n'est ajouté sans
// un clic. Toute l'édition passe par Raccourcis.qml, comme la page « Raccourcis » des réglages.
// Verre : flou de Hyprland derrière (règle de calque nc-fiche, regles.lua), fond de la palette à 58 %, et sous chaque
// colonne un voile du fond à 25 % (rayon 10, il ne se voit pas comme une carte) : le texte reste lisible sur un fond
// d'écran clair flouté ; sans flou (Économie, flou coupé) : 92 %, lisible même sur du blanc pur. Le texte secondaire y
// est un cran plus proche du texte (texteSecondaire). Clavier : Échap annule la capture, quitte l'édition, ferme.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import Quickshell.Wayland

PanelWindow {
    id: fiche
    signal fermer()
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    // Calque Top, sous l'île (Overlay) : la pilule, ses bannières et ses activités restent au-dessus de la fiche (entre
    // surfaces du même calque, la plus récente passerait devant). La barre de Noctalia est aussi en Top, créée avant :
    // la fiche la couvre, et un clic dessus ferme la fiche. Overlay seulement devant une fenêtre en plein écran, qui
    // passe au-dessus du calque Top : la fiche y serait invisible tout en gardant le clavier (même règle que Vue.qml)
    WlrLayershell.layer: Hyprland.activeToplevel && Hyprland.activeToplevel.lastIpcObject
                         && (Hyprland.activeToplevel.lastIpcObject.fullscreen || 0) > 0 ? WlrLayer.Overlay : WlrLayer.Top
    WlrLayershell.namespace: "nc-fiche"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    color: "transparent"

    property bool edition: false
    readonly property var lignes: Raccourcis.lignes // les raccourcis du catalogue de nc-reglages (gardé par Raccourcis.qml)
    property real hautReserve: Gabarit.barre        // place réservée en haut de l'écran (la barre), donnée par shell.qml
    Component.onCompleted: { Raccourcis.relire(); entree = true }
    property var tentative: null                    // dernière capture envoyée : pour « Remplacer » si les touches sont prises
    property var conflit: null
    property bool ajout: false                      // la petite carte « + Ajouter » est ouverte
    property var applis: []                         // pour les suggestions de « + Ajouter » (nc-apps list, lu à l'ouverture)
    onAjoutChanged: {
        if (ajout && !applis.length && !lectureApplis.running) lectureApplis.running = true
        if (ajout && !iaActif.running) iaActif.running = true
        if (!ajout) { demandeIA.running = false; proposition = null; erreurIA = "" }
    }
    Process {
        id: lectureApplis
        command: [Raccourcis.bin + "nc-apps", "list"]
        stdout: StdioCollector { onStreamFinished: { try { fiche.applis = JSON.parse(text) } catch (e) { fiche.applis = [] } } }
    }
    // ── « + Ajouter » par l'IA : seulement si nc-ia est installé et l'IA permise (nc-ia actif : 0 ; IA_MODE=non : 1 ;
    // absent : ne démarre pas). Vérifié à l'ouverture de la carte ; l'IA n'est appelée que sur demande ──
    property bool iaPermise: false
    readonly property bool iaPrete: iaPermise && !Reglages.iaCoupee
    property var proposition: null                  // ce que l'IA propose : {touches, cible, genre, nom, detail}
    property string erreurIA: ""
    Process {
        id: iaActif
        command: [Raccourcis.bin + "nc-ia", "actif"]
        onExited: code => fiche.iaPermise = code === 0
    }
    Process {
        id: demandeIA
        stdout: StdioCollector { onStreamFinished: fiche.lireProposition(text) }
    }
    function proposer() {
        var t = champIA.texte.trim()
        if (!t || demandeIA.running || !iaPrete) return
        proposition = null; erreurIA = ""
        demandeIA.command = [Raccourcis.bin + "nc-ia", "raccourci", "--json", t]
        demandeIA.running = true
    }
    // La réponse de nc-ia raccourci (déjà vérifiée : touches, appli, bureau, page de l'île) : proposée, jamais ajoutée
    function lireProposition(texte) {
        if (!ajout) return                          // carte refermée pendant la demande
        var d = null
        try { d = JSON.parse(String(texte).trim().split("\n").pop()) } catch (e) {}
        if (d && d.ok && d.touches && d.cible) {
            proposition = d; champTouchesIA.texte = d.touches; champNomIA.texte = d.nom || ""
        } else erreurIA = d && d.erreur ? d.erreur : Reglages.t("L'IA n'a pas répondu de façon lisible : réessaie, ou crée-le à la main.",
                                                                 "The AI did not answer readably: try again, or create it by hand.")
    }
    // [Ajouter] : par le même chemin que l'ajout à la main (Raccourcis.ajouter), touches prises comprises (« Remplacer »)
    function ajouterProposition() {
        var p = proposition, touches = champTouchesIA.texte.trim(), nom = champNomIA.texte.trim() || (p ? p.nom : "")
        if (!p || !touches) return
        tentative = { r: { modifiable: true, nom: nom, ajout: { cible: p.cible, nom: nom } }, touches: touches }
        Raccourcis.ajouter(touches, p.cible, nom)
        annulerProposition(); champIA.texte = ""; ajout = false; zoneClavier.forceActiveFocus()
    }
    function annulerProposition() { proposition = null; erreurIA = ""; champTouchesIA.texte = ""; champNomIA.texte = "" }
    // Ouvrir « + Ajouter » (depuis l'en-tête) : passe en édition, où s'affichent le résultat et « Remplacer »
    function ouvrirAjout() { edition = true; conflit = null; ajout = true; champCible.forceActiveFocus() }
    // Les applis dont le nom ou l'identifiant contient ce qui est tapé (6 au plus)
    function suggestions(t) {
        t = String(t || "").trim().toLowerCase()
        if (t.length < 2 || /^(bureau|desktop|ile|île|island)\b/.test(t)) return []
        return applis.filter(a => String(a.name || "").toLowerCase().indexOf(t) >= 0 || String(a.id || "").toLowerCase().indexOf(t) >= 0).slice(0, 6)
    }
    readonly property bool verre: Reglages.val("FENETRES_FLOU", "oui") !== "non" && !Reglages.sobre
    readonly property real opaciteFond: verre ? 0.58 : 0.92
    // Sous chaque colonne de texte : le fond de la palette, en plus, à 25 % (remonte le contraste sans faire de carte)
    readonly property real voileColonne: 0.25
    // Texte secondaire de la fiche : texteSec un cran vers le texte (plus clair sur une palette sombre, plus foncé sur
    // une claire). Pas texteDoux : c'est le blanc ANSI du terminal, pâle aussi sur une palette claire
    readonly property color texteSecondaire: Qt.tint(Couleurs.texteSec, Qt.alpha(Couleurs.texte, 0.35))
    // Interrupteur éteint : le verre voilé du texte, pour se détacher de la carte (3:1, même sur le pire fond derrière)
    readonly property real voilePiste: 0.7
    readonly property real largeurEcran: fiche.screen ? fiche.screen.width : 1600
    readonly property real hauteurEcran: fiche.screen ? fiche.screen.height : 1000

    // ── Les raccourcis ──
    Connections {
        target: Raccourcis
        function onEcrit() {
            if (Raccourcis.erreur && fiche.tentative && /déjà pris|already in use/i.test(Raccourcis.message)) fiche.conflit = fiche.tentative
            fiche.tentative = null
        }
        function onCaptureFinie() { zoneClavier.forceActiveFocus() }
    }
    function section(r) { return r.mien !== "" ? "Mes raccourcis" : (r.aide || "Système") }
    readonly property var parSection: {
        var s = {}
        lignes.forEach(r => { var n = section(r); (s[n] = s[n] || []).push(r) })   // les désactivés aussi, grisés
        return s
    }
    readonly property var titres: ({ "Applis et barre": "Apps & Bar", "Fenêtres": "Windows", "Bureaux": "Desktops",
                                     "Souris": "Mouse", "Système": "System", "IA": "AI", "Mes raccourcis": "My Shortcuts" })
    // Les touches d'un raccourci, en groupes : « Super + Ctrl + molette / Super + = » -> [["Super", "Ctrl", "molette"],
    // ["Super", "="]] ; « / » sépare deux combinaisons, « + » deux touches, toujours entre espaces (la touche « + » ou
    // « - » n'est pas un séparateur)
    function groupes(r) {
        return String(r.valeur || "").split(/\s+\/\s+/).map(g => g.trim().split(/\s+\+\s+/).filter(t => t !== "")).filter(g => g.length)
    }
    // Une combinaison comparable : « Super + Q », « Super+Q » ou ["Super", "Q"] -> « super+q »
    function norm(t) { return (Array.isArray(t) ? t.join("+") : String(t)).replace(/\s+/g, "").toLowerCase() }

    // ── Disposition : le cadre du carrousel (Gabarit.qml) ; trois ou quatre colonnes de même largeur selon la place,
    // les sections réparties pour que toutes finissent à peu près à la même hauteur ; la liste défile seulement si elle
    // ne tient pas (petit écran) ──
    readonly property rect cadre: Gabarit.cadre(largeurEcran, hauteurEcran, hautReserve)
    readonly property int nbColonnes: Math.max(2, Math.min(4, Math.floor((cadre.width - 2 * Gabarit.marge + 24) / (340 + 24))))
    readonly property real largeurColonne: Math.floor((cadre.width - 2 * Gabarit.marge - 24 * (nbColonnes - 1)) / nbColonnes)
    readonly property var ordreSections: ["Applis et barre", "Fenêtres", "Bureaux", "Système", "IA", "Souris", "Mes raccourcis"]
    // Largeur estimée des pastilles d'un raccourci (7,4 points par caractère) : la colonne des touches de chaque section,
    // et l'équilibrage des colonnes ; une ligne décide de passer ses touches au-dessus d'après leur largeur réelle
    function largeurTouches(r) {
        var l = 0
        groupes(r).forEach((g, j) => {
            if (j > 0) l += 24                      // « ou »
            g.forEach((k, i) => { l += (i > 0 ? 17 : 0) + k.length * 7.4 + 16 })
        })
        return l
    }
    // Hauteur estimée d'une section (comme Ligne : rangées de pastilles, description sur 3 lignes au plus)
    function hauteurSection(n) {
        var rs = parSection[n] || []
        if (!rs.length) return 0
        var kw = Math.min(190, Math.max(60, ...rs.map(largeurTouches))), h = 56, place = largeurColonne - (edition ? 44 : 0)
        var lignesTexte = (r, l) => Math.min(3, Math.max(1, Math.ceil(r.nom.length * 7.3 / Math.max(1, l))))
        rs.forEach(r => {
            var t = largeurTouches(r)
            if (t > kw) h += 3 + Math.ceil(t / place) * 29 - 5 + 4 + 17 * lignesTexte(r, place) + 6
            else h += Math.max(30, 12 + 17 * lignesTexte(r, place - kw - 14))
        })
        return h
    }
    readonly property var colonnes: {
        var c = [], h = []
        for (let k = 0; k < nbColonnes; k++) { c.push([]); h.push(0) }
        ordreSections.forEach(n => {
            var hs = hauteurSection(n)
            if (!hs) return
            var i = h.indexOf(Math.min(...h))       // la colonne la plus courte
            c[i].push(n); h[i] += hs
        })
        return c
    }

    // ── Fermer, quitter l'édition ; une capture interrompue rend TOUJOURS ses raccourcis à Hyprland ──
    function quitter() {
        if (Raccourcis.capture) Raccourcis.finCapture("")
        fiche.fermer()                              // Hyprland fait le fondu de sortie (flou et carte ensemble)
    }
    Component.onDestruction: if (Raccourcis.capture) Raccourcis.finCapture("")
    onVisibleChanged: if (!visible && Raccourcis.capture) Raccourcis.finCapture("")

    MouseArea { anchors.fill: parent; onClicked: fiche.quitter() }          // un clic à côté ferme
    // Montrée seulement quand ses raccourcis sont là (jamais une carte vide qui clignote)
    readonly property bool montree: lignes.length > 0
    property bool entree: false

    FocusScope {
        id: zoneClavier
        anchors.fill: parent
        focus: true
        Component.onCompleted: forceActiveFocus()
        Keys.onPressed: event => {
            if (Raccourcis.capture) {
                let t = Raccourcis.combinaison(event)
                event.accepted = true
                if (t === "") return
                if (t === "annuler") { Raccourcis.finCapture(""); return }
                if (t === "?") { capture.aide = Reglages.t("Ajoute Super, Ctrl ou Alt (ou une touche F1…F12).", "Add Super, Ctrl or Alt (or an F1…F12 key)."); return }
                fiche.tentative = { r: Raccourcis.capture, touches: t }
                Raccourcis.finCapture(t)
                return
            }
            if (event.key === Qt.Key_Escape) {
                event.accepted = true
                if (fiche.conflit) fiche.conflit = null
                else if (fiche.ajout) fiche.ajout = false
                else if (fiche.edition) fiche.edition = false
                else fiche.quitter()
            }
        }
    }

    // ── La carte de verre ──
    Item {
        id: carte
        x: fiche.cadre.x; y: fiche.cadre.y
        width: fiche.cadre.width; height: fiche.cadre.height
        // Entrée : zoom de 0,96 à 1 (200 ms, ralenti à la fin) pendant le fondu de Hyprland ; direct en sobre
        visible: fiche.montree
        scale: fiche.entree ? 1 : 0.96
        Behavior on scale { enabled: !Reglages.sobre; NumberAnimation { duration: Gabarit.entree; easing.type: Easing.OutCubic } }
        // Contour aux couleurs de l'île (ILE_CONTOUR : dégradé de l'accent, discret, aucun)
        Rectangle {
            anchors.fill: fondVerre; anchors.margins: -1.5; radius: fondVerre.radius + 1.5
            visible: Couleurs.aContour
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[0] }
                GradientStop { position: 0.5; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[1] }
                GradientStop { position: 1; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[2] }
            }
        }
        Rectangle {
            id: fondVerre
            anchors.fill: parent; radius: Gabarit.rayon
            color: Qt.alpha(Couleurs.fond, fiche.opaciteFond)
            // Reflet du verre : un liseré clair en haut, qui s'efface vers les bords
            Rectangle {
                x: 28; width: parent.width - 56; height: 1; y: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: Qt.rgba(1, 1, 1, 0) }
                    GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.16) }
                    GradientStop { position: 1; color: Qt.rgba(1, 1, 1, 0) }
                }
            }
        }
        MouseArea { anchors.fill: parent }                                     // un clic dans la carte ne ferme pas

        Texte {
            x: Gabarit.marge; y: 24; font.pixelSize: 18; font.weight: Font.Bold
            text: fiche.edition ? Reglages.t("Modifier les raccourcis", "Edit shortcuts") : Reglages.t("Raccourcis", "Shortcuts")
        }
        // « + Ajouter », toujours là (même hors édition) : ouvre la carte « Nouveau raccourci »
        Rectangle {
            id: boutonAjouter
            objectName: "nc-fiche-plus"
            anchors.right: boutonModifier.left; anchors.rightMargin: 10; y: 20
            width: rangeeAjouter.implicitWidth + 24; height: 30; radius: 15
            color: zAjouter.containsMouse ? Couleurs.gris3 : Couleurs.gris2
            Row {
                id: rangeeAjouter; anchors.centerIn: parent; spacing: 6
                Texte { text: "+"; font.pixelSize: 16; font.weight: Font.Bold; color: Couleurs.accent }
                Texte { text: Reglages.t("Ajouter", "Add"); font.weight: Font.DemiBold }
            }
            MouseArea { id: zAjouter; objectName: "nc-fiche-ajouter"; anchors.fill: parent; hoverEnabled: true; onClicked: fiche.ouvrirAjout() }
        }
        // « Modifier » / « OK »
        Rectangle {
            id: boutonModifier
            objectName: "nc-fiche-modifier"
            anchors.right: parent.right; anchors.rightMargin: 28; y: 20
            width: libModifier.implicitWidth + 28; height: 30; radius: 15
            color: fiche.edition ? Couleurs.accent : (zModifier.containsMouse ? Couleurs.gris3 : Couleurs.gris2)
            Texte {
                id: libModifier; anchors.centerIn: parent; font.weight: Font.DemiBold
                color: fiche.edition ? Couleurs.surAccent : Couleurs.texte
                text: fiche.edition ? Reglages.t("OK", "Done") : Reglages.t("Modifier", "Edit")
            }
            MouseArea { id: zModifier; anchors.fill: parent; hoverEnabled: true
                        onClicked: { fiche.edition = !fiche.edition; fiche.ajout = false; fiche.conflit = null; zoneClavier.forceActiveFocus() } }
        }

        // La liste défile (molette, pavé tactile) ; l'en-tête et « Modifier » / « OK » restent en place
        WheelHandler {
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            property real cumul: 0
            onWheel: event => {
                cumul += event.angleDelta.y
                if (Math.abs(cumul) < 120) return               // un cran de molette, ou un geste assez long
                defilement.defiler(cumul)
                cumul = 0
            }
        }
        // La liste déborde de 10 de chaque côté : la place du voile des colonnes, sans le couper
        Defilement {
            id: defilement
            objectName: "nc-fiche-liste"
            x: Gabarit.marge - 10; y: 56
            width: parent.width - 2 * Gabarit.marge + 20; height: parent.height - y - 46
            contentWidth: width; contentHeight: contenu.height + 20
            Row {
                id: contenu
                x: 10; y: 10
                spacing: 24
                Repeater {
                    model: fiche.colonnes
                    Item {
                        id: colonne
                        required property var modelData
                        width: fiche.largeurColonne; height: pile.height
                        // Le voile : le fond de la palette à 25 %, sous le texte de la colonne
                        Rectangle {
                            objectName: "nc-fiche-voile"
                            anchors.fill: parent; anchors.margins: -10; radius: 10
                            color: Qt.alpha(Couleurs.fond, fiche.voileColonne)
                        }
                        Column {
                        id: pile
                        width: parent.width
                        spacing: 0
                        clip: true                      // rien ne déborde dans la colonne voisine
                        Repeater {
                            model: colonne.modelData
                            Column {
                                id: bloc
                                required property string modelData
                                required property int index
                                readonly property var rangees: fiche.parSection[modelData] || []
                                readonly property real kw: Math.min(190, Math.max(60, ...rangees.map(fiche.largeurTouches)))
                                visible: rangees.length > 0
                                width: colonne.width
                                Item { width: 1; height: bloc.index > 0 ? 22 : 0 }
                                Texte {
                                    width: colonne.width; height: 34; color: Couleurs.accent; font.pixelSize: 14; font.weight: Font.Bold
                                    text: Reglages.en ? (fiche.titres[bloc.modelData] || bloc.modelData) : bloc.modelData
                                }
                                Repeater {
                                    model: bloc.rangees
                                    Ligne { required property var modelData; r: modelData; kw: bloc.kw; largeur: colonne.width }
                                }
                            }
                        }
                        }
                    }
                }
            }
        }

        // Message : résultat d'une écriture, ou combinaison déjà prise avec « Remplacer »
        // Sur un voile du fond, comme les colonnes (un peu plus marqué : il apparaît seul, au bas de la carte)
        Rectangle {
            anchors.centerIn: rangeeMessage; width: rangeeMessage.width + 24; height: 34; radius: 17
            visible: rangeeMessage.visible; color: Qt.alpha(Couleurs.fond, 0.5)
        }
        Row {
            id: rangeeMessage
            objectName: "nc-fiche-message"
            anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 14
            spacing: 10
            visible: Raccourcis.message !== "" && fiche.edition
            Texte {
                anchors.verticalCenter: parent.verticalCenter
                text: Raccourcis.message; color: Raccourcis.erreur ? Couleurs.rouge : Couleurs.texte; font.pixelSize: 12
            }
            Rectangle {
                visible: !!fiche.conflit; width: libRemplacer.implicitWidth + 22; height: 26; radius: 13; color: Couleurs.rouge
                Texte { id: libRemplacer; anchors.centerIn: parent; text: Reglages.t("Remplacer", "Replace"); color: "#ffffff"; font.pixelSize: 12 }
                MouseArea { objectName: "nc-fiche-remplacer"; anchors.fill: parent; onClicked: fiche.remplacer() }
            }
            Rectangle {
                visible: !!fiche.conflit; width: libAnnuler.implicitWidth + 22; height: 26; radius: 13; color: Couleurs.gris2
                Texte { id: libAnnuler; anchors.centerIn: parent; text: Reglages.t("Annuler", "Cancel"); font.pixelSize: 12 }
                MouseArea { anchors.fill: parent; onClicked: fiche.conflit = null }
            }
        }
    }
    // Remplacer : l'autre raccourci qui a ces touches est désactivé (ou retiré, si c'est l'un des tiens), puis on refait
    function remplacer() {
        var c = conflit
        conflit = null
        if (!c) return
        var autre = lignes.find(x => !x.desactive && groupes(x).some(g => norm(g) === norm(c.touches)) && x !== c.r && x.cle !== (c.r && c.r.cle))
        if (autre) Raccourcis.supprimer(autre)
        tentative = c
        if (c.r && c.r.ajout) Raccourcis.ajouter(c.touches, c.r.ajout.cible, c.r.ajout.nom)
        else Raccourcis.raccourci(c.r, "changer", c.touches)
    }


    // ── Une ligne : touches, puis description ; en édition : − (les tiens), touches à changer, nom à renommer, ↺,
    // interrupteur (ceux de la config) ──
    component Ligne: Item {
        id: ligne
        objectName: "nc-fiche-ligne-" + r.cle
        property var r
        property real kw: 220
        property real largeur: 490
        readonly property bool mien: r.mien !== ""
        // Éteint : touches et description grisées, pas l'interrupteur (à pleine opacité, pour le rallumer)
        readonly property real attenue: r.desactive ? 0.45 : 1
        readonly property bool origine: fiche.edition && r.modifie && !mien && !r.desactive          // ↺ montré
        // En édition : − à gauche pour les tiens ; à droite, l'interrupteur (34) et le ↺ pour ceux de la config
        readonly property real gauche: fiche.edition && mien ? 30 : 0
        readonly property real droite: !fiche.edition || mien ? 0 : 44 + (origine ? 26 : 0)
        // Touches au-dessus de la description quand elles ne tiennent pas dans la colonne des touches (largeur réelle,
        // mesurée hors écran, pas l'estimation)
        readonly property bool longues: mesure.implicitWidth > kw
        readonly property real placeTexte: largeur - gauche - kw - 14 - droite
        readonly property real hauteurTexte: fiche.edition && mien ? 24 : description.implicitHeight
        width: largeur
        // La hauteur suit le vrai texte (3 lignes au plus) et les rangées de pastilles ; jamais d'après leur y, qui dépend
        // de la hauteur hors mode longues (boucle de liaison au changement de mode)
        readonly property real basTouches: 3 + blocTouches.height
        height: longues ? basTouches + 4 + hauteurTexte + 6 : Math.max(30, hauteurTexte + 12)
        transformOrigin: Item.Center
        // En édition, la ligne survolée frétille une fois, comme sur l'iPhone (deux allers-retours, 300 ms) ; à refaire en
        // ressortant puis en revenant. Rien sans survol, rien en sobre (Économie, sans effets)
        readonly property bool fretille: fretillement.running
        function survoler() { if (fiche.edition && !Reglages.sobre) fretillement.restart() }
        HoverHandler { onHoveredChanged: if (hovered) ligne.survoler() }
        SequentialAnimation {
            id: fretillement
            onStopped: ligne.rotation = 0
            RotationAnimator { target: ligne; from: 0; to: 0.6; duration: 38 }
            RotationAnimator { target: ligne; from: 0.6; to: -0.6; duration: 75 }
            RotationAnimator { target: ligne; from: -0.6; to: 0.6; duration: 75 }
            RotationAnimator { target: ligne; from: 0.6; to: -0.6; duration: 75 }
            RotationAnimator { target: ligne; from: -0.6; to: 0; duration: 37 }
        }
        // − : supprimer l'un des tiens. En verre, comme l'interrupteur ; rouge seulement au survol
        Rectangle {
            id: moins
            visible: fiche.edition && ligne.mien
            anchors.verticalCenter: parent.verticalCenter
            width: 22; height: 22; radius: 11
            color: zMoins.containsMouse ? Qt.alpha(Couleurs.carteSurvol, 0.75) : Qt.alpha(Couleurs.carte, 0.55)
            border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.28)
            // Reflet du verre : le haut s'éclaire à peine (blanc à 18 %, effacé à mi-hauteur), sans sortir du bord
            Rectangle {
                anchors.fill: parent; anchors.margins: 1; radius: height / 2
                gradient: Gradient {
                    GradientStop { position: 0; color: Qt.rgba(1, 1, 1, 0.18) }
                    GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0) }
                }
            }
            Texte { anchors.centerIn: parent; text: "−"; font.pixelSize: 16; font.weight: Font.Bold
                    color: zMoins.containsMouse ? Couleurs.rouge : Couleurs.texte }
            MouseArea {
                id: zMoins
                objectName: "nc-fiche-moins-" + ligne.r.cle
                anchors.fill: parent; anchors.margins: -4; hoverEnabled: true
                onClicked: if (ligne.mien) Raccourcis.supprimer(ligne.r)          // un des tiens : retirer
            }
        }
        // Les pastilles, groupe par groupe (« ou » entre deux combinaisons) ; un groupe ne se coupe pas
        Flow {
            id: blocTouches
            objectName: "nc-fiche-pastilles-" + ligne.r.cle
            x: ligne.gauche
            width: ligne.longues ? ligne.largeur - x - ligne.droite : ligne.kw
            y: ligne.longues ? 3 : (ligne.height - height) / 2
            spacing: 5
            opacity: ligne.attenue
            Repeater {
                model: fiche.groupes(ligne.r)
                GroupeTouches { required property var modelData; required property int index; touches: modelData; premier: index === 0
                         edite: fiche.edition && ligne.r.modifiable }
            }
        }
        // Les mêmes pastilles sur une seule rangée, invisibles : leur vraie largeur (hors du Flow, qui en dépend)
        Row {
            id: mesure
            opacity: 0; enabled: false
            spacing: blocTouches.spacing
            Repeater {
                model: fiche.groupes(ligne.r)
                GroupeTouches { required property var modelData; required property int index; touches: modelData; premier: index === 0 }
            }
        }
        // Hors du Flow (dedans, sa taille dépendrait du Flow lui-même : boucle de mise en page)
        MouseArea {
            objectName: "nc-fiche-touches-" + ligne.r.cle
            x: blocTouches.x; y: blocTouches.y; width: blocTouches.width; height: blocTouches.height
            enabled: fiche.edition && ligne.r.modifiable
            onClicked: { if (Raccourcis.capturer(ligne.r)) { capture.aide = ""; zoneClavier.forceActiveFocus() } }
        }
        // Description : le texte entier (3 lignes au plus, sans « … »), dans sa place ; ou le nom de l'un des tiens à
        // renommer en édition
        Texte {
            id: description
            objectName: "nc-fiche-description-" + ligne.r.cle
            visible: !(fiche.edition && ligne.mien)
            x: ligne.longues ? ligne.gauche : ligne.gauche + ligne.kw + 14
            width: ligne.longues ? ligne.largeur - x - ligne.droite : ligne.placeTexte
            y: ligne.longues ? ligne.basTouches + 4 : (ligne.height - implicitHeight) / 2
            opacity: ligne.attenue
            text: ligne.r.nom; color: fiche.texteSecondaire
            wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideNone    // entre les mots, au milieu d'un mot trop long
        }
        Rectangle {
            visible: fiche.edition && ligne.mien
            x: description.x; y: ligne.longues ? description.y : (ligne.height - 24) / 2
            width: description.width; height: 24; radius: 7
            color: Qt.alpha(Couleurs.carte, 0.6); border.width: 1; border.color: champNom.activeFocus ? Couleurs.accent : Qt.alpha(Couleurs.texte, 0.25)
            TextInput {
                id: champNom
                objectName: "nc-fiche-nom-" + ligne.r.cle
                anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8
                verticalAlignment: TextInput.AlignVCenter; clip: true
                color: Couleurs.texte; font.family: "Adwaita Sans"; font.pixelSize: 13
                text: ligne.r.nom
                onAccepted: { if (text.trim() && text !== ligne.r.nom) Raccourcis.raccourci(ligne.r, "renommer", "", text.trim()); zoneClavier.forceActiveFocus() }
                Keys.onEscapePressed: { text = ligne.r.nom; zoneClavier.forceActiveFocus() }
            }
        }
        // ↺ : comme dans la config, juste avant l'interrupteur
        Texte {
            visible: ligne.origine
            anchors.right: interrupteur.left; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
            width: 16; horizontalAlignment: Text.AlignHCenter
            text: "↺"; color: Couleurs.accent; font.pixelSize: 16
            MouseArea { objectName: "nc-fiche-origine-" + ligne.r.cle; anchors.fill: parent; anchors.margins: -6
                        onClicked: Raccourcis.raccourci(ligne.r, "origine") }
        }
        // Interrupteur façon iPhone, en verre : allumé (l'accent) ou éteint ; la pastille glisse avec le ressort de l'île
        Item {
            id: interrupteur
            visible: fiche.edition && !ligne.mien
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            width: 34; height: 20
            property bool allume: !ligne.r.desactive     // tout de suite au clic ; la ligne relue confirme
            Rectangle {
                anchors.fill: parent; radius: height / 2
                color: Qt.alpha(Couleurs.carte, 0.55)
                Rectangle {
                    anchors.fill: parent; radius: parent.radius
                    color: interrupteur.allume ? Couleurs.accent : Qt.alpha(Couleurs.texte, fiche.voilePiste)
                    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 160 } }
                }
                // Reflet du verre : le haut s'éclaire à peine (blanc à 18 %, effacé à mi-hauteur), sans sortir du bord
                Rectangle {
                    anchors.fill: parent; anchors.margins: 1; radius: height / 2
                    gradient: Gradient {
                        GradientStop { position: 0; color: Qt.rgba(1, 1, 1, 0.18) }
                        GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0) }
                    }
                }
            }
            Rectangle {
                width: 16; height: 16; radius: 8; y: 2
                x: interrupteur.allume ? interrupteur.width - width - 2 : 2
                color: "#ffffff"                         // blanche, comme sur l'iPhone
                Behavior on x { enabled: !Reglages.sobre; SpringAnimation { spring: 3.4; damping: 0.36 } }
            }
            MouseArea {
                objectName: "nc-fiche-interrupteur-" + ligne.r.cle
                anchors.fill: parent; anchors.margins: -4
                onClicked: {
                    if (ligne.mien) return
                    Raccourcis.raccourci(ligne.r, interrupteur.allume ? "desactiver" : "reactiver")
                    interrupteur.allume = !interrupteur.allume
                }
            }
        }
    }

    // ── « + Ajouter » : que lance le raccourci, son nom, puis ses touches ──
    Rectangle {
        id: carteAjout
        visible: fiche.ajout && !Raccourcis.capture && fiche.montree
        anchors.centerIn: parent
        width: 440; height: colonneAjout.height + 36; radius: 22
        color: Qt.alpha(Couleurs.fond, 0.94); border.width: 1; border.color: Qt.alpha(Couleurs.accent, 0.5)
        MouseArea { anchors.fill: parent }
        Column {
            id: colonneAjout
            x: 22; y: 18; width: parent.width - 44; spacing: 10
            Texte { text: Reglages.t("Nouveau raccourci", "New shortcut"); font.pixelSize: 15; font.weight: Font.Bold }
            Champ { id: champCible; objectName: "nc-fiche-cible"; indice: Reglages.t("Une appli (firefox), « bureau 3 », « ile son » ou une commande", "An app (firefox), “bureau 3”, “ile son” or a command") }
            // Tes applis qui correspondent : un clic les choisit (le raccourci ira à leur fenêtre, sinon les lancera)
            Flow {
                width: parent.width; spacing: 6
                visible: fiche.suggestions(champCible.texte).length > 0
                Repeater {
                    model: fiche.suggestions(champCible.texte)
                    Rectangle {
                        required property var modelData
                        height: 26; width: libAppli.implicitWidth + 20; radius: 13
                        color: zAppli.containsMouse ? Couleurs.gris3 : Couleurs.gris2
                        Texte { id: libAppli; anchors.centerIn: parent; text: modelData.name || modelData.id; font.pixelSize: 12 }
                        MouseArea {
                            id: zAppli; objectName: "nc-fiche-appli-" + modelData.id; anchors.fill: parent; hoverEnabled: true
                            onClicked: { champCible.texte = modelData.id; if (!champNomAjout.texte) champNomAjout.texte = modelData.name || "" }
                        }
                    }
                }
            }
            Champ { id: champNomAjout; indice: Reglages.t("Son nom (facultatif)", "Its name (optional)") }
            Rectangle {
                width: libChoisir.implicitWidth + 28; height: 32; radius: 16
                color: champCible.texte.trim() ? Couleurs.accent : Couleurs.gris3
                Texte { id: libChoisir; anchors.centerIn: parent; text: Reglages.t("Choisir les touches", "Choose the keys")
                        color: champCible.texte.trim() ? Couleurs.surAccent : fiche.texteSecondaire }
                MouseArea {
                    objectName: "nc-fiche-choisir"
                    anchors.fill: parent; enabled: champCible.texte.trim() !== ""
                    onClicked: {
                        var nom = champNomAjout.texte.trim() || champCible.texte.trim()
                        if (Raccourcis.capturer({ modifiable: true, nom: nom, ajout: { cible: champCible.texte.trim(), nom: champNomAjout.texte.trim() } })) {
                            fiche.ajout = false; capture.aide = ""; champCible.texte = ""; champNomAjout.texte = ""; zoneClavier.forceActiveFocus()
                        }
                    }
                }
            }
            // ── Par l'IA (seulement si elle est permise) : décrire, l'IA propose, on corrige, [Ajouter] ou [Annuler] ──
            Item { visible: fiche.iaPrete; width: 1; height: 4 }
            Texte { visible: fiche.iaPrete; text: Reglages.t("Ou décris-le à l'IA", "Or describe it to the AI"); font.pixelSize: 12
                    font.weight: Font.Bold; color: Couleurs.accent }
            Champ {
                id: champIA; objectName: "nc-fiche-ia"
                visible: fiche.iaPrete && !fiche.proposition
                indice: Reglages.t("Décris ton raccourci… (Super + F ouvre Firefox sur le bureau 2)", "Describe your shortcut… (Super + F opens Firefox on desktop 2)")
                onValide: fiche.proposer()
            }
            Rectangle {
                visible: fiche.iaPrete && !fiche.proposition && (champIA.texte.trim() !== "" || demandeIA.running)
                width: libProposer.implicitWidth + 28; height: 32; radius: 16
                color: demandeIA.running ? Couleurs.gris3 : Couleurs.accent
                Texte { id: libProposer; anchors.centerIn: parent
                        text: demandeIA.running ? Reglages.t("L'IA réfléchit…", "The AI is thinking…") : Reglages.t("Proposer", "Suggest")
                        color: demandeIA.running ? Couleurs.texte : Couleurs.surAccent }
                MouseArea { objectName: "nc-fiche-ia-proposer"; anchors.fill: parent; enabled: !demandeIA.running; onClicked: fiche.proposer() }
            }
            Texte {
                objectName: "nc-fiche-ia-erreur"
                visible: fiche.iaPrete && fiche.erreurIA !== ""; width: parent.width
                text: fiche.erreurIA; color: Couleurs.orange; font.pixelSize: 12; wrapMode: Text.Wrap; maximumLineCount: 3
            }
            // La proposition, à corriger au besoin : touches et nom ; la cible est dite telle qu'elle a été vérifiée
            Column {
                objectName: "nc-fiche-ia-proposition"
                visible: fiche.iaPrete && !!fiche.proposition
                width: parent.width; spacing: 8
                Texte { width: parent.width; wrapMode: Text.Wrap; maximumLineCount: 2; color: fiche.texteSecondaire; font.pixelSize: 12
                        text: fiche.proposition ? Reglages.t("Proposé par l'IA : ", "Suggested by the AI: ") + fiche.proposition.detail : "" }
                Row {
                    width: parent.width; spacing: 10
                    Texte { width: 56; height: 32; text: Reglages.t("Touches", "Keys"); color: fiche.texteSecondaire; font.pixelSize: 12 }
                    Champ { id: champTouchesIA; objectName: "nc-fiche-ia-touches"; width: parent.width - 66; onValide: fiche.ajouterProposition() }
                }
                Row {
                    width: parent.width; spacing: 10
                    Texte { width: 56; height: 32; text: Reglages.t("Nom", "Name"); color: fiche.texteSecondaire; font.pixelSize: 12 }
                    Champ { id: champNomIA; objectName: "nc-fiche-ia-nom"; width: parent.width - 66; onValide: fiche.ajouterProposition() }
                }
                Row {
                    spacing: 8
                    Rectangle {
                        width: libAjouterIA.implicitWidth + 28; height: 32; radius: 16
                        color: champTouchesIA.texte.trim() ? Couleurs.accent : Couleurs.gris3
                        Texte { id: libAjouterIA; anchors.centerIn: parent; text: Reglages.t("Ajouter", "Add")
                                color: champTouchesIA.texte.trim() ? Couleurs.surAccent : fiche.texteSecondaire }
                        MouseArea { objectName: "nc-fiche-ia-ajouter"; anchors.fill: parent; enabled: champTouchesIA.texte.trim() !== ""
                                    onClicked: fiche.ajouterProposition() }
                    }
                    Rectangle {
                        width: libAnnulerIA.implicitWidth + 28; height: 32; radius: 16
                        color: zAnnulerIA.containsMouse ? Couleurs.gris3 : Couleurs.gris2
                        Texte { id: libAnnulerIA; anchors.centerIn: parent; text: Reglages.t("Annuler", "Cancel") }
                        MouseArea { id: zAnnulerIA; objectName: "nc-fiche-ia-annuler"; anchors.fill: parent; hoverEnabled: true
                                    onClicked: { fiche.annulerProposition(); champIA.forceActiveFocus() } }
                    }
                }
            }
        }
    }
    component Champ: Rectangle {
        property alias texte: saisie.text
        property string indice: ""
        signal valide()                             // Entrée
        function forceActiveFocus() { saisie.forceActiveFocus() }
        width: parent.width; height: 32; radius: 9
        color: Qt.alpha(Couleurs.carte, 0.8); border.width: 1; border.color: saisie.activeFocus ? Couleurs.accent : Qt.alpha(Couleurs.texte, 0.25)
        TextInput {
            id: saisie
            anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10
            verticalAlignment: TextInput.AlignVCenter; clip: true
            color: Couleurs.texte; font.family: "Adwaita Sans"; font.pixelSize: 13
            Keys.onEscapePressed: { fiche.ajout = false; zoneClavier.forceActiveFocus() }
            onAccepted: parent.valide()
            Texte { anchors.fill: parent; visible: !saisie.text && !saisie.activeFocus; text: parent.parent.indice; color: fiche.texteSecondaire; font.pixelSize: 12 }
        }
    }

    // ── Capture des touches ──
    Rectangle {
        id: capture
        property string aide: ""
        visible: !!Raccourcis.capture && fiche.montree
        anchors.centerIn: parent
        width: 420; height: 132; radius: 22
        color: Qt.alpha(Couleurs.fond, 0.95); border.width: 1.5; border.color: Couleurs.accent
        MouseArea { anchors.fill: parent }
        Column {
            anchors.centerIn: parent; spacing: 8; width: parent.width - 40
            Texte { width: parent.width; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 15; font.weight: Font.Bold
                    text: Reglages.t("Tape les nouvelles touches…", "Type the new keys…") }
            Texte { width: parent.width; horizontalAlignment: Text.AlignHCenter; color: fiche.texteSecondaire
                    text: Raccourcis.capture ? "« " + Raccourcis.capture.nom + " »" : "" }
            Texte { width: parent.width; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 12
                    color: capture.aide ? Couleurs.orange : fiche.texteSecondaire
                    text: capture.aide || Reglages.t("Échap pour annuler", "Esc to cancel") }
        }
    }
}
