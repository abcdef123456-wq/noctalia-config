// Le bouton ⚙ de l'île ouverte (en bas à droite, sous les points de page) : ouvre la fenêtre des réglages sur la section de la
// page affichée (`vue`), et ferme l'île. Chaque page a sa section : l'énergie pour la batterie et le jeu, le son pour le
// son, les agents pour Claude et l'assistant, etc. ; les pages sans section à elles (réseau, météo, presse-papiers,
// résumé, concentration…) ouvrent « Île », où se trouvent leurs réglages.
import QtQuick

BoutonReglages {
    id: bouton
    property string vue: ""
    readonly property var sections: ({
        charge: "Énergie", jeu: "Énergie", sante: "Île", son: "Son et luminosité", bluetooth: "Son et luminosité",
        claude: "Agents IA (coucou)", assistant: "Agents IA (coucou)", notifications: "Notifications",
        systeme: "Mises à jour", calendrier: "Intégration Google", fenetres: "Fenêtres", terminal: "Terminal"
    })
    objectName: "nc-ile-reglages"
    taille: 26
    opacity: zoneSurvol.hovered ? 1 : 0.7
    section: sections[vue] || "Île"
    aide: Reglages.t("Réglages de cette page", "Settings for this page")
    HoverHandler { id: zoneSurvol }
}
