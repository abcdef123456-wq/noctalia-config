// Champ d'un formulaire du cockpit JARVIS : nom au-dessus, saisie dans une pastille (accent quand elle a le focus) ;
// secret : masqué ; booléen : un bouton Activé / Désactivé
import QtQuick
Column {
    id: champ
    property string titre
    property string aide: ""
    property string erreur: ""                 // message sous le champ (valeur refusée) ; vide : rien
    property bool secret: false
    property bool booleen: false
    property alias texte: input.text
    signal change(string valeur)
    spacing: 5
    height: implicitHeight
    Texte { width: parent.width; text: champ.titre; textFormat: Text.PlainText; secondaire: true; font.pixelSize: 12; leftPadding: 4 }
    Rectangle {
        width: parent.width; height: 38; radius: 19; color: Couleurs.gris2
        border.width: 1; border.color: input.activeFocus ? Couleurs.accent : "transparent"
        TextInput {
            id: input
            visible: !champ.booleen
            anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 14
            verticalAlignment: TextInput.AlignVCenter
            clip: true; maximumLength: 4000; selectByMouse: true
            color: Couleurs.texte; selectionColor: Couleurs.accent
            echoMode: champ.secret ? TextInput.Password : TextInput.Normal
            font.pixelSize: 13
            onTextEdited: champ.change(text)
        }
        JarvisBouton { anchors.fill: parent; visible: champ.booleen; texte: input.text === "1" ? Reglages.t("Activé", "Enabled") : Reglages.t("Désactivé", "Disabled"); primaire: input.text === "1"; onClic: { input.text = input.text === "1" ? "0" : "1"; champ.change(input.text) } }
        Texte { anchors.fill: parent; anchors.leftMargin: 14; verticalAlignment: Text.AlignVCenter; text: champ.aide; visible: !champ.booleen && !input.text && !input.activeFocus; secondaire: true; font.pixelSize: 12 }
    }
    Texte { objectName: "nc-jarvis-champ-erreur"; width: parent.width; visible: champ.erreur !== ""; text: champ.erreur; textFormat: Text.PlainText
            wrapMode: Text.Wrap; elide: Text.ElideNone; color: Couleurs.rouge; font.pixelSize: 12; leftPadding: 4 }
}
