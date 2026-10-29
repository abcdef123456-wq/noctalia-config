// Sous la carte d'un fournisseur ABSENT (VpnCarteFournisseur.qml) : comment avoir son client.
//   - installation.mode « auto » : le bouton « Installer » et une phrase claire (un terminal s'ouvre, sudo y demande le mot de passe) ;
//     rien ne se lance sans ce clic, jamais automatiquement ;
//   - installation.mode « guide » : le bouton « Voir comment installer » déplie les étapes (texte fixe du dépôt, déjà filtré par nc-vpn)
//     et « Ouvrir la page officielle » ouvre le lien (xdg-open, en argv). Rien n'est exécuté.
// Le modèle `installation` vient de VpnEtat (nc-vpn fournisseurs-json) : {mode, lien, etapes}. Sans lui, rien n'est affiché.
import QtQuick

Column {
    id: i
    signal installer(string ident)                // « Installer » : la fenêtre se ferme, un terminal s'ouvre (Vpn.qml)
    signal ouvrirLien(string lien)                // « Ouvrir la page officielle »
    property string ident: ""
    property var installation: null
    property bool etapesVisibles: false
    readonly property bool auto: installation !== null && installation !== undefined && installation.mode === "auto"
    readonly property bool guide: installation !== null && installation !== undefined && installation.mode === "guide"
    spacing: 8
    visible: auto || guide

    Texte {
        objectName: "nc-vpn-installer-phrase"
        visible: i.auto
        width: parent.width; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 12
        text: Reglages.t("Ouvre un terminal ; ton mot de passe sera demandé par sudo. Chaque étape est affichée avant d'être lancée.",
                         "Opens a terminal; your password will be asked by sudo. Each step is shown before it runs.")
    }
    Rectangle {
        objectName: "nc-vpn-installer-bouton"
        visible: i.auto
        width: libelleInstaller.implicitWidth + 32; height: 32; radius: 16
        color: zoneInstaller.containsMouse ? Qt.alpha(Couleurs.accent, 0.4) : Qt.alpha(Couleurs.accent, 0.25)
        opacity: VpnEtat.cible === "" && VpnEtat.installation === "" ? 1 : 0.6
        Accessible.role: Accessible.Button
        Accessible.name: libelleInstaller.text
        Texte { id: libelleInstaller; anchors.centerIn: parent; text: Reglages.t("Installer", "Install"); font.pixelSize: 12; font.weight: Font.DemiBold }
        MouseArea { id: zoneInstaller; anchors.fill: parent; hoverEnabled: true
                    enabled: VpnEtat.cible === "" && VpnEtat.installation === ""; onClicked: i.installer(i.ident) }
    }

    Rectangle {
        objectName: "nc-vpn-installer-voir"
        visible: i.guide
        width: libelleVoir.implicitWidth + 32; height: 32; radius: 16
        color: zoneVoir.containsMouse ? Qt.alpha(Couleurs.accent, 0.4) : Qt.alpha(Couleurs.accent, 0.25)
        Accessible.role: Accessible.Button
        Accessible.name: libelleVoir.text
        Texte { id: libelleVoir; anchors.centerIn: parent; text: Reglages.t("Voir comment installer", "See how to install"); font.pixelSize: 12; font.weight: Font.DemiBold }
        MouseArea { id: zoneVoir; anchors.fill: parent; hoverEnabled: true; onClicked: i.etapesVisibles = !i.etapesVisibles }
    }
    Column {
        objectName: "nc-vpn-installer-etapes"
        visible: i.guide && i.etapesVisibles
        width: parent.width; spacing: 4
        Repeater {
            model: i.guide ? i.installation.etapes : []
            Texte { width: i.width; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 12; text: (index + 1) + ". " + modelData }
        }
    }
    Rectangle {
        objectName: "nc-vpn-installer-page"
        visible: i.guide && i.etapesVisibles
        width: libellePage.implicitWidth + 32; height: 32; radius: 16
        color: zonePage.containsMouse ? Qt.alpha(Couleurs.accent, 0.4) : Qt.alpha(Couleurs.accent, 0.25)
        Accessible.role: Accessible.Button
        Accessible.name: libellePage.text
        Texte { id: libellePage; anchors.centerIn: parent; text: Reglages.t("Ouvrir la page officielle", "Open the official page"); font.pixelSize: 12; font.weight: Font.DemiBold }
        MouseArea { id: zonePage; anchors.fill: parent; hoverEnabled: true; onClicked: i.ouvrirLien(i.installation.lien) }
    }
}
