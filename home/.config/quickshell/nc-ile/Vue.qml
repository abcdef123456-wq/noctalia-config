// Vue de toutes les fenêtres (comme Mission Control) : Super + A, trois doigts vers le haut, ou un coin actif.
//   Même allure que le carrousel (Super + W) : un cadre sur le fond d'écran flouté, qui couvre tout l'écran (rien ne se
//   voit derrière) ; pendant la vue, la souris ne donne plus le focus aux fenêtres de dessous.
//   Les bureaux de l'écran en cube : le choisi devant, le bord des voisins de biais sur les côtés. Parcourir les bureaux
//   (flèches, deux doigts à l'horizontale, clic sur un voisin ou en haut) fait tourner le cube, en reculant pendant le
//   mouvement ; le vrai bureau ne change qu'en quittant la vue : on arrive sur le bureau choisi.
//   Animation, recul, voisins visibles et durée : nc-reglages, section Animations (VUE_*).
//   Le bureau en miniature : chaque fenêtre à sa place et à sa taille, à la même échelle (comme sur l'écran) ;
//   les masquées à la place qu'elles avaient, par-dessus (même si une autre fenêtre a pris leur place), voilées et
//   marquées « Masquée ». Les bureaux de l'écran en haut.
//   Glisser une fenêtre : elle rétrécit dans la main ; lâchée sur un bureau (en haut, ou sur le côté : le voisin) elle
//   y est envoyée, sur une autre fenêtre elles échangent leurs places.
//   Clic : aller sur la fenêtre · clic molette : la fermer
//   Au survol : boutons Masquer et Fermer. Masquer ici ne bouge rien : la fenêtre devient translucide, marquée
//   « Masquée », et n'est vraiment masquée qu'à la fermeture de la vue (second clic : annulé). Un clic sur une masquée
//   la ramène, au premier plan, sur le bureau choisi.
//   Quitter (Échap, trois doigts vers le bas, clic hors du bureau) : on va sur le bureau choisi, qui grandit jusqu'à
//   remplir l'écran.
import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Widgets
import QtQuick.Effects
import "Geometrie.js" as Geometrie

