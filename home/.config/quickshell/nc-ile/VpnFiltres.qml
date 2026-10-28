// Les filtres de la liste VPN : les pastilles « Tous », une par fournisseur (Proton, Nord, Mullvad ; CyberGhost seulement si un de ses
// profils existe : VpnEtat.fournisseurs), « Profils perso » ; dessous le champ « Rechercher un pays, un serveur ou un profil… ».
// Deux propriétés en sortie : filtre (tous, proton, nord, mullvad, cyberghost, perso) et recherche (texte tapé, brut).
import QtQuick

Column {
    id: f
    property string filtre: "tous"
    property alias recherche: champ.text
    function donnerFocus() { champ.forceActiveFocus() }
    spacing: 10

    readonly property var pastilles: {
        var l = [{ id: "tous", nom: Reglages.t("Tous", "All") }]
        VpnEtat.fournisseurs.forEach(p => l.push({ id: p.id, nom: p.id === "proton" ? "Proton" : (p.id === "nord" ? "Nord" : p.fournisseur) }))
        l.push({ id: "perso", nom: Reglages.t("Profils perso", "My profiles") })
        return l
    }

    Flow {
        objectName: "nc-vpn-filtres"
        width: parent.width; spacing: 8
        Repeater {
            model: f.pastilles
            VpnPastille {
                objectName: "nc-vpn-filtre-" + modelData.id
                texte: modelData.nom
                choisi: f.filtre === modelData.id
                onClic: f.filtre = modelData.id
            }
        }
    }
    Rectangle {
        width: parent.width; height: 38; radius: 19
        color: Qt.alpha(Couleurs.carte, 0.6)
        border.width: 1; border.color: champ.activeFocus ? Qt.alpha(Couleurs.accent, 0.7) : Qt.alpha(Couleurs.texte, 0.1)
        Ico { id: loupe; x: 14; anchors.verticalCenter: parent.verticalCenter; nom: "search"; taille: 18; color: Couleurs.texteSec }
        TextInput {
            id: champ
            objectName: "nc-vpn-recherche"
            anchors.left: loupe.right; anchors.leftMargin: 8; anchors.right: parent.right; anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            color: Couleurs.texte; font.pixelSize: 13; font.family: "Adwaita Sans"
            selectionColor: Qt.alpha(Couleurs.accent, 0.5); clip: true
            maximumLength: 60
            inputMethodHints: Qt.ImhNoPredictiveText
        }
        Texte {
            visible: champ.text === ""
            anchors.left: champ.left; anchors.right: champ.right; anchors.verticalCenter: parent.verticalCenter
            text: Reglages.t("Rechercher un pays, un serveur ou un profil…", "Search a country, a server or a profile…")
            secondaire: true; font.pixelSize: 13
        }
    }
}
