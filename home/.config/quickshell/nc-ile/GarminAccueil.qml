// Carte d'accueil de Garmin.qml quand rien n'est connecté : Installer le connecteur, Connecter, Essayer la démo
import QtQuick

Rectangle {
    id: a
    radius: Couleurs.rayon(22, width, height)
    color: Qt.alpha(Couleurs.carte, 0.7)
    implicitHeight: col.implicitHeight + 36
    Column {
        id: col
        x: 18; y: 18; width: parent.width - 36; spacing: 10
        Texte {
            width: parent.width; font.pixelSize: 16; font.weight: Font.DemiBold; wrapMode: Text.Wrap
            text: Reglages.t("Relier ta montre Garmin", "Connect your Garmin watch")
        }
        Texte {
            objectName: "nc-garmin-mention"
            width: parent.width; wrapMode: Text.Wrap; secondaire: true
            text: Reglages.t("Connecteur non officiel : peut cesser de marcher si Garmin change son service. Les données restent sur cet ordinateur.",
                             "Unofficial connector: may stop working if Garmin changes its service. Data stays on this computer.")
        }
        Flow {
            width: parent.width; spacing: 8
            Repeater {
                model: [
                    { n: "inst", t: Reglages.t("Installer le connecteur", "Install the connector"), v: !GarminEtat.installe, f: () => GarminEtat.installer() },
                    { n: "conn", t: Reglages.t("Connecter", "Connect"), v: GarminEtat.installe, f: () => GarminEtat.connecter() },
                    { n: "demo", t: Reglages.t("Essayer la démo", "Try the demo"), v: true, f: () => GarminEtat.demoBasculer() }
                ]
                delegate: Rectangle {
                    required property var modelData
                    visible: modelData.v
                    objectName: "nc-garmin-bouton-" + modelData.n
                    height: 34; width: etiq.implicitWidth + 28; radius: Couleurs.rayon(17, width, height)
                    color: modelData.n === "demo" ? Couleurs.carteSurvol : Couleurs.accent
                    Texte {
                        id: etiq; anchors.centerIn: parent; text: parent.modelData.t
                        color: parent.modelData.n === "demo" ? Couleurs.texte : Couleurs.surAccent
                    }
                    MouseArea { anchors.fill: parent; onClicked: parent.modelData.f() }
                }
            }
        }
    }
}
