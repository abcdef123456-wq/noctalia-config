// Liste qui défile dans une page de l'île. Elle ne prend pas la molette elle-même (sinon la page la garderait et on ne
// pourrait plus changer de page) : l'île la lui passe (defiler), et change de page quand la liste est déjà au bout.
import QtQuick

Flickable {
    id: f
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    interactive: false
    // Rend vrai si la liste a bougé (sinon, l'île passe à la page voisine)
    function defiler(dy) {
        var max = Math.max(0, contentHeight - height)
        var n = Math.max(0, Math.min(max, contentY - dy))
        if (Math.abs(n - contentY) < 0.5) return false
        contentY = n
        return true
    }
    Behavior on contentY { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
}