PanelWindow {
    id: v
    required property var modelData
    screen: modelData
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    // Calque Top, sous l'île (Overlay) : ses notifications et activités passent par-dessus la vue (entre surfaces du
    // même calque, la plus récente serait au-dessus). Overlay seulement devant une fenêtre en plein écran.
    WlrLayershell.layer: Hyprland.activeToplevel && Hyprland.activeToplevel.lastIpcObject
                         && (Hyprland.activeToplevel.lastIpcObject.fullscreen || 0) > 0 ? WlrLayer.Overlay : WlrLayer.Top
    WlrLayershell.namespace: "nc-vue"
    // Clavier et souris pour la vue, sauf pendant qu'on choisit une zone à capturer (nc-capture : vuePause), sinon
    // le clic de la sélection tombait sur la vue
    WlrLayershell.keyboardFocus: Etat.vuePause ? WlrKeyboardFocus.None : WlrKeyboardFocus.Exclusive
    color: "transparent"

    readonly property var moniteur: Hyprland.monitorFor(modelData)
    readonly property int bureau: moniteur && moniteur.activeWorkspace ? moniteur.activeWorkspace.id : -1
    // Bureaux de cet écran (les bureaux cachés « special: » à part), dans l'ordre
    readonly property var bureaux: Hyprland.workspaces.values.filter(w => w.id > 0 && w.monitor === moniteur).sort((a, b) => a.id - b.id)
    // Fenêtres du bureau affiché, puis les masquées (sur l'écran actif seulement)
    // Les fenêtres d'un bureau, puis ses masquées (à la place qu'elles avaient ; sans trace de leur bureau : sur le
    // bureau affiché de l'écran actif)
    function fenetresDe(id) {
        var vis = Hyprland.toplevels.values.filter(t => t.workspace && t.workspace.id === id && t.wayland)
        var red = Hyprland.toplevels.values.filter(t => t.workspace && t.workspace.name === "special:reduites" && t.wayland
            && (tailles[adresse(t)] ? tailles[adresse(t)].ws === id : (id === bureau && Hyprland.focusedMonitor === moniteur)))
        return vis.concat(red)
    }
    readonly property var fenetres: fenetresDe(bureau)
    function fenetre(action, t) { Quickshell.execDetached([Etat.bin + "nc-fenetre", action, adresse(t)]); relire() }
    function adresse(t) { var a = String(t.address); return a.startsWith("0x") ? a : "0x" + a }
    function dispatch(lua) { Quickshell.execDetached(["hyprctl", "eval", "hl.dispatch(" + lua + ")"]); relire() }
    // Place et taille des fenêtres relues après chaque changement (déplacer, échanger, fermer, masquer…) : sinon la
    // mise en page restait l'ancienne. Hyprland range les fenêtres en animation : relu tout de suite, puis une fois en place.
    function relire() { relireVite.restart(); relireApres.restart() }
    Timer { id: relireVite; interval: 60; onTriggered: { Hyprland.refreshToplevels(); Hyprland.refreshWorkspaces() } }
    Timer { id: relireApres; interval: 450; onTriggered: { Hyprland.refreshToplevels(); Hyprland.refreshWorkspaces() } }
    Connections {
        target: Hyprland
        // Ouvertes, fermées, déplacées, flottantes… (y compris par le clavier ou une autre appli pendant la vue)
        function onRawEvent(e) {
            if (/^(openwindow|closewindow|movewindow|changefloatingmode|fullscreen|createworkspace|destroyworkspace|moveworkspace)/.test(e.name)) v.relire()
        }
    }
    // Quitter la vue, de toutes les façons (Échap, clic, trois doigts vers le bas, une fenêtre, un bureau) : on va sur le
    // bureau choisi. Il grandit jusqu'à remplir l'écran pendant que Hyprland y passe, derrière ; puis la vue s'efface.
    function fermer() {
        if (partant) return
        partant = true
        if (choisi > 0 && choisi !== bureau) dispatch("hl.dsp.focus({ workspace = " + choisi + " })")
        fin = 1
        limiteCapture = Date.now() + dureeFin + 1000
        sortie.start()
    }
    property bool partant: false
    // Même trajet dans les deux sens : 1 = bureau grandeur réelle, 0 = vue d'ensemble.
    property real fin: 1
    readonly property int dureeFin: Reglages.sobre ? 0 : 260
    Behavior on fin { NumberAnimation { duration: v.dureeFin; easing.type: Easing.InOutCubic } }
    readonly property real entree: partant ? 1 : 1 - fin
    property real limiteCapture: 0
    Timer {
        id: sortie; interval: v.dureeFin + 20; repeat: true
        onTriggered: {
            // Un clic Masquer suivi aussitôt d'Échap laisse finir la copie de l'image, sans attente illimitée.
            if (Object.keys(Etat.vueCaptures).length && Date.now() < v.limiteCapture) { interval = 50; return }
            stop(); Etat.vueFenetres = false
        }
    }
    // Le bureau choisi dans la vue : on le parcourt sans changer de bureau ; il suit le vrai bureau s'il change
    // (trois doigts, Hyprland). Un bureau inconnu un instant (Hyprland pendant une capture…) ne compte pas.
    property int choisi: bureau
    onBureauChanged: if (bureau > 0 && !partant) choisi = bureau
    // Bureau voisin sur cet écran (flèches, clic sur un bord) : le cube tourne
    function voisin(sens) {
        var i = bureaux.findIndex(b => b.id === choisi) + sens
        if (i >= 0 && i < bureaux.length) choisi = bureaux[i].id
    }
    function valider() { fermer() }
    function allerA(t) { fenetre("aller", t); fermer() }   // nc-fenetre : le pointeur reste où il est
    function masquee(t) { return t && t.workspace && t.workspace.name === "special:reduites" }
    // Une fenêtre masquée revient sur le bureau choisi (nc-fenetre aller), les autres : on y va
    function activer(t) {
        if (masquee(t)) { Quickshell.execDetached([Etat.bin + "nc-fenetre", "aller", adresse(t), String(choisi)]); fermer(); return }
        if (enAttente[adresse(t)]) basculerAttente(t)
        allerA(t)
    }
    // « Masquer » dans la vue : rien ne bouge, la fenêtre est estompée ; elle n'est vraiment masquée qu'à la
    // fermeture de la vue (sinon les autres s'agrandiraient aussitôt pour prendre sa place). Un second clic annule.
    property var enAttente: ({})
    function annulerAttente(t) {
        var a = adresse(t), r = Object.assign({}, enAttente), images = Object.assign({}, Etat.vueImages)
        delete r[a]; delete images[a]
        enAttente = r; Etat.vueImages = images
    }
    function basculerAttente(t, source) {
        var r = Object.assign({}, enAttente), a = adresse(t)
        if (r[a]) { annulerAttente(t); return }
        else {
            var o = t.lastIpcObject || {}
            if (!o.at || !o.size || !t.workspace) return
            var entree = { address: a, x: o.at[0], y: o.at[1], w: o.size[0], h: o.size[1],
                           ws: t.workspace.id, fl: !!o.floating, mx: zone.mx, my: zone.my, mw: zone.mw, mh: zone.mh }
            r[a] = entree
            if (source && source.hasContent) {
                var token = a + ":" + Date.now(), e = Math.min(1, 1280 / Math.max(o.size[0], o.size[1]))
                var taille = Qt.size(Math.max(1, Math.round(o.size[0] * e)), Math.max(1, Math.round(o.size[1] * e)))
                Etat.captureVue(token, true)
                if (!source.grabToImage(resultat => {
                    Etat.captureVue(token, false)
                    if (v.enAttente[a] === entree) Etat.conserverVueImage(a, resultat, taille.width * taille.height)
                }, taille)) Etat.captureVue(token, false)
            }
        }
        enAttente = r
    }
    // Vue ouverte : la souris ne donne plus le focus aux fenêtres de dessous (le titre de la barre ne défile plus) ;
    // le réglage d'avant est remis à la fermeture
    Component.onDestruction: {
        var lot = Object.values(enAttente)
        if (lot.length) Etat.masquerVue(lot)
        Quickshell.execDetached(["hyprctl", "eval", "if _G.nc_vue_souris ~= nil then hl.config({ input = { follow_mouse = _G.nc_vue_souris } }) _G.nc_vue_souris = nil end"])
    }

    // Ouverture : reprendre exactement le zoom de fermeture, en sens inverse.
    Component.onCompleted: {
        Hyprland.refreshToplevels(); Hyprland.refreshMonitors(); fin = 0
        Etat.vuePause = false                      // une capture interrompue ne la laisse pas sans clavier
        Quickshell.execDetached(["hyprctl", "eval", "if _G.nc_vue_souris == nil then _G.nc_vue_souris = hl.get_config('input:follow_mouse') end hl.config({ input = { follow_mouse = 0 } })"])
        // Écarter les images des fenêtres fermées ou restaurées depuis la dernière ouverture.
        var images = Object.assign({}, Etat.vueImages)
        var cachees = Hyprland.toplevels.values.filter(t => v.masquee(t)).map(t => v.adresse(t))
        for (var a in images) if (!Etat.vueMasquageEnCours && cachees.indexOf(a) < 0) delete images[a]
        Etat.vueImages = images
    }
    Timer { interval: 60; running: true; onTriggered: { Hyprland.refreshToplevels() } }

    // ── Fond comme le carrousel (Super + W) : un cadre sous la barre, le fond d'écran de cet écran flouté ──
    // Hauteur réservée en haut de cet écran par la barre de Noctalia (hyprctl monitors : reserved = gauche, haut, droite, bas)
    readonly property int hautBarre: { var r = moniteur && moniteur.lastIpcObject ? moniteur.lastIpcObject.reserved : null; return r && r.length > 1 && r[1] > 0 ? r[1] : 42 }
    readonly property int bord: 8
    // Le fond d'écran : celui que Noctalia a retenu pour cet écran, en version floutée du carrousel s'il l'a préparée
    FileView { id: etatNoctalia; path: Quickshell.env("HOME") + "/.local/state/noctalia/settings.toml"; blockLoading: true }
    readonly property string fondOriginal: {
        var t = etatNoctalia.text() || "", nom = (v.modelData.name || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
        var m = t.match(new RegExp("\\[wallpaper\\.monitors\\.\"?" + nom + "\"?\\]\\s*\\npath\\s*=\\s*\"([^\"]+)\""))
                || t.match(/\[wallpaper\.default\]\s*\npath\s*=\s*"([^"]+)"/)
        return m ? m[1] : ""
    }
    // Place, taille et bureau des fenêtres masquées avant d'être cachées (nc-fenetre reduire)
    FileView {
        id: taillesMasquees
        path: (Quickshell.env("XDG_RUNTIME_DIR") || "/tmp") + "/nc-reduites-tailles"
        blockLoading: true
        watchChanges: true
        onFileChanged: reload()
        printErrors: false
    }
    readonly property var tailles: {
        var r = {}
        for (var l of (taillesMasquees.text() || "").split("\n")) {
            var c = l.trim().split(/\s+/)
            if (c.length >= 6) r[c[0]] = { x: +c[1], y: +c[2], w: +c[3], h: +c[4], ws: +c[5],
                                          mx: +c[7], my: +c[8], mw: +c[9], mh: +c[10] }
        }
        return r
    }

    // Tout l'écran couvert (barre comprise) : rien de ce qui se passe derrière ne se voit
    Item {
        id: ecran
        anchors.fill: parent
        layer.enabled: true                          // flou calculé une fois, gardé en image (pas à chaque image du cube)
        Rectangle { anchors.fill: parent; color: Couleurs.carte }
        // Flouté ici (la version floutée du carrousel est en WebP, que Qt ne lit pas toujours) ; petite image : flou léger
        Image {
            id: fond
            anchors.fill: parent; fillMode: Image.PreserveAspectCrop; asynchronous: true; visible: false
            sourceSize: Qt.size(width / 3, height / 3)
            // Ni chargement ni flou en Économie ou sans effets : le fond uni suffit
            source: v.fondOriginal !== "" && !Reglages.sobre && !Reglages.imagesLegeres ? "file://" + v.fondOriginal : ""
        }
        MultiEffect { anchors.fill: parent; source: fond; blurEnabled: true; blur: 1; blurMax: 40; autoPaddingEnabled: false }
        Rectangle { anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.45) }
        MouseArea { anchors.fill: parent; onClicked: v.fermer() }
    }
    Rectangle {
        id: cadre
        x: v.bord; y: v.hautBarre + v.bord; width: v.width - 2 * v.bord; height: v.height - y - v.bord
        radius: 10; color: Qt.rgba(1, 1, 1, 0.03)
        border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.08)
        opacity: 1 - v.fin
    }
    Item {
        anchors.fill: parent
        focus: true
        Keys.onEscapePressed: v.fermer()
        Keys.onReturnPressed: v.valider()
        Keys.onEnterPressed: v.valider()
        Keys.onLeftPressed: v.voisin(-1)
        Keys.onRightPressed: v.voisin(1)
    }

    // ── Bureaux ──
    Row {
        id: rangee
        anchors.horizontalCenter: parent.horizontalCenter
        y: cadre.y + 16
        spacing: 10
        opacity: 1 - v.fin
        Repeater {
            model: v.bureaux
            Rectangle {
                id: pastille
                required property var modelData
                readonly property bool actif: modelData.id === v.choisi
                width: Math.max(64, etiq.implicitWidth + 28); height: 40; radius: 20
                color: depotBureau.containsDrag ? Couleurs.accent : (actif ? Couleurs.gris4 : (zp.containsMouse ? Couleurs.gris3 : Couleurs.gris2))
                border.width: actif ? 1.5 : 0; border.color: Couleurs.accent
                Behavior on color { ColorAnimation { duration: 120 } }
                Texte {
                    id: etiq
                    anchors.centerIn: parent; font.pixelSize: 14; font.weight: Font.DemiBold
                    text: Reglages.t("Bureau ", "Desktop ") + pastille.modelData.name + (pastille.modelData.toplevels.values.length
                          ? "  ·  " + pastille.modelData.toplevels.values.length : "")
                }
                MouseArea {
                    id: zp; anchors.fill: parent; hoverEnabled: true
                    onClicked: v.choisi = pastille.modelData.id                    // le cube tourne jusqu'à lui
                    onDoubleClicked: { v.choisi = pastille.modelData.id; v.valider() }
                }
                // Fenêtre lâchée ici : envoyée sur ce bureau (on reste sur la vue)
                DropArea {
                    id: depotBureau; anchors.fill: parent
                    onDropped: d => {
                        var t = d.source && d.source.toplevel
                        if (t && !v.masquee(t))
                            v.envoyer(t, pastille.modelData.id)
                    }
                }
            }
        }
        // Nouveau bureau vide
        Rectangle {
            width: 40; height: 40; radius: 20; color: zn.containsMouse ? Couleurs.gris3 : Couleurs.gris2
            Ico { anchors.centerIn: parent; nom: "add"; taille: 20 }
            MouseArea { id: zn; anchors.fill: parent; hoverEnabled: true; onClicked: v.dispatch("hl.dsp.focus({ workspace = 'emptynm' })") }
            DropArea {
                anchors.fill: parent
                onDropped: d => {
                    var t = d.source && d.source.toplevel
                    if (t && !v.masquee(t))
                        v.dispatch("hl.dsp.window.move({ workspace = 'emptynm', follow = false, window = 'address:" + v.adresse(t) + "' })")
                }
            }
        }
    }

    // ── Le bureau en miniature : une seule échelle pour toutes les fenêtres, chacune à sa place ; les masquées par-dessus ──
    Item {
        id: zone
        anchors { top: rangee.bottom; topMargin: 22; bottom: cadre.bottom; bottomMargin: 18; left: cadre.left; leftMargin: 22; right: cadre.right; rightMargin: 22 }
        readonly property int n: v.fenetres.length
        // L'écran, en points
        readonly property var mon: v.moniteur && v.moniteur.lastIpcObject ? v.moniteur.lastIpcObject : ({})
        readonly property real mw: v.width
        readonly property real mh: v.height
        readonly property real mx: mon.x || 0
        readonly property real my: mon.y || 0
        // Taille et place (en points, sur l'écran) : celles d'avant pour une masquée
        function taille(t) {
            var m = v.masquee(t) ? v.tailles[v.adresse(t)] : null
            if (m) { var r = Geometrie.adapter(m, mx, my, mw, mh); return [r.w, r.h] }
            var o = t.lastIpcObject || {}; return o.size ? o.size : [mw / 2, mh / 2]
        }
        function place(t) {
            var m = v.masquee(t) ? v.tailles[v.adresse(t)] : null
            if (m) { var r = Geometrie.adapter(m, mx, my, mw, mh); return [r.x, r.y] }
            var o = t.lastIpcObject || {}
            if (o.at && !v.masquee(t)) return o.at
            var tl = taille(t); return [mx + (mw - tl[0]) / 2, my + (mh - tl[1]) / 2]   // masquée sans trace : au milieu
        }
        // Réglages (nc-reglages, Animations) : cube, glisse ou fondu ; recul pendant le mouvement ; voisins visibles ; durée
        readonly property string anim: ["cube", "glisse", "fondu"].indexOf(Reglages.val("VUE_BUREAUX", "cube")) >= 0
                                        ? Reglages.val("VUE_BUREAUX", "cube") : "cube"
        readonly property bool voisins: anim !== "fondu" && Reglages.val("VUE_VOISINS", "oui") !== "non"
        readonly property real reculMax: Reglages.val("VUE_RECUL", "oui") !== "non" ? 0.16 : 0
        readonly property int duree: Reglages.sobre ? 0
                                     : Math.max(0, Math.min(2000, parseInt(Reglages.val("VUE_DUREE", "320")) || 0))

        // Une seule échelle pour tout le bureau, sans déformer ; de la place sur les côtés pour les bureaux voisins
        readonly property real e: Math.min(width * (voisins ? 0.78 : 0.94) / mw, height / mh)
        readonly property real fw: mw * e
        readonly property real fh: mh * e
        readonly property real bx: (width - fw) / 2
        readonly property real by: (height - fh) / 2

        // ── Les bureaux en cube : le choisi au milieu, les voisins de biais de chaque côté (on en voit le bord) ──
        // Si le bureau choisi manque un instant de la liste (Hyprland la rafraîchit), le cube reste où il est
        readonly property int trouve: v.bureaux.findIndex(b => b.id === v.choisi)
        property int courant: 0
        onTrouveChanged: placerDepart()
        property real pos: 0
        property bool initialise: false
        // La création QML ne suffit pas : l'écran et le bureau peuvent arriver pendant le fondu d'ouverture.
        readonly property bool pret: initialise && trouve >= 0 && v.entree >= 1
                                     && v.width > 0 && v.height > 0 && width > 0 && height > 0
        function placerDepart() {
            if (trouve < 0) return
            courant = trouve
            if (!initialise) { pos = courant; initialise = true }
        }
        Component.onCompleted: placerDepart()
        onCourantChanged: if (!glisse) pos = courant
        // L'arrivée sur un bureau : une animation. Aux doigts, la position suit la cible image par image (lissage
        // exponentiel, à la cadence de l'écran) : une animation relancée à chaque évènement du pavé tactile repartait
        // à pleine vitesse à chaque fois et faisait trembler le cube (revue PERF-03)
        Behavior on pos {
            enabled: zone.pret && !zone.glisse
            NumberAnimation { duration: zone.duree; easing.type: Easing.InOutCubic }
        }
        FrameAnimation {
            running: zone.glisse
            onTriggered: zone.pos += (zone.cible - zone.pos) * (1 - Math.exp(-frameTime / 0.035))
        }
        // Pas de bureau d'un côté (le premier, le dernier) : l'ensemble se décale vers ce côté, pas de vide inutile
        // Pendant un glisser, un nouveau bureau apparaît du côté où il n'y en a pas (à gauche, s'il reste un numéro libre)
        readonly property int nouveauGauche: v.traine && anim !== "fondu" && courant === 0 && v.bureaux.length && v.bureaux[0].id > 1
                                             ? v.bureaux[0].id - 1 : -1
        readonly property int nouveauDroite: v.traine && anim !== "fondu" && v.bureaux.length && courant === v.bureaux.length - 1
                                             ? v.bureaux[v.bureaux.length - 1].id + 1 : -1
        readonly property real gauche: nouveauGauche > 0 ? 1 : Math.max(0, Math.min(1, pos))
        readonly property real droite: nouveauDroite > 0 ? 1 : Math.max(0, Math.min(1, v.bureaux.length - 1 - pos))
        readonly property real decalage: voisins ? (gauche - droite) * (width - fw) / 4 : 0
        // Le décalage suivi en douceur quand un nouveau bureau apparaît (pendant que le cube tourne : tel quel)
        property real dec: decalage
        Behavior on dec { enabled: zone.pret && !zone.bouge; NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

        // Recul : le cube s'éloigne pendant qu'il tourne (ou qu'on glisse), et revient une fois arrêté
        readonly property bool bouge: glisse || Math.abs(pos - courant) > 0.002
        property real recul: 0
        onPretChanged: if (!pret) { rezoom.stop(); recul = 0 }
        onBougeChanged: {
            if (!pret) { rezoom.stop(); recul = 0; return }
            if (bouge) { rezoom.stop(); recul = 1 } else rezoom.restart()
        }
        Timer { id: rezoom; interval: 80; onTriggered: zone.recul = 0 }
        Behavior on recul { enabled: zone.pret; NumberAnimation { duration: Math.min(260, zone.duree / 2); easing.type: Easing.OutCubic } }

        // Deux doigts à l'horizontale sur le pavé tactile (ou molette inclinée) : le cube suit les doigts ; on lâche, il
        // finit sur le bureau le plus proche (un petit geste suffit à passer au suivant)
        property bool glisse: false
        property real depart: 0
        property real cible: 0
        property real amorceHorizontale: 0
        Timer {
            id: finGlisse; interval: 160
            onTriggered: {
                zone.amorceHorizontale = 0
                if (!zone.glisse) return
                var c = zone.cible
                var i = Math.round(c + (c > zone.depart + 0.01 ? 0.3 : (c < zone.depart - 0.01 ? -0.3 : 0)))
                i = Math.max(0, Math.min(v.bureaux.length - 1, i))
                zone.glisse = false
                if (v.bureaux[i]) v.choisi = v.bureaux[i].id
                zone.pos = zone.courant
            }
        }
        function defilerHorizontal(e) {
            if (!pret || v.partant || Etat.vuePause || v.bureaux.length < 2) return
            var precis = e.pixelDelta.x !== 0 || e.pixelDelta.y !== 0
            var dx = precis ? e.pixelDelta.x : e.angleDelta.x / 2
            var dy = precis ? e.pixelDelta.y : e.angleDelta.y / 2
            // Un geste d'ouverture surtout vertical ne doit pas lancer un petit aller-retour du cube.
            if (dx === 0 || Math.abs(dx) <= Math.abs(dy)) {
                if (!glisse) amorceHorizontale = 0
                return
            }
            if (!glisse && precis) {
                amorceHorizontale += dx
                finGlisse.restart()
                if (Math.abs(amorceHorizontale) < 6) return
                dx = amorceHorizontale
            }
            amorceHorizontale = 0
            if (!glisse) { depart = courant; cible = pos; glisse = true }
            cible = Math.max(-0.3, Math.min(v.bureaux.length - 0.7, cible - dx / (fw * 0.8)))
            finGlisse.restart()                          // la position suit la cible (FrameAnimation)
        }
        WheelHandler {
            orientation: Qt.Horizontal
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: e => zone.defilerHorizontal(e)
        }
        Item {
            id: scene
            // Ouverture / fermeture : même géométrie, du bureau grandeur réelle à la miniature et inversement.
            readonly property real grand: 1 + (1 / zone.e - 1) * v.fin
            readonly property real fx: zone.bx + zone.dec + zone.fw / 2 - zone.width / 2   // centre du bureau, depuis le milieu
            readonly property real fy: zone.by + zone.fh / 2 - zone.height / 2
            width: zone.width; height: zone.height
            x: v.fin * (v.width / 2 - zone.x - zone.width / 2 - grand * fx)
            y: v.fin * (v.height / 2 - zone.y - zone.height / 2 - grand * fy)
            scale: (1 - zone.reculMax * zone.recul) * grand
            Repeater {
                model: v.bureaux
                Item {
                    id: face
                    required property var modelData
                    required property int index
                    readonly property int bureauId: modelData.id
                    readonly property real d: index - zone.pos           // 0 : au milieu ; ±1 : voisin
                    readonly property real dd: Math.max(-1.3, Math.min(1.3, d))
                    readonly property var fenetresIci: v.fenetresDe(bureauId)
                    // Voisins cachés à l'arrêt si on ne veut pas les voir ; fondu : un seul bureau à la fois
                    visible: Math.abs(d) < (zone.anim === "fondu" ? 1 : 1.5) && (Math.abs(d) < 0.999 || zone.voisins || zone.bouge)
                    width: zone.fw; height: zone.fh
                    // Un écart entre les faces : les cadres des écrans ne se chevauchent pas sur l'arête
                    x: zone.bx + zone.dec + (zone.anim === "fondu" ? 0 : dd * (zone.fw + 28))
                    y: zone.by
                    z: 10 - Math.abs(d)
                    opacity: (Math.abs(d) > 0.01 ? 1 - v.fin : 1)
                             * (zone.anim === "fondu" ? Math.max(0, 1 - Math.abs(d)) : 1 - 0.45 * Math.min(1, Math.abs(d)))
                    // Charnière sur le bord commun avec le bureau du milieu, en perspective : une face de cube
                    transform: Rotation {
                        origin.x: face.d > 0 ? 0 : face.width; origin.y: face.height / 2
                        axis { x: 0; y: 1; z: 0 }
                        angle: zone.anim === "cube" ? face.dd * 72 : 0
                        distanceToPlane: zone.fw * 1.6
                    }
                    // Clic sur le bureau choisi, hors des fenêtres : y aller
                    MouseArea {
                        anchors.fill: parent; z: -1
                        visible: Math.abs(face.d) < 0.01
                        onClicked: v.valider()
                    }

                    // Le cadre de l'écran
                    Rectangle {
                        x: -8; y: -8; width: zone.fw + 16; height: zone.fh + 16; radius: 18
                        // Le bureau voisin sur lequel on lâcherait une fenêtre : cerclé
                        readonly property bool vise: v.coteVise !== 0 && face.index - zone.courant === v.coteVise
                        color: Qt.rgba(1, 1, 1, vise ? 0.1 : 0.04)
                        border.width: vise ? 3 : 1; border.color: vise ? Couleurs.accent : Qt.rgba(1, 1, 1, 0.12)
                        opacity: 1 - v.fin
                    }
                    Texte {
                        anchors.centerIn: parent
                        visible: face.fenetresIci.length === 0
                        text: Reglages.t("Aucune fenêtre sur ce bureau", "No windows on this desktop"); secondaire: true; font.pixelSize: 18
                    }
                    Repeater {
                        model: face.fenetresIci
                        Item {
                            id: case_
                            required property var modelData
                            required property int index
                            readonly property var ipc: modelData.lastIpcObject || ({})
                            readonly property bool masquee: v.masquee(modelData)
                            // Masquée ou sur le point de l'être : translucide, à sa place
                            readonly property bool estompee: masquee || !!v.enAttente[v.adresse(modelData)]
                            readonly property var sz: zone.taille(modelData)
                            readonly property var pl: zone.place(modelData)
                            width: sz[0] * zone.e; height: sz[1] * zone.e
                            x: (pl[0] - zone.mx) * zone.e
                            y: (pl[1] - zone.my) * zone.e
                            // Les masquées par-dessus (estompées, même si une autre a pris leur place), celle qu'on traîne encore au-dessus
                            z: estompee ? (survol.hovered ? 8 : 7) : (survol.hovered ? 5 : 0)
                            readonly property var instantane: estompee ? Etat.vueImages[v.adresse(modelData)] : null

                            // Déposer une autre fenêtre ici : elles échangent leurs places (fenêtres affichées seulement)
                            DropArea {
                                id: depot
                                anchors.fill: parent
                                enabled: !case_.masquee
                                onDropped: d => {
                                    var t = d.source && d.source.toplevel
                                    if (t && t !== case_.modelData && !v.masquee(t)) {
                                        v.annulerAttente(t); v.annulerAttente(case_.modelData)
                                        v.dispatch("hl.dsp.window.swap({ window = 'address:" + v.adresse(t) + "', target = 'address:" + v.adresse(case_.modelData) + "' })")
                                    }
                                }
                            }
                            Rectangle {
                                anchors.fill: parent; anchors.margins: 2; radius: 12; z: 1
                                visible: depot.containsDrag && v.traine !== case_.modelData
                                color: Qt.rgba(1, 1, 1, 0.08); border.width: 2; border.color: Couleurs.accent
                            }

                            Item {
                                id: carte
                                property var toplevel: case_.modelData
                                // Un peu d'air entre les fenêtres collées (les espaces de Hyprland, réduits, ne se voient plus)
                                readonly property real marge: Math.min(7, case_.width * 0.04)
                                x: marge; y: marge
                                width: case_.width - 2 * marge; height: case_.height - 2 * marge
                                // Survol de toute la carte, boutons du coin compris : sinon, la souris sur un bouton la faisait
                                // rétrécir, le bouton sortait de sous la souris, elle regrossissait… (va-et-vient)
                                scale: zf.pressed ? 0.97 : (survol.hovered ? 1.03 : 1)
                                Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                                // Glissée : elle reste ici, effacée ; c'est sa réduction, dans la main, qui suit le pointeur
                                opacity: v.traine === case_.modelData ? 0.3 : 1

                                Rectangle {
                                    anchors.fill: parent; anchors.margins: -3; radius: 14
                                    color: "transparent"; border.width: 3
                                    border.color: survol.hovered ? Couleurs.accent : "transparent"
                                }
                                ClippingRectangle {
                                    anchors.fill: parent; radius: case_.estompee ? 10 : 0
                                    // Même superposition avant et après fermeture : fond plein et contenu estompé.
                                    color: case_.estompee ? Qt.rgba(Couleurs.carte.r, Couleurs.carte.g, Couleurs.carte.b, 1) : "transparent"
                                    Item {
                                        anchors.fill: parent
                                        visible: !imageGardee.visible
                                        opacity: case_.estompee ? 0.45 : 1
                                        ScreencopyView {
                                            id: capture
                                            // Masquée : Hyprland l'a redimensionnée dans le bureau caché ; son image à la même échelle que les autres
                                            // fenêtres, coin en haut à gauche sur sa place d'avant (le texte garde sa taille, rien n'est tassé)
                                            readonly property var taille: case_.masquee && case_.ipc.size ? case_.ipc.size : null
                                            width: taille ? Math.max(parent.width, taille[0] * zone.e) : parent.width
                                            height: taille ? Math.max(parent.height, taille[1] * zone.e) : parent.height
                                            captureSource: case_.modelData.wayland
                                            // En direct seulement le bureau du milieu, à l'arrêt : pendant que le cube tourne ou à la sortie,
                                            // la dernière image (fluide, moins de travail pour la carte graphique)
                                            live: !case_.estompee && Math.abs(face.d) < 0.01 && !zone.bouge && !v.partant
                                            layer.enabled: true
                                            layer.smooth: true
                                        }
                                    }
                                    Image {
                                        id: imageGardee
                                        anchors.fill: parent
                                        visible: case_.estompee && status === Image.Ready
                                        source: case_.instantane ? case_.instantane.url : ""
                                        opacity: 0.45
                                        cache: false
                                    }
                                }
                                // Masquée sans image (Hyprland ne la dessine plus) : une carte avec la grande icône de l'appli
                                Rectangle {
                                    anchors.fill: parent; radius: 12; color: Couleurs.gris2
                                    visible: case_.masquee && !imageGardee.visible && !capture.hasContent
                                    Image {
                                        anchors.centerIn: parent
                                        readonly property real t: Math.min(96, parent.height * 0.4)
                                        width: t; height: t; sourceSize: Qt.size(192, 192)
                                        source: Quickshell.iconPath(String(case_.ipc.class || "").toLowerCase(), "application-x-executable")
                                    }
                                }
                                // Translucide et cerclée, pour la distinguer des fenêtres affichées
                                Rectangle {
                                    visible: case_.estompee; z: 1
                                    anchors.fill: parent; radius: 10
                                    color: "transparent"; border.width: 2; border.color: Qt.rgba(1, 1, 1, 0.4)
                                }
                                // Badge « Masquée », en haut à gauche
                                Rectangle {
                                    visible: case_.estompee; z: 2
                                    anchors.top: parent.top; anchors.left: parent.left; anchors.margins: 8
                                    width: badge.implicitWidth + 34; height: 28; radius: 14; color: Qt.rgba(0, 0, 0, 0.65)
                                    Ico { anchors.verticalCenter: parent.verticalCenter; x: 9; nom: "visibility_off"; taille: 15; color: "#ffffff" }
                                    Texte { id: badge; anchors.verticalCenter: parent.verticalCenter; x: 28; text: Reglages.t("Masquée", "Hidden")
                                            font.pixelSize: 12; font.weight: Font.DemiBold; color: "#ffffff" }
                                }
                                // Nom de l'appli et titre, dans la miniature, en bas
                                Rectangle {
                                    z: 2; visible: parent.width > 100; opacity: 1 - v.fin
                                    anchors.bottom: parent.bottom; anchors.bottomMargin: 8; anchors.horizontalCenter: parent.horizontalCenter
                                    width: Math.min(parent.width - 16, nom.implicitWidth + 22); height: 26; radius: 13; color: Qt.rgba(0, 0, 0, 0.65)
                                    Row {
                                        id: nom
                                        anchors.centerIn: parent; spacing: 6
                                        Image {
                                            width: 16; height: 16; sourceSize: Qt.size(32, 32); anchors.verticalCenter: parent.verticalCenter
                                            source: Quickshell.iconPath(String(case_.ipc.class || "").toLowerCase(), true)
                                            visible: source != ""
                                        }
                                        Texte {
                                            anchors.verticalCenter: parent.verticalCenter
                                            width: Math.min(implicitWidth, carte.width - 60); elide: Text.ElideRight
                                            text: case_.modelData.title || case_.ipc.class || ""; font.pixelSize: 12; color: "#ffffff"
                                        }
                                    }
                                }
                                // Boutons au survol : réduire, fermer (au-dessus de la zone de clic de la miniature)
                                HoverHandler { id: survol }
                                Row {
                                    z: 2
                                    anchors.top: parent.top; anchors.right: parent.right; anchors.margins: 8
                                    spacing: 6
                                    opacity: survol.hovered ? 1 : 0
                                    Behavior on opacity { NumberAnimation { duration: 120 } }
                                    Repeater {
                                        // Liste fixe (seule l'icône suit l'état) : refaite à chaque clic, les boutons étaient recréés
                                        // sous la souris et le survol sautait sur la croix
                                        model: ["masquer", "fermer"]
                                        Rectangle {
                                            required property string modelData
                                            width: 30; height: 30; radius: 15
                                            color: zb.containsMouse ? (modelData === "fermer" ? Couleurs.rouge : Couleurs.gris4) : Qt.rgba(0, 0, 0, 0.6)
                                            Ico { anchors.centerIn: parent; taille: 17; color: "#ffffff"
                                                  nom: parent.modelData === "fermer" ? "close" : (case_.estompee ? "visibility" : "visibility_off") }
                                            MouseArea {
                                                id: zb; anchors.fill: parent; hoverEnabled: true
                                                onClicked: parent.modelData === "fermer"
                                                           ? v.dispatch("hl.dsp.window.close({ window = 'address:" + v.adresse(case_.modelData) + "' })")
                                                           : (case_.masquee ? v.activer(case_.modelData) : v.basculerAttente(case_.modelData, capture))
                                            }
                                        }
                                    }
                                }
                                MouseArea {
                                    id: zf
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    acceptedButtons: Qt.LeftButton | Qt.MiddleButton
                                    // Tirer la fenêtre (plus de 10 px) : elle passe dans la main ; sinon c'est un clic
                                    property point appui
                                    property bool tiree: false
                                    onPressed: e => { appui = Qt.point(e.x, e.y); tiree = false }
                                    onPositionChanged: e => {
                                        if (!pressed || !(e.buttons & Qt.LeftButton)) return
                                        if (!tiree && !case_.masquee && Math.hypot(e.x - appui.x, e.y - appui.y) > 10) {
                                            tiree = true
                                            var o = carte.mapToItem(ecran, 0, 0), f = carte.mapToItem(ecran, carte.width, carte.height)
                                            v.prendre(case_.modelData, o.x, o.y, f.x - o.x, f.y - o.y)
                                        }
                                        if (tiree) { var q = mapToItem(ecran, e.x, e.y); v.suivre(q.x, q.y) }
                                    }
                                    onReleased: if (tiree) v.lacher()
                                    onCanceled: if (tiree) v.lacher(true)
                                    onClicked: e => {
                                        if (tiree) return
                                        if (e.button === Qt.MiddleButton) v.dispatch("hl.dsp.window.close({ window = 'address:" + v.adresse(case_.modelData) + "' })")
                                        else v.activer(case_.modelData)
                                    }
                                }
                            }
                        }
                    }
                    // Bureau voisin : un clic dessus le fait venir devant (ses fenêtres ne réagissent qu'au milieu)
                    MouseArea {
                        anchors.fill: parent; z: 50
                        visible: Math.abs(face.d) > 0.01
                        onClicked: v.choisi = face.bureauId
                    }
                }
            }
            // Le nouveau bureau qui apparaît pendant un glisser, du côté où il n'y en a pas : y lâcher la fenêtre le crée
            Repeater {
                model: [{ i: -1, id: zone.nouveauGauche }, { i: v.bureaux.length, id: zone.nouveauDroite }]
                Item {
                    id: nouveau
                    required property var modelData
                    readonly property real d: modelData.i - zone.pos
                    readonly property real dd: Math.max(-1.3, Math.min(1.3, d))
                    readonly property bool vise: v.coteVise === (modelData.i < 0 ? -1 : 1)
                    visible: modelData.id > 0 && Math.abs(d) < 1.5
                    width: zone.fw; height: zone.fh
                    x: zone.bx + zone.dec + dd * (zone.fw + 28); y: zone.by
                    z: 10 - Math.abs(d)
                    opacity: 1 - 0.45 * Math.min(1, Math.abs(d))
                    transform: Rotation {
                        origin.x: nouveau.d > 0 ? 0 : nouveau.width; origin.y: nouveau.height / 2
                        axis { x: 0; y: 1; z: 0 }
                        angle: zone.anim === "cube" ? nouveau.dd * 72 : 0
                        distanceToPlane: zone.fw * 1.6
                    }
                    Rectangle {
                        x: -8; y: -8; width: zone.fw + 16; height: zone.fh + 16; radius: 18
                        color: Qt.rgba(1, 1, 1, nouveau.vise ? 0.1 : 0.04)
                        border.width: nouveau.vise ? 3 : 1; border.color: nouveau.vise ? Couleurs.accent : Qt.rgba(1, 1, 1, 0.2)
                    }
                    Column {
                        anchors.centerIn: parent; spacing: 10
                        Ico { anchors.horizontalCenter: parent.horizontalCenter; nom: "add"; taille: 48; color: Couleurs.texteSec }
                        Texte { anchors.horizontalCenter: parent.horizontalCenter; text: Reglages.t("Nouveau bureau", "New desktop"); secondaire: true; font.pixelSize: 20 }
                    }
                }
            }
        }
    }

    // ── Glisser une fenêtre : elle rétrécit dans la main et suit le pointeur, au-dessus de tout. Lâchée sur un bureau
    //    (en haut, ou sur le côté : le bureau voisin) elle y est envoyée ; sur une autre fenêtre, elles échangent leurs
    //    places ; ailleurs, rien ne bouge ──
    property var traine: null
    function prendre(t, x, y, l, h) {
        annulerAttente(t)
        main.l0 = l; main.h0 = h; main.px = x + l / 2; main.py = y + h / 2; main.r = 0
        traine = t
        main.r = 1
    }
    function suivre(x, y) { main.px = x; main.py = y }
    // Envoyer une fenêtre sur un autre bureau, du côté le plus proche de celui d'où elle vient : vers un bureau à gauche,
    // elle se range à droite des siennes, et inversement (Hyprland la mettait du côté de la souris, donc au bord opposé)
    function envoyer(t, ws) {
        annulerAttente(t)
        var src = t.workspace ? t.workspace.id : bureau
        var cote = ws < src ? 2 : 1                  // dwindle force_split : 1 à gauche / en haut, 2 à droite / en bas
        Quickshell.execDetached(["hyprctl", "eval", "local a = hl.get_config('dwindle:force_split') "
            + "hl.config({ dwindle = { force_split = " + cote + " } }) "
            + "hl.dispatch(hl.dsp.window.move({ workspace = " + ws + ", follow = false, window = 'address:" + adresse(t) + "' })) "
            + "hl.config({ dwindle = { force_split = a } })"])
        relire()
    }
    function lacher(annule) {
        if (!annule) main.Drag.drop()
        traine = null
        coteVise = 0
    }
    // Les côtés : la moitié visible du bureau voisin (ou du nouveau bureau) ; lâchée là, la fenêtre y va. Rien n'est
    // dessiné : c'est le bureau visé qui s'allume.
    property int coteVise: 0
    Repeater {
        model: [-1, 1]
        DropArea {
            id: cote
            required property int modelData
            readonly property int cible: v.bureaux[zone.courant + modelData] ? v.bureaux[zone.courant + modelData].id
                                         : (modelData < 0 ? zone.nouveauGauche : zone.nouveauDroite)
            readonly property real bordFace: zone.x + zone.bx + zone.dec + (modelData > 0 ? zone.fw + 6 : -6)
            visible: v.traine !== null && cible > 0
            x: modelData < 0 ? cadre.x : bordFace
            width: Math.max(0, modelData < 0 ? bordFace - cadre.x : cadre.x + cadre.width - bordFace)
            y: zone.y; height: zone.height
            onContainsDragChanged: v.coteVise = containsDrag ? modelData : (v.coteVise === modelData ? 0 : v.coteVise)
            onDropped: d => {
                var t = d.source && d.source.toplevel
                if (t && cote.cible > 0) v.envoyer(t, cote.cible)
            }
        }
    }
    Item {
        id: main
        property var toplevel: v.traine
        property real l0: 200
        property real h0: 120
        property real px: 0
        property real py: 0
        property real r: 0                           // 0 : taille de la miniature ; 1 : réduite dans la main
        Behavior on r { enabled: v.traine !== null; NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
        readonly property real lf: Math.min(l0, 240)
        width: l0 + (lf - l0) * r
        height: width * h0 / Math.max(1, l0)
        x: px - width / 2; y: py - height / 2
        visible: v.traine !== null
        Drag.active: v.traine !== null
        Drag.source: main
        Drag.hotSpot.x: width / 2; Drag.hotSpot.y: height / 2
        ClippingRectangle {
            anchors.fill: parent; radius: 12; color: Couleurs.carte
            border.width: 2; border.color: Couleurs.accent
            ScreencopyView {
                anchors.fill: parent; anchors.margins: 2
                captureSource: main.toplevel ? main.toplevel.wayland : null
                live: false
            }
        }
    }
}
