import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Io

WidgetBarreLibelle {
    id: bouton
    readonly property bool espaceVide: barre.type === "spacer"
    readonly property string image: barre.definition.custom_image || (barre.nom === "logo" && !glypheTabler
        ? Quickshell.iconPath("noctalia", true) : "")
    readonly property var mode: {
        switch (barre.type) {
        case "control-center": case "logo": return { icone: "dashboard", nom: Reglages.t("Centre de contrôle", "Control Center"), action: () => barre.page("centre") }
        case "launcher": case "app-launcher": return { icone: "apps", nom: Reglages.t("Lanceur d’applications", "Application launcher"), action: () => Etat.chercher(barre.ecran ? barre.ecran.name : "") }
        case "session": return { icone: "power_settings_new", nom: Reglages.t("Menu de session", "Session menu"), action: () => Quickshell.execDetached(["noctalia", "msg", "panel-toggle", "session"]) }
        default: return { icone: "", nom: "", action: null }
        }
    }
    readonly property string glypheTabler: barre.definition.glyph || ""
    readonly property int code: {
        const cle = glypheTabler
        if (!cle) return 0
        if (/^(U\+|0x)[\da-f]+$/i.test(cle)) return parseInt(cle.slice(2), 16)
        try { const g = JSON.parse(tabler.text())[cle]; return g ? parseInt(g.codepoint.slice(2), 16) : 0 } catch (e) { return 0 }
    }
    affiche: espaceVide ? longueur > 0 : largeurContenu > 0 && hauteurContenu > 0
    readonly property real longueur: Number(barre.definition.length ?? 12)
    implicitWidth: espaceVide ? (barre.vertical ? 1 : longueur) : largeurContenu
    implicitHeight: espaceVide ? (barre.vertical ? longueur : 1) : hauteurContenu
    glyphe: mode.icone
    encreGlyphe: barre.teinte(barre.definition.color, barre.premierPlan)
    libelle: barre.definition.text || barre.definition.custom_label || ""
    infobulle: mode.nom || libelle
    maximum: barre.vertical ? 34 : 240
    interagir: barre.definition.interactive ?? !espaceVide
    gauche: mode.action
    visuel: image !== "" && barre.definition.show_glyph !== false ? imagePerso
        : code > 0 && code <= 0x10ffff && policeTabler.status === FontLoader.Ready && barre.definition.show_glyph !== false ? glyphePerso : null

    // La police est livrée par Noctalia, uniquement chargée pour un glyphe explicitement configuré.
    FontLoader { id: policeTabler; source: bouton.glypheTabler ? "file:///usr/share/noctalia/assets/fonts/noctalia-tabler.ttf" : "" }
    FileView {
        id: tabler
        path: bouton.glypheTabler && !/^(U\+|0x)/i.test(bouton.glypheTabler) ? "/usr/share/noctalia/assets/fonts/tabler.json" : ""
        printErrors: false
    }
    Component {
        id: glyphePerso
        Item {
            implicitWidth: bouton.barre.tailleIcone; implicitHeight: implicitWidth
            Text {
                anchors.centerIn: parent
                text: String.fromCodePoint(bouton.code)
                font.family: policeTabler.name; font.pixelSize: bouton.barre.tailleIcone
                color: bouton.encreGlyphe
            }
        }
    }
    Component {
        id: imagePerso
        Item {
            implicitWidth: bouton.barre.tailleIcone; implicitHeight: implicitWidth
            Image {
                anchors.fill: parent
                source: bouton.image.startsWith("/") ? "file://" + bouton.image : bouton.image
                sourceSize: Qt.size(width * 2, height * 2)
                fillMode: Image.PreserveAspectFit
                layer.enabled: bouton.barre.definition.custom_image_colorize === true
                layer.effect: MultiEffect { colorization: 1; colorizationColor: bouton.encreGlyphe }
            }
        }
    }
}
