pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Shapes
import Quickshell.Widgets
import Quickshell.Services.Mpris

// Scène native du thème Dracula : géométrie vectorielle nette, typographie du thème
// à l'échelle 1:1 (sans étirement matriciel) et palette synchronisée avec Couleurs.
Item {
    id: racine
    required property string page
    required property string rubrique
    property string filtre: "toutes"
    signal choisirFiltre(string valeur)
    signal ouvrirControle()
    signal ouvrirRecherche()
    signal ouvrirThemes()

    readonly property bool musique: page === "musique"
    readonly property bool boite: page === "notifications"
    readonly property bool breve: page !== "essentiel" && !boite && !musique
    readonly property bool animer: !Notifs.enPause && !Reglages.sobre

    implicitHeight: breve ? 40 : (boite ? 108 : (musique ? 126 : 146))

    // ── En-tête sobre pour les pages secondaires (Système, Minuteur, Agents…) ──
    Item {
        visible: racine.breve
        anchors.fill: parent

        Rectangle {
            x: 2; anchors.verticalCenter: parent.verticalCenter
            width: 3; height: 18; radius: 1.5
            color: Couleurs.accent
        }
        Texte {
            x: 13; anchors.verticalCenter: parent.verticalCenter
            width: Math.max(0, parent.width - 20)
            text: racine.rubrique
            font.pixelSize: 16; font.weight: Font.Bold
            color: Couleurs.texte
        }
        Rectangle {
            anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
            height: 1
            color: Qt.alpha(Couleurs.accent, 0.16)
        }
    }

    // ── Carte principale pour Accueil, Musique et Notifications ──
    Rectangle {
        id: carte
        visible: !racine.breve
        anchors.fill: parent
        radius: 12
        color: Qt.alpha(Couleurs.carte, 0.90)
        border.width: 1
        border.color: Qt.alpha(Couleurs.accent, 0.26)

        // Filet spéculaire supérieur en dégradé violet → rose (signature Dracula)
        Rectangle {
            x: 14; y: 1
            width: Math.max(0, parent.width - 28); height: 1
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.28; color: Qt.alpha(Couleurs.accent, 0.55) }
                GradientStop { position: 0.72; color: Qt.alpha(Couleurs.rose, 0.45) }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }

        // ══════════════ 1. ACCUEIL (ESSENTIEL) ══════════════
        Item {
            visible: racine.page === "essentiel"
            anchors.fill: parent

            // Indicateur d'état nocturne + heure tabulaire nette
            Column {
                x: 18; y: 14
                width: Math.max(0, parent.width / 2 - 22)
                spacing: 2

                Row {
                    width: parent.width
                    spacing: 7
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 12; height: 12; radius: 6
                        color: Qt.alpha(Etat.joue ? Couleurs.vert : (Notifs.concentration ? Couleurs.rose : Couleurs.accent), 0.18)
                        Rectangle {
                            anchors.centerIn: parent
                            width: 6; height: 6; radius: 3
                            color: Etat.joue ? Couleurs.vert : (Notifs.concentration ? Couleurs.rose : Couleurs.accent)
                        }
                    }
                    Texte {
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.max(0, parent.width - 19)
                        text: Etat.joue ? Reglages.t("AUDIO ACTIF", "PLAYING NOW")
                            : Notifs.concentration ? (Modes.nomVisible || Reglages.t("CONCENTRATION", "FOCUS"))
                            : Reglages.t("SESSION NOCTURNE", "NIGHT SESSION")
                        font.pixelSize: 10; font.weight: Font.Bold
                        font.letterSpacing: 1.3
                        font.capitalization: Font.AllUppercase
                        color: Couleurs.accentClair
                    }
                }

                Texte {
                    objectName: racine.page === "essentiel" ? "nc-scene-titre" : ""
                    text: Etat.heure
                    width: parent.width
                    fontSizeMode: Text.HorizontalFit
                    minimumPixelSize: 22
                    font.pixelSize: 38; font.weight: Font.Bold
                    font.features: ({ "tnum": 1 })
                    color: Couleurs.texte
                }
            }

            // Date complète et pastille d'état à droite
            Column {
                anchors.right: parent.right; anchors.rightMargin: 18
                width: Math.max(0, parent.width / 2 - 24)
                y: 18
                spacing: 6

                Texte {
                    anchors.right: parent.right
                    objectName: "nc-essentiel-date"
                    width: parent.width
                    horizontalAlignment: Text.AlignRight
                    visible: Reglages.val("ILE_DATE", "oui") !== "non"
                    text: Etat.dateLongue
                    font.pixelSize: 12; font.weight: Font.Medium
                    color: Couleurs.texteDoux
                }

                Rectangle {
                    anchors.right: parent.right
                    visible: !Partage.silence && Notifs.nonLues > 0
                    width: Math.min(parent.width, etiqDroite.implicitWidth + 18); height: 22; radius: 6
                    color: Qt.alpha(Couleurs.rose, 0.16)
                    border.width: 1
                    border.color: Qt.alpha(Couleurs.rose, 0.42)

                    Row {
                        id: etiqDroite
                        anchors.centerIn: parent; spacing: 5
                        width: Math.max(0, parent.width - 18)
                        Ico {
                            anchors.verticalCenter: parent.verticalCenter
                            nom: "notifications_active"
                            taille: 13
                            color: Couleurs.rose
                        }
                        Texte {
                            anchors.verticalCenter: parent.verticalCenter
                            width: Math.max(0, parent.width - 18)
                            text: String(Notifs.nonLues) + Reglages.t(Notifs.nonLues > 1 ? " alertes" : " alerte", Notifs.nonLues > 1 ? " alerts" : " alert")
                            font.pixelSize: 11; font.weight: Font.DemiBold
                            color: Couleurs.rose
                        }
                    }
                }
            }

            // Séparateur horizontal net (1 px aligné sur la grille)
            Rectangle {
                x: 16; y: 92
                width: Math.max(0, parent.width - 32); height: 1
                color: Qt.alpha(Couleurs.accent, 0.14)
            }

            // Barre des trois commandes rapides aux accents Dracula (Violet, Cyan, Rose)
            Row {
                id: barreActions
                x: 14; y: 101
                width: Math.max(0, parent.width - 28); height: 32
                spacing: 8
                readonly property real lPrimaire: Math.round((width - 16) * 0.40)
                readonly property real lSec: Math.floor((width - 16 - lPrimaire) / 2)

                BoutonDracula {
                    objectName: "nc-essentiel-controle"
                    width: barreActions.lPrimaire; height: 32
                    icone: "tune"
                    libelle: Reglages.t("Contrôle", "Control")
                    teinte: Couleurs.accent
                    primaire: true
                    onClicked: racine.ouvrirControle()
                }
                BoutonDracula {
                    objectName: "nc-essentiel-recherche"
                    width: barreActions.lSec; height: 32
                    icone: "search"
                    libelle: Reglages.t("Recherche", "Search")
                    teinte: Couleurs.cyan
                    onClicked: racine.ouvrirRecherche()
                }
                BoutonDracula {
                    objectName: "nc-essentiel-themes"
                    width: Math.max(0, barreActions.width - barreActions.lPrimaire - barreActions.lSec - 16)
                    height: 32
                    icone: "palette"
                    libelle: Reglages.t("Thèmes", "Themes")
                    teinte: Couleurs.rose
                    onClicked: racine.ouvrirThemes()
                }
            }
        }

        // ══════════════ 2. MUSIQUE (PLATINE STUDIO DRACULA) ══════════════
        Item {
            visible: racine.musique
            anchors.fill: parent

            // Pochette haute netteté ou disque studio Dracula
            ControleAction {
                id: cadrePochette
                x: 14; y: 14; width: 98; height: 98
                padding: 0
                enabled: !!Etat.lecteur && Etat.lecteur.canRaise
                text: Reglages.t("Ouvrir le lecteur", "Open player")
                background: Rectangle {
                    radius: 10
                    color: Qt.darker(Couleurs.fond, 1.18)
                    border.width: cadrePochette.visualFocus ? 2 : 1
                    border.color: cadrePochette.contientPointeur ? Couleurs.accent : Qt.alpha(Couleurs.accent, 0.30)

                    // Vinyle minimaliste net si aucune pochette n'est fournie
                    Shape {
                        anchors.fill: parent
                        visible: imgArt.status !== Image.Ready && imgApp.status !== Image.Ready
                        preferredRendererType: Shape.CurveRenderer
                        ShapePath {
                            fillColor: "transparent"
                            strokeColor: Qt.alpha(Couleurs.accent, 0.16)
                            strokeWidth: 1
                            PathAngleArc { centerX: 49; centerY: 49; radiusX: 36; radiusY: 36; startAngle: 0; sweepAngle: 360 }
                        }
                        ShapePath {
                            fillColor: Qt.alpha(Couleurs.accent, 0.16)
                            strokeColor: Qt.alpha(Couleurs.accent, 0.42)
                            strokeWidth: 1
                            PathAngleArc { centerX: 49; centerY: 49; radiusX: 20; radiusY: 20; startAngle: 0; sweepAngle: 360 }
                        }
                    }

                    ClippingRectangle {
                        anchors.fill: parent; anchors.margins: 1
                        radius: 9; color: "transparent"
                        visible: imgArt.status === Image.Ready
                        Image {
                            id: imgArt
                            anchors.fill: parent; fillMode: Image.PreserveAspectCrop
                            source: Etat.pochette; asynchronous: true
                            sourceSize: Qt.size(256, 256)
                        }
                    }
                    Image {
                        id: imgApp
                        anchors.centerIn: parent; width: 48; height: 48
                        source: imgArt.status !== Image.Ready ? Etat.iconeLecteur : ""
                        visible: status === Image.Ready
                    }
                    Ico {
                        anchors.centerIn: parent
                        nom: "music_note"; taille: 22
                        color: Couleurs.accentClair
                        visible: imgArt.status !== Image.Ready && !imgApp.visible
                    }
                }
                onClicked: { Etat.lecteur.raise(); Etat.fermer() }
            }

            // Métadonnées et commandes de transport alignées
            Item {
                x: 126; y: 14
                width: Math.max(0, parent.width - 140); height: 98

                Row {
                    width: parent.width
                    spacing: 6
                    Rectangle {
                        id: statut
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.round(statutRow.implicitWidth + 12); height: 18; radius: 5
                        color: Etat.joue ? Qt.alpha(Couleurs.accent, 0.18) : Qt.alpha(Couleurs.voile, 0.06)
                        border.width: 1
                        border.color: Etat.joue ? Qt.alpha(Couleurs.accent, 0.42) : Qt.alpha(Couleurs.voile, 0.12)
                        Row {
                            id: statutRow
                            anchors.centerIn: parent; spacing: 5
                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: 5; height: 5; radius: 2.5
                                color: Etat.joue ? Couleurs.vert : Couleurs.texteSec
                            }
                            Texte {
                                anchors.verticalCenter: parent.verticalCenter
                                text: Etat.joue ? Reglages.t("EN LECTURE", "PLAYING")
                                    : (Etat.lecteur && Etat.lecteur.playbackState === MprisPlaybackState.Paused
                                        ? Reglages.t("EN PAUSE", "PAUSED") : Reglages.t("VEILLE", "IDLE"))
                                font.pixelSize: 9; font.weight: Font.Bold; font.letterSpacing: 1.0
                                color: Etat.joue ? Couleurs.accentClair : Couleurs.texteSec
                            }
                        }
                    }
                    Texte {
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.max(0, parent.width - statut.width - parent.spacing)
                        visible: !!Etat.lecteur && Etat.lecteur.identity !== "" && width > 24
                        text: Etat.lecteur ? "· " + Etat.lecteur.identity : ""
                        font.pixelSize: 11; color: Couleurs.texteSec
                    }
                }

                Texte {
                    objectName: racine.musique ? "nc-scene-titre" : ""
                    y: 23; width: parent.width
                    text: Etat.titre || (Etat.lecteur ? Reglages.t("Sans titre", "Untitled") : Reglages.t("Aucun lecteur", "No player"))
                    font.pixelSize: 18; font.weight: Font.Bold
                    color: Couleurs.texte
                }

                Texte {
                    y: 47; width: parent.width
                    text: Etat.artiste || (Etat.lecteur ? Etat.lecteur.identity : Reglages.t("Lance un morceau pour l'afficher ici", "Start playback to control it here"))
                    font.pixelSize: 12; font.weight: Font.Medium
                    color: Couleurs.texteDoux
                }

                Row {
                    y: 68; height: 30; spacing: 8
                    readonly property real largeurFleche: Math.min(42, Math.max(0, (width - 2 * spacing) / 4))
                    width: parent.width

                    BoutonDracula {
                        objectName: "nc-transport-precedent"
                        width: parent.largeurFleche; height: 30
                        enabled: !!Etat.lecteur && Etat.lecteur.canGoPrevious
                        icone: "skip_previous"
                        libelle: Reglages.t("Précédent", "Previous")
                        afficherTexte: false
                        teinte: Couleurs.accent
                        onClicked: Etat.lecteur.previous()
                    }
                    BoutonDracula {
                        objectName: "nc-transport-lecture"
                        width: Math.min(116, Math.max(0, parent.width - 2 * (parent.largeurFleche + parent.spacing))); height: 30
                        enabled: !!Etat.lecteur && Etat.lecteur.canTogglePlaying
                        icone: Etat.joue ? "pause" : "play_arrow"
                        libelle: Etat.joue ? "Pause" : Reglages.t("Lecture", "Play")
                        teinte: Couleurs.accent
                        primaire: true
                        onClicked: Etat.lecturePause()
                    }
                    BoutonDracula {
                        objectName: "nc-transport-suivant"
                        width: parent.largeurFleche; height: 30
                        enabled: !!Etat.lecteur && Etat.lecteur.canGoNext
                        icone: "skip_next"
                        libelle: Reglages.t("Suivant", "Next")
                        afficherTexte: false
                        teinte: Couleurs.accent
                        onClicked: Etat.lecteur.next()
                    }
                }
            }
        }

        // ══════════════ 3. NOTIFICATIONS (BOÎTE DE RÉCEPTION) ══════════════
        Item {
            visible: racine.boite
            anchors.fill: parent

            Row {
                x: 18; y: 15; spacing: 8
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 8; height: 8; radius: 4
                    color: Notifs.nonLues > 0 ? Couleurs.rose : Couleurs.vert
                }
                Texte {
                    objectName: racine.boite ? "nc-scene-titre" : ""
                    anchors.verticalCenter: parent.verticalCenter
                    text: Notifs.nonLues > 0
                        ? String(Notifs.nonLues) + Reglages.t(Notifs.nonLues > 1 ? " non lues" : " non lue", " unread")
                        : Reglages.t("Tout est lu", "All caught up")
                    font.pixelSize: 20; font.weight: Font.Bold
                    color: Couleurs.texte
                }
            }

            Texte {
                anchors.right: parent.right; anchors.rightMargin: 18
                y: 20
                text: Reglages.t("Boîte de réception", "Inbox")
                font.pixelSize: 11; font.weight: Font.Medium
                color: Couleurs.texteSec
            }

            Rectangle {
                x: 16; y: 54
                width: Math.max(0, parent.width - 32); height: 1
                color: Qt.alpha(Couleurs.accent, 0.14)
            }

            Row {
                id: barreFiltres
                x: 14; y: 64
                width: Math.max(0, parent.width - 28); height: 30
                spacing: 8
                readonly property real lBouton: Math.floor((width - 16) / 3)

                Repeater {
                    model: 3
                    delegate: BoutonDracula {
                        required property int index
                        readonly property string cle: ["toutes", "nonlues", "urgentes"][index]
                        objectName: "nc-notifs-filtre-" + cle
                        width: index === 2 ? Math.max(0, barreFiltres.width - 2 * barreFiltres.lBouton - 16) : barreFiltres.lBouton
                        height: 30
                        icone: ["inbox", "mark_email_unread", "priority_high"][index]
                        libelle: [Reglages.t("Toutes", "All"), Reglages.t("Non lues", "Unread"), Reglages.t("Urgentes", "Urgent")][index]
                        teinte: index === 2 ? Couleurs.rose : (index === 1 ? Couleurs.cyan : Couleurs.accent)
                        choisi: racine.filtre === cle
                        estFiltre: true
                        onClicked: racine.choisirFiltre(cle)
                    }
                }
            }
        }
    }

    // Bouton net aligné au pixel, sans SVG étiré
    component BoutonDracula: ControleAction {
        id: btn
        property string icone: ""
        property string libelle: ""
        property color teinte: Couleurs.accent
        property bool primaire: false
        property bool choisi: false
        property bool afficherTexte: true
        readonly property bool montreTexte: afficherTexte && libelleVisible.implicitWidth + 29 <= width
        property bool estFiltre: false

        text: libelle
        opacity: enabled ? 1.0 : 0.42
        Accessible.checkable: estFiltre
        Accessible.checked: choisi
        ToolTip.visible: hovered && !montreTexte
        ToolTip.text: libelle
        ToolTip.delay: 450

        readonly property bool actifVisuel: primaire || choisi
        background: Rectangle {
            radius: 8
            color: btn.pressed ? Qt.alpha(btn.teinte, 0.32)
                 : btn.contientPointeur ? Qt.alpha(btn.teinte, btn.actifVisuel ? 0.26 : 0.16)
                 : btn.actifVisuel ? Qt.alpha(btn.teinte, 0.16)
                 : Qt.alpha(Couleurs.voile, 0.045)
            border.width: btn.visualFocus ? 2 : 1
            border.color: btn.contientPointeur || btn.visualFocus ? Qt.alpha(btn.teinte, 0.85)
                        : btn.actifVisuel ? Qt.alpha(btn.teinte, 0.48)
                        : Qt.alpha(Couleurs.voile, 0.11)
            Behavior on color { enabled: racine.animer; ColorAnimation { duration: 130; easing.type: Easing.OutCubic } }
            Behavior on border.color { enabled: racine.animer; ColorAnimation { duration: 130; easing.type: Easing.OutCubic } }
        }
        contentItem: Item {
            Row {
                anchors.centerIn: parent
                spacing: 6
                Ico {
                    anchors.verticalCenter: parent.verticalCenter
                    nom: btn.icone; taille: 15
                    color: btn.contientPointeur || btn.actifVisuel ? Qt.lighter(btn.teinte, 1.12) : btn.teinte
                }
                Texte {
                    id: libelleVisible
                    visible: btn.montreTexte
                    anchors.verticalCenter: parent.verticalCenter
                    text: btn.libelle
                    font.pixelSize: 12
                    font.weight: btn.actifVisuel ? Font.DemiBold : Font.Medium
                    color: Couleurs.texte
                }
            }
        }
    }
}
