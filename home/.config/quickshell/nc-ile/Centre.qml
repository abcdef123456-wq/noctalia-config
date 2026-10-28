// Centre de contrôle de l'île (île ouverte), dans le langage du Centre de contrôle d'iOS.
// Appui long (ou clic droit) sur Wi-Fi, Bluetooth ou le volume : page de détails.
// Modules : connexions, musique, nuit, jeu, luminosité, volume, énergie. Le crayon (en haut à droite) ouvre le mode
// édition : œil pour masquer ou remontrer un module, flèches pour le monter ou le descendre, « Réinitialiser »,
// « Terminer » ; au moins un module reste visible. Clavier en édition : ↑ ↓ choisir, Maj + ↑ ↓ déplacer, Espace ou
// Entrée masquer / montrer, Échap terminer. L'ordre et les modules masqués sont gardés (Memo « centre ») ; la
// disposition de départ est celle d'avant : les modules se rangent en lignes de 168 points (deux pastilles s'empilent,
// les glissières se partagent le reste), l'énergie en bandeau.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Widgets
import Quickshell.Services.UPower

Item {
    id: centre
    readonly property color bleu: Couleurs.accent
    readonly property color orange: Couleurs.orange
    readonly property color indigo: Couleurs.violet
    readonly property color rose: Couleurs.rose
    readonly property color vert: Couleurs.vert
    readonly property var s: Etat.sys

    // ── Disposition ──
    // forme : grand (168 x 168), flex (le reste de la ligne, 88 au moins : dans l'île la page fait 378 points et les deux
    // glissières y ont 93 points chacune, comme avant ; maxi : pas plus large que ça, une glissière seule reste étroite),
    // petit (168 x 78, deux s'empilent), bande (toute la largeur, 64)
    readonly property var modules: ({
        connexions: { nom: Reglages.t("Connexions", "Connections"), icone: "wifi", forme: "grand" },
        musique: { nom: Reglages.t("Musique", "Music"), icone: "music_note", forme: "flex" },
        nuit: { nom: Reglages.t("Nuit", "Night Shift"), icone: "wb_twilight", forme: "petit" },
        jeu: { nom: Reglages.t("Mode jeu", "Game Mode"), icone: "sports_esports", forme: "petit" },
        luminosite: { nom: Reglages.t("Luminosité", "Brightness"), icone: "light_mode", forme: "flex", maxi: 168 },
        volume: { nom: "Volume", icone: "volume_up", forme: "flex", maxi: 168 },
        energie: { nom: Reglages.t("Énergie", "Power"), icone: "bolt", forme: "bande" },
        ia: { nom: Reglages.t("IA", "AI"), icone: "auto_awesome", forme: "petit" }
    })
    readonly property var defaut: ["connexions", "musique", "nuit", "jeu", "luminosite", "volume", "energie", "ia"]
    property var ordre: defaut
    property var masques: []
    readonly property var visibles: ordre.filter(id => masques.indexOf(id) < 0)
    property bool edition: false
    property int choix: 0                        // module choisi au clavier, en édition
    property bool pret: false                    // disposition gardée relue
    readonly property int ecart: 12

    // Range les modules visibles en lignes : { id, x, y, w, h }
    function calculer(ids, largeur) {
        var res = [], y = 0, ligne = [], fixe = 0, nflex = 0
        function fermer() {
            if (!ligne.length) return
            var reste = Math.max(0, largeur - fixe - centre.ecart * (ligne.length - 1))
            var x = 0, haut = 168, seulPetit = ligne.length === 1 && ligne[0].forme === "petit" && ligne[0].ids.length === 1
            if (seulPetit) haut = 78
            for (let i = 0; i < ligne.length; i++) {
                let c = ligne[i], w = c.forme === "flex" ? Math.min(c.maxi || reste, Math.floor(reste / nflex)) : 168
                if (c.forme === "petit") {
                    for (let k = 0; k < c.ids.length; k++) res.push({ id: c.ids[k], x: x, y: y + k * (78 + centre.ecart), w: 168, h: 78 })
                } else res.push({ id: c.ids[0], x: x, y: y, w: w, h: 168 })
                x += w + centre.ecart
            }
            y += haut + centre.ecart
            ligne = []; fixe = 0; nflex = 0
        }
        for (let i = 0; i < ids.length; i++) {
            let id = ids[i], forme = centre.modules[id].forme
            if (forme === "bande") {
                fermer()
                res.push({ id: id, x: 0, y: y, w: largeur, h: 64 })
                y += 64 + centre.ecart
                continue
            }
            let libre = largeur - fixe - nflex * 88 - centre.ecart * ligne.length
            if (forme === "petit") {
                // Deux pastilles de suite s'empilent dans la même case (cellule remplacée, pas modifiée en place)
                let derniere = ligne.length ? ligne[ligne.length - 1] : null
                if (derniere && derniere.forme === "petit" && derniere.ids.length === 1) { ligne[ligne.length - 1] = { forme: "petit", ids: [derniere.ids[0], id] }; continue }
                if (libre < 168) fermer()
                ligne.push({ forme: "petit", ids: [id] }); fixe += 168
            } else if (forme === "grand") {
                if (libre < 168) fermer()
                ligne.push({ forme: "grand", ids: [id] }); fixe += 168
            } else {
                if (libre < 88) fermer()
                ligne.push({ forme: "flex", ids: [id], maxi: centre.modules[id].maxi || 0 }); nflex++
            }
        }
        fermer()
        return { cases: res, hauteur: Math.max(0, y - centre.ecart) }
    }
    readonly property var disposition: calculer(visibles, width)
    readonly property real hauteurVoulue: 22 + ecart + disposition.hauteur + (edition ? ecart + outils.height : 0)
    onHauteurVoulueChanged: Etat.annoncerHauteur("centre", hauteurVoulue)
    Component.onCompleted: {
        Etat.annoncerHauteur("centre", hauteurVoulue)
        Memo.lire("centre", v => {
            if (!centre) return              // page déjà détruite (l'île a changé de page avant la relecture)
            if (v && Array.isArray(v.ordre)) {
                let o = v.ordre.filter(id => centre.modules[id] !== undefined)
                centre.defaut.forEach(id => { if (o.indexOf(id) < 0) o.push(id) })
                centre.ordre = o
            }
            if (v && Array.isArray(v.masques)) centre.masques = v.masques.filter(id => centre.modules[id] !== undefined && centre.ordre.indexOf(id) >= 0)
            if (centre.visibles.length === 0) centre.masques = []
            centre.pret = true
        })
    }
    function garder() { Memo.ecrire("centre", { ordre: ordre, masques: masques }) }
    function basculer(id) {
        if (masques.indexOf(id) >= 0) masques = masques.filter(x => x !== id)
        else if (visibles.length > 1) masques = masques.concat([id])
        garder()
    }
    function deplacer(id, sens) {
        var o = ordre.slice(), i = o.indexOf(id), j = i + sens
        if (i < 0 || j < 0 || j >= o.length) return
        o.splice(i, 1); o.splice(j, 0, id); ordre = o
        choix = Math.max(0, visibles.indexOf(id))
        garder()
    }
    function reinitialiser() { ordre = defaut; masques = []; choix = 0; garder() }
    function editer(oui) {
        edition = oui
        if (oui) { choix = 0; forceActiveFocus() }
    }
    function terminer() { editer(false) }
    onVisibleChanged: if (!visible) edition = false

    // Clavier en édition
    Keys.onPressed: e => {
        if (!edition) return
        var id = visibles[choix]
        if (e.key === Qt.Key_Escape) { terminer(); e.accepted = true }
        else if (e.key === Qt.Key_Down && (e.modifiers & Qt.ShiftModifier)) { if (id) deplacer(id, 1); e.accepted = true }
        else if (e.key === Qt.Key_Up && (e.modifiers & Qt.ShiftModifier)) { if (id) deplacer(id, -1); e.accepted = true }
        else if (e.key === Qt.Key_Down) { choix = Math.min(visibles.length - 1, choix + 1); e.accepted = true }
        else if (e.key === Qt.Key_Up) { choix = Math.max(0, choix - 1); e.accepted = true }
        else if (e.key === Qt.Key_Space || e.key === Qt.Key_Return || e.key === Qt.Key_Enter) { if (id) basculer(id); e.accepted = true }
    }

    // ── En-tête : date, batterie, assistant, crayon ──
    Item {
        id: tete
        width: parent.width; height: 22
        Texte { anchors.left: parent.left; anchors.leftMargin: 6; text: centre.edition ? Reglages.t("Modifier les modules", "Edit modules") : Etat.dateLongue; secondaire: true; font.weight: Font.DemiBold }
        Row {
            anchors.right: parent.right; anchors.rightMargin: 6; spacing: 5
            Texte { visible: Etat.aBatterie && !centre.edition; text: Etat.pourcent + Reglages.t(" %", "%"); font.weight: Font.DemiBold }
            Ico {
                visible: Etat.aBatterie && !centre.edition
                nom: Etat.branche ? "battery_charging_full" : (Etat.pourcent > 80 ? "battery_full" : (Etat.pourcent > 30 ? "battery_5_bar" : "battery_2_bar"))
                taille: 18; color: Etat.branche ? centre.vert : (Etat.pourcent <= 20 ? Couleurs.rouge : Couleurs.texte)
                rotation: 90
            }
            Ico {
                visible: !centre.edition
                nom: "chat"; taille: 20; color: Couleurs.accent
                MouseArea { anchors.fill: parent; anchors.margins: -5; onClicked: Etat.aller("assistant") }
                Accessible.role: Accessible.Button
                Accessible.name: Reglages.t("Ouvrir l’assistant", "Open assistant")
                Accessible.onPressAction: Etat.aller("assistant")
            }
            Ico {
                objectName: "nc-centre-crayon"
                nom: centre.edition ? "check" : "edit"; taille: 20; color: centre.edition ? centre.vert : Couleurs.texteSec
                MouseArea { anchors.fill: parent; anchors.margins: -5; onClicked: centre.editer(!centre.edition) }
                Accessible.role: Accessible.Button
                Accessible.name: centre.edition ? Reglages.t("Terminer", "Done") : Reglages.t("Modifier les modules (masquer, réordonner)", "Edit modules (hide, reorder)")
                Accessible.onPressAction: centre.editer(!centre.edition)
            }
        }
    }

    // ── Modules, placés par la disposition ──
    Item {
        id: zone
        anchors.top: tete.bottom; anchors.topMargin: centre.ecart
        width: parent.width; height: centre.disposition.hauteur
        Repeater {
            model: centre.disposition.cases
            Item {
                id: case_
                required property var modelData
                readonly property string identifiant: modelData.id
                readonly property bool choisi: centre.edition && centre.visibles[centre.choix] === identifiant
                objectName: "nc-centre-" + identifiant
                x: modelData.x; y: modelData.y; width: modelData.w; height: modelData.h
                Behavior on x { enabled: centre.pret; NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                Behavior on y { enabled: centre.pret; NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                Loader {
                    anchors.fill: parent
                    sourceComponent: ({ connexions: cConnexions, musique: cMusique, nuit: cNuit, jeu: cJeu, luminosite: cLuminosite, volume: cVolume, energie: cEnergie, ia: cIA })[case_.identifiant]
                }
                // Mode édition : voile, nom, œil et flèches ; le module en dessous ne réagit plus
                Rectangle {
                    anchors.fill: parent; radius: 18
                    visible: centre.edition
                    color: Qt.rgba(0, 0, 0, 0.62)
                    border.width: case_.choisi ? 2 : 0; border.color: Couleurs.accent
                    MouseArea { anchors.fill: parent; onClicked: centre.choix = centre.visibles.indexOf(case_.identifiant) }
                    // Le nom du module, dans une petite pastille lisible par-dessus le contenu voilé
                    Rectangle {
                        anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 8
                        width: nomModule.implicitWidth + 16; height: 22; radius: 11; color: Couleurs.gris3
                        visible: parent.width >= 150
                        Texte { id: nomModule; anchors.centerIn: parent; text: centre.modules[case_.identifiant].nom; font.pixelSize: 12; font.weight: Font.DemiBold }
                    }
                    Row {
                        anchors.centerIn: parent; spacing: 4
                        Repeater {
                            model: [
                                { id: "monter", icone: "keyboard_arrow_up", aide: Reglages.t("Monter", "Move up"), ok: centre.ordre.indexOf(case_.identifiant) > 0 },
                                { id: "masquer", icone: "visibility_off", aide: Reglages.t("Masquer", "Hide"), ok: centre.visibles.length > 1 },
                                { id: "descendre", icone: "keyboard_arrow_down", aide: Reglages.t("Descendre", "Move down"), ok: centre.ordre.indexOf(case_.identifiant) < centre.ordre.length - 1 }
                            ]
                            Rectangle {
                                id: bouton
                                required property var modelData
                                objectName: "nc-centre-" + case_.identifiant + "-" + modelData.id
                                width: 30; height: 30; radius: 15
                                color: zb.containsMouse ? Couleurs.gris4 : Couleurs.gris3
                                opacity: modelData.ok ? 1 : 0.35
                                Ico { anchors.centerIn: parent; nom: bouton.modelData.icone; taille: 18 }
                                MouseArea {
                                    id: zb; anchors.fill: parent; hoverEnabled: true; enabled: bouton.modelData.ok
                                    onClicked: {
                                        centre.choix = centre.visibles.indexOf(case_.identifiant)
                                        if (bouton.modelData.id === "masquer") centre.basculer(case_.identifiant)
                                        else centre.deplacer(case_.identifiant, bouton.modelData.id === "monter" ? -1 : 1)
                                    }
                                    onContainsMouseChanged: centre.aide = containsMouse ? bouton.modelData.aide : ""
                                }
                                Accessible.role: Accessible.Button
                                Accessible.name: bouton.modelData.aide + " : " + centre.modules[case_.identifiant].nom
                            }
                        }
                    }
                }
            }
        }
    }
    property string aide: ""                 // infobulle du bouton survolé, en édition

    // ── Outils du mode édition : masqués, infobulle, Réinitialiser, Terminer ──
    Column {
        id: outils
        anchors.top: zone.bottom; anchors.topMargin: centre.ecart
        width: parent.width; spacing: 8
        visible: centre.edition
        Flow {
            width: parent.width; spacing: 6
            visible: centre.masques.length > 0
            Texte { text: Reglages.t("Masqués :", "Hidden:"); secondaire: true; font.pixelSize: 12; height: 28; verticalAlignment: Text.AlignVCenter }
            Repeater {
                model: centre.masques
                Rectangle {
                    id: masque
                    required property string modelData
                    objectName: "nc-centre-masque-" + modelData
                    width: lm.implicitWidth + 44; height: 28; radius: 14; color: zm.containsMouse ? Couleurs.gris3 : Couleurs.gris2
                    Ico { x: 10; anchors.verticalCenter: parent.verticalCenter; nom: centre.modules[masque.modelData].icone; taille: 15; color: Couleurs.texteSec }
                    Texte { id: lm; x: 30; anchors.verticalCenter: parent.verticalCenter; text: centre.modules[masque.modelData].nom; font.pixelSize: 12 }
                    MouseArea {
                        id: zm; anchors.fill: parent; hoverEnabled: true
                        onClicked: centre.basculer(masque.modelData)
                        onContainsMouseChanged: centre.aide = containsMouse ? Reglages.t("Montrer ", "Show ") + centre.modules[masque.modelData].nom : ""
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: Reglages.t("Montrer ", "Show ") + centre.modules[masque.modelData].nom
                }
            }
        }
        Item {
            width: parent.width; height: 32
            Texte { anchors.left: parent.left; anchors.leftMargin: 6; anchors.verticalCenter: parent.verticalCenter; text: centre.aide; secondaire: true; font.pixelSize: 12 }
            Row {
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                Repeater {
                    model: [{ id: "reinitialiser", texte: Reglages.t("Réinitialiser", "Reset"), accent: false },
                            { id: "terminer", texte: Reglages.t("Terminer", "Done"), accent: true }]
                    Rectangle {
                        id: action
                        required property var modelData
                        objectName: "nc-centre-" + modelData.id
                        width: la.implicitWidth + 28; height: 32; radius: 16
                        color: modelData.accent ? Couleurs.accent : (za.containsMouse ? Couleurs.gris3 : Couleurs.gris2)
                        Texte { id: la; anchors.centerIn: parent; text: action.modelData.texte; font.weight: Font.DemiBold; font.pixelSize: 13; color: action.modelData.accent ? Couleurs.surAccent : Couleurs.texte }
                        MouseArea { id: za; anchors.fill: parent; hoverEnabled: true; onClicked: action.modelData.id === "terminer" ? centre.terminer() : centre.reinitialiser() }
                        Accessible.role: Accessible.Button
                        Accessible.name: action.modelData.texte
                    }
                }
            }
        }
    }

    // ── Les modules eux-mêmes ──
    // Connexions façon macOS : rond (activer / couper) + nom et état (clic : liste des réseaux / appareils)
    Component {
        id: cConnexions
        Module {
            Column {
                anchors.fill: parent; anchors.margins: 12; spacing: 8
                Repeater {
                    model: [
                        { cle: "wifi", icone: "wifi", nom: "Wi-Fi", page: "reseau" },
                        { cle: "bluetooth", icone: "bluetooth", nom: "Bluetooth", page: "bluetooth" },
                        { cle: "dnd", icone: "dark_mode", nom: Reglages.t("Concentration", "Focus"), page: "notifications" }
                    ]
                    Item {
                        id: lc
                        required property var modelData
                        readonly property bool actif: modelData.cle === "dnd" ? Notifs.concentration : Etat.valeur(modelData.cle, centre.s[modelData.cle]) === "on"
                        readonly property string etat: modelData.cle === "wifi" ? (actif ? (centre.s.reseau || Reglages.t("Activé", "On")) : Reglages.t("Désactivé", "Off"))
                                                    : modelData.cle === "dnd" ? (actif ? Reglages.t("Ne pas déranger", "Do Not Disturb") : Reglages.t("Désactivée", "Off"))
                                                    : (actif ? Reglages.t("Activé", "On") : Reglages.t("Désactivé", "Off"))
                        width: parent.width; height: 41
                        Rectangle {
                            anchors.fill: parent; anchors.leftMargin: -6; anchors.rightMargin: -6; radius: 12
                            color: zl.containsMouse && lc.modelData.page !== "" ? Couleurs.gris2 : "transparent"
                            Behavior on color { ColorAnimation { duration: 120 } }
                        }
                        Rond {
                            id: rl
                            anchors.verticalCenter: parent.verticalCenter
                            taille: 36; icone: lc.modelData.icone; actif: lc.actif
                            couleur: lc.modelData.cle === "dnd" ? centre.indigo : centre.bleu
                            onAppuiLong: if (lc.modelData.cle === "dnd" && Modes.reglage) Modes.ouvrirPage()
                            onClic: lc.modelData.cle === "dnd" ? Notifs.basculerConcentration() : Etat.inverser(lc.modelData.cle, ["noctalia", "msg", lc.modelData.cle + "-toggle"])
                        }
                        Column {
                            anchors.left: rl.right; anchors.leftMargin: 9; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                            Texte { text: lc.modelData.nom; font.weight: Font.DemiBold; font.pixelSize: 13; width: parent.width }
                            Texte { text: lc.etat; secondaire: true; font.pixelSize: 11; width: parent.width }
                        }
                        MouseArea {
                            id: zl
                            anchors.fill: parent; anchors.leftMargin: 40
                            hoverEnabled: true
                            onPressAndHold: if (lc.modelData.cle === "dnd" && Modes.reglage) Modes.ouvrirPage()
                            onClicked: lc.modelData.page !== "" ? Etat.aller(lc.modelData.page) : rl.clic()
                        }
                    }
                }
            }
        }
    }
    Component {
        id: cMusique
        Module {
            Column {
                anchors.fill: parent; anchors.margins: 14; spacing: 10
                Row {
                    spacing: 10; width: parent.width
                    ClippingRectangle {
                        width: 54; height: 54; radius: 12; color: Couleurs.gris2
                        Image { anchors.fill: parent; source: Etat.pochette; fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize: Qt.size(144, 144) }
                        Image { anchors.centerIn: parent; width: 34; height: 34; source: Etat.pochette === "" ? Etat.iconeLecteur : ""; sourceSize: Qt.size(68, 68); visible: Etat.pochette === "" }
                        Ico { anchors.centerIn: parent; nom: "music_note"; taille: 26; color: Couleurs.texteSec; visible: Etat.pochette === "" && Etat.iconeLecteur === "" }
                    }
                    Column {
                        width: parent.width - 64; spacing: 2
                        anchors.verticalCenter: parent.verticalCenter
                        Texte { width: parent.width; text: Etat.titre !== "" ? Etat.titre : Reglages.t("Rien en lecture", "Not Playing"); font.weight: Font.DemiBold; font.pixelSize: 14 }
                        Texte { width: parent.width; text: Etat.artiste !== "" ? Etat.artiste : (Etat.lecteur ? Etat.lecteur.identity : Reglages.t("Lance une musique", "Play some music")); secondaire: true }
                    }
                }
                // Progression
                Rectangle {
                    width: parent.width; height: 4; radius: 2; color: Couleurs.gris3
                    Rectangle {
                        height: parent.height; radius: 2; color: Couleurs.texte
                        width: Etat.lecteur && Etat.lecteur.length > 0 ? parent.width * Math.min(1, Etat.lecteur.position / Etat.lecteur.length) : 0
                    }
                }
                // Commandes
                Row {
                    anchors.horizontalCenter: parent.horizontalCenter; spacing: 26
                    component Commande: Ico {
                        id: cmd
                        signal clic()
                        color: Etat.lecteur ? Couleurs.texte : Couleurs.gris4
                        scale: zoneClic.pressed ? 0.85 : 1
                        Behavior on scale { SpringAnimation { spring: 6; damping: 0.4 } }
                        MouseArea { id: zoneClic; anchors.fill: parent; anchors.margins: -8; onClicked: cmd.clic() }
                    }
                    Commande { nom: "fast_rewind"; taille: 30; onClic: if (Etat.lecteur) Etat.lecteur.previous() }
                    Commande { nom: Etat.joue ? "pause" : "play_arrow"; taille: 38; onClic: Etat.lecturePause() }
                    Commande { nom: "fast_forward"; taille: 30; onClic: if (Etat.lecteur) Etat.lecteur.next() }
                }
            }
        }
    }
    component Pastille: Module {
        id: pa
        property string icone
        property string titre
        property string sous
        property bool actif
        property color couleur
        cliquable: true
        Row {
            anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 12; spacing: 10
            Rectangle {
                width: 40; height: 40; radius: 20; color: pa.actif ? pa.couleur : Couleurs.gris3
                Behavior on color { ColorAnimation { duration: 160 } }
                Ico { anchors.centerIn: parent; nom: pa.icone; taille: 21; color: pa.actif ? Couleurs.surCouleur : Couleurs.texte }
            }
            Column {
                anchors.verticalCenter: parent.verticalCenter
                Texte { text: pa.titre; font.weight: Font.DemiBold }
                Texte { text: pa.sous; secondaire: true; font.pixelSize: 11 }
            }
        }
    }
    Component {
        id: cNuit
        Pastille {
            icone: "wb_twilight"; titre: Reglages.t("Nuit", "Night Shift"); sous: Etat.nuit ? Reglages.t("Tons chauds", "Warmer colors") : Reglages.t("Désactivée", "Off"); actif: Etat.nuit; couleur: centre.orange
            onClic: { Etat.nuit = !Etat.nuit; Etat.faire(["noctalia", "msg", "nightlight-force-toggle"]) }
        }
    }
    // IA du bureau (nc-ia) : clic, coupée partout ou rallumée (le mode d'avant, automatique ou choisi, revient) ;
    // en dessous, celle qui répond
    Component {
        id: cIA
        Pastille {
            id: pIA
            property string qui: ""
            // Hors ligne : seule une IA de ce PC (Ollama) reste ; relu quand la connexion change
            readonly property bool enLigne: Connexion.enLigne
            onEnLigneChanged: lireQui.running = true
            icone: "auto_awesome"; titre: Reglages.t("IA", "AI"); actif: !Reglages.iaCoupee; couleur: Couleurs.violet
            sous: Reglages.iaCoupee ? Reglages.t("Coupée partout", "Off everywhere")
                  : (qui || (enLigne ? Reglages.t("Aucune disponible", "None available") : Reglages.t("Hors ligne", "Offline")))
            Process {
                id: lireQui
                running: true
                command: [Quickshell.env("HOME") + "/.local/bin/nc-ia", "quelle", "--json"]
                stdout: StdioCollector { onStreamFinished: { try { pIA.qui = JSON.parse(text).nom || "" } catch (e) {} } }
            }
            Connections { target: Reglages; function onIaCoupeeChanged() { if (!Reglages.iaCoupee) lireQui.running = true } }
            onClic: {
                var bin = Quickshell.env("HOME") + "/.local/bin/nc-reglages"
                if (Reglages.iaCoupee) Memo.lire("ia-avant", v => Etat.faire([bin, "set", "IA_MODE", v && (v.mode === "manuel" || v.mode === "auto") ? v.mode : "auto"]))
                else { Memo.ecrire("ia-avant", { mode: Reglages.val("IA_MODE", "auto") }); Etat.faire([bin, "set", "IA_MODE", "non"]) }
            }
        }
    }
    Component {
        id: cJeu
        Pastille {
            icone: "sports_esports"; titre: Reglages.t("Mode jeu", "Game Mode"); sous: Etat.jeu ? Reglages.t("Effets coupés", "Effects off") : Reglages.t("Désactivé", "Off"); actif: Etat.jeu; couleur: centre.orange
            onClic: Etat.faire(["hyprctl", "eval", "nc.mode_jeu()"])
        }
    }
    Component {
        id: cLuminosite
        Glissiere {
            icone: "light_mode"; valeur: Etat.luminosite
            onChange: v => Etat.reglerLuminosite(v)
        }
    }
    Component {
        id: cVolume
        Glissiere {
            icone: Etat.muet ? "volume_off" : (Etat.volume < 0.34 ? "volume_mute" : (Etat.volume < 0.67 ? "volume_down" : "volume_up"))
            valeur: Etat.muet ? 0 : Etat.volume
            onChange: v => Etat.reglerVolume(v)
            onAppuiLong: Etat.aller("son")
        }
    }
    // Énergie : module façon macOS. Clic : mode suivant ; flèche, appui long ou clic droit : liste des modes
    Component {
        id: cEnergie
        Module {
            id: energie
            readonly property var modes: [
                { nom: Reglages.t("Économie", "Power saver"), icone: "battery_saver", couleur: Couleurs.jaune, texte: Couleurs.surCouleur, p: PowerProfile.PowerSaver },
                { nom: Reglages.t("Équilibré", "Balanced"), icone: "battery_full", couleur: Couleurs.gris3, texte: Couleurs.texte, p: PowerProfile.Balanced },
                { nom: "Performance", icone: "bolt", couleur: Couleurs.orange, texte: Couleurs.surCouleur, p: PowerProfile.Performance }
            ]
            readonly property int index: Etat.profil === PowerProfile.PowerSaver ? 0 : (Etat.profil === PowerProfile.Performance ? 2 : 1)
            readonly property var mode: modes[index]
            cliquable: true
            onClic: Etat.choisirProfil(modes[(index + 1) % 3].p)
            onAppuiLong: Etat.aller("systeme")
            Row {
                anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 12; spacing: 12
                Rectangle {
                    width: 40; height: 40; radius: 20; color: energie.mode.couleur
                    Behavior on color { ColorAnimation { duration: 200 } }
                    Ico { anchors.centerIn: parent; nom: energie.mode.icone; taille: 22; color: energie.mode.texte; rotation: energie.mode.icone === "bolt" ? 0 : 90 }
                }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    Texte { text: Reglages.t("Énergie", "Power"); font.weight: Font.DemiBold; font.pixelSize: 14 }
                    Texte { text: energie.mode.nom; secondaire: true }
                }
            }
            Ico {
                anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter
                nom: "chevron_right"; taille: 24; color: Couleurs.texteSec
                MouseArea { anchors.fill: parent; anchors.margins: -10; onClicked: Etat.aller("systeme") }
            }
        }
    }
}
