// Liste qui défile dans une page de l'île. Elle ne prend pas la molette elle-même (sinon la page la garderait et on ne
// pourrait plus changer de page) : l'île la lui passe (defiler), et change de page quand la liste est déjà au bout.
import QtQuick

Flickable {
    id: f
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    interactive: false
    // Position visée : chaque petit pas du pavé tactile s'y ajoute (partir de la position en cours d'animation
    // ralentissait tout et la liste n'arrivait jamais au bout)
    property real cible: 0
    onContentHeightChanged: cible = Math.min(cible, Math.max(0, contentHeight - height))
    // Rend vrai si la liste a bougé (sinon, l'île passe à la page voisine)
    function defiler(dy) {
        var max = Math.max(0, contentHeight - height)
        var n = Math.max(0, Math.min(max, cible - dy))
        if (Math.abs(n - cible) < 0.5) return false
        cible = n
        contentY = n
        return true
    }
    Behavior on contentY { NumberAnimation { duration: 90; easing.type: Easing.OutCubic } }
}
