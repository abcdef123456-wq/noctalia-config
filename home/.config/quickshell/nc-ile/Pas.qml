// Horloge des mouvements sans fin de l'île (étincelle qui tourne, logos qui flottent, flèche de téléchargement, point
// d'enregistrement, onde sonore) : 30 images par seconde, au lieu de la fréquence de l'écran (165 Hz).
// Chaque image coûte presque autant, quelle que soit la taille de ce qui bouge : environ 1,2 ms de GPU pour Quickshell,
// plus une recomposition par Hyprland. Une étincelle de 16 px qui tournait à 165 images/s prenait à elle seule le
// cinquième de l'iGPU (mesuré : 19 %, 0,1 % une fois arrêtée). À 30 images/s, un si petit mouvement reste fluide.
// t : secondes écoulées pendant que l'horloge tourne (elle reprend où elle s'était arrêtée).
import QtQuick

Timer {
    property real t: 0
    interval: 33
    repeat: true
    onTriggered: t += interval / 1000
}
