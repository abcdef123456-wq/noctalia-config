// Tableau de bord : la composition du thème place l'heure, l'illustration et les indicateurs.
import QtQuick
import Quickshell
import Quickshell.Widgets
import Quickshell.Services.UPower
import "CompositionIle.js" as Composition

Item {
    id: vue
    property var plan: Composition.pour(Couleurs.themeActif)
    readonly property var composition: Composition.accueil(plan)
    readonly property bool estBrut: Couleurs.styleBrut
    readonly property bool estTerminal: Couleurs.styleTerminal
    readonly property bool estEditorial: Couleurs.styleEditorial
    readonly property bool estNeon: Couleurs.styleNeon
    readonly property bool estApple: Couleurs.styleApple
    readonly property bool aResumeNotif: !Partage.silence && !Etat.aMusique && Notifs.nonLues > 0
    readonly property var derniereNotif: aResumeNotif && Notifs.liste.length > 0 ? Notifs.liste[0] : null
    readonly property string dateFormatee: {
        var d = Etat.dateLongue || ""
        if (!d) return ""
        var cap = d.charAt(0).toUpperCase() + d.slice(1)
        return (estBrut || estTerminal) ? cap.toUpperCase() : cap
    }
    readonly property real progresMusique: Etat.lecteur && Etat.lecteur.length > 0
        ? Math.max(0, Math.min(1, Etat.lecteur.position / Etat.lecteur.length)) : 0
    signal ouvrirControle(Item bouton)
    signal ouvrirRecherche()
    signal ouvrirThemes()

    implicitHeight: colonne.implicitHeight

    Column {
        id: colonne
        width: parent.width
        spacing: 12

        Item {
            id: zoneHero
            width: parent.width
            height: Math.max(vue.composition.h, blocAmbiant.y + blocAmbiant.implicitHeight + 4,
                             blocTemps.y + blocTemps.implicitHeight + 4)
            readonly property var placeHeure: vue.composition.heure
            readonly property var placeArt: vue.composition.art
            readonly property var placeEtat: vue.composition.etat

            Rectangle {
                anchors.fill: parent
                visible: vue.plan.accueil === "carte" || vue.plan.accueil === "dalle" || vue.plan.accueil === "terminal"
                color: vue.plan.accueil === "terminal" ? "transparent" : Couleurs.surfaceDouce
                radius: Couleurs.rayon(vue.plan.accueil === "carte" ? Couleurs.rayonBloc : 0, width, height)
                border.width: vue.plan.accueil === "carte" ? 0 : 1
                border.color: Couleurs.bordureSubtile
            }
            Rectangle {
                visible: vue.plan.accueil === "marge" || vue.plan.accueil === "jardin"
                x: parent.width * (vue.plan.accueil === "marge" ? .29 : .60)
                y: 8; width: 1; height: parent.height - 16
                color: Couleurs.separateur
            }
            MotifIle {
                dessin: vue.plan.dessin
                x: zoneHero.width * zoneHero.placeArt[0]; y: zoneHero.placeArt[1]
                width: zoneHero.width * zoneHero.placeArt[2]; height: zoneHero.placeArt[3]
                opacity: vue.plan.accueil === "minimal" ? .32 : .84
            }
            Column {
                id: blocTemps
                objectName: "nc-essentiel-temps"
                x: zoneHero.width * zoneHero.placeHeure[0] + (vue.plan.accueil === "terminal" || vue.plan.accueil === "dalle" ? 12 : 0)
                y: zoneHero.placeHeure[1]
                width: zoneHero.width * zoneHero.placeHeure[2]
                spacing: 2
                readonly property int alignement: zoneHero.placeHeure[3] === "centre" ? Text.AlignHCenter
                    : zoneHero.placeHeure[3] === "droite" ? Text.AlignRight : Text.AlignLeft
                Texte {
                    id: heureTxt
                    objectName: "nc-essentiel-heure"
                    width: parent.width
                    horizontalAlignment: blocTemps.alignement
                    text: (vue.plan.accueil === "terminal" ? "> " : "") + Etat.heure
                    font.pixelSize: Math.max(1, Math.min(parent.width / 3.3, vue.estBrut ? 42 : vue.plan.accueil === "minimal" ? 46 : 38))
                    font.weight: vue.estEditorial ? Font.Normal : (vue.estBrut ? Font.Black : Font.DemiBold)
                    font.features: ({ "tnum": 1 })
                    font.letterSpacing: vue.estEditorial ? -0.5 : (vue.estBrut ? 0.8 : -0.4)
                    color: (vue.estTerminal || vue.estBrut) ? Couleurs.accent : Couleurs.texte
                }

                Texte {
                    objectName: "nc-essentiel-date"
                    width: parent.width
                    horizontalAlignment: blocTemps.alignement
                    visible: Reglages.val("ILE_DATE", "oui") !== "non"
                    text: vue.dateFormatee
                    secondaire: true
                    font.pixelSize: (vue.estBrut || vue.estTerminal) ? 10 : 12
                    font.letterSpacing: (vue.estBrut || vue.estTerminal) ? 0.8 : 0
                }
            }

            // Tous les états restent accessibles, que le thème les range comme une légende ou un statut.
            Column {
                id: blocAmbiant
                objectName: "nc-essentiel-etat"
                x: zoneHero.width * zoneHero.placeEtat[0] + (vue.plan.accueil === "dalle" ? 12 : 0)
                y: Math.max(zoneHero.placeEtat[1], x < blocTemps.x + blocTemps.width && x + width > blocTemps.x
                            ? blocTemps.y + blocTemps.implicitHeight + 6 : 0)
                width: zoneHero.width * zoneHero.placeEtat[2] - (vue.plan.accueil === "dalle" ? 24 : 0)
                spacing: 5
                readonly property string alignement: zoneHero.placeEtat[3]
                function debut(ligne) {
                    return Math.max(0, alignement === "centre" ? (width - ligne) / 2
                                      : alignement === "droite" ? width - ligne : 0)
                }
                // Météo + Batterie sur une ligne fluide
                Row {
                    x: blocAmbiant.debut(implicitWidth)
                    spacing: 8
                    visible: Etat.meteoPilule || Etat.batteriePc

                    Row {
                        visible: Etat.meteoPilule
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 4
                        Ico {
                            anchors.verticalCenter: parent.verticalCenter
                            nom: Etat.meteo.icone || "partly_cloudy_day"
                            taille: 16
                            color: vue.estNeon || vue.estTerminal ? Couleurs.accent : Couleurs.texteDoux
                        }
                        Texte {
                            anchors.verticalCenter: parent.verticalCenter
                            text: (Etat.meteo.temp !== undefined ? Etat.meteo.temp : "") + "°"
                            font.pixelSize: 14; font.weight: Font.DemiBold
                            font.features: ({ "tnum": 1 })
                        }
                    }

                    Rectangle {
                        visible: Etat.batteriePc
                        anchors.verticalCenter: parent.verticalCenter
                        width: rowBat.implicitWidth + 14; height: 24
                        radius: Couleurs.rayon((vue.estBrut || vue.estTerminal) ? 2 : 12, width, height)
                        color: Etat.enCharge ? Qt.alpha(Couleurs.vert, 0.16) : Couleurs.surfaceDouce
                        border.width: (vue.estBrut || vue.estTerminal || vue.estNeon) ? 1 : 0
                        border.color: Etat.enCharge ? Qt.alpha(Couleurs.vert, 0.45) : Couleurs.bordureSubtile
                        Row {
                            id: rowBat
                            anchors.centerIn: parent; spacing: 4
                            Ico {
                                anchors.verticalCenter: parent.verticalCenter
                                nom: Etat.enCharge ? "bolt" : (Etat.pourcent <= 20 ? "battery_alert" : "battery_5_bar")
                                taille: 13
                                color: Etat.enCharge ? Couleurs.vert : (Etat.pourcent <= 20 ? Couleurs.rouge : Couleurs.texteSec)
                            }
                            Texte {
                                anchors.verticalCenter: parent.verticalCenter
                                text: Etat.pourcent + Reglages.t(" %", "%")
                                font.pixelSize: 11; font.weight: Font.DemiBold
                                font.features: ({ "tnum": 1 })
                                color: Etat.enCharge ? Couleurs.vert : (Etat.pourcent <= 20 ? Couleurs.rouge : Couleurs.texte)
                            }
                        }
                    }
                }

                // Pastilles d'état actives (seulement si VPN ou Concentration actif)
                Row {
                    x: blocAmbiant.debut(implicitWidth)
                    spacing: 6
                    visible: Notifs.concentration || VpnEtat.indicateur || Modes.pastille

                    Rectangle {
                        visible: Notifs.concentration || Modes.pastille
                        width: rMode.implicitWidth + 12; height: 20
                        radius: Couleurs.rayon((vue.estBrut || vue.estTerminal) ? 2 : 10, width, height)
                        color: Qt.alpha(Couleurs.violet, 0.16)
                        Row {
                            id: rMode; anchors.centerIn: parent; spacing: 4
                            Ico { anchors.verticalCenter: parent.verticalCenter; nom: Modes.pastille ? Modes.actifIcone : "do_not_disturb_on"; taille: 12; color: Couleurs.violet }
                            Texte {
                                anchors.verticalCenter: parent.verticalCenter
                                text: Modes.nomVisible || Reglages.t("Silence", "DND")
                                width: Math.max(0, Math.min(implicitWidth, blocAmbiant.width - (VpnEtat.indicateur ? 71 : 28)))
                                font.pixelSize: 10; font.weight: Font.DemiBold; color: Couleurs.violet
                            }
                        }
                    }

                    Rectangle {
                        visible: VpnEtat.indicateur
                        width: rVpn.implicitWidth + 12; height: 20
                        radius: Couleurs.rayon((vue.estBrut || vue.estTerminal) ? 2 : 10, width, height)
                        color: Qt.alpha(Couleurs.vert, 0.15)
                        Row {
                            id: rVpn; anchors.centerIn: parent; spacing: 4
                            Ico { anchors.verticalCenter: parent.verticalCenter; nom: "shield_lock"; taille: 12; color: Couleurs.vert }
                            Texte { anchors.verticalCenter: parent.verticalCenter; text: "VPN"; font.pixelSize: 10; font.weight: Font.DemiBold; color: Couleurs.vert }
                        }
                    }
                }
            }
        }

        // ── Activité en direct : Mini-lecteur Musique fluide (si média actif) ──
        Rectangle {
            objectName: "nc-essentiel-musique"
            visible: Etat.aMusique
            width: parent.width
            height: 62
            radius: Couleurs.rayon((vue.estBrut || vue.estTerminal) ? 3 : 16, width, height)
            color: vue.estEditorial ? "transparent" : Couleurs.surfaceDouce
            border.width: (vue.estBrut || vue.estTerminal || vue.estNeon || vue.estEditorial) ? 1 : 0
            border.color: vue.estNeon ? Couleurs.accentBord : Couleurs.bordureSubtile

            // Pochette
            ClippingRectangle {
                id: pochette
                x: 9; anchors.verticalCenter: parent.verticalCenter
                width: 44; height: 44
                radius: Couleurs.rayon((vue.estBrut || vue.estTerminal) ? 2 : 11, width, height)
                color: Couleurs.gris2
                Image {
                    anchors.fill: parent
                    source: Reglages.imagesLegeres ? "" : Etat.pochette
                    fillMode: Image.PreserveAspectCrop
                    visible: status === Image.Ready
                }
                Ico {
                    anchors.centerIn: parent
                    nom: "music_note"; taille: 20; color: Couleurs.accent
                    visible: Reglages.imagesLegeres || Etat.pochette === ""
                }
                MouseArea {
                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                    onClicked: if (Etat.vues.indexOf("musique") >= 0) Etat.aller("musique")
                }
            }

            Column {
                anchors.left: pochette.right; anchors.leftMargin: 10
                anchors.right: commandesMusique.left; anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                spacing: 3

                Texte {
                    width: parent.width
                    text: Etat.titre
                    font.pixelSize: 13; font.weight: Font.DemiBold
                }
                Texte {
                    width: parent.width
                    visible: Etat.artiste !== ""
                    text: Etat.artiste
                    secondaire: true; font.pixelSize: 11
                }
                // Barre de progression fine intégrée
                Rectangle {
                    visible: !!Etat.lecteur && Etat.lecteur.length > 0
                    width: parent.width; height: 3
                    radius: Couleurs.rayon(2, width, height)
                    color: Qt.alpha(Couleurs.voile, 0.14)
                    Rectangle {
                        width: parent.width * vue.progresMusique
                        height: parent.height
                        radius: parent.radius
                        color: Couleurs.accent
                    }
                }
            }

            Row {
                id: commandesMusique
                anchors.right: parent.right; anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4

                Rectangle {
                    width: 26; height: 26
                    radius: Couleurs.rayon((vue.estBrut || vue.estTerminal) ? 2 : 13, width, height)
                    color: zPrev.containsMouse ? Couleurs.gris3 : "transparent"
                    Ico { anchors.centerIn: parent; nom: "skip_previous"; taille: 16; color: Couleurs.texteSec }
                    MouseArea { id: zPrev; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: if (Etat.lecteur) Etat.lecteur.previous() }
                    Accessible.role: Accessible.Button
                    Accessible.name: Reglages.t("Morceau précédent", "Previous track")
                }
                Rectangle {
                    width: 30; height: 30
                    radius: Couleurs.rayon((vue.estBrut || vue.estTerminal) ? 2 : 15, width, height)
                    color: zPlay.containsMouse ? Couleurs.accentClair : (vue.estBrut || vue.estTerminal || vue.estNeon ? Couleurs.accent : Couleurs.gris2)
                    Ico {
                        anchors.centerIn: parent
                        nom: Etat.joue ? "pause" : "play_arrow"; taille: 17
                        color: (zPlay.containsMouse || vue.estBrut || vue.estTerminal || vue.estNeon) ? Couleurs.surAccent : Couleurs.texte
                    }
                    MouseArea { id: zPlay; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: Etat.lecturePause() }
                    Accessible.role: Accessible.Button
                    Accessible.name: Etat.joue ? Reglages.t("Pause", "Pause") : Reglages.t("Lecture", "Play")
                }
                Rectangle {
                    width: 26; height: 26
                    radius: Couleurs.rayon((vue.estBrut || vue.estTerminal) ? 2 : 13, width, height)
                    color: zNext.containsMouse ? Couleurs.gris3 : "transparent"
                    Ico { anchors.centerIn: parent; nom: "skip_next"; taille: 16; color: Couleurs.texteSec }
                    MouseArea { id: zNext; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: if (Etat.lecteur) Etat.lecteur.next() }
                    Accessible.role: Accessible.Button
                    Accessible.name: Reglages.t("Morceau suivant", "Next track")
                }
            }
        }

        // ── Activité en direct : Aperçu des notifications non lues (si pas de musique) ──
        Rectangle {
            objectName: "nc-essentiel-notifs"
            visible: vue.aResumeNotif
            width: parent.width
            height: 44
            radius: Couleurs.rayon((vue.estBrut || vue.estTerminal) ? 3 : 14, width, height)
            color: zn.containsMouse ? Couleurs.carteSurvol : (vue.estEditorial ? "transparent" : Couleurs.surfaceDouce)
            border.width: (vue.estBrut || vue.estTerminal || vue.estNeon || vue.estEditorial) ? 1 : 0
            border.color: Couleurs.bordureSubtile

            MouseArea {
                id: zn
                anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: if (Etat.vues.indexOf("notifications") >= 0) Etat.aller("notifications")
            }

            Rectangle {
                id: dotNotif
                x: 12; anchors.verticalCenter: parent.verticalCenter
                width: 8; height: 8
                radius: Couleurs.rayon((vue.estBrut || vue.estTerminal) ? 1 : 4, width, height)
                color: Couleurs.accent
            }

            Texte {
                anchors.left: dotNotif.right; anchors.leftMargin: 10
                anchors.right: compteurNotif.left; anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                text: vue.derniereNotif ? (vue.derniereNotif.summary || vue.derniereNotif.appName || Reglages.t("Nouvelle notification", "New notification"))
                                        : Reglages.t("Notifications non lues", "Unread notifications")
                font.pixelSize: 12; font.weight: Font.Medium
            }

            Rectangle {
                id: compteurNotif
                anchors.right: parent.right; anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                width: Math.max(22, texteCompteur.implicitWidth + 10); height: 20
                radius: Couleurs.rayon((vue.estBrut || vue.estTerminal) ? 2 : 10, width, height)
                color: Couleurs.accent
                Texte {
                    id: texteCompteur
                    anchors.centerIn: parent
                    text: String(Notifs.nonLues)
                    font.pixelSize: 10; font.weight: Font.Bold
                    color: Couleurs.surAccent
                }
            }
        }

        // Séparateur et passerelle vers les surfaces du bureau.
        Rectangle {
            width: parent.width; height: 1
            color: Couleurs.separateur
            opacity: 0.7
        }

        Item {
            id: actions
            width: parent.width
            height: 32

            // Bouton principal : ouvrir le Centre de contrôle dédié
            Rectangle {
                id: boutonControle
                objectName: "nc-essentiel-controle"
                anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                width: rowCtrl.implicitWidth + 22; height: 32
                radius: Couleurs.rayon((vue.estBrut || vue.estTerminal) ? 2 : 16, width, height)
                color: zc.containsMouse ? Couleurs.surfaceActive : Couleurs.surfaceDouce
                border.width: (vue.estBrut || vue.estTerminal || vue.estNeon || vue.estEditorial) ? 1 : 0
                border.color: zc.containsMouse ? Couleurs.accent : Couleurs.bordureSubtile
                Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 110 } }

                Row {
                    id: rowCtrl
                    anchors.centerIn: parent; spacing: 7
                    Ico {
                        anchors.verticalCenter: parent.verticalCenter
                        nom: "tune"; taille: 15
                        color: zc.containsMouse ? Couleurs.texteSurSurfaceActive : Couleurs.accent
                    }
                    Texte {
                        anchors.verticalCenter: parent.verticalCenter
                        text: (vue.estBrut || vue.estTerminal)
                              ? Reglages.t("CONTRÔLE", "CONTROL")
                              : Reglages.t("Centre de contrôle", "Control Center")
                        font.pixelSize: (vue.estBrut || vue.estTerminal) ? 10 : 12
                        font.weight: Font.DemiBold
                        font.letterSpacing: (vue.estBrut || vue.estTerminal) ? 0.8 : 0
                        color: zc.containsMouse ? Couleurs.texteSurSurfaceActive : Couleurs.texte
                    }
                }
                MouseArea {
                    id: zc; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: vue.ouvrirControle(boutonControle)
                }
                Accessible.role: Accessible.Button
                Accessible.name: Reglages.t("Centre de contrôle", "Control Center")
            }

            // Actions secondaires compactes à droite : Recherche + Thèmes
            Row {
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                spacing: 6

                Rectangle {
                    objectName: "nc-essentiel-recherche"
                    width: 32; height: 32
                    radius: Couleurs.rayon((vue.estBrut || vue.estTerminal) ? 2 : 16, width, height)
                    color: zr.containsMouse ? Couleurs.surfaceActive : Couleurs.surfaceDouce
                    border.width: (vue.estBrut || vue.estTerminal || vue.estNeon || vue.estEditorial) ? 1 : 0
                    border.color: zr.containsMouse ? Couleurs.accent : Couleurs.bordureSubtile
                    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 110 } }
                    Ico {
                        anchors.centerIn: parent; nom: "search"; taille: 16
                        color: zr.containsMouse ? Couleurs.texteSurSurfaceActive : Couleurs.texteSec
                    }
                    MouseArea {
                        id: zr; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: vue.ouvrirRecherche()
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: Reglages.t("Rechercher", "Search")
                }

                Rectangle {
                    objectName: "nc-essentiel-themes"
                    width: 32; height: 32
                    radius: Couleurs.rayon((vue.estBrut || vue.estTerminal) ? 2 : 16, width, height)
                    color: zth.containsMouse ? Couleurs.surfaceActive : Couleurs.surfaceDouce
                    border.width: (vue.estBrut || vue.estTerminal || vue.estNeon || vue.estEditorial) ? 1 : 0
                    border.color: zth.containsMouse ? Couleurs.accent : Couleurs.bordureSubtile
                    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 110 } }
                    Ico {
                        anchors.centerIn: parent; nom: "palette"; taille: 16
                        color: zth.containsMouse ? Couleurs.texteSurSurfaceActive : Couleurs.texteSec
                    }
                    MouseArea {
                        id: zth; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: vue.ouvrirThemes()
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: Reglages.t("Thèmes du bureau", "Desktop themes")
                }
            }
        }
    }
}
