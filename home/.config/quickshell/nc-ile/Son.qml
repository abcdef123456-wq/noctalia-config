// Page « Son », façon macOS : volume général, sortie et micro (lignes sobres, coche bleue), puis chaque application
// qui joue du son avec son icône et son propre curseur.
import QtQuick
import Quickshell
import Quickshell.Services.Pipewire

Item {
    id: son
    function defiler(dy) { return defil.defiler(dy) }
    readonly property var noeuds: Pipewire.nodes.values
    readonly property var sorties: noeuds.filter(n => n.isSink && !n.isStream && n.audio)
    readonly property var entrees: noeuds.filter(n => !n.isSink && !n.isStream && n.audio && (n.properties["media.class"] || "").indexOf("Source") >= 0)
    readonly property var applis: noeuds.filter(n => n.isStream && n.audio && !n.isSink)
    PwObjectTracker { objects: son.sorties.concat(son.entrees, son.applis) }

    function nom(n) { return n.properties["application.name"] || n.description || n.nickname || n.name || "?" }
    // Noms lisibles pour les périphériques (« Ryzen HD Audio Controller Stéréo analogique » → « Haut-parleurs »)
    function nomAppareil(n, entree) {
        var d = n.description || n.nickname || n.name || "?", b = (n.name || "").toLowerCase(), l = d.toLowerCase()
        if (b.indexOf("hdmi") >= 0 || l.indexOf("hdmi") >= 0 || b.indexOf("displayport") >= 0) return "Écran (HDMI)"
        if (b.indexOf("bluez") >= 0 || l.indexOf("headphone") >= 0 || l.indexOf("casque") >= 0) return d
        if (b.indexOf("usb") >= 0) return d.replace(/ (Stéréo|Stereo|Mono|Analog|analogique).*$/i, "")
        if (b.indexOf("alsa") >= 0 && (b.indexOf("analog") >= 0 || b.indexOf("pci") >= 0)) return entree ? "Micro intégré" : "Haut-parleurs"
        return d
    }
    function iconeAppli(n) {
        var p = n.properties
        return Quickshell.iconPath(p["application.icon-name"] || (p["application.process.binary"] || "").toLowerCase() || "audio-x-generic", "audio-x-generic")
    }

    component Titre: Texte { font.pixelSize: 12; font.weight: Font.DemiBold; secondaire: true; height: 24; verticalAlignment: Text.AlignBottom; leftPadding: 8 }

    Defilement {
        id: defil
        anchors.fill: parent
        contentHeight: colonne.implicitHeight
        Column {
            id: colonne
            width: son.width; spacing: 4
            onImplicitHeightChanged: Etat.annoncerHauteur("son", implicitHeight + 6)
            Component.onCompleted: Etat.annoncerHauteur("son", implicitHeight + 6)

            Texte { text: "Son"; font.pixelSize: 20; font.weight: Font.Bold; height: 32; leftPadding: 4 }
            Curseur {
                width: son.width
                icone: Etat.muet ? "volume_off" : "volume_up"
                valeur: Etat.muet ? 0 : Etat.volume
                onChange: v => Etat.reglerVolume(v)
            }

            Titre { text: "Sortie" }
            Repeater {
                model: son.sorties
                Ligne {
                    required property var modelData
                    readonly property string n: son.nomAppareil(modelData, false)
                    titre: n
                    icone: n.indexOf("HDMI") >= 0 ? "tv" : ((modelData.name || "").indexOf("bluez") >= 0 || n.toLowerCase().indexOf("head") >= 0 ? "headphones" : "laptop_mac")
                    actif: modelData === Pipewire.defaultAudioSink
                    droite: actif ? "check" : ""; couleurDroite: "#0a84ff"
                    onClic: Pipewire.preferredDefaultAudioSink = modelData
                }
            }

            Titre { text: "Micro" }
            Repeater {
                model: son.entrees
                Ligne {
                    required property var modelData
                    titre: son.nomAppareil(modelData, true)
                    sous: modelData.audio && modelData.audio.muted ? "Coupé · clic droit pour le remettre" : ""
                    icone: modelData.audio && modelData.audio.muted ? "mic_off" : "mic"
                    actif: modelData === Pipewire.defaultAudioSource
                    droite: actif ? "check" : ""; couleurDroite: "#0a84ff"
                    onClic: Pipewire.preferredDefaultAudioSource = modelData
                    onClicDroit: if (modelData.audio) modelData.audio.muted = !modelData.audio.muted
                }
            }

            Titre { text: "Applications" }
            Texte { text: "Aucune application ne joue de son."; secondaire: true; visible: son.applis.length === 0; height: 30; leftPadding: 8 }
            Repeater {
                model: son.applis
                Item {
                    required property var modelData
                    width: son.width; height: 44
                    Image {
                        id: ic
                        anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter
                        width: 26; height: 26; sourceSize: Qt.size(52, 52)
                        source: son.iconeAppli(modelData)
                    }
                    Column {
                        anchors.left: ic.right; anchors.leftMargin: 10; anchors.right: parent.right; anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter; spacing: 4
                        Texte { text: son.nom(modelData); font.pixelSize: 12; secondaire: true; width: parent.width }
                        Curseur {
                            width: parent.width; height: 18; radius: 9; icone: ""
                            valeur: modelData.audio ? modelData.audio.volume : 0
                            onChange: v => { if (modelData.audio) modelData.audio.volume = v }
                        }
                    }
                }
            }
        }
    }
}
