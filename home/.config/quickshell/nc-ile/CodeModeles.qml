// Le modèle d'un nouveau projet vide (Code.qml, mode « nouveau ») en pastilles : vide, Python, C, page web. Le choix part
// avec `nc-code --nouveau NOM --modele X`. Départ : le modèle par défaut des réglages (CODE_MODELE).
import QtQuick

Row {
    id: modeles
    property string modele: "vide"
    signal choisir(string valeur)
    spacing: 6
    Repeater {
        model: [{ v: "vide", t: Reglages.t("Vide", "Empty") }, { v: "python", t: "Python" }, { v: "c", t: "C" },
                { v: "web", t: Reglages.t("Page web", "Web page") }]
        PastilleChoix {
            required property var modelData
            objectName: "nc-code-modele-" + modelData.v
            texte: modelData.t
            actif: modeles.modele === modelData.v
            onClic: modeles.choisir(modelData.v)
        }
    }
}
