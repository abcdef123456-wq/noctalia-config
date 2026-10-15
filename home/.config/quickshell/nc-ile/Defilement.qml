// Liste qui défile dans une page de l'île. Elle ne prend pas la molette elle-même (sinon la page la garderait et on ne
// pourrait plus changer de page) : l'île la lui passe (defiler), et change de page quand la liste est déjà au bout.
import QtQuick

Flickable {
    id: f
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    interactive: false
    // Un geste (pavé tactile ou cran de molette) fait défiler d'un grand coup : presque une hauteur de liste
    property real cible: 0
    onContentHeightChanged: cible = Math.min(cible, Math.max(0, contentHeight - height))
    // Rend vrai si la liste a bougé (sinon, l'île passe à la page voisine) ; dy > 0 : vers le haut
    function defiler(dy) {
        var max = Math.max(0, contentHeight - height)
        var n = Math.max(0, Math.min(max, cible + (dy > 0 ? -1 : 1) * height * 0.85))
        if (Math.abs(n - cible) < 0.5) return false
        cible = n
        contentY = n
        return true
    }
    Behavior on contentY { NumberAnimation { duration: 340; easing.type: Easing.OutCubic } }
}
