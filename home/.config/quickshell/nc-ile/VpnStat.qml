// Une petite mesure de la carte VPN : un titre discret au-dessus, la valeur en plus gros dessous (texte brut, Texte.qml).
// Une valeur absente s'écrit « indisponible » (c'est l'appelant qui la donne).
import QtQuick

Column {
    id: s
    property string titre: ""
    property string valeur: ""
    property color couleurValeur: Couleurs.texte
    spacing: 2
    Texte { text: s.titre; secondaire: true; font.pixelSize: 11 }
    Texte { objectName: "nc-vpn-stat-valeur"; text: s.valeur; color: s.couleurValeur; font.pixelSize: 14; font.weight: Font.DemiBold }
}
