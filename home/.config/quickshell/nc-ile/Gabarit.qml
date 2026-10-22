pragma Singleton
// Gabarit des menus du bureau : la taille de la fenêtre des réglages. Tout nouveau menu (fiche des raccourcis, réglages,
// menus à venir) prend quasiment cette taille, bornée à l'écran, pour que tous se ressemblent (demande de l'utilisateur).
import QtQuick

QtObject {
    readonly property int largeur: 1040
    readonly property int hauteur: 740
    readonly property int largeurMini: 720
    readonly property int hauteurMini: 480
    readonly property int rayon: 28                 // la carte d'un menu
    readonly property int marge: 32                 // marge intérieure
    readonly property int bordEcran: 40             // au moins ça entre un menu et le bord de l'écran
    readonly property int entree: 200               // apparition (ms) ; la sortie : le même mouvement, plus court
    readonly property int sortie: 120
}
