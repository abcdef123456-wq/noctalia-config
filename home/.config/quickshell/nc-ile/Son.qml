// Page « Son » : sortie et micro par défaut, et volume de chaque application (comme l'onglet Audio de Noctalia)
import QtQuick
import Quickshell.Services.Pipewire

Item {
    id: son
    readonly property var noeuds: Pipewire.nodes.values
    readonly property var sorties: noeuds.filter(n => n.isSink && !n.isStream && n.audio)
    readonly property var entrees: noeuds.filter(n => !n.isSink && !n.isStream && n.audio && (n.properties["media.class"] || "").indexOf("Source") >= 0)
    readonly property var applis: noeuds.filter(n => n.isStream && n.audio && !n.isSink)
    PwObjectTracker { objects: son.sorties.concat(son.entrees, son.applis) }

    function nom(n) {
        return n.properties["application.name"] || n.description || n.nickname || n.name || "?"
    }

    component Titre: Texte { font.pixelSize: 12; font.weight: Font.Bold; secondaire: true; height: 22 }

    // Ligne d'appareil : rond bleu si c'est celui utilisé
    component Appareil: Module {
        id: ap
        property var noeud
        property bool defaut
        property string icone
        width: son.width; height: 50; radius: 16; cliquable: true
        Row {
            anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 10; spacing: 10
            Rectangle {
                width: 32; height: 32; radius: 16; color: ap.defaut ? "#0a84ff" : "#3a3a3c"
                Ico { anchors.centerIn: parent; nom: ap.icone; taille: 18 }
            }
            Texte { text: son.nom(ap.noeud); font.weight: Font.DemiBold; width: son.width - 110; anchors.verticalCenter: parent.verticalCenter }
        }
        Ico { anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter; nom: "check"; taille: 20; color: "#0a84ff"; visible: ap.defaut }
    }

    Flickable {
        anchors.fill: parent
        contentHeight: colonne.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Column {
            id: colonne
            width: son.width; spacing: 6
            Row {
                spacing: 10; height: 34
                Ico { nom: "volume_up"; taille: 24; anchors.verticalCenter: parent.verticalCenter }
                Texte { text: "Son"; font.pixelSize: 20; font.weight: Font.Bold; anchors.verticalCenter: parent.verticalCenter }
            }
            Titre { text: "SORTIE" }
            Repeater {
                model: son.sorties
                Appareil {
                    required property var modelData
                    noeud: modelData; defaut: modelData === Pipewire.defaultAudioSink
                    icone: (son.nom(modelData).toLowerCase().indexOf("hdmi") >= 0 || son.nom(modelData).indexOf("GB2") >= 0) ? "tv" : "speaker"
                    onClic: Pipewire.preferredDefaultAudioSink = modelData
                }
            }
            Titre { text: "MICRO" }
            Repeater {
                model: son.entrees
                Appareil {
                    required property var modelData
                    noeud: modelData; defaut: modelData === Pipewire.defaultAudioSource
                    icone: modelData.audio && modelData.audio.muted ? "mic_off" : "mic"
                    onClic: Pipewire.preferredDefaultAudioSource = modelData
                    onAppuiLong: if (modelData.audio) modelData.audio.muted = !modelData.audio.muted
                }
            }
            Titre { text: "APPLICATIONS" }
            Texte { text: "Aucune application ne joue de son."; secondaire: true; visible: son.applis.length === 0; height: 26 }
            Repeater {
                model: son.applis
                Module {
                    required property var modelData
                    width: son.width; height: 58; radius: 16
                    Column {
                        anchors.fill: parent; anchors.margins: 10; spacing: 6
                        Row {
                            width: parent.width; spacing: 8
                            Texte { text: son.nom(modelData); font.weight: Font.DemiBold; width: parent.width - 50 }
                            Texte { text: Math.round((modelData.audio ? modelData.audio.volume : 0) * 100) + " %"; secondaire: true }
                        }
                        // Volume de l'application : barre qu'on clique ou fait glisser
                        Rectangle {
                            width: parent.width; height: 8; radius: 4; color: "#3a3a3c"
                            Rectangle { height: parent.height; radius: 4; color: "white"; width: parent.width * Math.min(1, modelData.audio ? modelData.audio.volume : 0) }
                            MouseArea {
                                anchors.fill: parent; anchors.margins: -8; preventStealing: true
                                function regler(x) { if (modelData.audio) modelData.audio.volume = Math.max(0, Math.min(1, x / width)) }
                                onPressed: e => regler(e.x)
                                onPositionChanged: e => { if (pressed) regler(e.x) }
                            }
                        }
                    }
                }
            }
        }
    }
}
