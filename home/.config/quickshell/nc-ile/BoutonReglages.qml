// Le bouton ⚙ des panneaux : ouvre la fenêtre des réglages (nc-reglages fenetre) directement sur la section `section`
// (son nom français ou anglais, comme « nc-reglages fenetre Terminal »). En argv, jamais une ligne de shell.
import QtQuick
import Quickshell

Rectangle {
    id: bouton
    property string section: ""
    property string aide: Reglages.t("Réglages", "Settings")
    property real taille: 30
    signal ouvert()
    width: taille; height: taille; radius: taille / 2
    color: zone.containsMouse ? Qt.alpha(Couleurs.accent, 0.25) : Qt.alpha(Couleurs.carte, 0.6)
    border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.1)
    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
    Accessible.role: Accessible.Button
    Accessible.name: bouton.aide
    function ouvrir() {
        var cmd = [Quickshell.env("HOME") + "/.local/bin/nc-reglages", "fenetre"]
        if (section !== "") cmd.push(section)
        Quickshell.execDetached(cmd)
        ouvert()
    }
    Ico { anchors.centerIn: parent; nom: "settings"; taille: Math.round(bouton.taille * 0.53); color: zone.containsMouse ? Couleurs.accent : Couleurs.texteSec }
    MouseArea { id: zone; objectName: "bouton-reglages-zone"; anchors.fill: parent; hoverEnabled: true; onClicked: bouton.ouvrir() }
}
