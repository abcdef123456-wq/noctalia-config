// Ligne d'action sous une carte texte de la page Presse-papiers (Presse.qml), selon ce que dit le texte (PresseAnalyse.qml) :
//   couleur  une pastille de la couleur et ses conversions (hex, rgb, hsl)
//   lien     « Ouvrir » (xdg-open, adresse http ou https vérifiée, en argv)
//   chemin   « Ouvrir le dossier » (seulement si le chemin existe : un test à l'affichage de la carte)
//   calcul   le résultat avec qalc, sans réseau (chiffres et opérateurs seulement), borné à 2 s, seulement à l'affichage de la carte
//   nombre   les écritures hexadécimale et binaire
// Rien n'est lancé sans clic, sauf le test du chemin et l'aperçu du calcul. Rien du tout pendant un partage d'écran
// (masque), écran éteint ou réglage ILE_PRESSE_ACTIONS=non. Les textes sont affichés en texte brut.
import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: a
    property string texte: ""
    property bool masque: false
    readonly property bool active: Reglages.val("ILE_PRESSE_ACTIONS", "oui") !== "non" && !masque
    readonly property string maison: Quickshell.env("HOME") || ""
    readonly property var info: active ? PresseAnalyse.detecter(texte, maison) : null
    readonly property string genre: info ? info.genre : ""
    property string nature: ""             // chemin : d (dossier) ou f (fichier) une fois vu, vide s'il n'existe pas
    property string calcule: ""
    // La ligne n'existe que si elle a quelque chose à dire ou à faire
    readonly property bool utile: genre === "couleur" || genre === "url" || genre === "nombre"
                                  || (genre === "chemin" && nature !== "") || (genre === "calcul" && calcule !== "")
    readonly property bool voir: active && visible && Etat.ecranVu
    height: 34

    function ouvrir() {
        if (!utile) return
        if (genre === "url" && /^https?:\/\/[^\s'"<>`\\]+$/i.test(info.url)) Quickshell.execDetached(["xdg-open", info.url])
        else if (genre === "chemin") Quickshell.execDetached(["xdg-open", nature === "d" ? info.chemin : PresseAnalyse.dossierDe(info.chemin)])
    }

    Process {
        id: vue
        command: ["sh", "-c", "if [ -d \"$1\" ]; then echo d; elif [ -e \"$1\" ]; then echo f; fi", "sh", a.genre === "chemin" ? a.info.chemin : "/"]
        running: a.voir && a.genre === "chemin"
        stdout: StdioCollector { onStreamFinished: a.nature = text.trim() }
    }
    Process {
        id: qalc
        command: ["timeout", "2", "qalc", "-t", a.genre === "calcul" ? a.info.expr : "0"]
        running: a.voir && a.genre === "calcul" && PresseAnalyse.qalcDispo === 1
        stdout: StdioCollector { onStreamFinished: a.calcule = PresseAnalyse.resultat(text, a.info ? a.info.expr : "") }
    }
    onVoirChanged: if (voir && genre === "calcul" && PresseAnalyse.qalcDispo < 0) PresseAnalyse.demandeQalc = true

    Row {
        visible: a.utile
        x: 14; anchors.verticalCenter: parent.verticalCenter; spacing: 8
        Rectangle {
            visible: a.genre === "couleur"
            anchors.verticalCenter: parent.verticalCenter; width: 18; height: 18; radius: 9
            color: a.genre === "couleur" ? Qt.rgba(a.info.r / 255, a.info.g / 255, a.info.b / 255, 1) : "transparent"
            border.width: 1; border.color: Couleurs.gris3
        }
        Ico { visible: a.genre === "calcul" || a.genre === "nombre"; anchors.verticalCenter: parent.verticalCenter; nom: "calculate"; taille: 16; color: Couleurs.texteSec }
        Texte {
            anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.pixelSize: 12
            width: Math.min(implicitWidth, a.width - 150)
            text: a.genre === "couleur" ? a.info.hex + " · " + a.info.rgb + " · " + a.info.hsl
                : a.genre === "calcul" ? "= " + a.calcule
                : a.genre === "nombre" ? a.info.hex + " · " + a.info.bin
                : a.genre === "url" ? a.info.url.replace(/^https?:\/\//i, "")
                : a.genre === "chemin" ? a.info.chemin : ""
        }
        Rectangle {
            id: bouton
            objectName: "nc-presse-ouvrir"
            visible: a.genre === "url" || a.genre === "chemin"
            anchors.verticalCenter: parent.verticalCenter; height: 24; width: etiquette.implicitWidth + 22; radius: 12
            color: zone.containsMouse ? Couleurs.accentClair : Couleurs.accent
            Texte {
                id: etiquette
                anchors.centerIn: parent; font.pixelSize: 12; font.weight: Font.DemiBold; color: Couleurs.surAccent
                text: a.genre === "chemin" ? Reglages.t("Ouvrir le dossier", "Open folder") : Reglages.t("Ouvrir", "Open")
            }
            MouseArea { id: zone; anchors.fill: parent; hoverEnabled: true; onClicked: a.ouvrir() }
            Accessible.role: Accessible.Button
            Accessible.name: etiquette.text
        }
    }
}
