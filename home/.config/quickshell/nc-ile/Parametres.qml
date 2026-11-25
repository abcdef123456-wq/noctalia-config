// Réglages du bureau : accueil, domaines et rubriques. Les vues transversales (recherche,
// modifications) n'effacent pas l'emplacement courant. Les contrôles écrivent dans nc-reglages.
import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import "AideConfig.js" as Aide

FloatingWindow {
    id: fen
    title: Reglages.t("Réglages du bureau", "Desktop settings")
    visible: false
    implicitWidth: Gabarit.largeur; implicitHeight: Gabarit.hauteur
    minimumSize: Qt.size(Gabarit.largeurMini, Gabarit.hauteurMini)
    color: "transparent"

    readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
    property var catalogue: []
    // `section` est un identifiant stable de la fenêtre, jamais un libellé traduit.
    property string domaine: ""
    property string section: ""
    property string requeteSection: ""
    property string recherche: ""
    property bool filtreModifies: false
    property string message: ""
    property int dureeMessage: 6000
    onMessageChanged: if (message !== "" && !erreur) effaceMessage.restart()
    property bool erreur: false
    property bool lectureIllisible: false
    property var file: []
    readonly property var capture: Raccourcis.capture
    property string captureMessage: ""
    property bool ileOuverte: false
    signal fermerIle()
    property bool relire: false
    readonly property bool enCours: lecture.running || ecriture.running || relire || file.length > 0
    property var navigation: ({ sections: [], domaines: [] })
    readonly property var sections: navigation.sections.map(s => s.id)
    readonly property var sectionCourante: navigation.sections.find(s => s.id === section) || null
    readonly property var domaineCourant: navigation.domaines.find(d => d.id === (sectionCourante ? sectionCourante.domaine : domaine)) || null
    readonly property bool vueRecherche: recherche.trim() !== ""
    readonly property bool vueListe: vueRecherche || filtreModifies || section !== ""
    readonly property var chiffres: {
        const parId = Object.create(null)
        for (const s of navigation.sections) parId[s.source] = { total: 0, modifies: 0 }
        for (const r of catalogue) {
            const c = parId[r.section]
            if (c) { c.total++; if (r.modifie) c.modifies++ }
        }
        const parRoute = {}
        for (const d of navigation.domaines) {
            let modifies = 0
            for (const s of d.sections) {
                const c = parId[s.source]
                parRoute[s.id] = c
                modifies += c.modifies
            }
            parRoute["domaine:" + d.id] = { modifies: modifies }
        }
        return parRoute
    }
    readonly property int nbModifies: catalogue.reduce((n, r) => n + (r.modifie ? 1 : 0), 0)

    // Clés françaises du catalogue, identifiants de navigation, alias IPC anglais, icônes et descriptions.
    // Les rubriques nouvelles restent découvrables dans « Autres » sans modifier le catalogue.
    readonly property var structure: [
        { id: "bureau", nom: ["Bureau et style", "Desktop and style"], icone: "palette",
          description: ["Thème, fonds d’écran, barre et comportement des fenêtres.", "Theme, wallpapers, bar and window behavior."],
          sections: [
            ["Apparence", "apparence", "Appearance", "palette", "Style du bureau et typographie.", "Desktop style and typography."],
            ["Fonds d'écran", "fonds-ecran", "Wallpapers", "wallpaper", "Images, dossiers et transitions.", "Images, folders and transitions."],
            ["Barre et dock", "barre-dock", "Bar and Dock", "dock_to_bottom", "Disposition, pastilles et applications épinglées.", "Layout, pills and pinned apps."],
            ["Fenêtres", "fenetres", "Windows", "window", "Disposition, transparence et sessions.", "Layout, transparency and sessions."],
            ["Animations", "animations", "Animations", "animation", "Mouvement du bureau et des fenêtres.", "Desktop and window motion."]
          ] },
        { id: "ile", nom: ["Île et alertes", "Island and alerts"], icone: "widgets",
          description: ["Pilule, pages de l’île, Spotlight et notifications.", "Pill, island pages, Spotlight and notifications."],
          sections: [
            ["Île", "ile", "Island", "widgets", "Allure, contenu de la pilule et recherche Spotlight.", "Design, pill content and Spotlight search."],
            ["Pages de l’île", "pages-ile", "Island pages", "layers", "Choisir les pages disponibles dans l’île.", "Choose the pages shown in the island."],
            ["Notifications", "notifications", "Notifications", "notifications", "Bannières, partage d’écran et Ne pas déranger.", "Banners, screen sharing and Do Not Disturb."]
          ] },
        { id: "systeme", nom: ["Système", "System"], icone: "devices",
          description: ["Énergie, affichage, son et périphériques.", "Power, display, sound and input devices."],
          sections: [
            ["Énergie", "energie", "Power", "bolt", "Profils d’alimentation et modes graphiques.", "Power profiles and graphics modes."],
            ["Son et luminosité", "son-luminosite", "Sound and Brightness", "volume_up", "Niveaux, pas de réglage et affichage.", "Levels, adjustment steps and display."],
            ["Lumière nocturne", "lumiere-nocturne", "Night Light", "wb_twilight", "Température des couleurs et horaires.", "Color temperature and schedule."],
            ["Clavier et souris", "clavier-souris", "Keyboard and Mouse", "keyboard", "Disposition, pointeur et gestes.", "Keyboard layout, pointer and gestures."],
            ["Veille", "veille", "Sleep", "bedtime", "Écran, verrouillage et mise en veille.", "Display, locking and sleep."],
            ["Captures", "captures", "Screenshots", "screenshot_monitor", "Comportement et destination des captures.", "Screenshot behavior and destination."]
          ] },
        { id: "apps", nom: ["Applications et raccourcis", "Apps and shortcuts"], icone: "apps",
          description: ["Applications, terminal, touches et snippets.", "Apps, terminal, key bindings and snippets."],
          sections: [
            ["Applications", "applications", "Applications", "apps", "Programmes par défaut et intégration au bureau.", "Default apps and desktop integration."],
            ["Terminal", "terminal", "Terminal", "terminal", "Émulateur, police et options du terminal.", "Terminal emulator, font and options."],
            ["Raccourcis", "raccourcis", "Shortcuts", "keyboard_command_key", "Consulter, modifier ou désactiver les touches.", "View, edit or disable key bindings."],
            ["Snippets", "snippets", "Snippets", "content_paste", "Gérer les extraits de texte réutilisables.", "Manage reusable text snippets."]
          ] },
        { id: "ia", nom: ["IA et services", "AI and services"], icone: "auto_awesome",
          description: ["Assistant, agents, comptes et services connectés.", "Assistant, agents, accounts and connected services."],
          sections: [
            ["Intelligence artificielle", "intelligence-artificielle", "Artificial intelligence", "auto_awesome", "Fournisseurs, modèles et clés d’API.", "Providers, models and API keys."],
            ["Agents IA (coucou)", "agents-ia", "AI Agents (coucou)", "smart_toy", "Agents et connexion à l’assistant JARVIS.", "Agents and JARVIS assistant connection."],
            ["Cloud JARVIS", "cloud-jarvis", "JARVIS Cloud", "cloud", "Synchronisation et données JARVIS.", "JARVIS sync and data."],
            ["Santé Garmin", "sante-garmin", "Garmin health", "favorite", "Connecteur Garmin et données de santé.", "Garmin connector and health data."],
            ["Intégration Google", "integration-google", "Google integration", "calendar_month", "Connexion et intégration des services Google.", "Google service sign-in and integration."]
          ] },
        { id: "maintenance", nom: ["Maintenance", "Maintenance"], icone: "build",
          description: ["Mises à jour, composants et nouveautés.", "Updates, components and release notes."],
          sections: [
            ["Mises à jour", "mises-a-jour", "Updates", "system_update", "Préférences et rapports de mise à jour.", "Update preferences and reports."],
            ["Composants", "composants", "Components", "extension", "Installer ou retirer des composants.", "Install or remove components."],
            ["Nouveautés", "nouveautes", "What's New", "new_releases", "Retrouver les derniers changements.", "See what’s changed."]
          ] },
        { id: "autres", nom: ["Autres", "Other"], icone: "tune",
          description: ["Rubriques supplémentaires du catalogue.", "Additional catalogue sections."], sections: [] }
    ]

    function organiserSections(lignes) {
        const parSource = new Map()
        for (const r of lignes) if (!parSource.has(r.section)) parSource.set(r.section, r.sectionNom)
        const anciennes = navigation.sections
        const sources = Array.from(parSource)
        if (sources.length === anciennes.length && sources.every(([s, n], i) => s === anciennes[i].source && n === anciennes[i].nom)) return

        const parDomaine = {}
        const parCle = new Map()
        for (const d of structure) {
            const liste = []
            parDomaine[d.id] = liste
            for (const [source, id, en, icone, descFr, descEn] of d.sections) {
                if (!parSource.has(source)) continue
                const s = { id: id, source: source, domaine: d.id, nom: parSource.get(source), en: en,
                            icone: icone, description: Reglages.t(descFr, descEn) }
                liste.push(s)
                parCle.set(source, s)
            }
        }
        for (const [source, nom] of sources) {
            if (parCle.has(source)) continue
            const s = { id: "catalogue:" + source, source: source, domaine: "autres", nom: nom, en: nom,
                        icone: "tune", description: Reglages.t("Voir les préférences de cette rubrique.", "View this section’s preferences.") }
            parDomaine.autres.push(s)
            parCle.set(source, s)
        }
        navigation = {
            sections: sources.map(([s]) => parCle.get(s)),
            domaines: structure.filter(d => parDomaine[d.id].length).map(d => ({
                id: d.id, nom: Reglages.t(d.nom[0], d.nom[1]), icone: d.icone,
                description: Reglages.t(d.description[0], d.description[1]), sections: parDomaine[d.id]
            }))
        }
    }

    property var prepAide: null
    FileView {
        id: indexAide
        path: (Quickshell.env("XDG_CACHE_HOME") || Quickshell.env("HOME") + "/.cache") + "/nc/aide-config.json"
        printErrors: false
        onLoaded: { try { fen.prepAide = Aide.preparer(JSON.parse(text())) } catch (e) { fen.prepAide = null } }
    }
    Process { id: majAide; command: [fen.bin + "nc-aide-config", "index"]; onExited: indexAide.reload() }
    function ligneDoc(e) {
        return { cle: "doc:" + e.fichier + ":" + e.titre + ":" + e.texte.length, section: "", sectionNom: Reglages.t("Documentation", "Documentation"),
                 nom: e.titre, genre: "doc", aide: e.texte, choix: [], valeur: "", affiche: "", modifie: false, defaut: "", mini: 0, maxi: 0, pas: 1, unite: "", zero: "" }
    }
    readonly property var visibles: {
        var mots = normaliser(recherche).split(/[\s+]+/).filter(m => m !== "")
        if (!mots.length) {
            if (filtreModifies) return catalogue.filter(r => r.modifie)
            const source = sectionCourante ? sectionCourante.source : ""
            if (!source) return []
            const lignes = catalogue.filter(r => r.section === source)
            if (section !== "ile") return lignes
            const groupes = [[], [], [], []]
            for (const r of lignes) groupes[groupeIle(r.cle)].push(r)
            return groupes[0].concat(groupes[1], groupes[2], groupes[3])
        }
        var exacts = catalogue.filter(r => {
            var t = normaliser(r.nom + " " + r.aide + " " + r.cle + " " + r.sectionNom + " " + r.affiche)
            return mots.every(m => t.indexOf(m) >= 0)
        })
        if (!prepAide || (!Aide.estQuestion(recherche) && exacts.length >= 3)) return exacts
        var deja = {}, plus = [], docs = []
        exacts.forEach(r => deja[r.cle] = true)
        Aide.chercher(prepAide, recherche, 10).forEach(e => {
            if (e.type === "doc") { if (docs.length < 2) docs.push(ligneDoc(e)) }
            else {
                let r = catalogue.find(x => x.nom === e.titre && !deja[x.cle])
                if (r) { deja[r.cle] = true; plus.push(r) }
            }
        })
        return exacts.concat(plus, docs)
    }

    readonly property var titresGroupesIle: [
        Reglages.t("Pilule et outils", "Pill and tools"),
        "VPN",
        "Spotlight",
        Reglages.t("Alertes système", "System alerts")
    ]
    function groupeIle(cle) {
        if (cle.startsWith("VPN_")) return 1
        if (cle.startsWith("SPOTLIGHT_")) return 2
        if (cle === "BATTERIE_ALERTE" || cle === "CHALEUR_ALERTE" || cle === "IA_CHALEUR") return 3
        return 0
    }
    function groupePreference(r) {
        if (r.genre === "raccourci") return r.aide
        if (section === "ile") return titresGroupesIle[groupeIle(r.cle)]
        return ""
    }

    property var parCle: ({})
    property string contexteListe: ""
    ListModel { id: modeleCles }
    onVisiblesChanged: synchroniser()
    function synchroniser() {
        var v = visibles, m = modeleCles, pareil = v.length === m.count
        const groupes = !vueRecherche && !filtreModifies ? v.map(groupePreference) : []
        const grouper = groupes.some(g => g !== groupes[0])
        var carte = Object.assign({}, parCle)
        v.forEach(r => carte[r.cle] = r)
        parCle = carte
        for (let i = 0; pareil && i < v.length; i++) {
            const item = m.get(i)
            pareil = item.cle === v[i].cle && item.groupe === (grouper ? groupes[i] : "")
        }
        if (pareil) return
        var ctx = section + "\n" + recherche + "\n" + (filtreModifies ? "1" : "0")
        var meme = ctx === contexteListe && m.count > 0
        contexteListe = ctx
        var y = liste.contentY, cle = liste.currentIndex >= 0 && liste.currentIndex < m.count ? m.get(liste.currentIndex).cle : ""
        m.clear()
        v.forEach((r, i) => m.append({ cle: r.cle, groupe: grouper ? groupes[i] : "" }))
        var i = meme ? v.findIndex(r => r.cle === cle) : -1
        liste.currentIndex = i >= 0 ? i : (v.length ? 0 : -1)
        if (!meme) { liste.contentY = 0; return }
        var garder = () => { liste.contentY = Math.max(0, Math.min(y, liste.contentHeight - liste.height)) }
        garder(); Qt.callLater(garder)
    }

    function focaliserScene() {
        if (vueListe) liste.forceActiveFocus()
        else accueil.forceActiveFocus()
    }
    function demarrerRecherche(t) {
        sidebar.champRecherche.text = t
        sidebar.champRecherche.forceActiveFocus()
        sidebar.champRecherche.cursorPosition = t.length
    }
    function viderFiltres() {
        sidebar.champRecherche.text = ""
        recherche = ""
        filtreModifies = false
        if (confirmation) liste.currentItem.aConfirmer = false
    }
    function allerAccueil() {
        requeteSection = ""
        section = ""; domaine = ""
        viderFiltres()
        focaliserScene()
    }
    function allerDomaine(id) {
        requeteSection = ""
        section = ""; domaine = id
        viderFiltres()
        focaliserScene()
    }
    function chercherTexte(t) { requeteSection = ""; sidebar.champRecherche.text = t; filtreModifies = false; focaliserScene() }
    function selectionnerSection(s) {
        domaine = s.domaine; section = s.id
        viderFiltres()
    }
    function allerSection(s) {
        // Les appels IPC historiques acceptent les libellés français et anglais, y compris à froid.
        requeteSection = s
        if (resoudreSection()) focaliserScene()
    }
    function resoudreSection() {
        if (!requeteSection) return false
        const nom = normaliser(requeteSection.trim()).replace(/’/g, "'")
        const s = navigation.sections.find(x => [x.id, x.source, x.nom, x.en].some(n => normaliser(n).replace(/’/g, "'") === nom))
        if (!s) return false
        requeteSection = ""
        selectionnerSection(s)
        return true
    }
    function basculerModifies() {
        requeteSection = ""
        const activer = !filtreModifies
        viderFiltres()
        filtreModifies = activer
        focaliserScene()
    }
    function normaliser(t) { var s = String(t).toLowerCase(); try { return s.normalize("NFD").replace(/[\u0300-\u036f]/g, "") } catch (e) { return s } }
    function afficher(nom) {
        surEcran(nom)
        const ouvrir = !visible
        visible = true
        if (ouvrir) allerAccueil()
        charger()
        if (!majAide.running) majAide.running = true
        focaliserScene()
    }
    function surEcran(nom) {
        var ecrans = Quickshell.screens
        for (let i = 0; i < ecrans.length; i++) if (ecrans[i].name === nom) { screen = ecrans[i]; return }
    }
    onClosed: close()
    function close() { visible = false }
    function charger() { if (lecture.running) relire = true; else lecture.running = true }
    function commande(args) { file.push([bin + "nc-reglages"].concat(args)); file = file; suivant() }
    function regler(cle, valeur) {
        localement(cle, String(valeur))
        if (cle === "SNIPPET_AJOUTER") { entrees.push(String(valeur)); commande(["set", cle, "-"]) }
        else commande(["set", cle, String(valeur)])
    }
    property var entrees: []
    function remettre(cle) { var r = reglage(cle); if (r) localement(cle, r.defaut); commande(["reset", cle]) }
    function localement(cle, v) {
        var r = reglage(cle)
        if (!r || r.valeur === v) return
        var n = Object.assign({}, r)
        n.valeur = v; n.modifie = v !== String(r.defaut)
        if (r.genre === "ouinon" || r.genre === "choix" || r.genre === "hz") {
            var c = r.choix.find(x => x[0] === v)
            n.affiche = c ? c[1] : (r.genre === "hz" && /^[0-9]+$/.test(v) ? v + " Hz" : v)
        } else if (r.genre === "entier") n.affiche = v === "0" && r.zero ? r.zero : v + (r.unite ? " " + r.unite : "")
        else return
        catalogue = catalogue.map(x => x.cle === cle ? n : x)
    }
    function suivant() {
        if (ecriture.running || !file.length) return
        var c = file.shift(); file = file
        ecriture.stdinEnabled = c[2] === "SNIPPET_AJOUTER" && c[3] === "-"
        ecriture.entree = ecriture.stdinEnabled ? (entrees.shift() || "") : ""
        ecriture.command = c
        ecriture.parti = false
        ecriture.running = true
    }
    function lancerAction(r, confirme) {
        var c = r && r.commande ? Array.prototype.slice.call(r.commande).map(String) : []
        if (!c.length || (r.confirmer && !confirme)) return
        if (r.relire) { file.push([bin + c[0]].concat(c.slice(1))); file = file; suivant() }
        else Quickshell.execDetached([bin + c[0]].concat(c.slice(1)))
    }
    function demanderAction(r) {
        if (!r || !r.confirmer) { lancerAction(r); return }
        var l = liste.currentItem
        if (!l || l.r.cle !== r.cle) return
        if (l.aConfirmer) { l.aConfirmer = false; lancerAction(r, true) }
        else l.aConfirmer = true
    }
    readonly property bool confirmation: !!(liste.currentItem && liste.currentItem.aConfirmer)
    function raccourci(r, action, touches) { Raccourcis.raccourci(r, action, touches) }
    Connections {
        target: Raccourcis
        function onEcrit() { if (Raccourcis.message) { fen.message = Raccourcis.message; fen.erreur = Raccourcis.erreur }; fen.charger() }
        function onCaptureFinie() { if (fen.visible) fen.focaliserScene() }
    }
    function remettreLigne(r) {
        if (!r || !r.modifie) return
        if (r.genre !== "raccourci") remettre(r.cle)
        else if (r.desactive) raccourci(r, "reactiver")
        else if (r.mien === "") raccourci(r, "origine")
    }
    function supprimerLigne(r) {
        if (!r || r.genre !== "raccourci") return
        if (r.mien !== "") raccourci(r, "retirer")
        else if (!r.desactive) raccourci(r, "desactiver")
    }
    function capturer(r) {
        if (!Raccourcis.capturer(r)) return
        captureMessage = ""
        zoneCapture.forceActiveFocus()
    }
    function finCapture(touches) { Raccourcis.finCapture(touches) }
    function combinaison(event) { return Raccourcis.combinaison(event) }
    function reglage(cle) { for (let i = 0; i < catalogue.length; i++) if (catalogue[i].cle === cle) return catalogue[i]; return null }
    function borner(r, v) { v = Math.round(v / r.pas) * r.pas; return Math.max(r.mini, Math.min(r.maxi, v)) }
    function changer(r, d) {
        if (!r || r.genre === "raccourci") return
        if (r.genre === "ouinon") regler(r.cle, r.valeur === "oui" ? "non" : "oui")
        else if (r.genre === "choix" || r.genre === "hz") {
            let c = r.choix, i = 0
            for (let k = 0; k < c.length; k++) if (c[k][0] === r.valeur) i = k
            if (c.length) regler(r.cle, c[(i + d + c.length) % c.length][0])
        } else if (r.genre === "entier") regler(r.cle, borner(r, Number(r.valeur) + d * r.pas))
    }
    function basculer(r) {
        if (!r) return
        if (r.genre === "raccourci") { if (r.desactive) raccourci(r, "reactiver"); else capturer(r); return }
        if (r.genre === "action") { demanderAction(r); return }
        if (r.genre === "info") return
        if (r.genre === "rapport") { if (liste.currentItem) liste.currentItem.deplie = !liste.currentItem.deplie; return }
        if (r.genre === "texte" || r.genre === "dossier") { if (liste.currentItem) liste.currentItem.editer() }
        else changer(r, 1)
    }
    function sectionSuivante(d) {
        const ss = navigation.sections
        if (!ss.length) return
        const i = sections.indexOf(section)
        const prochaine = ss[i < 0 ? (d > 0 ? 0 : ss.length - 1) : (i + d + ss.length) % ss.length]
        requeteSection = ""
        selectionnerSection(prochaine)
        liste.currentIndex = liste.count ? 0 : -1
    }
    function lettre(event) {
        var c = event.text || ""
        if (c.length === 1 && (c.toLowerCase() !== c.toUpperCase() || (c >= "0" && c <= "9"))) return c
        if ((event.key >= Qt.Key_A && event.key <= Qt.Key_Z) || (event.key >= Qt.Key_0 && event.key <= Qt.Key_9)) return String.fromCharCode(event.key).toLowerCase()
        return ""
    }
    readonly property var courant: liste.currentIndex >= 0 && liste.currentIndex < visibles.length ? visibles[liste.currentIndex] : null

    Process {
        id: lecture
        command: [fen.bin + "nc-reglages", "catalogue"]
        onRunningChanged: if (!running && fen.relire) Qt.callLater(() => { fen.relire = false; lecture.running = true })
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    let d = JSON.parse(text)
                    if (!Array.isArray(d)) throw new Error("catalogue")
                    if (ecriture.running || fen.file.length > 0) return
                    var avant = {}
                    fen.catalogue.forEach(r => avant[r.cle] = r)
                    d = d.map(r => { var o = avant[r.cle]; return o && JSON.stringify(o) === JSON.stringify(r) ? o : r })
                    fen.organiserSections(d)
                    fen.catalogue = d
                    if (fen.resoudreSection()) fen.focaliserScene()
                    else {
                        fen.requeteSection = ""
                        const refocaliser = liste.activeFocus && !fen.vueRecherche && !fen.filtreModifies
                        if (fen.section && !fen.sectionCourante) fen.section = ""
                        if (fen.domaine && !fen.domaineCourant) fen.domaine = ""
                        if (refocaliser && !fen.vueListe) fen.focaliserScene()
                    }
                    if (fen.lectureIllisible) { fen.lectureIllisible = false; fen.message = ""; fen.erreur = false }
                } catch (e) {
                    fen.message = Reglages.t("Réglages illisibles : lance nc-reglages dans un terminal.", "Settings unreadable: run nc-settings in a terminal.")
                    fen.erreur = true; fen.lectureIllisible = true
                }
            }
        }
        stderr: StdioCollector {}
    }
    Process {
        id: ecriture
        property string entree: ""
        property bool parti: false
        onStarted: { parti = true; if (stdinEnabled) { write(entree); entree = ""; stdinEnabled = false } }
        onRunningChanged: if (!running && !parti) { entree = ""; stdinEnabled = false; fen.message = Reglages.t("Commande introuvable.", "Command not found."); fen.erreur = true; fen.suivant() }
        stdout: StdioCollector { onStreamFinished: { fen.message = text.trim().split("\n").pop() || ""; fen.erreur = false } }
        stderr: StdioCollector { onStreamFinished: if (text.trim()) { fen.message = text.trim().split("\n").pop(); fen.erreur = true } }
        onExited: (code, status) => { if (code !== 0 && !fen.erreur) { fen.message = Reglages.t("Valeur refusée.", "Value rejected."); fen.erreur = true }; fen.charger(); fen.suivant() }
    }
    Timer { id: effaceMessage; interval: fen.dureeMessage; running: fen.message !== "" && !fen.erreur; onTriggered: fen.message = "" }

    Shortcut {
        sequence: "Escape"; enabled: !fen.capture
        onActivated: {
            if (fen.confirmation) liste.currentItem.aConfirmer = false
            else if (fen.ileOuverte) fen.fermerIle()
            else if (fen.recherche !== "" || fen.filtreModifies) { fen.viderFiltres(); fen.focaliserScene() }
            else fen.close()
        }
    }
    Shortcut { sequences: ["Ctrl+F", "Ctrl+K"]; enabled: !fen.capture; onActivated: { sidebar.champRecherche.forceActiveFocus(); sidebar.champRecherche.selectAll() } }
    Shortcut {
        sequence: "Alt+Left"; enabled: !fen.capture && !fen.vueRecherche && !fen.filtreModifies && !!fen.domaineCourant
        onActivated: if (fen.sectionCourante) fen.allerDomaine(fen.domaineCourant.id); else fen.allerAccueil()
    }
    onVisibleChanged: if (!visible && capture) finCapture("")

    // ── Contenu principal : deux volets (rail gauche + scène droite) ──
    Item {
        id: tout
        objectName: "nc-reglages-tout"
        anchors.fill: parent

        // Surface verre / thème (floutée par Hyprland quand FENETRES_FLOU=oui)
        Rectangle {
            anchors.fill: parent
            color: Qt.alpha(Couleurs.fond, Couleurs.opacitePanneau)
        }

        // ── Volet gauche : rail de navigation par catégories ──
        ParametresSidebar {
            id: sidebar
            anchors.top: parent.top; anchors.bottom: parent.bottom; anchors.left: parent.left
            width: Math.max(216, Math.min(264, Math.round(tout.width * 0.25)))
            domaines: fen.navigation.domaines
            domaineActif: fen.domaineCourant ? fen.domaineCourant.id : ""
            sectionActive: fen.section
            chiffres: fen.chiffres
            recherche: fen.recherche
            filtreModifies: fen.filtreModifies
            totalReglages: fen.catalogue.length
            nbModifies: fen.nbModifies
            enCours: fen.enCours

            onChoisirAccueil: fen.allerAccueil()
            onChoisirDomaine: id => fen.allerDomaine(id)
            onChoisirSection: id => fen.allerSection(id)
            onChangerRecherche: texte => {
                fen.requeteSection = ""
                fen.recherche = texte
                if (texte.trim() !== "") fen.filtreModifies = false
                liste.currentIndex = liste.count ? 0 : -1
            }
            onBasculerFiltreModifies: fen.basculerModifies()
            onAllerListe: fen.focaliserScene()
            onSectionDelta: d => fen.sectionSuivante(d)
            onDemarrerRecherche: lettre => fen.demarrerRecherche(lettre)
            onRelire: fen.charger()
        }

        // ── Scène : accueil, menu du domaine ou préférences ──
        Item {
            id: scene
            anchors.top: parent.top; anchors.bottom: parent.bottom
            anchors.left: sidebar.right; anchors.right: parent.right

            component LienReglages: AbstractButton {
                id: lien
                property bool courant: false
                hoverEnabled: true
                focusPolicy: Qt.StrongFocus
                padding: 0
                implicitWidth: etiquette.implicitWidth + 16
                implicitHeight: 26
                Accessible.name: text
                Keys.onReturnPressed: clicked()
                Keys.onEnterPressed: clicked()
                background: Rectangle {
                    radius: Couleurs.rayonBouton
                    color: lien.courant ? Couleurs.surfaceActive : (lien.hovered || lien.activeFocus ? Couleurs.surfaceDouce : "transparent")
                    border.width: lien.activeFocus ? 2 : (lien.courant ? Couleurs.epaisseurBordureCarte : 0)
                    border.color: lien.activeFocus ? Couleurs.accent : Couleurs.accentBord
                }
                contentItem: Texte {
                    id: etiquette
                    horizontalAlignment: Text.AlignHCenter
                    text: lien.text; font.pixelSize: 12; font.weight: Font.DemiBold
                    color: lien.courant ? Couleurs.texteSurSurfaceActive : Couleurs.texteDoux
                }
            }

            Item {
                id: enteteScene
                anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
                height: enteteContenu.implicitHeight + 24

                Column {
                    id: enteteContenu
                    anchors.left: parent.left; anchors.leftMargin: 24
                    anchors.right: boutonsFenetre.left; anchors.rightMargin: 12
                    y: 10; spacing: 6

                    Row {
                        objectName: "nc-reglages-fil-ariane"
                        visible: fen.vueListe || !!fen.domaineCourant
                        width: parent.width
                        spacing: 3
                        LienReglages {
                            id: lienAccueil
                            text: Reglages.t("Accueil", "Home")
                            onClicked: fen.allerAccueil()
                        }
                        Ico {
                            id: separateurAccueil
                            anchors.verticalCenter: parent.verticalCenter; nom: "chevron_right"; taille: 13; color: Couleurs.texteSec
                        }
                        LienReglages {
                            id: lienDomaine
                            visible: !fen.vueRecherche && !fen.filtreModifies && !!fen.sectionCourante && !!fen.domaineCourant
                            text: fen.domaineCourant ? fen.domaineCourant.nom : ""
                            onClicked: fen.allerDomaine(fen.domaineCourant.id)
                        }
                        Ico {
                            id: separateurDomaine
                            visible: !fen.vueRecherche && !fen.filtreModifies && !!fen.sectionCourante && !!fen.domaineCourant
                            anchors.verticalCenter: parent.verticalCenter; nom: "chevron_right"; taille: 13; color: Couleurs.texteSec
                        }
                        Texte {
                            width: Math.max(0, parent.width - lienAccueil.width - separateurAccueil.width - parent.spacing * 2
                                            - (lienDomaine.visible ? lienDomaine.width + separateurDomaine.width + parent.spacing * 2 : 0))
                            anchors.verticalCenter: parent.verticalCenter
                            text: fen.vueRecherche ? Reglages.t("Recherche", "Search")
                                : fen.filtreModifies ? Reglages.t("Modifiés", "Modified")
                                : fen.sectionCourante ? fen.sectionCourante.nom : fen.domaineCourant ? fen.domaineCourant.nom : ""
                            secondaire: true; font.pixelSize: 12
                        }
                    }
                    Row {
                        width: parent.width; spacing: 12
                        Rectangle {
                            id: iconeScene
                            width: 40; height: 40
                            radius: Couleurs.rayonBloc
                            color: Couleurs.surfaceActive
                            border.width: Couleurs.epaisseurBordureCarte; border.color: Couleurs.accentBord
                            Ico {
                                anchors.centerIn: parent
                                nom: fen.vueRecherche ? "search" : fen.filtreModifies ? "edit"
                                    : fen.sectionCourante ? fen.sectionCourante.icone : fen.domaineCourant ? fen.domaineCourant.icone : "home"
                                taille: 21; color: Couleurs.texteSurSurfaceActive
                            }
                        }
                        Column {
                            width: Math.max(0, parent.width - iconeScene.width - parent.spacing)
                            spacing: 2
                            Texte {
                                objectName: "nc-reglages-titre-section"
                                width: parent.width
                                text: fen.vueRecherche ? Reglages.t("Résultats pour « ", "Results for “") + fen.recherche.trim() + Reglages.t(" »", "”")
                                    : fen.filtreModifies ? Reglages.t("Réglages modifiés", "Modified settings")
                                    : fen.sectionCourante ? fen.sectionCourante.nom
                                    : fen.domaineCourant ? fen.domaineCourant.nom : Reglages.t("Accueil", "Home")
                                font.pixelSize: Couleurs.styleEditorial ? 25 : 22; font.weight: Font.Bold
                            }
                            Texte {
                                width: parent.width
                                wrapMode: Text.Wrap; elide: Text.ElideNone
                                secondaire: true; font.pixelSize: 12
                                text: {
                                    if (!fen.vueListe) return fen.domaineCourant ? fen.domaineCourant.description
                                        : Reglages.t("Personnalise ton bureau, rubrique par rubrique.", "Make the desktop yours, section by section.")
                                    const n = fen.visibles.length
                                    const m = fen.visibles.filter(r => r.modifie).length
                                    const nombre = n + Reglages.t(n === 1 ? " élément" : " éléments", n === 1 ? " item" : " items")
                                    return m > 0 ? nombre + " · " + m + Reglages.t(m === 1 ? " modifié" : " modifiés", " modified") : nombre
                                }
                            }
                        }
                    }
                }

                // Boutons de fenêtre en haut à droite
                Row {
                    id: boutonsFenetre
                    anchors.right: parent.right; anchors.rightMargin: 20
                    y: 15
                    spacing: 8
                    AssistantCommande {
                        rond: true; width: 34; height: 34; icone: "close"
                        aide: Reglages.t("Fermer (Échap)", "Close (Esc)")
                        onClic: fen.close()
                    }
                }

                Rectangle {
                    anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                    anchors.leftMargin: 24; anchors.rightMargin: 24
                    height: 1; color: Couleurs.separateur
                }
            }

            Flow {
                id: liensFreres
                objectName: "nc-reglages-rubriques-voisines"
                anchors.top: enteteScene.bottom; anchors.topMargin: 8
                anchors.left: parent.left; anchors.right: parent.right
                anchors.leftMargin: 24; anchors.rightMargin: 24
                visible: !fen.vueRecherche && !fen.filtreModifies && !!fen.sectionCourante && !!fen.domaineCourant && fen.domaineCourant.sections.length > 1
                spacing: 5
                Repeater {
                    model: liensFreres.visible ? fen.domaineCourant.sections : []
                    LienReglages {
                        required property var modelData
                        objectName: "nc-reglages-rubrique-" + modelData.id
                        text: modelData.nom
                        courant: modelData.id === fen.section
                        onClicked: fen.allerSection(modelData.id)
                    }
                }
            }

            ParametresAccueil {
                id: accueil
                visible: !fen.vueListe
                anchors.top: enteteScene.bottom; anchors.topMargin: 14
                anchors.left: parent.left; anchors.right: parent.right
                anchors.bottom: pied.top; anchors.bottomMargin: 8
                anchors.leftMargin: 24; anchors.rightMargin: 24
                domaines: fen.navigation.domaines
                domaine: fen.domaineCourant
                stats: fen.chiffres
                total: fen.catalogue.length
                modifies: fen.nbModifies
                enCours: fen.enCours
                onChoisirDomaine: id => fen.allerDomaine(id)
                onChoisirSection: id => fen.allerSection(id)
                onMontrerModifies: fen.basculerModifies()
                onAllerRail: sidebar.zoneSections.forceActiveFocus()
                onDemarrerRecherche: lettre => fen.demarrerRecherche(lettre)
            }

            // ── Liste des réglages (cartes aérées et contrôles modernes) ──
            ListView {
                id: liste
                objectName: "nc-reglages-liste"
                visible: fen.vueListe
                anchors.top: liensFreres.visible ? liensFreres.bottom : enteteScene.bottom
                anchors.topMargin: liensFreres.visible ? 8 : 14
                anchors.left: parent.left; anchors.right: parent.right
                anchors.bottom: pied.top; anchors.bottomMargin: 8
                anchors.leftMargin: 24; anchors.rightMargin: 24
                clip: true; spacing: 10; model: modeleCles
                boundsBehavior: Flickable.StopAtBounds
                currentIndex: 0
                highlightMoveDuration: 80
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                section.property: "groupe"
                section.delegate: Texte {
                    required property string section
                    width: liste.width; height: section === "" ? 0 : 24
                    visible: section !== ""
                    text: section; secondaire: true; font.pixelSize: 12; font.weight: Font.Bold
                }

                onCountChanged: if (currentIndex < 0 && count) currentIndex = 0
                onCurrentIndexChanged: if (currentIndex >= 0) positionViewAtIndex(currentIndex, ListView.Contain)

                Keys.onPressed: event => {
                    var r = fen.courant
                    event.accepted = true
                    if (event.key === Qt.Key_Down) { if (currentIndex < count - 1) currentIndex++ }
                    else if (event.key === Qt.Key_Up) {
                        if (currentIndex > 0) currentIndex--
                        else if (fen.vueRecherche) sidebar.champRecherche.forceActiveFocus()
                        else sidebar.zoneSections.forceActiveFocus()
                    }
                    else if (event.key === Qt.Key_Right || event.key === Qt.Key_Plus) fen.changer(r, 1)
                    else if (event.key === Qt.Key_Left || event.key === Qt.Key_Minus) fen.changer(r, -1)
                    else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) fen.basculer(r)
                    else if (event.key === Qt.Key_Tab) fen.sectionSuivante(1)
                    else if (event.key === Qt.Key_Backtab) fen.sectionSuivante(-1)
                    else if (event.key === Qt.Key_Home) currentIndex = count ? 0 : -1
                    else if (event.key === Qt.Key_End) currentIndex = count - 1
                    else if (event.key === Qt.Key_PageDown) currentIndex = Math.min(count - 1, currentIndex + 8)
                    else if (event.key === Qt.Key_PageUp) currentIndex = Math.max(0, currentIndex - 8)
                    else if (event.key === Qt.Key_R && !(event.modifiers & Qt.ControlModifier)) fen.remettreLigne(r)
                    else if (event.key === Qt.Key_Delete || event.key === Qt.Key_Backspace) { if (r && r.genre === "raccourci") fen.supprimerLigne(r); else fen.remettreLigne(r) }
                    else if (!(event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)) && fen.lettre(event) !== "") {
                        fen.demarrerRecherche(fen.lettre(event))
                    }
                    else event.accepted = false
                }
                WheelHandler { onWheel: e => { liste.contentY = Math.max(0, Math.min(Math.max(0, liste.contentHeight - liste.height), liste.contentY - e.angleDelta.y)); e.accepted = true } }

                // État vide élégant
                Column {
                    anchors.centerIn: parent; spacing: 8
                    visible: liste.count === 0
                    Ico { anchors.horizontalCenter: parent.horizontalCenter; nom: fen.recherche.trim() ? "search_off" : "tune"; taille: 32; color: Couleurs.texteSec; opacity: 0.6 }
                    Texte {
                        anchors.horizontalCenter: parent.horizontalCenter; secondaire: true; font.pixelSize: 14
                        text: fen.recherche.trim()
                            ? Reglages.t("Aucun réglage ne correspond.", "No setting matches.")
                            : fen.filtreModifies ? Reglages.t("Aucun réglage modifié.", "No modified settings.")
                            : fen.enCours ? Reglages.t("Chargement…", "Loading…") : Reglages.t("Aucun réglage dans cette rubrique.", "No settings in this section.")
                    }
                }

                delegate: Rectangle {
                    id: ligne
                    required property string cle
                    required property string groupe
                    required property int index
                    objectName: "nc-reglage-" + cle
                    readonly property var r: fen.parCle[cle]
                    property bool deplie: false
                    property bool aConfirmer: false
                    readonly property bool estCourante: ListView.isCurrentItem
                    // Choix nombreux ou longs : placés proprement sous la description pour ne jamais écraser le texte
                    readonly property bool choixEnDessous: (r.genre === "choix" || r.genre === "hz")
                        && (r.choix.length > 4 || r.choix.some(c => String(c[1]).length > 14))
                    onEstCouranteChanged: if (!estCourante) aConfirmer = false

                    width: liste.width
                    height: Math.max(66, blocLigne.implicitHeight + 28)
                    radius: Couleurs.rayonBloc
                    color: r.genre === "doc" ? Couleurs.accentDoux
                         : (estCourante && liste.activeFocus ? Couleurs.carteSurvol : Couleurs.surfaceDouce)
                    border.width: estCourante && liste.activeFocus ? 2 : Couleurs.epaisseurBordureCarte
                    border.color: estCourante && liste.activeFocus ? Couleurs.accent : Couleurs.bordureSubtile
                    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 110 } }

                    function editer() { saisie.forceActiveFocus(); saisie.selectAll() }
                    MouseArea { anchors.fill: parent; z: -1; onClicked: { liste.currentIndex = ligne.index; liste.forceActiveFocus() } }

                    Column {
                        id: blocLigne
                        anchors.left: parent.left; anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.leftMargin: 18; anchors.rightMargin: 16
                        spacing: 10

                        // Rangée supérieure : texte à gauche, contrôle principal à droite
                        Item {
                            width: parent.width
                            readonly property bool empiler: commande.implicitWidth > 0 && width - commande.implicitWidth < 240
                            implicitHeight: empiler ? contenu.implicitHeight + 10 + commande.implicitHeight
                                                    : Math.max(contenu.implicitHeight, commande.implicitHeight)

                            Column {
                                id: contenu
                                anchors.left: parent.left
                                width: parent.empiler ? parent.width : Math.max(0, commande.x - (commande.width > 0 ? 16 : 0))
                                y: parent.empiler ? 0 : (parent.height - height) / 2
                                spacing: 4

                                Texte {
                                    width: parent.width; wrapMode: Text.Wrap; elide: Text.ElideNone
                                    text: ligne.r.nom
                                    font.weight: Font.DemiBold; font.pixelSize: 14
                                }
                                Flow {
                                    width: parent.width
                                    visible: fen.vueRecherche || fen.filtreModifies || ligne.r.modifie
                                    spacing: 5
                                    // Pastille de section lors d'une recherche ou du filtre Modifiés
                                    Rectangle {
                                        visible: (fen.recherche.trim() !== "" || fen.filtreModifies) && ligne.r.sectionNom !== ""
                                        width: Math.min(sec.implicitWidth + 14, parent.width); height: 20
                                        radius: Couleurs.rayonBouton
                                        color: Couleurs.surfaceDouce
                                        border.width: Couleurs.epaisseurBordureCarte; border.color: Couleurs.bordureSubtile
                                        Texte {
                                            id: sec; anchors.centerIn: parent; width: Math.max(0, parent.width - 14)
                                            text: ligne.r.sectionNom; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 11; secondaire: true
                                        }
                                    }
                                    // Badge discret « Modifié »
                                    Rectangle {
                                        visible: ligne.r.modifie
                                        width: badgeMod.implicitWidth + 12; height: 19
                                        radius: Couleurs.rayonBouton
                                        color: Couleurs.surfaceActive
                                        Texte { id: badgeMod; anchors.centerIn: parent; text: Reglages.t("Modifié", "Modified"); font.pixelSize: 10; font.weight: Font.DemiBold; color: Couleurs.texteSurSurfaceActive }
                                    }
                                }

                                Texte {
                                    visible: ligne.r.aide !== "" && ligne.r.genre !== "rapport"
                                        && !(ligne.r.genre === "raccourci" && ligne.groupe !== "")
                                    width: parent.width
                                    text: ligne.r.aide; secondaire: true; font.pixelSize: 12
                                    wrapMode: Text.Wrap; elide: Text.ElideNone
                                }
                                Texte {
                                    visible: ligne.aConfirmer
                                    objectName: "nc-reglage-question-" + ligne.r.cle
                                    width: parent.width
                                    text: ligne.r.confirmer || ""
                                    color: Couleurs.rouge; font.pixelSize: 12; font.weight: Font.DemiBold
                                    wrapMode: Text.Wrap; elide: Text.ElideNone
                                }

                                // Rapport de mise à jour (Markdown filtré sans réseau)
                                Text {
                                    visible: ligne.r.genre === "rapport"
                                    width: parent.width
                                    text: ligne.r.genre === "rapport" ? AssistantEtat.sansReseau(ligne.r.aide || "") : ""
                                    textFormat: Text.MarkdownText
                                    wrapMode: Text.Wrap; color: Couleurs.texte
                                    font.family: Couleurs.police; font.pixelSize: 13
                                }
                                Texte {
                                    visible: ligne.r.genre === "rapport" && !!ligne.r.ia
                                    text: Reglages.t("Résumé par ", "Summary by ") + (ligne.r.ia || "")
                                    secondaire: true; font.pixelSize: 11
                                }
                                Column {
                                    visible: ligne.r.genre === "rapport" && ligne.deplie
                                    width: parent.width; spacing: 4; topPadding: 6
                                    Repeater {
                                        model: ligne.r.genre === "rapport" && ligne.deplie ? (ligne.r.details || []) : []
                                        Texte {
                                            required property string modelData
                                            width: parent.width; text: "• " + modelData
                                            secondaire: true; font.pixelSize: 12
                                            wrapMode: Text.Wrap; elide: Text.ElideNone
                                        }
                                    }
                                }
                            }

                            // Contrôles alignés à droite
                            Row {
                                id: commande
                                anchors.right: parent.right
                                y: parent.empiler ? contenu.height + 10 : (parent.height - height) / 2
                                spacing: 8

                                // 1. Interrupteur oui/non tactile
                                Rectangle {
                                    visible: ligne.r.genre === "ouinon"
                                    anchors.verticalCenter: parent.verticalCenter
                                    readonly property bool oui: ligne.r.valeur === "oui"
                                    width: 48; height: 26; radius: Couleurs.rayonBouton
                                    color: oui ? Couleurs.accent : Couleurs.gris3
                                    border.width: oui ? 0 : 1; border.color: Couleurs.bordureSubtile
                                    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 130 } }
                                    Rectangle {
                                        x: parent.oui ? parent.width - width - 3 : 3
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 20; height: 20; radius: Math.min(Couleurs.rayonBouton, width / 2)
                                        color: parent.oui ? Couleurs.surAccent : Couleurs.texte
                                        Behavior on x { enabled: !Reglages.sobre; NumberAnimation { duration: 130; easing.type: Easing.OutCubic } }
                                    }
                                    MouseArea {
                                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                        onClicked: { liste.currentIndex = ligne.index; fen.regler(ligne.r.cle, parent.oui ? "non" : "oui") }
                                    }
                                }

                                // 2. Barre segmentée compacte (2 à 4 choix courts)
                                Rectangle {
                                    visible: (ligne.r.genre === "choix" || ligne.r.genre === "hz") && !ligne.choixEnDessous
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: segRow.implicitWidth + 6; height: 34
                                    radius: Couleurs.rayonBouton
                                    color: Couleurs.surfaceDouce
                                    border.width: Couleurs.epaisseurBordureCarte; border.color: Couleurs.bordureSubtile
                                    Row {
                                        id: segRow
                                        anchors.centerIn: parent; spacing: 3
                                        Repeater {
                                            model: (ligne.r.genre === "choix" || ligne.r.genre === "hz") && !ligne.choixEnDessous ? ligne.r.choix : []
                                            Rectangle {
                                                id: seg
                                                required property var modelData
                                                readonly property bool estActif: ligne.r.valeur === modelData[0]
                                                width: segTxt.implicitWidth + 18; height: 26
                                                radius: Couleurs.rayonBouton
                                                color: estActif ? Couleurs.surfaceActive : (zSeg.containsMouse ? Couleurs.gris3 : "transparent")
                                                Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 110 } }
                                                Texte {
                                                    id: segTxt; anchors.centerIn: parent
                                                    text: seg.modelData[1]
                                                    font.pixelSize: 12; font.weight: seg.estActif ? Font.DemiBold : Font.Medium
                                                    color: seg.estActif ? Couleurs.texteSurSurfaceActive : Couleurs.texteSec
                                                }
                                                MouseArea {
                                                    id: zSeg; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                                    onClicked: { liste.currentIndex = ligne.index; fen.regler(ligne.r.cle, seg.modelData[0]) }
                                                }
                                            }
                                        }
                                    }
                                }

                                // 3. Entier : curseur fluide + boutons −/+ + badge valeur
                                Row {
                                    visible: ligne.r.genre === "entier"
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 8

                                    Rectangle {
                                        width: 26; height: 26; radius: Couleurs.rayonBouton
                                        anchors.verticalCenter: parent.verticalCenter
                                        color: zMoins.containsMouse ? Couleurs.gris3 : Couleurs.gris2
                                        Ico { anchors.centerIn: parent; nom: "remove"; taille: 15; color: Couleurs.texte }
                                        MouseArea { id: zMoins; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: { liste.currentIndex = ligne.index; fen.changer(ligne.r, -1) } }
                                    }
                                    Item {
                                        width: 128; height: 26; anchors.verticalCenter: parent.verticalCenter
                                        readonly property real frac: ligne.r.maxi > ligne.r.mini ? Math.max(0, Math.min(1, (Number(ligne.r.valeur) - ligne.r.mini) / (ligne.r.maxi - ligne.r.mini))) : 0
                                        Rectangle {
                                            anchors.verticalCenter: parent.verticalCenter
                                            width: parent.width; height: 6; radius: Couleurs.rayon(3, width, height)
                                            color: Couleurs.gris2
                                            Rectangle {
                                                width: Math.max(height, parent.width * parent.parent.frac)
                                                height: parent.height; radius: Couleurs.rayon(3, width, height)
                                                color: Couleurs.jauge
                                            }
                                        }
                                        Rectangle {
                                            x: Math.max(0, Math.min(parent.width - width, parent.width * parent.frac - width / 2))
                                            anchors.verticalCenter: parent.verticalCenter
                                            width: 14; height: 14; radius: width / 2
                                            color: Couleurs.texte; border.width: 2; border.color: Couleurs.accent
                                        }
                                        MouseArea {
                                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                            function appliquer(mx) {
                                                var f = Math.max(0, Math.min(1, mx / width))
                                                fen.regler(ligne.r.cle, fen.borner(ligne.r, ligne.r.mini + f * (ligne.r.maxi - ligne.r.mini)))
                                            }
                                            onPressed: m => { liste.currentIndex = ligne.index; appliquer(m.x) }
                                            onPositionChanged: m => { if (pressed) appliquer(m.x) }
                                        }
                                    }
                                    Rectangle {
                                        width: 26; height: 26; radius: Couleurs.rayonBouton
                                        anchors.verticalCenter: parent.verticalCenter
                                        color: zPlus.containsMouse ? Couleurs.gris3 : Couleurs.gris2
                                        Ico { anchors.centerIn: parent; nom: "add"; taille: 15; color: Couleurs.texte }
                                        MouseArea { id: zPlus; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: { liste.currentIndex = ligne.index; fen.changer(ligne.r, 1) } }
                                    }
                                    Rectangle {
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: Math.max(54, valEntier.implicitWidth + 16); height: 28
                                        radius: Couleurs.rayonBouton
                                        color: Couleurs.gris2; border.width: 1; border.color: Couleurs.bordureSubtile
                                        Texte {
                                            id: valEntier; anchors.centerIn: parent
                                            text: ligne.r.affiche; font.pixelSize: 12; font.weight: Font.DemiBold
                                            font.features: ({ "tnum": 1 })
                                        }
                                    }
                                }

                                // 4. Champ texte / dossier
                                Rectangle {
                                    visible: ligne.r.genre === "texte" || ligne.r.genre === "dossier"
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 230; height: 34; radius: Couleurs.rayonBouton
                                    color: Couleurs.surfaceDouce
                                    border.width: saisie.activeFocus ? 2 : Couleurs.epaisseurBordureCarte
                                    border.color: saisie.activeFocus ? Couleurs.accent : Couleurs.bordureSubtile
                                    TextInput {
                                        id: saisie
                                        anchors.fill: parent; anchors.leftMargin: 11; anchors.rightMargin: 11
                                        verticalAlignment: TextInput.AlignVCenter; clip: true; selectByMouse: true
                                        color: Couleurs.texte; selectionColor: Couleurs.accent
                                        font.family: Couleurs.police; font.pixelSize: 13
                                        text: ligne.r.valeur
                                        onAccepted: { fen.regler(ligne.r.cle, text); liste.forceActiveFocus() }
                                        Keys.onEscapePressed: { text = ligne.r.valeur; liste.forceActiveFocus() }
                                    }
                                }

                                // 5. Information en lecture seule
                                Rectangle {
                                    visible: ligne.r.genre === "info"
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: Math.min(340, infoTxt.implicitWidth + 22); height: 30
                                    radius: Couleurs.rayonBouton
                                    color: Couleurs.surfaceDouce; border.width: Couleurs.epaisseurBordureCarte; border.color: Couleurs.bordureSubtile
                                    Texte {
                                        id: infoTxt
                                        objectName: "nc-reglage-info-" + ligne.r.cle
                                        visible: ligne.r.genre === "info"
                                        anchors.centerIn: parent
                                        width: Math.min(implicitWidth, 318)
                                        text: ligne.r.affiche; secondaire: true; font.pixelSize: 12
                                    }
                                }

                                // 6. Action & confirmation en ligne
                                ParametresBouton {
                                    visible: ligne.r.genre === "action" && !ligne.aConfirmer
                                    anchors.verticalCenter: parent.verticalCenter; petit: true
                                    objectName: "nc-reglage-action-" + ligne.r.cle
                                    texte: ligne.r.affiche
                                    onClic: { liste.currentIndex = ligne.index; fen.demanderAction(ligne.r) }
                                }
                                ParametresBouton {
                                    visible: ligne.aConfirmer
                                    anchors.verticalCenter: parent.verticalCenter; petit: true; danger: true; actif: true
                                    objectName: "nc-reglage-confirmer-" + ligne.r.cle
                                    texte: ligne.r.bouton || Reglages.t("Confirmer", "Confirm")
                                    onClic: { liste.currentIndex = ligne.index; ligne.aConfirmer = false; fen.lancerAction(ligne.r, true) }
                                }
                                ParametresBouton {
                                    visible: ligne.aConfirmer
                                    anchors.verticalCenter: parent.verticalCenter; petit: true
                                    objectName: "nc-reglage-annuler-" + ligne.r.cle
                                    texte: Reglages.t("Annuler", "Cancel")
                                    onClic: { ligne.aConfirmer = false; liste.forceActiveFocus() }
                                }

                                // 7. Rapport dépliable
                                ParametresBouton {
                                    visible: ligne.r.genre === "rapport"
                                    anchors.verticalCenter: parent.verticalCenter; petit: true
                                    objectName: "nc-rapport-bouton-" + ligne.r.cle
                                    texte: ligne.deplie ? Reglages.t("Masquer", "Hide") : ligne.r.affiche
                                    onClic: { liste.currentIndex = ligne.index; ligne.deplie = !ligne.deplie }
                                }

                                // 8. Raccourci : vraies touches clavier (keycaps) + actions
                                Row {
                                    visible: ligne.r.genre === "raccourci"
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 4
                                    opacity: ligne.r.desactive ? 0.45 : 1
                                    Repeater {
                                        model: ligne.r.genre === "raccourci" ? String(ligne.r.affiche || "").split(/\s*\+\s*/).filter(x => x !== "") : []
                                        Rectangle {
                                            required property string modelData
                                            width: kTxt.implicitWidth + 16; height: 28
                                            radius: Couleurs.rayonBouton
                                            color: Couleurs.gris2
                                            border.width: 1; border.color: Couleurs.gris4
                                            Texte {
                                                id: kTxt; anchors.centerIn: parent
                                                text: parent.modelData
                                                font.pixelSize: 12; font.weight: Font.DemiBold
                                                font.strikeout: !!ligne.r.desactive
                                            }
                                        }
                                    }
                                }
                                ParametresBouton {
                                    visible: ligne.r.genre === "raccourci" && !!ligne.r.modifiable
                                    anchors.verticalCenter: parent.verticalCenter; petit: true
                                    texte: Reglages.t("Changer", "Change")
                                    onClic: { liste.currentIndex = ligne.index; fen.capturer(ligne.r) }
                                }
                                ParametresBouton {
                                    visible: ligne.r.genre === "raccourci" && ligne.r.mien === ""
                                    anchors.verticalCenter: parent.verticalCenter; petit: true
                                    texte: ligne.r.desactive ? Reglages.t("Réactiver", "Turn on") : Reglages.t("Désactiver", "Disable")
                                    onClic: { liste.currentIndex = ligne.index; if (ligne.r.desactive) fen.raccourci(ligne.r, "reactiver"); else fen.raccourci(ligne.r, "desactiver") }
                                }
                                ParametresBouton {
                                    visible: ligne.r.genre === "raccourci" && ligne.r.mien !== ""
                                    anchors.verticalCenter: parent.verticalCenter; petit: true
                                    texte: Reglages.t("Retirer", "Remove")
                                    onClic: { liste.currentIndex = ligne.index; fen.raccourci(ligne.r, "retirer") }
                                }

                                // 9. Bouton ↺ (remettre la valeur de la config)
                                AssistantCommande {
                                    rond: true; width: 30; height: 30; icone: "restart_alt"
                                    visible: ligne.r.modifie && !(ligne.r.genre === "raccourci" && (ligne.r.desactive || ligne.r.mien !== ""))
                                    aide: ligne.r.genre === "raccourci" ? Reglages.t("Touches d'origine", "Original keys") : Reglages.t("Valeur de la config", "Config value")
                                    onClic: { liste.currentIndex = ligne.index; fen.remettreLigne(ligne.r) }
                                }
                            }
                        }

                        // Choix nombreux / longs : rangée dédiée et aérée sous la description
                        Flow {
                            visible: ligne.choixEnDessous
                            width: parent.width
                            spacing: 6
                            Repeater {
                                model: ligne.choixEnDessous ? ligne.r.choix : []
                                ParametresBouton {
                                    required property var modelData
                                    petit: true
                                    texte: modelData[1]
                                    actif: ligne.r.valeur === modelData[0]
                                    onClic: { liste.currentIndex = ligne.index; fen.regler(ligne.r.cle, modelData[0]) }
                                }
                            }
                        }
                    }
                }
            }

            // ── Pied de scène : retour d'action + repères clavier concis ──
            Item {
                id: pied
                anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                anchors.leftMargin: 24; anchors.rightMargin: 24
                height: 38

                Rectangle {
                    anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
                    height: 1; color: Couleurs.separateur
                }

                Row {
                    anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                    spacing: 8
                    Ico {
                        visible: fen.message !== ""
                        anchors.verticalCenter: parent.verticalCenter
                        nom: fen.erreur ? "error" : "check_circle"; taille: 16
                        color: fen.erreur ? Couleurs.rouge : Couleurs.vert
                    }
                    Texte {
                        anchors.verticalCenter: parent.verticalCenter
                        font.pixelSize: 12; elide: Text.ElideRight
                        width: Math.max(120, pied.width - 28)
                        color: fen.erreur ? Couleurs.rouge : Couleurs.texteSec
                        text: fen.enCours && !fen.message ? Reglages.t("Application…", "Applying…")
                            : (fen.message || (fen.confirmation ? Reglages.t("Entrée : confirmer · Échap : annuler", "Enter: confirm · Esc: cancel")
                            : (fen.courant && fen.courant.genre === "raccourci" && liste.activeFocus
                               ? Reglages.t("↑↓ Choisir · Entrée Changer · Suppr Désactiver · r Origine · Échap Fermer",
                                            "↑↓ Choose · Enter Change · Del Disable · r Reset · Esc Close")
                               : (sidebar.zoneSections.activeFocus
                                  ? Reglages.t("↑↓ Parcourir · ←→ Déplier ou changer · Entrée Ouvrir",
                                               "↑↓ Browse · ←→ Expand or switch · Enter Open")
                                  : !fen.vueListe ? Reglages.t("↑ Volet · ↓ Rubriques · Tab Naviguer · Ctrl+F Chercher",
                                                              "↑ Sidebar · ↓ Sections · Tab Navigate · Ctrl+F Search")
                                  : Reglages.t("↑↓ Naviguer · ←→ Modifier · Entrée Basculer · Tab Rubrique · r Défaut",
                                               "↑↓ Navigate · ←→ Change · Enter Toggle · Tab Section · r Reset")))))
                    }
                }
            }
        }

        // ── Modale de capture d'un nouveau raccourci clavier ──
        Rectangle {
            anchors.fill: parent; visible: !!fen.capture; color: Qt.rgba(0, 0, 0, 0.58); z: 20
            MouseArea { anchors.fill: parent; onClicked: fen.finCapture("") }
            Rectangle {
                anchors.centerIn: parent
                width: Math.min(520, parent.width - 80)
                height: colCapture.implicitHeight + 52
                radius: Couleurs.rayonPanneau
                color: Couleurs.carte; border.width: Couleurs.epaisseurBordureCarte; border.color: Couleurs.accent
                Column {
                    id: colCapture
                    anchors.centerIn: parent; width: parent.width - 48; spacing: 12
                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 52; height: 52; radius: Couleurs.rayonBloc
                        color: Couleurs.surfaceActive; border.width: Couleurs.epaisseurBordureCarte; border.color: Couleurs.accentBord
                        Ico { anchors.centerIn: parent; nom: "keyboard"; taille: 28; color: Couleurs.texteSurSurfaceActive }
                    }
                    Texte {
                        width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
                        font.pixelSize: 16; font.weight: Font.Bold
                        text: fen.capture ? fen.capture.nom : ""
                    }
                    Texte {
                        width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; secondaire: true
                        text: Reglages.t("Appuie sur la nouvelle combinaison (avec Super, Ctrl ou Alt). Échap : annuler.",
                                         "Press the new combination (with Super, Ctrl or Alt). Esc: cancel.")
                    }
                    Texte {
                        width: parent.width; horizontalAlignment: Text.AlignHCenter
                        visible: fen.captureMessage !== ""; color: Couleurs.rouge
                        text: fen.captureMessage
                    }
                }
            }
            Item {
                id: zoneCapture
                objectName: "nc-reglages-capture"
                anchors.fill: parent
                Keys.onPressed: event => {
                    event.accepted = true
                    var t = fen.combinaison(event)
                    if (t === "") return
                    if (t === "annuler") { fen.finCapture(""); return }
                    if (t === "?") { fen.captureMessage = Reglages.t("Ajoute au moins Super, Ctrl ou Alt (Échap pour annuler).", "Add at least Super, Ctrl or Alt (Esc to cancel)."); return }
                    fen.finCapture(t)
                }
                Keys.onShortcutOverride: event => { event.accepted = true }
            }
        }
    }
}
