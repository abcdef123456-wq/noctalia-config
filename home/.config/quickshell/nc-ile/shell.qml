//@ pragma UseQApplication
//@ pragma IconTheme NC
// nc-ile : l'île dynamique de noctalia-config, en Quickshell, par-dessus la barre de Noctalia.
//   qs -c nc-ile                         lancer (service : nc-ile.service)
//   qs -c nc-ile ipc call ile basculer   ouvrir / fermer sur l'écran actif, sur le centre de contrôle (Super + C)
//   qs -c nc-ile ipc call ile ouvrir     ouvrir sur ce qui se passe (musique…) ; … suivante / precedente : changer de page
//   qs -c nc-ile ipc call ile luminosite montrer la luminosité (touches de luminosité)
//   qs -c nc-ile ipc call ile page wifi  ouvrir une page : wifi, bluetooth, son, notifications
//   qs -c nc-ile ipc call ile effacerNotifications | concentration | recherche (Spotlight, Super + R)
//   qs -c nc-ile ipc call ile projection   projection sur un second écran, comme Windows + P (Super + O)
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland

ShellRoot {
    id: racine
    Variants {
        model: Quickshell.screens
        Ile {}
    }
    // Vue de toutes les fenêtres (Super + A, trois doigts vers le haut, coin actif) : chargée seulement à l'ouverture.
    // Elle utilise la capture d'écran de Quickshell, absente de certains paquets : sans elle, seule la vue manque
    // (un message le dit) ; déclarée ici directement, c'est toute l'île qui ne se chargeait plus.
    property Component composantVue: null
    property var vues: []
    // Cockpit chargé seulement à la demande ; aucune capture ni connexion de backend au démarrage.
    property var jarvisFenetre: null
    property Component composantJarvis: null
    // Petite fenêtre de chat JARVIS (Super + Alt + A, nc-jarvis chat) : une fenêtre flottante ordinaire, que l'île ne ferme pas
    property var jarvisChatFenetre: null
    property Component composantJarvisChat: null
    // Fenêtre « Connexion JARVIS » (nc-assistant configurer) : créée à la demande
    property var connexionFenetre: null
    property Component composantConnexion: null
    // Fenêtre des réglages (Super + Alt + , ; nc-reglages fenetre) : une fenêtre classique, créée à la demande
    property var reglagesFenetre: null
    property Component composantReglages: null
    // Raccourci d'une fenêtre-outil déjà ouverte (réglages, cockpit, chat JARVIS) : nc-fenetre outil décide — sur un
    // autre bureau ou masquée, elle vient sur le bureau affiché ; ici derrière, elle passe devant ; ici et active, elle
    // est masquée comme avec Super + H (rangée ou libre, elle garde sa forme). Introuvable dans Hyprland : fermée.
    Process {
        id: outil
        property var fenetre: null
        onExited: (code, status) => { if (code === 3 && outil.fenetre) outil.fenetre.close(); outil.fenetre = null }
    }
    // Une fenêtre-outil sait si l'île est ouverte : Échap ferme alors l'île, pas la fenêtre
    function brancherIle(fenetre) {
        if (!fenetre) return
        fenetre.ileOuverte = Qt.binding(() => Etat.ecranOuvert !== "")
        fenetre.fermerIle.connect(() => { Etat.fermer(); Etat.projection = false })
    }
    function basculerOutil(fenetre, titre) {
        if (outil.running) return
        outil.fenetre = fenetre
        outil.command = [Quickshell.env("HOME") + "/.local/bin/nc-fenetre", "outil", titre]
        outil.running = true
    }
    Connections {
        target: Etat
        function onVueFenetresChanged() {
            racine.vues.forEach(v => v.destroy())
            racine.vues = []
            if (!Etat.vueFenetres) { Etat.vueCaptures = ({}); return }
            if (!racine.composantVue) racine.composantVue = Qt.createComponent("Vue.qml")
            if (racine.composantVue.status !== Component.Ready) {
                console.warn("Vue des fenêtres indisponible : " + racine.composantVue.errorString())
                Etat.vueFenetres = false
                Quickshell.execDetached(["notify-send", "-a", Reglages.t("Vue des fenêtres", "Window Overview"),
                                         Reglages.t("Vue des fenêtres indisponible", "Window Overview unavailable"),
                                         Reglages.t("Impossible de charger la vue. Consulte le journal de nc-ile pour l'erreur détaillée.", "Couldn't load the overview. Check the nc-ile journal for the detailed error.")])
                return
            }
            racine.vues = Quickshell.screens.map(s => racine.composantVue.createObject(racine, { modelData: s }))
        }
    }
    // Projection sur un second écran (Super + O, nc-ecrans) : chargée seulement à l'ouverture
    LazyLoader {
        active: Etat.projection
        Projection {}
    }
    // Coins actifs (nc-reglages → Clavier et souris)
    Variants {
        model: Quickshell.screens
        Coins {}
    }
    // Fond d'écran animé (nc-reglages → Fonds d'écran) : créé seulement s'il est choisi
    Variants {
        model: Reglages.val("FOND_ANIME", "non") === "aurore" && !Reglages.sobre ? Quickshell.screens : []
        Fond {}
    }

    IpcHandler {
        target: "ile"
        function basculer(): void { Etat.basculer(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : Quickshell.screens[0].name, true) }
        function ouvrir(): void { Etat.basculer(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : Quickshell.screens[0].name, false) }
        function fermer(): void { Etat.fermer(); Etat.projection = false }
        function pomodoro(): void { if (Etat.pomodoro) Etat.arreterMinuteur(); else Etat.lancerPomodoro() }
        function vue(): void { if (Etat.vueFenetres) vueFermer(); else vueOuvrir() }
        function vueOuvrir(): void { Etat.fermer(); Etat.vueFenetres = true }
        function vuePause(oui: bool): void { Etat.vuePause = oui }      // nc-capture, le temps de choisir une zone
        // Par la vue elle-même : elle va sur le bureau choisi, en grandissant
        function vueFermer(): void { if (racine.vues.length) racine.vues.slice().forEach(v => v.fermer()); else Etat.vueFenetres = false }
        // Projection (Super + O) : ouvre la fenêtre ; déjà ouverte, la referme
        function projection(): void {
            if (Etat.projection) { Etat.projection = false; return }
            Etat.fermer()
            Etat.projection = true
        }
        function rechercher(texte: string): void {
            Etat.saisie = texte
            if (!Etat.recherche) recherche()
        }
        function valider(): void { Etat.validerRecherche() }
        function recherche(): void { Etat.chercher(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : Quickshell.screens[0].name) }
        function suivante(): void { Etat.changerVue(1) }
        function precedente(): void { Etat.changerVue(-1) }
        function luminosite(): void { Etat.lireLuminosite(true) }
        function volume(): void { Etat.activite("volume") }
        function media(): void {}
        function notifications(): void { Etat.basculer(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : Quickshell.screens[0].name, true); Etat.aller("notifications") }
        function effacerNotifications(): void { Notifs.toutEffacer() }
        function concentration(): void { Notifs.basculerConcentration() }
        function concentrationRegler(actif: bool): void { Notifs.concentration = actif }   // mode jeu
        function concentrationEtat(): string { return Notifs.concentration ? "oui" : "non" }
        // Ouvre l'île sur une page ; si elle y est déjà, la referme (clic sur une icône de la barre)
        function page(nom: string): void {
            if (Etat.vues.indexOf(nom) < 0) return
            if (nom === "assistant" && racine.jarvisFenetre) racine.jarvisFenetre.close()
            if (Etat.ecranOuvert !== "" && !Etat.recherche && Etat.vueActive === nom) { Etat.fermer(); return }
            if (Etat.ecranOuvert === "") basculer()
            Etat.aller(nom)
        }
        // Cockpit : déjà ouvert, le même raccourci le ramène ici, le met devant ou le range (basculerOutil)
        function jarvis(): void {
            if (racine.jarvisFenetre && racine.jarvisFenetre.visible) { racine.basculerOutil(racine.jarvisFenetre, "JARVIS"); return }
            Etat.fermer()
            if (!racine.jarvisFenetre) {
                if (!racine.composantJarvis) racine.composantJarvis = Qt.createComponent("Jarvis.qml")
                if (racine.composantJarvis.status !== Component.Ready) {
                    console.warn("Cockpit JARVIS indisponible : " + racine.composantJarvis.errorString())
                    return
                }
                racine.jarvisFenetre = racine.composantJarvis.createObject(racine)
                racine.brancherIle(racine.jarvisFenetre)
            }
            if (racine.jarvisFenetre) {
                racine.jarvisFenetre.afficher(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "")
            }
        }
        function jarvisFermer(): void { if (racine.jarvisFenetre) racine.jarvisFenetre.close() }
        // Petite fenêtre de chat : ouverte vierge ; déjà ouverte, le même raccourci la ramène ici, la met devant ou la
        // range (basculerOutil : la conversation reste)
        function jarvisChat(): void {
            if (racine.jarvisChatFenetre && racine.jarvisChatFenetre.visible) { racine.basculerOutil(racine.jarvisChatFenetre, "JARVIS Chat"); return }
            if (!racine.jarvisChatFenetre) {
                if (!racine.composantJarvisChat) racine.composantJarvisChat = Qt.createComponent("JarvisChat.qml")
                if (racine.composantJarvisChat.status !== Component.Ready) {
                    console.warn("Chat JARVIS indisponible : " + racine.composantJarvisChat.errorString())
                    return
                }
                racine.jarvisChatFenetre = racine.composantJarvisChat.createObject(racine)
                racine.brancherIle(racine.jarvisChatFenetre)
            }
            if (racine.jarvisChatFenetre) racine.jarvisChatFenetre.afficher(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "")
        }
        function jarvisChatFermer(): void { if (racine.jarvisChatFenetre) racine.jarvisChatFenetre.close() }
        // Réglages en fenêtre : déjà ouverte, le même appel la ramène ici, la met devant ou la range (basculerOutil)
        function reglages(): void {
            if (racine.reglagesFenetre && racine.reglagesFenetre.visible) { racine.basculerOutil(racine.reglagesFenetre, "Réglages du bureau"); return }
            if (!racine.reglagesFenetre) {
                if (!racine.composantReglages) racine.composantReglages = Qt.createComponent("Parametres.qml")
                if (racine.composantReglages.status !== Component.Ready) {
                    console.warn("Fenêtre des réglages indisponible : " + racine.composantReglages.errorString())
                    return
                }
                racine.reglagesFenetre = racine.composantReglages.createObject(racine)
                racine.brancherIle(racine.reglagesFenetre)
            }
            if (racine.reglagesFenetre) racine.reglagesFenetre.afficher(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "")
        }
        function reglagesFermer(): void { if (racine.reglagesFenetre) racine.reglagesFenetre.close() }
        // Connexion à JARVIS en graphique (adresse, clé, test) ; déjà ouverte : ramenée ici, mise devant ou rangée
        function connexionJarvis(): void {
            if (racine.connexionFenetre && racine.connexionFenetre.visible) { racine.basculerOutil(racine.connexionFenetre, "Connexion JARVIS"); return }
            if (!racine.connexionFenetre) {
                if (!racine.composantConnexion) racine.composantConnexion = Qt.createComponent("ConnexionJarvis.qml")
                if (racine.composantConnexion.status !== Component.Ready) {
                    console.warn("Fenêtre de connexion JARVIS indisponible : " + racine.composantConnexion.errorString())
                    return
                }
                racine.connexionFenetre = racine.composantConnexion.createObject(racine)
                racine.brancherIle(racine.connexionFenetre)
            }
            if (racine.connexionFenetre) racine.connexionFenetre.afficher(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "")
        }
    }
}
