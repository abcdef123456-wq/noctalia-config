// Fond de l'île en encoche : coins du haut carrés, coins du bas arrondis (rayon « rayon »), sans recouvrement
// (le fond reste net même semi-transparent, ILE_VERRE). Posé derrière le contenu de l'île, qui a alors un fond transparent.
import QtQuick
// radius: 0.01 et non 0 : un rectangle à rayon nul fait sortir Qt software en RGB, sans alpha (voir outils/rendu-ile.py)

Item {
    id: f
    property color couleur: "black"
    property real rayon: 0
    Rectangle { width: f.width; height: f.height - f.rayon; radius: 0.01; color: f.couleur }
    Item {
        y: f.height - f.rayon; width: f.width; height: f.rayon; clip: true
        Rectangle { y: -f.rayon; width: f.width; height: 2 * f.rayon; radius: f.rayon; color: f.couleur }
    }
}
