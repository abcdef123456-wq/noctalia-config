// Page « Son », comme les réglages d'iOS : grand curseur de volume, puis des cartes groupées.
//   Sortie : un appareil par ligne, coche bleue sur celui qui sert ;
//   Micro : interrupteur (coupé / actif), volume d'entrée, choix du micro s'il y en a plusieurs ;
//   Applications : icône, nom et fin curseur pour chaque appli qui joue du son.
import QtQuick
import Quickshell
import Quickshell.Services.Pipewire
import Quickshell.Widgets

Item {
    id: son
    function defiler(dy) { return defil.defiler(dy) }
    readonly property var noeuds: Pipewire.nodes.values
    // Par leur type (lisible sans s'attacher au nœud) : pour un flux, isSink est vrai quand il JOUE du son (il entre dans
    // le graphe) ; le filtre « !isSink » écartait donc toutes les applis qui jouent, et la liste restait vide
    readonly property var sorties: noeuds.filter(n => n.type === PwNodeType.AudioSink)
    readonly property var entrees: noeuds.filter(n => n.type === PwNodeType.AudioSource)
    readonly property var applis: noeuds.filter(n => n.type === PwNodeType.AudioOutStream)
    readonly property var micro: Pipewire.defaultAudioSource
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
    function iconeSortie(n) {
        var t = nomAppareil(n, false)
        if (t.indexOf("HDMI") >= 0) return "tv"
        if ((n.name || "").indexOf("bluez") >= 0 || t.toLowerCase().indexOf("head") >= 0 || t.toLowerCase().indexOf("casque") >= 0) return "headphones"
        return "speaker"
    }
    function iconeAppli(n) {
        var p = n.properties
        return Quickshell.iconPath(p["application.icon-name"] || (p["application.process.binary"] || "").toLowerCase() || "audio-x-generic", "audio-x-generic")
    }

    // ── Éléments ──
    component Titre: Texte { font.pixelSize: 13; font.weight: Font.DemiBold; secondaire: true; height: 30; verticalAlignment: Text.AlignBottom; leftPadding: 14; bottomPadding: 6 }
    // Carte groupée (fond gris foncé, coins arrondis)
    component Carte: ClippingRectangle {
        default property alias contenu: col.data
        width: parent ? parent.width : 300
        height: col.implicitHeight
        radius: 16; color: Couleurs.carte
        Column { id: col; width: parent.width }
    }
    // Ligne d'une carte : icône simple, nom, coche ; trait de séparation sauf pour la dernière
    component Option: Item {
        id: o
        property string icone: ""
        property string titre: ""
        property bool coche: false
        property bool dernier: false
        signal clic()
        width: parent ? parent.width : 300; height: 46
        Rectangle { anchors.fill: parent; color: zo.pressed ? Couleurs.gris2 : (zo.containsMouse ? Couleurs.carteSurvol : "transparent") }
        Ico { x: 14; anchors.verticalCenter: parent.verticalCenter; nom: o.icone; taille: 20; color: o.coche ? Couleurs.accent : Couleurs.texteDoux; plein: o.coche }
        Texte {
            x: 46; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 46 - 44
            text: o.titre; font.pixelSize: 14; font.weight: o.coche ? Font.DemiBold : Font.Normal
        }
        Ico { anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter; nom: "check"; taille: 20; color: Couleurs.accent; visible: o.coche; graisse: 600 }
        Rectangle { visible: !o.dernier; x: 46; anchors.bottom: parent.bottom; width: parent.width - 46; height: 1; color: Couleurs.gris2 }
        MouseArea { id: zo; anchors.fill: parent; hoverEnabled: true; onClicked: o.clic() }
    }
    // Fin curseur façon macOS : piste fine, partie remplie blanche, bouton rond
    component Piste: Item {
        id: f
        property real valeur: 0
        signal change(real v)
        height: 18
        Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 4; radius: 2; color: Couleurs.gris3 }
        Rectangle { anchors.verticalCenter: parent.verticalCenter; width: bouton.x + bouton.width / 2; height: 4; radius: 2; color: Couleurs.texte }
        Rectangle {
            id: bouton
            width: 16; height: 16; radius: 8; color: Couleurs.texte
            anchors.verticalCenter: parent.verticalCenter
            x: (f.width - width) * Math.max(0, Math.min(1, f.valeur))
        }
        MouseArea {
            anchors.fill: parent; anchors.margins: -6
            preventStealing: true
            function regler(x) { f.change(Math.max(0, Math.min(1, (x - 6) / f.width))) }
            onPressed: e => regler(e.x)
            onPositionChanged: e => { if (pressed) regler(e.x) }
        }
    }
    // Interrupteur façon iOS
    component Inter: Rectangle {
        id: it
        property bool allume: false
        signal bascule()
        width: 46; height: 28; radius: 14; color: allume ? Couleurs.vert : Couleurs.gris3
        Behavior on color { ColorAnimation { duration: 180 } }
        Rectangle {
            width: 24; height: 24; radius: 12; color: Couleurs.texte; y: 2; x: it.allume ? 20 : 2
            Behavior on x { SpringAnimation { spring: 5; damping: 0.5 } }
        }
        MouseArea { anchors.fill: parent; anchors.margins: -6; onClicked: it.bascule() }
    }

    Defilement {
        id: defil
        anchors.fill: parent
        contentHeight: colonne.implicitHeight

        Column {
            id: colonne
            width: son.width; spacing: 0
            onImplicitHeightChanged: Etat.annoncerHauteur("son", implicitHeight + 4)
            Component.onCompleted: Etat.annoncerHauteur("son", implicitHeight + 4)

            // En-tête et grand curseur
            Item {
                width: parent.width; height: 34
                Texte { anchors.verticalCenter: parent.verticalCenter; leftPadding: 4; text: "Son"; font.pixelSize: 20; font.weight: Font.Bold }
                Texte {
                    anchors.right: parent.right; anchors.rightMargin: 4; anchors.verticalCenter: parent.verticalCenter
                    text: Etat.muet ? "Coupé" : Math.round(Etat.volume * 100) + " %"
                    secondaire: true; font.pixelSize: 14; font.features: { "tnum": 1 }
                }
            }
            Item { width: 1; height: 8 }
            Curseur {
                width: son.width; height: 44; radius: 22
                icone: Etat.muet ? "volume_off" : (Etat.volume < 0.34 ? "volume_mute" : (Etat.volume < 0.67 ? "volume_down" : "volume_up"))
                valeur: Etat.muet ? 0 : Etat.volume
                onChange: v => Etat.reglerVolume(v)
            }

            Titre { text: "Sortie" }
            Carte {
                Repeater {
                    model: son.sorties
                    Option {
                        required property var modelData
                        required property int index
                        icone: son.iconeSortie(modelData)
                        titre: son.nomAppareil(modelData, false)
                        coche: modelData === Pipewire.defaultAudioSink
                        dernier: index === son.sorties.length - 1
                        onClic: Pipewire.preferredDefaultAudioSink = modelData
                    }
                }
            }

            Titre { text: "Micro"; visible: son.micro !== null }
            Carte {
                visible: son.micro !== null
                Item {
                    id: mic
                    width: parent.width; height: 92
                    readonly property bool coupe: son.micro && son.micro.audio ? son.micro.audio.muted : true
                    Ico { x: 14; y: 13; nom: mic.coupe ? "mic_off" : "mic"; taille: 20; color: mic.coupe ? Couleurs.rouge : Couleurs.texteDoux }
                    Column {
                        x: 46; y: 9; width: parent.width - 46 - 70
                        Texte { text: son.micro ? son.nomAppareil(son.micro, true) : ""; font.pixelSize: 14; width: parent.width }
                        Texte { text: mic.coupe ? "Coupé" : "Actif"; secondaire: true; font.pixelSize: 12 }
                    }
                    Inter {
                        anchors.right: parent.right; anchors.rightMargin: 14; y: 11
                        allume: !mic.coupe
                        onBascule: if (son.micro && son.micro.audio) son.micro.audio.muted = !son.micro.audio.muted
                    }
                    Piste {
                        x: 46; y: 60; width: parent.width - 46 - 20
                        opacity: mic.coupe ? 0.4 : 1
                        valeur: son.micro && son.micro.audio ? son.micro.audio.volume : 0
                        onChange: v => { if (son.micro && son.micro.audio) son.micro.audio.volume = v }
                    }
                    Rectangle { visible: son.entrees.length > 1; x: 46; anchors.bottom: parent.bottom; width: parent.width - 46; height: 1; color: Couleurs.gris2 }
                }
                // Choix du micro (s'il y en a plusieurs)
                Repeater {
                    model: son.entrees.length > 1 ? son.entrees : []
                    Option {
                        required property var modelData
                        required property int index
                        icone: "mic"
                        titre: son.nomAppareil(modelData, true)
                        coche: modelData === Pipewire.defaultAudioSource
                        dernier: index === son.entrees.length - 1
                        onClic: Pipewire.preferredDefaultAudioSource = modelData
                    }
                }
            }

            Titre { text: "Applications" }
            Carte {
                Texte { text: "Aucune application ne joue de son."; secondaire: true; visible: son.applis.length === 0; height: 46; leftPadding: 14 }
                Repeater {
                    model: son.applis
                    Item {
                        id: ap
                        required property var modelData
                        required property int index
                        width: parent.width; height: 58
                        Image {
                            x: 12; anchors.verticalCenter: parent.verticalCenter
                            width: 28; height: 28; sourceSize: Qt.size(56, 56)
                            source: son.iconeAppli(ap.modelData)
                        }
                        Column {
                            x: 52; width: parent.width - 52 - 18
                            anchors.verticalCenter: parent.verticalCenter; spacing: 6
                            Item {
                                width: parent.width; height: 16
                                Texte { text: son.nom(ap.modelData); font.pixelSize: 13; width: parent.width - 50 }
                                Texte {
                                    anchors.right: parent.right; secondaire: true; font.pixelSize: 12; font.features: { "tnum": 1 }
                                    text: ap.modelData.audio ? Math.round(ap.modelData.audio.volume * 100) + " %" : ""
                                }
                            }
                            Piste {
                                width: parent.width
                                valeur: ap.modelData.audio ? ap.modelData.audio.volume : 0
                                onChange: v => { if (ap.modelData.audio) ap.modelData.audio.volume = v }
                            }
                        }
                        Rectangle { visible: ap.index < son.applis.length - 1; x: 52; anchors.bottom: parent.bottom; width: parent.width - 52; height: 1; color: Couleurs.gris2 }
                    }
                }
            }
            Item { width: 1; height: 4 }
        }
    }
}
