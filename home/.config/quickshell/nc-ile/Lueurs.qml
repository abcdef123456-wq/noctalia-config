// Les lueurs du fond animé (Fond.qml) : trois grandes taches de couleur qui dérivent lentement et respirent. En mode
// vivant, elles prennent la teinte de l'heure (nuit, aube, jour, crépuscule), pulsent sur les basses de la musique et
// suivent la météo de l'île (gouttes de pluie, flocons, voile de brouillard, ciel couvert plus discret).
// Un simple Item sans rien de Wayland ni d'Hyprland : chargeable hors écran dans les tests. Tout ne dépend que de t,
// pouls, heure et meteoCode, mis à jour par Fond.qml à sa cadence : aucune animation à la fréquence de l'écran ici.
import QtQuick
import QtQuick.Shapes

Item {
    id: l
    property real t: 0
    property bool anime: true
    property bool vivant: false
    property real heure: 12          // heure décimale (19.5 = 19 h 30)
    property real pouls: 0           // niveau lissé des basses (0..1), de nc-pouls
    property int meteoCode: -1       // code OMM de nc-meteo, -1 : pas de météo

    // Météo (codes de l'OMM, comme nc-meteo) : pluie (bruine, averses, orage), neige, brouillard
    readonly property bool pluie: vivant && ((meteoCode >= 51 && meteoCode <= 67) || (meteoCode >= 80 && meteoCode <= 82) || meteoCode >= 95)
    readonly property bool neige: vivant && ((meteoCode >= 71 && meteoCode <= 77) || meteoCode === 85 || meteoCode === 86)
    readonly property bool brouillard: vivant && (meteoCode === 45 || meteoCode === 48)
    readonly property bool couvert: vivant && (meteoCode === 3 || pluie || neige || brouillard)

    // Teinte de l'heure : une couleur par lueur pour chaque moment, fondues d'un moment au suivant
    //   nuit (jusqu'à 5 h, dès 22 h) : violet, bleu, accent ; aube (vers 7 h) : rose, orange, accent ;
    //   jour (9 h à 17 h) : accent, violet, bleu (l'aurore) ; crépuscule (vers 19 h 30) : orange, violet, rose
    function fondu(a, b, k) { return Qt.rgba(a.r + (b.r - a.r) * k, a.g + (b.g - a.g) * k, a.b + (b.b - a.b) * k, 1) }
    readonly property var nuitCouleurs: [Couleurs.violet, Couleurs.bleu, Couleurs.accent]
    readonly property var jourCouleurs: [Couleurs.accent, Couleurs.violet, Couleurs.bleu]
    readonly property var moments: [[0, nuitCouleurs], [5, nuitCouleurs], [7, [Couleurs.rose, Couleurs.orange, Couleurs.accent]],
                                    [9, jourCouleurs], [17, jourCouleurs], [19.5, [Couleurs.orange, Couleurs.violet, Couleurs.rose]],
                                    [22, nuitCouleurs], [24, nuitCouleurs]]
    readonly property var teintes: {
        if (!vivant) return jourCouleurs
        var h = Math.max(0, Math.min(24, heure)), i = 1
        while (i < moments.length - 1 && moments[i][0] <= h) i++
        var a = moments[i - 1], b = moments[i], k = (h - a[0]) / (b[0] - a[0])
        var res = [fondu(a[1][0], b[1][0], k), fondu(a[1][1], b[1][1], k), fondu(a[1][2], b[1][2], k)]
        return brouillard ? res.map(c => fondu(c, Couleurs.texteSec, 0.5)) : res      // brouillard : voile gris
    }
    // La nuit (de 22 h à 5 h, fondue sur deux heures de chaque côté) et sous un ciel couvert, l'aurore se fait discrète
    readonly property real nuit: !vivant ? 0 : (heure < 5 || heure >= 22) ? 1 : heure < 7 ? (7 - heure) / 2 : heure >= 20 ? (heure - 20) / 2 : 0
    readonly property real force: (1 - 0.35 * nuit) * (couvert ? 0.8 : 1)

    Shape {
        anchors.fill: parent
        opacity: l.anime ? 1 : 0.6                           // en pause : figée, un peu plus discrète
        Behavior on opacity { NumberAnimation { duration: 800 } }
        preferredRendererType: Shape.CurveRenderer
        // Centre qui décrit une lente boucle, rayon qui respire et grandit sur les basses
        Lueur { largeur: l.width; hauteur: l.height; teinte: l.teintes[0]; force: l.force
                cx: 0.28 + 0.16 * Math.sin(l.t * 0.11); cy: 0.32 + 0.14 * Math.cos(l.t * 0.09); r: 0.55 + 0.06 * Math.sin(l.t * 0.2) + 0.12 * l.pouls }
        Lueur { largeur: l.width; hauteur: l.height; teinte: l.teintes[1]; force: l.force
                cx: 0.74 + 0.14 * Math.cos(l.t * 0.08); cy: 0.62 + 0.16 * Math.sin(l.t * 0.12); r: 0.5 + 0.07 * Math.cos(l.t * 0.17) + 0.08 * l.pouls }
        Lueur { largeur: l.width; hauteur: l.height; teinte: l.teintes[2]; force: l.force * (1 + 0.5 * l.pouls)
                cx: 0.5 + 0.22 * Math.sin(l.t * 0.06 + 2); cy: 0.9 + 0.08 * Math.cos(l.t * 0.1); r: 0.45 + 0.05 * l.pouls }
    }
    // Pluie ou neige : cachées (donc pas dessinées) quand le fond est en pause, pour ne pas les laisser figées en l'air
    Gouttes {
        anchors.fill: parent
        t: l.t; actif: l.pluie || l.neige; neige: l.neige
        opacity: l.anime && actif ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 800 } }
    }
}
