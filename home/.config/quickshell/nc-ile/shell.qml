//@ pragma UseQApplication
// nc-ile : l'île dynamique de noctalia-config, en Quickshell, par-dessus la barre de Noctalia.
//   qs -c nc-ile                         lancer (service : nc-ile.service)
//   qs -c nc-ile ipc call ile basculer   ouvrir / fermer sur l'écran actif, sur le centre de contrôle (Super + C)
//   qs -c nc-ile ipc call ile ouvrir     ouvrir sur ce qui se passe (musique…) ; … suivante / precedente : changer de page
//   qs -c nc-ile ipc call ile luminosite montrer la luminosité (touches de luminosité)
//   qs -c nc-ile ipc call ile page wifi  ouvrir une page : wifi, bluetooth, son
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland

ShellRoot {
    Variants {
        model: Quickshell.screens
        Ile {}
    }

    IpcHandler {
        target: "ile"
        function basculer(): void { Etat.basculer(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : Quickshell.screens[0].name, true) }
        function ouvrir(): void { Etat.basculer(Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : Quickshell.screens[0].name, false) }
        function fermer(): void { Etat.fermer() }
        function suivante(): void { Etat.changerVue(1) }
        function precedente(): void { Etat.changerVue(-1) }
        function luminosite(): void { Etat.lireLuminosite(true) }
        function volume(): void { Etat.activite("volume") }
        function media(): void {}
        function page(nom: string): void {
            if (Etat.ecranOuvert === "") basculer()
            Etat.aller(nom)
        }
    }
}
