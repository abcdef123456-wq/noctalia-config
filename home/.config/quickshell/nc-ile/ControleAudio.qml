// Tiroir Audio natif du Centre de contrôle :
// volume maître, sélection de sortie (avec batterie casque Bluetooth), micro + entrée, et mixeur par application
// branché en direct sur PipeWire — design cohérent avec l'archétype du thème actif.
import QtQuick
import Quickshell
import Quickshell.Services.Pipewire

Item {
    id: vue

    readonly property bool estBrut: Couleurs.styleBrut || Couleurs.styleTerminal
    readonly property bool estEditorial: Couleurs.styleEditorial
    readonly property var noeuds: Pipewire.nodes.values
    readonly property var sorties: noeuds.filter(n => n.type === PwNodeType.AudioSink)
    readonly property var entrees: noeuds.filter(n => n.type === PwNodeType.AudioSource)
    readonly property var applis: noeuds.filter(n => n.type === PwNodeType.AudioOutStream)
    readonly property var micro: Pipewire.defaultAudioSource

    PwObjectTracker { objects: vue.applis }

    function nomAppareil(n, entree) {
        if (!n) return ""
        var d = n.description || n.nickname || n.name || "?"
        var b = (n.name || "").toLowerCase(), l = d.toLowerCase()
        if (b.indexOf("hdmi") >= 0 || l.indexOf("hdmi") >= 0 || b.indexOf("displayport") >= 0) return Reglages.t("Écran (HDMI)", "Display (HDMI)")
        if (b.indexOf("bluez") >= 0 || l.indexOf("headphone") >= 0 || l.indexOf("casque") >= 0) return d
        if (b.indexOf("usb") >= 0) return d.replace(/ (Stéréo|Stereo|Mono|Analog|analogique).*$/i, "")
        if (b.indexOf("alsa") >= 0 && (b.indexOf("analog") >= 0 || b.indexOf("pci") >= 0)) return entree ? Reglages.t("Micro intégré", "Built-in Mic") : Reglages.t("Haut-parleurs", "Speakers")
        return d
    }
    function iconeSortie(n) {
        var t = nomAppareil(n, false).toLowerCase()
        if (t.indexOf("hdmi") >= 0) return "tv"
        if ((n.name || "").indexOf("bluez") >= 0 || t.indexOf("head") >= 0 || t.indexOf("casque") >= 0) return "headphones"
        return "speaker"
    }
    function batSortie(n) {
        if (!n || (n.name || "").indexOf("bluez") < 0) return ""
        var v = CasqueBatterie.niveauPour(n.description || n.nickname || "")
        return v > 0 ? " · " + v + "%" : ""
    }
    function nomAppli(n) { return (n.properties || {})["application.name"] || n.description || n.nickname || n.name || "?" }
    function iconeAppli(n) {
        var p = n.properties || {}
        return Quickshell.iconPath(p["application.icon-name"] || (p["application.process.binary"] || "").toLowerCase() || "audio-x-generic", "audio-x-generic")
    }

    component TitreSection: Texte {
        width: parent ? parent.width : 300
        font.pixelSize: vue.estBrut ? 9 : 11
        font.weight: Font.Bold
        font.letterSpacing: vue.estBrut ? 1.0 : 0.4
        secondaire: true
        topPadding: 4; bottomPadding: 2
    }

    component LigneAudio: Rectangle {
        id: appareil
        required property var modelData
        property bool entree: false
        readonly property bool actif: modelData === (entree ? vue.micro : Pipewire.defaultAudioSink)
        readonly property bool plein: actif && vue.estBrut
        readonly property string libelle: vue.nomAppareil(modelData, entree) + (entree ? "" : vue.batSortie(modelData))
        width: col.width; height: 42
        radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
        color: actif ? (vue.estBrut ? Couleurs.accent : Couleurs.accentDoux)
             : (choisir.contientPointeur ? Couleurs.carteSurvol : (vue.estEditorial ? "transparent" : Couleurs.surfaceDouce))
        border.width: (vue.estBrut || vue.estEditorial || actif) ? 1 : 0
        border.color: actif ? Couleurs.accent : Couleurs.bordureSubtile

        Ico {
            x: 12; anchors.verticalCenter: parent.verticalCenter
            nom: appareil.entree ? "mic" : vue.iconeSortie(appareil.modelData); taille: 17
            color: appareil.plein ? Couleurs.surAccent : (appareil.actif ? Couleurs.accent : Couleurs.texteSec)
        }
        Texte {
            x: 38; width: parent.width - 72; anchors.verticalCenter: parent.verticalCenter
            text: appareil.libelle
            font.pixelSize: 12; font.weight: appareil.actif ? Font.DemiBold : Font.Medium
            color: appareil.plein ? Couleurs.surAccent : Couleurs.texte
        }
        Ico {
            visible: appareil.actif
            anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
            nom: "check"; taille: 16; color: appareil.plein ? Couleurs.surAccent : Couleurs.accent
        }
        ControleAction {
            id: choisir; anchors.fill: parent
            text: appareil.libelle
            Accessible.checkable: true
            Accessible.checked: appareil.actif
            onClicked: {
                if (appareil.entree) Pipewire.preferredDefaultAudioSource = appareil.modelData
                else Pipewire.preferredDefaultAudioSink = appareil.modelData
            }
        }
    }

    Flickable {
        anchors.fill: parent
        contentWidth: width
        contentHeight: col.implicitHeight + 6
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: col
            width: parent.width
            spacing: 8

            // ── Volume principal ──
            Rectangle {
                width: parent.width; height: 54
                radius: Couleurs.rayon(Couleurs.rayonBloc, width, height)
                color: vue.estEditorial ? "transparent" : Couleurs.surfaceDouce
                border.width: 1; border.color: Couleurs.bordureSubtile

                ControleGlissiere {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left; anchors.right: parent.right
                    anchors.leftMargin: 10; anchors.rightMargin: 10
                    enabled: !!(Etat.sortie && Etat.sortie.audio)
                    icone: Etat.muet ? "volume_off" : (Etat.volume > 0.55 ? "volume_up" : "volume_down")
                    titre: Reglages.t("Volume", "Volume")
                    valeur: Etat.volume
                    muet: Etat.muet
                    onChanger: v => Etat.reglerVolume(v)
                    onBasculerMuet: Etat.basculerMuet()
                }
            }

            // ── Sorties audio ──
            TitreSection { text: Reglages.t("SORTIE AUDIO", "OUTPUT DEVICE") }
            Texte {
                visible: vue.sorties.length === 0
                width: parent.width; secondaire: true; font.pixelSize: 11
                text: Reglages.t("Aucune sortie audio disponible.", "No audio output available.")
            }
            Repeater { model: vue.sorties; LigneAudio {} }

            // ── Microphone ──
            TitreSection { text: Reglages.t("ENTRÉE AUDIO", "INPUT DEVICE") }
            Texte {
                visible: vue.entrees.length === 0
                width: parent.width; secondaire: true; font.pixelSize: 11
                text: Reglages.t("Aucune entrée audio disponible.", "No audio input available.")
            }
            Repeater { model: vue.entrees; LigneAudio { entree: true } }
            Rectangle {
                id: carteMicro
                visible: vue.micro !== null
                readonly property bool lie: !!(vue.micro && vue.micro.audio)
                readonly property bool coupe: lie ? vue.micro.audio.muted : true
                width: parent.width; height: 84
                radius: Couleurs.rayon(Couleurs.rayonBloc, width, height)
                color: vue.estEditorial ? "transparent" : Couleurs.surfaceDouce
                border.width: 1; border.color: Couleurs.bordureSubtile

                Column {
                    anchors.fill: parent; anchors.margins: 10; spacing: 6
                    Item {
                        width: parent.width; height: 24
                        Ico {
                            id: microIcone
                            anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                            nom: carteMicro.coupe ? "mic_off" : "mic"; taille: 16
                            color: !carteMicro.lie ? Couleurs.texteSec : (carteMicro.coupe ? Couleurs.rouge : Couleurs.accent)
                        }
                        Texte {
                            anchors.left: microIcone.right; anchors.leftMargin: 8
                            anchors.right: basculeMicro.left; anchors.rightMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            text: vue.nomAppareil(vue.micro, true)
                            font.pixelSize: 12; font.weight: Font.DemiBold
                        }
                        Rectangle {
                            id: basculeMicro
                            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                            width: 36; height: 20
                            radius: Couleurs.rayon(vue.estBrut ? 2 : 10, width, height)
                            color: carteMicro.coupe ? Couleurs.gris3 : Couleurs.accent
                            Rectangle {
                                x: carteMicro.coupe ? 2 : parent.width - width - 2
                                anchors.verticalCenter: parent.verticalCenter
                                width: 16; height: 16
                                radius: Couleurs.rayon(vue.estBrut ? 1 : 8, width, height)
                                color: carteMicro.coupe ? Couleurs.texte : Couleurs.surAccent
                            }
                            ControleAction {
                                anchors.fill: parent
                                enabled: carteMicro.lie
                                text: carteMicro.coupe ? Reglages.t("Réactiver le micro", "Unmute microphone") : Reglages.t("Couper le micro", "Mute microphone")
                                onClicked: Etat.basculerMicro()
                            }
                        }
                    }
                    ControleGlissiere {
                        width: parent.width; compact: true
                        enabled: carteMicro.lie
                        icone: carteMicro.coupe ? "mic_off" : "mic"
                        titre: Reglages.t("Entrée", "Input")
                        valeur: carteMicro.lie ? vue.micro.audio.volume : 0
                        muet: carteMicro.coupe
                        onChanger: v => { if (carteMicro.lie) vue.micro.audio.volume = v }
                        onBasculerMuet: Etat.basculerMicro()
                    }
                }
            }

            // ── Mixeur applications ──
            TitreSection { text: Reglages.t("APPLICATIONS", "APPLICATIONS") }
            Texte {
                visible: vue.applis.length === 0
                width: parent.width; topPadding: 4; bottomPadding: 4
                secondaire: true; font.pixelSize: 11
                text: Reglages.t("Aucune application ne joue de son.", "No apps are playing audio.")
            }
            Repeater {
                model: vue.applis
                Rectangle {
                    id: apCard
                    required property var modelData
                    width: col.width; height: 58
                    radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
                    color: vue.estEditorial ? "transparent" : Couleurs.surfaceDouce
                    border.width: 1; border.color: Couleurs.bordureSubtile

                    Column {
                        anchors.fill: parent; anchors.margins: 8; spacing: 2
                        Row {
                            width: parent.width; spacing: 8
                            Image {
                                anchors.verticalCenter: parent.verticalCenter
                                width: 18; height: 18; sourceSize: Qt.size(36, 36)
                                source: vue.iconeAppli(apCard.modelData)
                            }
                            Texte {
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - 28
                                text: vue.nomAppli(apCard.modelData)
                                font.pixelSize: 11; font.weight: Font.DemiBold
                            }
                        }
                        ControleGlissiere {
                            width: parent.width; compact: true
                            enabled: !!apCard.modelData.audio
                            icone: apCard.modelData.audio && apCard.modelData.audio.muted ? "volume_off" : "volume_up"
                            titre: vue.nomAppli(apCard.modelData)
                            valeur: apCard.modelData.audio ? apCard.modelData.audio.volume : 0
                            muet: apCard.modelData.audio ? apCard.modelData.audio.muted : false
                            onChanger: v => { if (apCard.modelData.audio) { apCard.modelData.audio.muted = false; apCard.modelData.audio.volume = v } }
                            onBasculerMuet: if (apCard.modelData.audio) apCard.modelData.audio.muted = !apCard.modelData.audio.muted
                        }
                    }
                }
            }
        }
    }
}
