pragma ComponentBehavior: Bound
import QtQuick
import Quickshell.Services.Mpris
import Quickshell.Widgets

Item {
    id: m
    property string disposition: "radial"
    property string motif: "music_note"
    property string dessin: ""
    objectName: "nc-musique-" + disposition

    readonly property var lecteur: Etat.lecteur
    readonly property string titre: Etat.titre || Reglages.t("Rien en lecture", "Not Playing")
    readonly property string source: lecteur ? lecteur.identity : ""
    readonly property string artiste: Etat.artiste || source
    readonly property string etatLecture: Etat.joue ? Reglages.t("En lecture", "Playing")
        : (lecteur && lecteur.playbackState === MprisPlaybackState.Paused ? Reglages.t("En pause", "Paused")
        : (lecteur ? Reglages.t("À l’arrêt", "Stopped") : Reglages.t("Aucun lecteur", "No player")))
    // MPRIS peut exposer une position sans durée : ne pas la prendre pour une progression à 100 %.
    readonly property bool positionConnue: !!lecteur && lecteur.positionSupported
    readonly property real duree: lecteur && lecteur.lengthSupported ? Math.max(0, lecteur.length) : 0
    readonly property real position: positionConnue ? borner(lecteur.position) : 0
    readonly property bool peutChercher: positionConnue && duree > 0 && lecteur.canSeek

    function borner(s) { return Math.max(0, duree > 0 ? Math.min(duree, s) : s) }
    function chercher(s) { if (peutChercher) lecteur.position = borner(s) }
    function temps(s) {
        s = Math.max(0, Math.floor(s))
        return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0")
    }

    Loader {
        anchors.fill: parent
        sourceComponent: {
            switch (m.disposition) {
            case "vinyle": return vinyle
            case "bande": return bande
            case "portrait": return portrait
            case "console": return consoleMedia
            case "scene": return scene
            default: return radial
            }
        }
    }

    component Cible: Item {
        id: cible
        required property string libelle
        readonly property bool survol: zone.containsMouse
        readonly property bool appuye: zone.pressed
        signal activer()
        activeFocusOnTab: enabled
        Accessible.role: Accessible.Button
        Accessible.name: libelle
        Accessible.onPressAction: if (enabled) activer()
        Keys.onReturnPressed: activer()
        Keys.onEnterPressed: activer()
        Keys.onSpacePressed: activer()
        MouseArea {
            id: zone
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: { cible.forceActiveFocus(Qt.MouseFocusReason); cible.activer() }
        }
    }

    component Touche: Cible {
        id: touche
        required property string symbole
        property bool principale: false
        property bool bloc: false
        opacity: enabled ? 1 : 0.42
        Rectangle {
            anchors.fill: parent
            radius: touche.bloc ? Couleurs.rayonBouton : height / 2
            color: touche.principale && touche.enabled ? (touche.survol ? Couleurs.accentClair : Couleurs.accent)
                : (touche.survol ? Couleurs.carteSurvol : Couleurs.surfaceDouce)
            border.width: touche.activeFocus || touche.bloc ? 1 : 0
            border.color: touche.activeFocus ? (touche.principale ? Couleurs.surAccent : Couleurs.accent) : Couleurs.bordureSubtile
            scale: touche.appuye ? 0.94 : 1
            Ico {
                anchors.centerIn: parent
                nom: touche.symbole; taille: touche.principale ? 24 : 19
                color: touche.principale && touche.enabled ? Couleurs.surAccent : Couleurs.texte
                Accessible.ignored: true
            }
        }
    }

    component Transports: Row {
        id: transports
        property bool touches: false
        property real largeurTouche: 43
        spacing: 6
        objectName: "nc-musique-transports"
        Touche {
            width: transports.largeurTouche; height: transports.height; bloc: transports.touches
            symbole: "skip_previous"; libelle: Reglages.t("Morceau précédent", "Previous track")
            enabled: !!m.lecteur && m.lecteur.canGoPrevious
            onActiver: if (enabled) m.lecteur.previous()
        }
        Touche {
            width: transports.largeurTouche + (transports.touches ? 0 : 14); height: transports.height; bloc: transports.touches
            principale: true; symbole: Etat.joue ? "pause" : "play_arrow"
            libelle: Etat.joue ? Reglages.t("Pause", "Pause") : Reglages.t("Lecture", "Play")
            enabled: !!m.lecteur && m.lecteur.canTogglePlaying
            onActiver: Etat.lecturePause()
        }
        Touche {
            width: transports.largeurTouche; height: transports.height; bloc: transports.touches
            symbole: "skip_next"; libelle: Reglages.t("Morceau suivant", "Next track")
            enabled: !!m.lecteur && m.lecteur.canGoNext
            onActiver: if (enabled) m.lecteur.next()
        }
    }

    component Sceau: Loader {
        sourceComponent: m.dessin !== "" ? vectoriel : glyphe
        Component { id: vectoriel; MotifIle { dessin: m.dessin } }
        Component {
            id: glyphe
            Ico { nom: m.motif || "music_note"; taille: Math.min(width, height) * 0.66; color: Couleurs.accent; Accessible.ignored: true }
        }
    }

    component Pochette: Cible {
        id: cadre
        property real arrondi: Couleurs.rayon(Couleurs.rayonBloc, width, height)
        property bool panoramique: false
        readonly property bool imagePresente: art.status === Image.Ready || icone.status === Image.Ready
        enabled: !!m.lecteur && m.lecteur.canRaise
        libelle: Reglages.t("Ouvrir le lecteur", "Open player")
        Accessible.ignored: !enabled
        onActiver: if (enabled) { m.lecteur.raise(); Etat.fermer() }
        Rectangle {
            anchors.fill: parent
            radius: cadre.arrondi
            color: Couleurs.carte
        }
        ClippingRectangle {
            anchors.fill: parent; radius: cadre.arrondi; color: "transparent"
            visible: art.status === Image.Ready
            Image {
                id: art
                anchors.fill: parent; fillMode: Image.PreserveAspectCrop
                // Etat applique la politique d’images (notamment ECO_IMAGES) avant tout chargement.
                source: Etat.pochette; asynchronous: true
                sourceSize: cadre.panoramique ? Qt.size(768, 768) : Qt.size(384, 384)
            }
        }
        Image {
            id: icone
            anchors.centerIn: parent
            anchors.verticalCenterOffset: cadre.panoramique ? -18 : 0
            width: Math.min(50, parent.width * 0.52); height: width
            source: art.status !== Image.Ready ? Etat.iconeLecteur : ""
            sourceSize: Qt.size(100, 100)
            visible: art.status !== Image.Ready && status === Image.Ready
        }
        Sceau {
            anchors.centerIn: parent; anchors.verticalCenterOffset: cadre.panoramique ? -18 : 0
            width: Math.min(parent.width * 0.65, parent.height * 0.65, cadre.panoramique ? 146 : 78)
            height: width
            active: !cadre.imagePresente
        }
        Loader {
            anchors.fill: parent
            active: cadre.panoramique
            sourceComponent: Rectangle {
                radius: cadre.arrondi
                gradient: Gradient {
                    GradientStop { position: 0.32; color: "transparent" }
                    GradientStop { position: 0.59; color: Qt.alpha(Couleurs.fond, 0.92) }
                    GradientStop { position: 1; color: Couleurs.fond }
                }
            }
        }
        Rectangle {
            anchors.fill: parent; radius: cadre.arrondi; color: "transparent"
            border.width: cadre.activeFocus ? 2 : 1
            border.color: cadre.survol || cadre.activeFocus ? Couleurs.accent : Couleurs.bordureSubtile
        }
    }

    component Onde: Row {
        id: onde
        visible: Etat.joue
        height: 21; spacing: 3
        Repeater {
            model: 5
            Rectangle {
                required property int index
                anchors.verticalCenter: onde.verticalCenter
                width: 3; height: 4 + Etat.bandes[index] * 16
                radius: width / 2; color: Couleurs.jauge
            }
        }
    }

    component Repere: Texte {
        secondaire: true
        font.pixelSize: 10
        font.capitalization: Font.AllUppercase
        font.letterSpacing: 1.2
    }

    component InfoPiste: Column {
        id: info
        property int tailleTitre: 19
        property bool deuxLignes: false
        spacing: 3
        Texte {
            width: info.width; text: m.titre
            font.pixelSize: info.tailleTitre; font.weight: Font.DemiBold
            wrapMode: info.deuxLignes ? Text.WrapAtWordBoundaryOrAnywhere : Text.NoWrap
            maximumLineCount: info.deuxLignes ? 2 : 1
        }
        Texte { width: info.width; visible: text !== ""; text: m.artiste; secondaire: true; font.pixelSize: 12 }
    }

    component Glissiere: Item {
        id: glissiere
        property bool segmentee: false
        readonly property real value: zoneSeek.pressed && zoneSeek.memePiste ? zoneSeek.apercu : m.position
        readonly property real minimumValue: 0
        readonly property real maximumValue: m.duree
        readonly property real stepSize: 5
        readonly property real fraction: m.duree > 0 ? value / m.duree : 0
        enabled: m.peutChercher
        activeFocusOnTab: enabled
        Accessible.role: enabled ? Accessible.Slider : Accessible.ProgressBar
        Accessible.name: Reglages.t("Position de lecture", "Playback position")
        Accessible.focusable: enabled
        Accessible.ignored: !m.positionConnue || m.duree <= 0
        Accessible.onIncreaseAction: m.chercher(value + stepSize)
        Accessible.onDecreaseAction: m.chercher(value - stepSize)
        Keys.onRightPressed: m.chercher(value + stepSize)
        Keys.onLeftPressed: m.chercher(value - stepSize)
        Keys.onPressed: e => {
            if (e.key === Qt.Key_Home) m.chercher(0)
            else if (e.key === Qt.Key_End) m.chercher(m.duree)
            else return
            e.accepted = true
        }

        Rectangle {
            id: rail
            width: parent.width; height: glissiere.segmentee ? 9 : 4
            anchors.verticalCenter: parent.verticalCenter
            radius: glissiere.segmentee ? 0 : 2
            color: Couleurs.separateur
            Rectangle { width: parent.width * glissiere.fraction; height: parent.height; radius: parent.radius; color: Couleurs.jauge }
            Repeater {
                model: glissiere.segmentee ? 19 : 0
                Rectangle {
                    required property int index
                    x: Math.round(rail.width * (index + 1) / 20)
                    width: 2; height: rail.height; color: Couleurs.carte
                }
            }
        }
        Rectangle {
            visible: glissiere.enabled && (zoneSeek.containsMouse || glissiere.activeFocus)
            width: 8; height: width; radius: width / 2
            x: Math.min(parent.width - width, Math.max(0, parent.width * glissiere.fraction - width / 2))
            anchors.verticalCenter: parent.verticalCenter; color: Couleurs.accent
        }
        MouseArea {
            id: zoneSeek
            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
            property var lecteurDepart: null
            property var pisteDepart
            property real apercu: 0
            readonly property bool memePiste: !!m.lecteur && lecteurDepart === m.lecteur && pisteDepart === m.lecteur.uniqueId
            function valeur(x) { return m.borner(m.duree * x / Math.max(1, width)) }
            onPressed: e => {
                glissiere.forceActiveFocus(Qt.MouseFocusReason)
                lecteurDepart = m.lecteur
                pisteDepart = m.lecteur.uniqueId
                apercu = valeur(e.x)
            }
            onPositionChanged: e => { if (pressed) apercu = valeur(e.x) }
            onReleased: e => { if (memePiste) m.chercher(valeur(e.x)); lecteurDepart = null }
            onCanceled: lecteurDepart = null
        }
    }

    component Progression: Item {
        id: progression
        property bool modeConsole: false
        readonly property real fraction: glissiere.fraction
        readonly property string ecoule: m.positionConnue ? m.temps(glissiere.value) : "—:—"
        readonly property string restant: m.positionConnue && m.duree > 0 ? "−" + m.temps(m.duree - glissiere.value) : "—:—"
        objectName: "nc-musique-progression"
        height: modeConsole ? 22 : 32
        Glissiere { id: glissiere; width: parent.width; height: 22; segmentee: progression.modeConsole }
        Texte { visible: !progression.modeConsole; anchors.bottom: parent.bottom; text: progression.ecoule; secondaire: true; font.pixelSize: 10 }
        Texte { visible: !progression.modeConsole; anchors.bottom: parent.bottom; anchors.right: parent.right; text: progression.restant; secondaire: true; font.pixelSize: 10 }
    }

    Component {
        id: radial
        Item {
            Item {
                id: plateau
                anchors.fill: parent
                Item {
                    id: cadran
                    width: Math.min(126, parent.height, parent.width * 0.39); height: width
                    anchors.verticalCenter: parent.verticalCenter
                    Repeater {
                        model: 36
                        Rectangle {
                            id: trait
                            required property int index
                            width: index % 3 === 0 ? 2 : 1
                            height: index % 3 === 0 ? 7 : 4
                            x: (cadran.width - width) / 2
                            color: index + 1 <= tempsRadial.fraction * 36 ? Couleurs.jauge : Couleurs.gris4
                            transform: Rotation { origin.x: trait.width / 2; origin.y: cadran.height / 2; angle: trait.index * 10 }
                        }
                    }
                    Pochette { width: Math.max(0, cadran.width - 20); height: width; arrondi: width / 2; anchors.centerIn: parent }
                }
                Item {
                    id: cartoucheRadial
                    anchors.left: cadran.right; anchors.leftMargin: 12
                    anchors.right: sceauRadial.left; anchors.rightMargin: sceauRadial.visible ? 12 : 0
                    anchors.verticalCenter: parent.verticalCenter
                    height: infoRadiale.implicitHeight + jeuRadial.height + tempsRadial.height + 19
                    InfoPiste { id: infoRadiale; width: parent.width; tailleTitre: 20 }
                    Onde { anchors.right: parent.right; anchors.verticalCenter: jeuRadial.verticalCenter; visible: Etat.joue && cartoucheRadial.width >= 192 }
                    Transports { id: jeuRadial; anchors.top: infoRadiale.bottom; anchors.topMargin: 8; height: 37; largeurTouche: 36 }
                    Progression { id: tempsRadial; anchors.top: jeuRadial.bottom; anchors.topMargin: 11; width: parent.width }
                }
                Sceau {
                    id: sceauRadial
                    anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                    visible: plateau.width >= 380 && (m.dessin !== "" || m.motif !== "")
                    active: visible; width: visible ? Math.min(94, plateau.width * 0.19) : 0; height: width
                }
            }
        }
    }

    Component {
        id: vinyle
        Item {
            Item {
                id: platine
                width: Math.min(192, parent.width * 0.47); height: parent.height
                Rectangle {
                    id: galette
                    anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(platine.height - 10, platine.width * 0.91); height: width; radius: width / 2
                    color: Couleurs.carte
                    border.width: 1; border.color: Couleurs.bordureSubtile
                    Repeater {
                        model: 9
                        Rectangle {
                            required property int index
                            anchors.centerIn: galette
                            width: galette.width * (0.92 - 0.072 * index); height: width; radius: width / 2
                            color: "transparent"; border.width: 1
                            border.color: index % 2 === 0 ? Couleurs.bordureSubtile : Couleurs.separateur
                        }
                    }
                    Rectangle { anchors.centerIn: parent; width: parent.width * 0.23; height: width; radius: width / 2; color: Couleurs.accentDoux }
                    Rectangle { anchors.centerIn: parent; width: 4; height: 4; radius: width / 2; color: Couleurs.texteSec }
                }
                Pochette { anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; width: parent.width * 0.54; height: width; arrondi: Couleurs.rayon(4, width, height) }
                Sceau { x: 3; y: 5; width: 34; height: width; active: m.dessin !== ""; opacity: 0.8 }
            }
            Item {
                anchors.left: platine.right; anchors.leftMargin: 13
                anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom
                Repere {
                    id: albumVinyle
                    width: parent.width - (ondeVinyle.visible ? 35 : 0); y: 8
                    text: m.lecteur && m.lecteur.trackAlbum ? m.lecteur.trackAlbum : m.etatLecture
                    color: Couleurs.accent
                }
                InfoPiste { width: parent.width; y: 31; tailleTitre: 21; deuxLignes: true }
                Progression { width: parent.width; anchors.bottom: jeuVinyle.top; anchors.bottomMargin: 5 }
                Transports { id: jeuVinyle; anchors.bottom: parent.bottom; height: 36; largeurTouche: 39 }
                Onde { id: ondeVinyle; anchors.right: parent.right; anchors.verticalCenter: albumVinyle.verticalCenter }
            }
        }
    }

    component Bobine: Rectangle {
        id: bobine
        required property real enroule
        width: 34; height: width; radius: width / 2
        color: Couleurs.gris2; border.width: 1; border.color: Couleurs.bordureSubtile
        Rectangle {
            anchors.centerIn: parent
            width: 11 + 17 * bobine.enroule; height: width; radius: width / 2; color: Couleurs.accentDoux
        }
        Ico { anchors.centerIn: parent; nom: "trip_origin"; taille: 16; color: Couleurs.texteSec; Accessible.ignored: true }
    }

    Component {
        id: bande
        Item {
            Rectangle {
                id: cassette
                width: parent.width; height: parent.height - 48
                radius: Couleurs.rayon(Couleurs.rayonBloc, width, height)
                color: Couleurs.surfaceDouce; border.width: 1; border.color: Couleurs.bordureSubtile
                Pochette { id: cassetteArt; x: 12; y: 12; width: 48; height: width }
                InfoPiste {
                    anchors.left: cassetteArt.right; anchors.leftMargin: 12
                    anchors.right: cassetteOnde.visible ? cassetteOnde.left : cassetteSceau.left; anchors.rightMargin: 10
                    anchors.verticalCenter: cassetteArt.verticalCenter; tailleTitre: 17
                }
                Sceau {
                    id: cassetteSceau
                    anchors.right: parent.right; anchors.rightMargin: 11; anchors.verticalCenter: cassetteArt.verticalCenter
                    active: m.dessin !== ""; width: active ? 34 : 0; height: width; opacity: 0.8
                }
                Onde {
                    id: cassetteOnde
                    anchors.right: cassetteSceau.left; anchors.rightMargin: cassetteSceau.active ? 9 : 2
                    anchors.verticalCenter: cassetteArt.verticalCenter
                }
                Rectangle {
                    anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 10
                    height: 52; radius: Couleurs.rayon(8, width, height); color: Couleurs.carte
                    Bobine { id: gauche; anchors.left: parent.left; anchors.leftMargin: 7; anchors.verticalCenter: parent.verticalCenter; enroule: 1 - tempsBande.fraction }
                    Bobine { id: droite; anchors.right: parent.right; anchors.rightMargin: 7; anchors.verticalCenter: parent.verticalCenter; enroule: tempsBande.fraction }
                    Progression {
                        id: tempsBande
                        anchors.left: gauche.right; anchors.right: droite.left; anchors.leftMargin: 9; anchors.rightMargin: 9
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }
            Transports {
                anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter
                height: 39; touches: true; largeurTouche: Math.min(104, (parent.width - 12) / 3)
            }
        }
    }

    Component {
        id: portrait
        Item {
            Pochette {
                id: grandArt
                anchors.top: parent.top; anchors.bottom: parent.bottom; anchors.topMargin: 4; anchors.bottomMargin: 4
                width: Math.min(210, parent.width * 0.42)
            }
            Item {
                anchors.left: grandArt.right; anchors.leftMargin: 17
                anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom
                Sceau { anchors.right: parent.right; y: 3; width: 33; height: width; active: m.dessin !== ""; opacity: 0.8 }
                Repere { width: parent.width - (m.dessin !== "" ? 41 : 0); y: 10; text: m.etatLecture; color: Couleurs.accent }
                Rectangle { y: 32; width: 34; height: 2; color: Couleurs.accent }
                InfoPiste { width: parent.width; y: 51; tailleTitre: 23; deuxLignes: true }
                Onde { anchors.bottom: tempsPortrait.top; anchors.right: parent.right; anchors.bottomMargin: 1 }
                Progression { id: tempsPortrait; width: parent.width; anchors.bottom: jeuPortrait.top; anchors.bottomMargin: 9 }
                Transports { id: jeuPortrait; anchors.bottom: parent.bottom; anchors.bottomMargin: 4; height: 36; largeurTouche: 39 }
            }
        }
    }

    Component {
        id: consoleMedia
        Item {
            Rectangle {
                id: moniteur
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                height: parent.height - 44
                radius: Couleurs.rayon(Couleurs.rayonBloc, width, height)
                color: Couleurs.carte; border.width: 1; border.color: Couleurs.bordureSubtile
                Sceau { anchors.right: parent.right; anchors.rightMargin: 11; y: 4; width: 20; height: width; active: m.dessin !== ""; opacity: 0.8 }
                Repere { x: 11; y: 9; width: parent.width - (m.dessin !== "" ? 49 : 22); text: "MPRIS / " + m.etatLecture; color: Couleurs.accent }
                Rectangle { x: 11; y: 28; width: parent.width - 22; height: 1; color: Couleurs.separateur }
                Texte {
                    id: afficheur
                    x: 11; width: Math.min(118, parent.width * 0.36); y: 40; height: 46
                    text: tempsConsole.ecoule; font.family: "monospace"; font.pixelSize: parent.width > 360 ? 32 : 26
                }
                Pochette { id: miniature; anchors.right: parent.right; anchors.rightMargin: 11; anchors.verticalCenter: afficheur.verticalCenter; width: 41; height: width }
                InfoPiste {
                    anchors.left: afficheur.right; anchors.leftMargin: 4; anchors.right: miniature.left; anchors.rightMargin: 9
                    anchors.verticalCenter: afficheur.verticalCenter; tailleTitre: 16
                }
                Progression { id: tempsConsole; x: 11; width: parent.width - 22; y: 90; modeConsole: true }
                Repere { x: 11; anchors.bottom: parent.bottom; anchors.bottomMargin: 8; text: Reglages.t("Restant", "Remaining") + " " + tempsConsole.restant }
                Onde { anchors.right: parent.right; anchors.rightMargin: 11; anchors.bottom: parent.bottom; anchors.bottomMargin: 6 }
            }
            Repere {
                anchors.left: parent.left; anchors.leftMargin: 2; anchors.right: jeuConsole.left; anchors.rightMargin: 8
                anchors.verticalCenter: jeuConsole.verticalCenter; text: m.source
            }
            Transports { id: jeuConsole; anchors.bottom: parent.bottom; anchors.right: parent.right; height: 36; largeurTouche: 42; touches: true }
        }
    }

    Component {
        id: scene
        Item {
            Pochette {
                id: toile
                width: parent.width; anchors.top: parent.top; anchors.bottom: tempsScene.top
                panoramique: true
            }
            Rectangle {
                id: vignetteScene
                visible: m.dessin !== "" && toile.imagePresente
                x: 9; y: 9; width: 48; height: width
                radius: Couleurs.rayon(8, width, height); color: Couleurs.carte
                Sceau { anchors.fill: parent; anchors.margins: 5; active: vignetteScene.visible }
            }
            InfoPiste {
                x: 13; width: parent.width - 26; anchors.bottom: toile.bottom; anchors.bottomMargin: 10
                tailleTitre: 23; deuxLignes: true
            }
            Rectangle {
                visible: Etat.joue
                anchors.top: toile.top; anchors.topMargin: 9; anchors.right: toile.right; anchors.rightMargin: 9
                width: 43; height: 27; radius: Couleurs.rayon(9, width, height); color: Couleurs.carte
                Onde { anchors.centerIn: parent }
            }
            Progression { id: tempsScene; width: parent.width; anchors.bottom: jeuScene.top; anchors.bottomMargin: 4 }
            Transports { id: jeuScene; anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter; height: 38; largeurTouche: 48 }
        }
    }
}
