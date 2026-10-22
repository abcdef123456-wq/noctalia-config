// Fiche des raccourcis (Super + /), éditable sur place : la même fiche que celle de Noctalia (sections de nc-keys, trois
// ou quatre colonnes selon la place), en verre aux couleurs du bureau. « Modifier » passe en mode édition, comme le
// Centre de contrôle de l'iPhone : − désactive un raccourci de la config (ou retire l'un des tiens), un toucher sur
// les touches attend la nouvelle combinaison, le nom de l'un des tiens se renomme, ↺ remet celui de la config,
// « + Ajouter » crée un raccourci (une appli, « bureau N », « ile PAGE » ou une commande). Toute l'édition passe par
// Raccourcis.qml, comme la page « Raccourcis » des réglages.
// Verre : flou de Hyprland derrière (règle de calque nc-fiche, regles.lua), fond de la palette à 80 % (le texte reste lisible même sur un fond d'écran
// blanc) ; sans flou (Économie, flou coupé) : 92 %. Clavier : Échap annule la capture, quitte l'édition, ferme.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

PanelWindow {
    id: fiche
    signal fermer()
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "nc-fiche"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    color: "transparent"

    property bool edition: false
    property var lignes: []                         // les raccourcis du catalogue de nc-reglages
    property var tentative: null                    // dernière capture envoyée : pour « Remplacer » si les touches sont prises
    property var conflit: null
    property bool ajout: false                      // la petite carte « + Ajouter » est ouverte
    property var applis: []                         // pour les suggestions de « + Ajouter » (nc-apps list, lu à l'ouverture)
    onAjoutChanged: if (ajout && !applis.length && !lectureApplis.running) lectureApplis.running = true
    Process {
        id: lectureApplis
        command: [Raccourcis.bin + "nc-apps", "list"]
        stdout: StdioCollector { onStreamFinished: { try { fiche.applis = JSON.parse(text) } catch (e) { fiche.applis = [] } } }
    }
    // Les applis dont le nom ou l'identifiant contient ce qui est tapé (6 au plus)
    function suggestions(t) {
        t = String(t || "").trim().toLowerCase()
        if (t.length < 2 || /^(bureau|desktop|ile|île|island)\b/.test(t)) return []
        return applis.filter(a => String(a.name || "").toLowerCase().indexOf(t) >= 0 || String(a.id || "").toLowerCase().indexOf(t) >= 0).slice(0, 6)
    }
    readonly property bool verre: Reglages.val("FENETRES_FLOU", "oui") !== "non" && !Reglages.sobre
    readonly property real opaciteFond: verre ? 0.8 : 0.92
    readonly property real largeurEcran: fiche.screen ? fiche.screen.width : 1600
    readonly property real hauteurEcran: fiche.screen ? fiche.screen.height : 1000

    // ── Les raccourcis ──
    Process {
        id: lecture
        command: [Raccourcis.bin + "nc-reglages", "catalogue"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try { fiche.lignes = JSON.parse(text).filter(r => r.genre === "raccourci") } catch (e) { fiche.lignes = [] }
            }
        }
    }
    function relire() { if (!lecture.running) lecture.running = true }
    Connections {
        target: Raccourcis
        function onEcrit() {
            if (Raccourcis.erreur && fiche.tentative && /déjà pris|already in use/i.test(Raccourcis.message)) fiche.conflit = fiche.tentative
            fiche.tentative = null
            fiche.relire()
        }
        function onCaptureFinie() { zoneClavier.forceActiveFocus() }
    }
    function section(r) { return r.mien !== "" ? "Mes raccourcis" : (r.aide || "Système") }
    readonly property var parSection: {
        var s = {}
        lignes.forEach(r => {
            if (r.desactive && !edition) return     // hors édition : seulement ceux qui marchent
            var n = section(r); (s[n] = s[n] || []).push(r)
        })
        if (edition && !s["Mes raccourcis"]) s["Mes raccourcis"] = []
        return s
    }
    readonly property var titres: ({ "Applis et barre": "Apps & Bar", "Fenêtres": "Windows", "Bureaux": "Desktops",
                                     "Souris": "Mouse", "Système": "System", "IA": "AI", "Mes raccourcis": "My Shortcuts" })
    function touches(r) { return String(r.valeur || "").split(/\s*\+\s*/).filter(t => t !== "") }
    function norm(t) { return String(t).replace(/\s+/g, "").toLowerCase() }

    // ── Disposition : trois colonnes, ou quatre plus étroites si elles ne tiennent pas (écran d'au moins 1400 points),
    // puis réduites s'il le faut (jamais sous 0,55), comme la fiche de Noctalia (revue de l'issue #1) ──
    readonly property var colonnes3: [["Applis et barre", "Bureaux"], ["Fenêtres", "Souris"], ["Système", "IA", "Mes raccourcis"]]
    readonly property var colonnes4: [["Applis et barre", "Bureaux"], ["Fenêtres"], ["Système", "Mes raccourcis"], ["IA", "Souris"]]
    readonly property real dispo: hauteurEcran - 120
    function largeurTouches(r) {
        var l = 0
        touches(r).forEach((k, i) => { l += (i > 0 ? 17 : 0) + k.length * 7.4 + 16 })
        return l
    }
    function hauteurColonne(noms, largeur) {
        var h = 0
        noms.forEach(n => {
            var rs = parSection[n]
            if (!rs || (!rs.length && !(edition && n === "Mes raccourcis"))) return
            if (h > 0) h += 22
            h += 34
            var kw = Math.min(largeur < 400 ? 150 : 220, Math.max(60, ...rs.map(largeurTouches)))
            rs.forEach(r => { h += largeurTouches(r) > kw || r.nom.length * 7.3 > largeur - kw - 14 - (edition ? 30 : 0) ? 48 : 30 })
            if (edition && n === "Mes raccourcis") h += 34
        })
        return h
    }
    readonly property bool quatre: {
        var h3 = Math.max(...colonnes3.map(c => hauteurColonne(c, 490)))
        return h3 > dispo && largeurEcran >= 1400
    }
    readonly property var colonnes: quatre ? colonnes4 : colonnes3
    readonly property real largeurColonne: quatre ? Math.min(490, Math.floor((largeurEcran - 64 - 60) / 4)) : 490
    readonly property real hauteurMax: Math.max(...colonnes.map(c => hauteurColonne(c, largeurColonne)))
    readonly property real zoom: Math.max(0.55, Math.min(1, largeurEcran / 1600, dispo / Math.max(1, hauteurMax + 90)))

    // ── Fermer, quitter l'édition ; une capture interrompue rend TOUJOURS ses raccourcis à Hyprland ──
    function quitter() {
        if (Raccourcis.capture) Raccourcis.finCapture("")
        fiche.fermer()
    }
    Component.onDestruction: if (Raccourcis.capture) Raccourcis.finCapture("")
    onVisibleChanged: if (!visible && Raccourcis.capture) Raccourcis.finCapture("")

    MouseArea { anchors.fill: parent; onClicked: fiche.quitter() }          // un clic à côté ferme

    FocusScope {
        id: zoneClavier
        anchors.fill: parent
        focus: true
        Component.onCompleted: forceActiveFocus()
        Keys.onPressed: event => {
            if (Raccourcis.capture) {
                var t = Raccourcis.combinaison(event)
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
        anchors.centerIn: parent
        width: contenu.width + 64; height: contenu.height + 90
        scale: fiche.zoom
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
            anchors.fill: parent; radius: 28
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
            x: 32; y: 24; font.pixelSize: 18; font.weight: Font.Bold
            text: fiche.edition ? Reglages.t("Modifier les raccourcis", "Edit shortcuts") : Reglages.t("Raccourcis", "Shortcuts")
        }
        // « Modifier » / « OK »
        Rectangle {
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

        Row {
            id: contenu
            x: 32; y: 66
            spacing: fiche.quatre ? 20 : 24
            Repeater {
                model: fiche.colonnes
                Column {
                    id: colonne
                    required property var modelData
                    width: fiche.largeurColonne
                    spacing: 0
                    Repeater {
                        model: colonne.modelData
                        Column {
                            id: bloc
                            required property string modelData
                            required property int index
                            readonly property var rangees: fiche.parSection[modelData] || []
                            readonly property real kw: Math.min(fiche.quatre ? 150 : 220, Math.max(60, ...rangees.map(fiche.largeurTouches)))
                            visible: rangees.length > 0 || (fiche.edition && modelData === "Mes raccourcis")
                            width: colonne.width
                            Item { width: 1; height: bloc.index > 0 ? 22 : 0 }
                            Texte {
                                height: 34; color: Couleurs.accent; font.pixelSize: 14; font.weight: Font.Bold
                                text: Reglages.en ? (fiche.titres[bloc.modelData] || bloc.modelData) : bloc.modelData
                            }
                            Repeater {
                                model: bloc.rangees
                                Ligne { required property var modelData; r: modelData; kw: bloc.kw; largeur: colonne.width }
                            }
                            // « + Ajouter », à la fin de « Mes raccourcis »
                            Item {
                                visible: fiche.edition && bloc.modelData === "Mes raccourcis"
                                width: colonne.width; height: visible ? 34 : 0
                                Row {
                                    anchors.verticalCenter: parent.verticalCenter; spacing: 8
                                    Rectangle { width: 22; height: 22; radius: 11; color: Couleurs.vert
                                                Texte { anchors.centerIn: parent; text: "+"; font.pixelSize: 16; font.weight: Font.Bold; color: "#ffffff" } }
                                    Texte { text: Reglages.t("Ajouter un raccourci", "Add a shortcut"); color: Couleurs.vert }
                                }
                                MouseArea { objectName: "nc-fiche-ajouter"; anchors.fill: parent; onClicked: { fiche.ajout = true; champCible.forceActiveFocus() } }
                            }
                        }
                    }
                }
            }
        }

        // Message : résultat d'une écriture, ou combinaison déjà prise avec « Remplacer »
        Row {
            anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 18
            spacing: 10
            visible: Raccourcis.message !== "" && fiche.edition
            Texte {
                anchors.verticalCenter: parent.verticalCenter
                text: Raccourcis.message; color: Raccourcis.erreur ? Couleurs.rouge : Couleurs.texteSec; font.pixelSize: 12
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
        var autre = lignes.find(x => !x.desactive && norm(x.valeur) === norm(c.touches) && x !== c.r && x.cle !== (c.r && c.r.cle))
        if (autre) Raccourcis.supprimer(autre)
        tentative = c
        if (c.r && c.r.ajout) Raccourcis.ajouter(c.touches, c.r.ajout.cible, c.r.ajout.nom)
        else Raccourcis.raccourci(c.r, "changer", c.touches)
    }

    // ── Une ligne : touches, puis description ; en édition : −, touches à changer, nom à renommer, ↺ ──
    component Ligne: Item {
        id: ligne
        property var r
        property real kw: 220
        property real largeur: 490
        readonly property bool mien: r.mien !== ""
        readonly property bool longues: fiche.largeurTouches(r) > kw
        readonly property real placeTexte: largeur - kw - 14 - (fiche.edition ? 30 : 0)
        width: largeur
        height: longues || r.nom.length * 7.3 > placeTexte ? 48 : 30
        opacity: r.desactive ? 0.45 : 1
        transformOrigin: Item.Center
        // Frétillement des lignes en édition, comme sur l'iPhone (pas en Économie ni sans effets)
        SequentialAnimation {
            running: fiche.edition && !Reglages.sobre && ligne.visible; loops: Animation.Infinite
            onRunningChanged: if (!running) ligne.rotation = 0
            RotationAnimator { target: ligne; from: -0.6; to: 0.6; duration: 140 }
            RotationAnimator { target: ligne; from: 0.6; to: -0.6; duration: 140 }
        }
        // − (ou ↺ pour un désactivé)
        Rectangle {
            id: moins
            visible: fiche.edition
            anchors.verticalCenter: parent.verticalCenter
            width: 22; height: 22; radius: 11
            color: ligne.r.desactive ? Couleurs.vert : Couleurs.rouge
            Texte { anchors.centerIn: parent; text: ligne.r.desactive ? "+" : "−"; font.pixelSize: 16; font.weight: Font.Bold; color: "#ffffff" }
            MouseArea {
                objectName: "nc-fiche-moins-" + ligne.r.cle
                anchors.fill: parent; anchors.margins: -4
                onClicked: { if (ligne.r.desactive) Raccourcis.raccourci(ligne.r, "reactiver"); else Raccourcis.supprimer(ligne.r) }
            }
        }
        Flow {
            id: blocTouches
            x: fiche.edition ? 30 : 0
            width: ligne.longues ? ligne.largeur - x : ligne.kw
            anchors.verticalCenter: ligne.longues ? undefined : parent.verticalCenter
            y: ligne.longues ? 2 : 0
            spacing: 5
            Repeater {
                model: fiche.touches(ligne.r)
                Row {
                    required property string modelData
                    required property int index
                    spacing: 5
                    Texte { visible: index > 0; text: "+"; secondaire: true; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                    Rectangle {
                        height: 24; width: libTouche.implicitWidth + 16; radius: 7
                        color: Qt.alpha(Couleurs.carte, 0.6)
                        border.width: fiche.edition && ligne.r.modifiable ? 1.5 : 1
                        border.color: fiche.edition && ligne.r.modifiable ? Couleurs.accent : Qt.alpha(Couleurs.texte, 0.25)
                        Texte { id: libTouche; anchors.centerIn: parent; text: modelData; font.pixelSize: 12; font.weight: Font.DemiBold }
                    }
                }
            }
        }
        // Hors du Flow (dedans, sa taille dépendrait du Flow lui-même : boucle de mise en page)
        MouseArea {
            objectName: "nc-fiche-touches-" + ligne.r.cle
            x: blocTouches.x; y: blocTouches.y; width: blocTouches.width; height: blocTouches.height
            enabled: fiche.edition && ligne.r.modifiable
            onClicked: { if (Raccourcis.capturer(ligne.r)) { capture.aide = ""; zoneClavier.forceActiveFocus() } }
        }
        // Description : texte, ou le nom de l'un des tiens à renommer en édition
        Texte {
            visible: !(fiche.edition && ligne.mien)
            x: ligne.longues ? (fiche.edition ? 30 : 0) : blocTouches.x + ligne.kw + 14
            y: ligne.longues ? 28 : 0
            width: ligne.longues ? ligne.largeur - x - 30 : ligne.placeTexte
            height: ligne.longues ? 18 : ligne.height
            text: ligne.r.nom; secondaire: true; wrapMode: Text.Wrap; maximumLineCount: 2
        }
        Rectangle {
            visible: fiche.edition && ligne.mien
            x: blocTouches.x + (ligne.longues ? 0 : ligne.kw + 14); y: ligne.longues ? 26 : (ligne.height - 24) / 2
            width: (ligne.longues ? ligne.largeur - x : ligne.placeTexte) - 30; height: 24; radius: 7
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
        // ↺ : comme dans la config
        Texte {
            visible: fiche.edition && ligne.r.modifie && !ligne.mien && !ligne.r.desactive
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            text: "↺"; color: Couleurs.accent; font.pixelSize: 16
            MouseArea { objectName: "nc-fiche-origine-" + ligne.r.cle; anchors.fill: parent; anchors.margins: -6
                        onClicked: Raccourcis.raccourci(ligne.r, "origine") }
        }
    }

    // ── « + Ajouter » : que lance le raccourci, son nom, puis ses touches ──
    Rectangle {
        id: carteAjout
        visible: fiche.ajout && !Raccourcis.capture
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
                        color: champCible.texte.trim() ? Couleurs.surAccent : Couleurs.texteSec }
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
        }
    }
    component Champ: Rectangle {
        property alias texte: saisie.text
        property string indice: ""
        function forceActiveFocus() { saisie.forceActiveFocus() }
        width: parent.width; height: 32; radius: 9
        color: Qt.alpha(Couleurs.carte, 0.8); border.width: 1; border.color: saisie.activeFocus ? Couleurs.accent : Qt.alpha(Couleurs.texte, 0.25)
        TextInput {
            id: saisie
            anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10
            verticalAlignment: TextInput.AlignVCenter; clip: true
            color: Couleurs.texte; font.family: "Adwaita Sans"; font.pixelSize: 13
            Keys.onEscapePressed: { fiche.ajout = false; zoneClavier.forceActiveFocus() }
            Texte { anchors.fill: parent; visible: !saisie.text && !saisie.activeFocus; text: parent.parent.indice; secondaire: true; font.pixelSize: 12 }
        }
    }

    // ── Capture des touches ──
    Rectangle {
        id: capture
        property string aide: ""
        visible: !!Raccourcis.capture
        anchors.centerIn: parent
        width: 420; height: 132; radius: 22
        color: Qt.alpha(Couleurs.fond, 0.95); border.width: 1.5; border.color: Couleurs.accent
        MouseArea { anchors.fill: parent }
        Column {
            anchors.centerIn: parent; spacing: 8; width: parent.width - 40
            Texte { width: parent.width; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 15; font.weight: Font.Bold
                    text: Reglages.t("Tape les nouvelles touches…", "Type the new keys…") }
            Texte { width: parent.width; horizontalAlignment: Text.AlignHCenter; secondaire: true
                    text: Raccourcis.capture ? "« " + Raccourcis.capture.nom + " »" : "" }
            Texte { width: parent.width; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 12
                    color: capture.aide ? Couleurs.orange : Couleurs.texteSec
                    text: capture.aide || Reglages.t("Échap pour annuler", "Esc to cancel") }
        }
    }
}
