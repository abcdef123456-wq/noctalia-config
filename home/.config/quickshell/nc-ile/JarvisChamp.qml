import QtQuick
Column {
    id: champ
    property string titre
    property string aide: ""
    property bool secret: false
    property bool booleen: false
    property alias texte: input.text
    signal change(string valeur)
    spacing: 6
    height: implicitHeight
    Texte { width: parent.width; text: champ.titre; textFormat: Text.PlainText; secondaire: true; font.pixelSize: 12 }
    Rectangle {
        width: parent.width; height: 42; radius: 12; color: Couleurs.gris2
        border.width: input.activeFocus ? 1 : 0; border.color: Couleurs.accent
        TextInput {
            id: input
            visible: !champ.booleen
            anchors.fill: parent; anchors.margins: 12
            verticalAlignment: TextInput.AlignVCenter
            clip: true; maximumLength: 4000; selectByMouse: true
            color: Couleurs.texte; selectionColor: Couleurs.accent
            echoMode: champ.secret ? TextInput.Password : TextInput.Normal
            font.family: "Adwaita Sans"; font.pixelSize: 13
            onTextEdited: champ.change(text)
        }
        JarvisBouton { anchors.fill: parent; visible: champ.booleen; texte: input.text === "1" ? Reglages.t("Activé", "Enabled") : Reglages.t("Désactivé", "Disabled"); primaire: input.text === "1"; onClic: { input.text = input.text === "1" ? "0" : "1"; champ.change(input.text) } }
        Texte { anchors.fill: parent; anchors.margins: 12; text: champ.aide; visible: !champ.booleen && !input.text && !input.activeFocus; secondaire: true; font.pixelSize: 12 }
    }
}
