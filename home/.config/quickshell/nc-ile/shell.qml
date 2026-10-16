//@ pragma UseQApplication
//@ pragma IconTheme NC
// nc-ile : l'île dynamique de noctalia-config, en Quickshell, par-dessus la barre de Noctalia.
//   qs -c nc-ile                         lancer (service : nc-ile.service)
//   qs -c nc-ile ipc call ile basculer   ouvrir / fermer sur l'écran actif, sur le centre de contrôle (Super + C)
//   qs -c nc-ile ipc call ile ouvrir     ouvrir sur ce qui se passe (musique…) ; … suivante / precedente : changer de page
//   qs -c nc-ile ipc call ile luminosite montrer la luminosité (touches de luminosité)
//   qs -c nc-ile ipc call ile page wifi  ouvrir une page : wifi, bluetooth, son, notifications
//   qs -c nc-ile ipc call ile effacerNotifications | concentration | recherche (Spotlight, Super + R)
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
    Connections {
        target: Etat
        function onVueFenetresChanged() {
            racine.vues.forEach(v => v.destroy())
            racine.vues = []
            if (!Etat.vueFenetres) return
            if (!racine.composantVue) racine.composantVue = Qt.createComponent("Vue.qml")
            if (racine.composantVue.status !== Component.Ready) {
                console.warn("Vue des fenêtres indisponible : " + racine.composantVue.errorString())
                Etat.vueFenetres = false
                Quickshell.execDetached(["notify-send", "-a", "Vue des fenêtres", "Vue des fenêtres indisponible",
                                         "Ta version de Quickshell n'a pas la capture des fenêtres."])
                return
            }
            racine.vues = Quickshell.screens.map(s => racine.composantVue.createObject(racine, { modelData: s }))
        }
    }
    // Coins actifs (nc-reglages → Clavier et souris)
    Variants {
        model: Quickshell.screens
        Coins {}
    }
    // Fond d'écran animé (nc-reglages → Fonds d'écran) : créé seulement s'il est choisi
    Variants {
        model: Reglages.val("FOND_ANIME", "non") === "aurore" && Reglages.val("EFFETS", "tous") !== "aucun" ? Quickshell.screens : []
        Fond {}
    }

    IpcHandler {
        target: "ile"
        function basculer(): void { Etat.basculer(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : Quickshell.screens[0].name, true) }
        function ouvrir(): void { Etat.basculer(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : Quickshell.screens[0].name, false) }
        function fermer(): void { Etat.fermer() }
        function pomodoro(): void { if (Etat.pomodoro) Etat.arreterMinuteur(); else Etat.lancerPomodoro() }
        function vue(): void { Etat.fermer(); Etat.vueFenetres = !Etat.vueFenetres }
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
            if (Etat.ecranOuvert !== "" && !Etat.recherche && Etat.vueActive === nom) { Etat.fermer(); return }
            if (Etat.ecranOuvert === "") basculer()
            Etat.aller(nom)
        }
    }
}
