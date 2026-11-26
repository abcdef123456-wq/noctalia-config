// Activités et actions sous la scène du thème actif.
import QtQuick
import Quickshell.Widgets

Item {
    id: vue
    readonly property bool estBrut: Couleurs.styleBrut
    readonly property bool estTerminal: Couleurs.styleTerminal
    readonly property bool estEditorial: Couleurs.styleEditorial
    readonly property bool estNeon: Couleurs.styleNeon
    readonly property bool aResumeNotif: !Partage.silence && !Etat.aMusique && Notifs.nonLues > 0
    readonly property var derniereNotif: aResumeNotif && Notifs.liste.length > 0 ? Notifs.liste[0] : null
    readonly property real progresMusique: Etat.lecteur && Etat.lecteur.length > 0
        ? Math.max(0, Math.min(1, Etat.lecteur.position / Etat.lecteur.length)) : 0

    implicitHeight: colonne.implicitHeight

    Column {
        id: colonne
        width: parent.width
        spacing: 12

        Item {
            width: parent.width
            visible: blocAmbiant.implicitHeight > 0
            height: blocAmbiant.implicitHeight
            Column {
                id: blocAmbiant
                objectName: "nc-essentiel-etat"
                width: parent.width
                spacing: 5
                // Météo + Batterie sur une ligne fluide
                Row {
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

    }
}
