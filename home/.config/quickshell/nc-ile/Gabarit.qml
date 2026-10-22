pragma Singleton
// Gabarit des menus du bureau. Un menu plein écran (fiche des raccourcis, et ceux à venir) prend le cadre exact du
// carrousel des fonds (nc-carousel/panel.luau : BORD 8, HAUT_BARRE 42, RAYON 10) : tout l'écran sous la barre, à 8 du
// bord ; sur 1600 x 1000 avec la barre à 42 : 8, 50, 1584 x 942, rayon 10 (demande de l'utilisateur).
// largeur / hauteur : la taille de départ de la fenêtre des réglages (Hyprland la pose ensuite en pleine place).
import QtQuick

QtObject {
    readonly property int largeur: 1040
    readonly property int hauteur: 740
    readonly property int largeurMini: 720
    readonly property int hauteurMini: 480
    readonly property int bord: 8                   // entre le cadre et le bord de l'écran (ou la barre)
    readonly property int barre: 42                 // place réservée en haut, si Hyprland ne l'a pas encore dite
    readonly property int rayon: 10                 // le cadre, comme le carrousel
    readonly property int marge: 32                 // marge intérieure du contenu
    readonly property int entree: 200               // léger zoom d'apparition (ms) ; le fondu est celui de Hyprland
    // Le cadre d'un menu sur un écran (taille logique) dont le haut est réservé sur `haut` points (la barre)
    function cadre(largeurEcran, hauteurEcran, haut) {
        var h = haut > 0 ? haut : barre
        return Qt.rect(bord, h + bord, largeurEcran - 2 * bord, hauteurEcran - h - 2 * bord)
    }
}
