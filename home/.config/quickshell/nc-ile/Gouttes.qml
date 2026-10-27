// Gouttes de pluie ou flocons de neige du fond vivant (Lueurs.qml) : quelques traits fins (ou petits ronds) de la
// couleur du texte, très transparents, qui tombent sur l'écran. Leur place ne dépend que du temps t du fond : aucune
// horloge ni animation en plus, rien ne bouge quand le fond est en pause.
import QtQuick

Item {
    id: g
    property real t: 0
    property bool actif: false
    property bool neige: false
    readonly property int nombre: !actif ? 0 : neige ? 28 : 18
    // Nombre pseudo-aléatoire stable (0..1) pour la goutte i et le trait k : chaque goutte garde sa colonne et sa vitesse
    function alea(i, k) { var x = Math.sin(i * 12.9898 + k * 78.233) * 43758.5453; return x - Math.floor(x) }

    Repeater {
        model: g.nombre
        Rectangle {
            required property int index
            // Vitesse en écrans par seconde : la neige flotte, la pluie file
            readonly property real vitesse: g.neige ? 0.05 + 0.04 * g.alea(index, 1) : 0.18 + 0.1 * g.alea(index, 1)
            readonly property real avancee: (g.t * vitesse + g.alea(index, 2) * 7) % 1.15
            x: (g.alea(index, 3) + (g.neige ? 0.02 * Math.sin(g.t * 0.8 + index) : 0)) * g.width
            y: (avancee - 0.1) * g.height
            width: g.neige ? 4 + 3 * g.alea(index, 4) : 1.5
            height: g.neige ? width : 18 + 12 * g.alea(index, 4)
            radius: width / 2
            color: Couleurs.texte
            opacity: g.neige ? 0.22 : 0.16
        }
    }
}
