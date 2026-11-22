// Vue « QR code » de la page Presse-papiers (Presse.qml) : le QR du texte choisi (nc-qr, qrencode) avec le début du texte
// en dessous et « Retour ». Le texte passe à nc-qr par son entrée standard, jamais en argument. Le PNG (dossier privé de
// $XDG_RUNTIME_DIR) est supprimé dès qu'on quitte la vue. Pendant un partage d'écran : un message, rien n'est lancé.
import QtQuick
import Quickshell
import Quickshell.Io

Rectangle {
    id: q
    property string texte: ""
    property bool masque: false
    property string png: ""
    property bool echec: false
    signal fermer()
    visible: texte !== ""
    color: Couleurs.fond
    onVisibleChanged: if (!visible) { effacer(); fab.stdinEnabled = true }   // stdin rouvert pour le prochain QR
    function effacer() {
        if (png !== "") Quickshell.execDetached(["rm", "-f", "--", png])
        png = ""; echec = false
    }

    Process {
        id: fab
        command: [Quickshell.env("HOME") + "/.local/bin/nc-qr"]
        stdinEnabled: true
        running: q.visible && !q.masque
        onStarted: { write(q.texte); stdinEnabled = false }
        stdout: StdioCollector { onStreamFinished: { let c = text.trim(); if (c.indexOf("/") === 0) q.png = c } }
        onExited: code => q.echec = code !== 0
    }

    Column {
        anchors.centerIn: parent; spacing: 12; width: parent.width - 40
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter; width: 250; height: 250; radius: Couleurs.rayon(14, width, height); color: "white"
            visible: !q.masque && q.png !== ""
            Image { anchors.fill: parent; anchors.margins: 12; fillMode: Image.PreserveAspectFit; smooth: false
                    source: q.png !== "" ? "file://" + q.png.split("/").map(encodeURIComponent).join("/") : "" }
        }
        Texte {
            visible: q.masque || q.echec
            width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; secondaire: true
            text: q.masque ? Reglages.t("QR caché pendant le partage d'écran", "QR hidden while sharing the screen")
                           : Reglages.t("Impossible de fabriquer le QR (texte de plus de 2000 caractères ?)", "Cannot make the QR (text over 2000 characters?)")
        }
        Texte {
            visible: !q.masque
            width: parent.width; horizontalAlignment: Text.AlignHCenter; maximumLineCount: 2; wrapMode: Text.Wrap
            font.pixelSize: 12; secondaire: true
            text: q.texte.replace(/\s+/g, " ").trim().slice(0, 120)
        }
        Rectangle {
            objectName: "nc-presse-qr-retour"
            anchors.horizontalCenter: parent.horizontalCenter; height: 30; width: lb.implicitWidth + 28; radius: Couleurs.rayon(15, width, height)
            color: zr.containsMouse ? Couleurs.accentClair : Couleurs.accent
            Texte { id: lb; anchors.centerIn: parent; font.pixelSize: 13; font.weight: Font.DemiBold; color: Couleurs.surAccent; text: Reglages.t("Retour", "Back") }
            MouseArea { id: zr; anchors.fill: parent; hoverEnabled: true; onClicked: q.fermer() }
            Accessible.role: Accessible.Button
            Accessible.name: Reglages.t("Retour à la liste", "Back to the list")
        }
    }
}
