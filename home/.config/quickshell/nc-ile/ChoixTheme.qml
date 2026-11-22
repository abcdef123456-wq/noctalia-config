// Carrousel des thèmes (Super + Alt + T, `qs -c nc-ile ipc call ile themes`, ou « Thèmes » dans la recherche). Une VRAIE fenêtre
// (FloatingWindow), titre « Thèmes ». Chaque carte est un mini bureau dessiné en direct avec les vraies valeurs du thème :
// fond de départ (miniature si elle existe, sinon la couleur de fond de la palette), mini-pilule (rayon, police, majuscules,
// contour), deux fenêtres (arrondi et bordure FENETRES_*), pastilles de la palette, nom. Rien n'est généré dans un fichier.
// Les thèmes viennent de `nc-reglages themes --json` (lecture seule). Gauche/droite ou molette : changer de carte ;
// Entrée (ou clic sur la carte du milieu) : `nc-reglages set STYLE <nom>` ; Échap : fermer sans rien changer.
// Rien ne tourne fermé (la fenêtre n'existe qu'ouverte).
import QtQuick
import Quickshell
import Quickshell.Io

FloatingWindow {
    id: ct
    signal fermer()
    title: Reglages.t("Thèmes", "Themes")
    color: "transparent"
    implicitWidth: ct.largeurFenetre
    implicitHeight: 360
    minimumSize: Qt.size(420, 300)
    onClosed: ct.fermer()
    onVisibleChanged: if (!visible) ct.fermer()

    readonly property real largeurEcran: ct.screen ? ct.screen.width : 1600
    readonly property int largeurFenetre: Math.min(1060, Math.round(largeurEcran * 0.92))
    readonly property int visibles: ct.largeurFenetre >= 900 ? 5 : 3      // toujours impair : une carte au milieu
    readonly property bool verre: Reglages.val("FENETRES_FLOU", "oui") !== "non" && !Reglages.sobre
    readonly property string bin: Quickshell.env("HOME") + "/.local/bin/nc-reglages"
    property var themes: []
    property int centre: 0
    property alias cible: carte         // pour le rendu hors écran

    function aller(delta) { ct.centre = Math.max(0, Math.min(ct.themes.length - 1, ct.centre + delta)) }
    function valider() {
        if (ct.themes.length === 0 || appliquer.running) return
        appliquer.command = [ct.bin, "set", "STYLE", ct.themes[ct.centre].nom]
        appliquer.running = true
    }
    function quitter() { ct.fermer() }

    // Valeur d'un réglage du thème, sinon le défaut d'aujourd'hui
    function rv(t, cle, defaut) { return t && t.reglages && t.reglages[cle] !== undefined && t.reglages[cle] !== "" ? String(t.reglages[cle]) : defaut }
    function pct(t) {
        var r = rv(t, "ILE_RAYON", "auto")
        var noms = { "auto": 100, "normal": 100, "carre": 0, "doux": 50, "rond": 200 }
        if (noms[r] !== undefined) return noms[r]
        var n = /^[0-9]+$/.test(r) ? parseInt(r) : 100
        return n <= 200 ? n : 100
    }
    function nombre(t, cle, defaut, maxi) { var n = Number(rv(t, cle, defaut)); return isNaN(n) ? defaut : Math.max(0, Math.min(maxi, n)) }

    Process {
        id: lire
        command: [ct.bin, "themes", "--json"]
        running: true
        stdout: StdioCollector { onStreamFinished: {
            var l = []
            try { l = JSON.parse(text) } catch (e) {}
            if (!Array.isArray(l)) l = []
            ct.themes = l
            var i = l.findIndex(x => x.actif)          // la carte du thème actif est au milieu à l'ouverture
            ct.centre = i >= 0 ? i : 0
        } }
    }
    Process { id: appliquer; onExited: ct.fermer() }

    Item {
        id: carte
        objectName: "nc-themes-carte"
        anchors.fill: parent
        focus: true
        Keys.onEscapePressed: ct.quitter()
        Keys.onLeftPressed: ct.aller(-1)
        Keys.onRightPressed: ct.aller(1)
        Keys.onReturnPressed: ct.valider()
        Keys.onEnterPressed: ct.valider()
        Rectangle { anchors.fill: parent; color: Qt.alpha(Couleurs.fond, ct.verre ? 0.62 : 0.92) }
        MouseArea {
            anchors.fill: parent
            onWheel: wheel => { ct.aller(wheel.angleDelta.y < 0 || wheel.angleDelta.x < 0 ? 1 : -1) }
        }

        Text {
            textFormat: Text.PlainText
            anchors.horizontalCenter: parent.horizontalCenter; y: 14
            text: Reglages.t("Choisir un thème", "Choose a theme")
            color: Couleurs.texte; font.pixelSize: 15; font.bold: true; font.family: Couleurs.police
        }
        Text {
            textFormat: Text.PlainText
            anchors.horizontalCenter: parent.horizontalCenter; y: parent.height - 28
            text: Reglages.t("← → choisir · Entrée appliquer · Échap fermer", "← → choose · Enter apply · Esc close")
            color: Couleurs.texteSec; font.pixelSize: 11; font.family: Couleurs.police
        }

        Repeater {
            model: ct.themes.length > 0 ? ct.visibles : 0
            delegate: Item {
                id: c
                readonly property int d: index - (ct.visibles - 1) / 2         // -2..2 : 0 est la carte du milieu
                readonly property int pos: ct.centre + d
                readonly property var t: pos >= 0 && pos < ct.themes.length ? ct.themes[pos] : null
                readonly property var col: t ? t.couleurs : ({})
                readonly property color surface: col.surface || "#1e1f24"
                readonly property color primaire: col.primary || "#8ab4f8"
                visible: t !== null
                objectName: "nc-themes-" + (d === 0 ? "centre" : "autre") + "-" + index
                width: 200; height: 240
                x: (carte.width - width) / 2 + d * 190
                y: (carte.height - height) / 2
                scale: d === 0 ? 1.0 : 0.8
                opacity: d === 0 ? 1.0 : 0.75
                z: d === 0 ? 1 : 0
                Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

                Rectangle {
                    anchors.fill: parent; radius: 16
                    color: Qt.alpha(Couleurs.carte, 0.9)
                    border.width: c.d === 0 ? 2 : 1
                    border.color: c.d === 0 ? c.primaire : Couleurs.gris3
                }
                // Le mini bureau
                Rectangle {
                    id: bureau
                    x: 10; y: 10; width: parent.width - 20; height: 150; radius: 10
                    color: c.surface; clip: true
                    Image {
                        anchors.fill: parent
                        source: c.t && c.t.miniature ? "file://" + c.t.miniature : ""
                        fillMode: Image.PreserveAspectCrop; asynchronous: true
                        sourceSize.width: 360                // un fond de 3840 px décodé en petit
                        visible: status === Image.Ready
                    }
                    // La mini-pilule, avec les vraies valeurs du thème
                    Rectangle {
                        id: pilule
                        objectName: "nc-themes-pilule"
                        anchors.horizontalCenter: parent.horizontalCenter; y: 8
                        width: 74; height: 18
                        readonly property bool noir: ct.rv(c.t, "ILE_STYLE", "terminal") === "noir"
                        readonly property string contour: ct.rv(c.t, "ILE_CONTOUR", "degrade")
                        radius: Math.min(height / 2, 9 * ct.pct(c.t) / 100)
                        color: noir ? "#000000" : c.surface
                        border.width: contour === "aucun" ? 0 : Math.max(1, Math.round(ct.nombre(c.t, "ILE_CONTOUR_EPAISSEUR", 2, 4) / 2))
                        border.color: contour === "discret" ? Qt.alpha(c.primaire, 0.4) : c.primaire
                        Text {
                            textFormat: Text.PlainText
                            anchors.centerIn: parent
                            text: { var s = Reglages.t("Île 12:30", "Island 12:30"); return ct.rv(c.t, "ILE_MAJUSCULES", "non") === "oui" ? s.toUpperCase() : s }
                            color: c.col.onSurface || "#e3e3e8"
                            font.pixelSize: 9
                            font.family: Qt.fontFamilies().indexOf(ct.rv(c.t, "ILE_POLICE", "")) >= 0 ? ct.rv(c.t, "ILE_POLICE", "") : Couleurs.police
                        }
                    }
                    // Deux petites fenêtres : arrondi et bordure du thème
                    Repeater {
                        model: 2
                        delegate: Rectangle {
                            x: 12 + index * 58; y: 44 + index * 22
                            width: 64; height: 52
                            radius: Math.min(height / 2, ct.nombre(c.t, "FENETRES_ARRONDI", 14, 20) * 0.6)
                            color: Qt.alpha(c.surface, 0.88)
                            border.width: ct.nombre(c.t, "FENETRES_BORDURE", 2, 4) > 0 ? 1 : 0
                            border.color: index === 0 ? c.primaire : (c.col.secondary || c.primaire)
                        }
                    }
                }
                // Les pastilles de la palette
                Row {
                    anchors.horizontalCenter: parent.horizontalCenter; y: 170; spacing: 6
                    Repeater {
                        model: [c.col.primary, c.col.secondary, c.col.tertiary, c.col.onSurface]
                        delegate: Rectangle { width: 14; height: 14; radius: 7; color: modelData || "#808080"; border.width: 1; border.color: Qt.alpha("#ffffff", 0.25) }
                    }
                }
                Text {
                    textFormat: Text.PlainText
                    anchors.horizontalCenter: parent.horizontalCenter; y: 194; width: parent.width - 16
                    horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
                    text: c.t ? c.t.libelle : ""
                    color: Couleurs.texte; font.pixelSize: 13; font.bold: c.d === 0; font.family: Couleurs.police
                }
                Text {
                    textFormat: Text.PlainText
                    anchors.horizontalCenter: parent.horizontalCenter; y: 214
                    visible: c.t !== null && c.t.actif === true
                    text: Reglages.t("Actif", "Active")
                    color: c.primaire; font.pixelSize: 11; font.family: Couleurs.police
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: { if (c.d === 0) ct.valider(); else ct.centre = c.pos }
                }
            }
        }
    }
}
