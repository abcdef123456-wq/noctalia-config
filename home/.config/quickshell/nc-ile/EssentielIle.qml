// Vue essentielle de l'île ouverte : uniquement l'extrême essentiel (heure, date, état bref météo/batterie,
// activité média ou notifications non lues, et accès direct au Centre de contrôle et à la Recherche).
// Son dessin s'adapte à la famille du thème actif (Couleurs.familleTheme, forme, rayon, bordure, police).
import QtQuick
import Quickshell
import Quickshell.Widgets
import Quickshell.Services.UPower

Item {
    id: vue
    readonly property bool estBrut: Couleurs.familleTheme === "brut" || Couleurs.forme === "cadre"
    readonly property bool estEditorial: Couleurs.familleTheme === "editorial"
    readonly property bool estNeon: Couleurs.familleTheme === "neon" || Couleurs.familleTheme === "matrice"
    readonly property bool aResumeNotif: !Etat.aMusique && Notifs.nonLues > 0
    readonly property var derniereNotif: aResumeNotif && Notifs.liste.length > 0 ? Notifs.liste[0] : null
    readonly property string dateLongue: Etat.dateLongue || ""
    signal ouvrirControle()
    signal ouvrirRecherche()
    signal ouvrirThemes()

    implicitHeight: colonne.implicitHeight

    Column {
        id: colonne
        width: parent.width
        spacing: 12

        // ── En-tête essentiel : grande heure, date et indicateurs discrets (météo / batterie / concentration) ──
        Rectangle {
            id: carteHeure
            width: parent.width
            height: rangeeHeure.implicitHeight + 24
            radius: Couleurs.rayon(18, width, height)
            color: vue.estBrut ? "transparent" : Couleurs.carte
            border.width: vue.estBrut ? Couleurs.epaisseurBordureCarte : 1
            border.color: Couleurs.bordureSubtile

            // Filet d'accent sur le bord gauche pour les thèmes architecturaux / terminal / néon
            Rectangle {
                visible: vue.estBrut || vue.estNeon
                x: 0; y: 10
                width: 3; height: parent.height - 20
                radius: Couleurs.rayon(2, width, height)
                color: Couleurs.accent
            }

            Item {
                id: rangeeHeure
                anchors.left: parent.left; anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: (vue.estBrut || vue.estNeon) ? 16 : 14
                anchors.rightMargin: 14
                implicitHeight: Math.max(blocHeure.implicitHeight, blocEtat.implicitHeight)

                Column {
                    id: blocHeure
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2

                    Texte {
                        objectName: "nc-essentiel-heure"
                        text: Etat.heure
                        font.pixelSize: vue.estEditorial ? 32 : 30
                        font.weight: vue.estEditorial ? Font.Medium : Font.Bold
                        font.features: ({ "tnum": 1 })
                        color: (vue.estBrut || vue.estNeon) ? Couleurs.accent : Couleurs.texte
                    }
                    Texte {
                        objectName: "nc-essentiel-date"
                        text: vue.dateLongue.charAt(0).toUpperCase() + vue.dateLongue.slice(1)
                        secondaire: true
                        font.pixelSize: 12
                    }
                }

                Column {
                    id: blocEtat
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 6

                    // Météo brève (si disponible)
                    Row {
                        anchors.right: parent.right
                        spacing: 5
                        visible: Etat.meteoPilule
                        Ico {
                            anchors.verticalCenter: parent.verticalCenter
                            nom: Etat.meteo.icone || "cloud"
                            taille: 16
                            color: Couleurs.accent
                        }
                        Texte {
                            anchors.verticalCenter: parent.verticalCenter
                            text: (Etat.meteo.temp !== undefined ? Etat.meteo.temp : "") + "°"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            font.features: ({ "tnum": 1 })
                        }
                    }

                    // Batterie compacte (sur portable)
                    Row {
                        anchors.right: parent.right
                        spacing: 5
                        visible: Etat.batteriePc
                        Ico {
                            anchors.verticalCenter: parent.verticalCenter
                            nom: Etat.enCharge ? "bolt" : (Etat.pourcent <= 20 ? "battery_1_bar" : (Etat.pourcent <= 55 ? "battery_4_bar" : "battery_full"))
                            taille: 15
                            color: Etat.enCharge ? Couleurs.vert : (Etat.pourcent <= 20 ? Couleurs.rouge : Couleurs.texteSec)
                        }
                        Texte {
                            anchors.verticalCenter: parent.verticalCenter
                            text: Etat.pourcent + Reglages.t(" %", "%")
                            secondaire: !Etat.enCharge && Etat.pourcent > 20
                            color: Etat.enCharge ? Couleurs.vert : (Etat.pourcent <= 20 ? Couleurs.rouge : Couleurs.texteSec)
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            font.features: ({ "tnum": 1 })
                        }
                    }

                    // Pastille Concentration / VPN si actif
                    Row {
                        anchors.right: parent.right
                        spacing: 6
                        visible: Modes.pastille || VpnEtat.indicateur
                        Ico {
                            visible: VpnEtat.indicateur
                            anchors.verticalCenter: parent.verticalCenter
                            nom: "shield_lock"
                            taille: 14
                            color: Couleurs.vert
                        }
                        Ico {
                            visible: Modes.pastille
                            anchors.verticalCenter: parent.verticalCenter
                            nom: Modes.actifIcone
                            taille: 14
                            color: Couleurs.accentClair
                        }
                    }
                }
            }
        }

        // ── Bandeau contextuel : musique en cours (si présente) ──
        Rectangle {
            objectName: "nc-essentiel-musique"
            visible: Etat.aMusique
            width: parent.width
            height: 58
            radius: Couleurs.rayon(16, width, height)
            color: zm.containsMouse ? Couleurs.carteSurvol : Couleurs.carte
            border.width: 1
            border.color: Couleurs.bordureSubtile
            Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }

            MouseArea {
                id: zm
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: if (Etat.vues.indexOf("musique") >= 0) Etat.aller("musique")
            }

            ClippingRectangle {
                id: pochette
                x: 10
                anchors.verticalCenter: parent.verticalCenter
                width: 38; height: 38
                radius: Couleurs.rayon(10, width, height)
                color: Couleurs.gris2
                Image {
                    anchors.fill: parent
                    source: Etat.pochette !== "" ? Etat.pochette : Etat.iconeLecteur
                    sourceSize: Qt.size(76, 76)
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: Etat.pochette !== ""
                }
                Ico {
                    anchors.centerIn: parent
                    nom: "music_note"
                    taille: 18
                    color: Couleurs.texteSec
                    visible: Etat.pochette === "" && Etat.iconeLecteur === ""
                }
            }

            Column {
                anchors.left: pochette.right; anchors.leftMargin: 10
                anchors.right: commandesMusique.left; anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                spacing: 1
                Texte {
                    width: parent.width
                    text: Etat.titre
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                }
                Texte {
                    width: parent.width
                    visible: Etat.artiste !== ""
                    text: Etat.artiste
                    secondaire: true
                    font.pixelSize: 11
                }
            }

            Row {
                id: commandesMusique
                anchors.right: parent.right; anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4

                Rectangle {
                    width: 30; height: 30; radius: width / 2
                    color: zPlay.containsMouse ? Couleurs.gris3 : Couleurs.gris2
                    Ico { anchors.centerIn: parent; nom: Etat.joue ? "pause" : "play_arrow"; taille: 17; color: Couleurs.texte }
                    MouseArea { id: zPlay; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: Etat.lecturePause() }
                    Accessible.role: Accessible.Button
                    Accessible.name: Etat.joue ? Reglages.t("Pause", "Pause") : Reglages.t("Lecture", "Play")
                }
                Rectangle {
                    width: 30; height: 30; radius: width / 2
                    color: zNext.containsMouse ? Couleurs.gris3 : "transparent"
                    Ico { anchors.centerIn: parent; nom: "skip_next"; taille: 17; color: Couleurs.texteSec }
                    MouseArea { id: zNext; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: if (Etat.lecteur) Etat.lecteur.next() }
                    Accessible.role: Accessible.Button
                    Accessible.name: Reglages.t("Morceau suivant", "Next track")
                }
            }
        }

        // ── Bandeau contextuel : aperçu des notifications non lues (si pas de musique) ──
        Rectangle {
            objectName: "nc-essentiel-notifs"
            visible: vue.aResumeNotif
            width: parent.width
            height: 48
            radius: Couleurs.rayon(15, width, height)
            color: zn.containsMouse ? Couleurs.carteSurvol : Couleurs.carte
            border.width: 1
            border.color: Couleurs.bordureSubtile

            MouseArea {
                id: zn
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: if (Etat.vues.indexOf("notifications") >= 0) Etat.aller("notifications")
            }

            Rectangle {
                id: pastilleNotif
                x: 12; anchors.verticalCenter: parent.verticalCenter
                width: 26; height: 26; radius: width / 2
                color: Couleurs.accentDoux
                Ico { anchors.centerIn: parent; nom: "notifications_active"; taille: 15; color: Couleurs.accent }
            }

            Texte {
                anchors.left: pastilleNotif.right; anchors.leftMargin: 10
                anchors.right: compteurNotif.left; anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                text: vue.derniereNotif ? (vue.derniereNotif.summary || vue.derniereNotif.appName || Reglages.t("Nouvelle notification", "New notification"))
                                        : Reglages.t("Notifications non lues", "Unread notifications")
                font.pixelSize: 12
                font.weight: Font.Medium
            }

            Rectangle {
                id: compteurNotif
                anchors.right: parent.right; anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                width: Math.max(22, texteCompteur.implicitWidth + 12); height: 22
                radius: height / 2
                color: Couleurs.accent
                Texte {
                    id: texteCompteur
                    anchors.centerIn: parent
                    text: String(Notifs.nonLues)
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: Couleurs.surAccent
                }
            }
        }

        // ── Passerelle épurée : Centre de contrôle, Recherche, Thèmes ──
        Row {
            id: actions
            width: parent.width
            spacing: 8

            Rectangle {
                objectName: "nc-essentiel-controle"
                width: Math.floor((parent.width - 52) * 0.62)
                height: 40
                radius: Couleurs.rayon(14, width, height)
                color: zc.containsMouse ? Couleurs.accent : Couleurs.accentDoux
                border.width: 1
                border.color: Couleurs.accentBord
                Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }

                Row {
                    anchors.centerIn: parent
                    spacing: 7
                    Ico {
                        anchors.verticalCenter: parent.verticalCenter
                        nom: "tune"; taille: 17
                        color: zc.containsMouse ? Couleurs.surAccent : Couleurs.accent
                    }
                    Texte {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Reglages.t("Centre de contrôle", "Control Center")
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        color: zc.containsMouse ? Couleurs.surAccent : Couleurs.texte
                    }
                }
                MouseArea {
                    id: zc
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: vue.ouvrirControle()
                }
                Accessible.role: Accessible.Button
                Accessible.name: Reglages.t("Ouvrir le Centre de contrôle", "Open Control Center")
            }

            Rectangle {
                objectName: "nc-essentiel-recherche"
                width: parent.width - Math.floor((parent.width - 52) * 0.62) - 52
                height: 40
                radius: Couleurs.rayon(14, width, height)
                color: zr.containsMouse ? Couleurs.carteSurvol : Couleurs.carte
                border.width: 1
                border.color: Couleurs.bordureSubtile

                Row {
                    anchors.centerIn: parent
                    spacing: 6
                    Ico { anchors.verticalCenter: parent.verticalCenter; nom: "search"; taille: 16; color: Couleurs.texteSec }
                    Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Chercher", "Search"); font.pixelSize: 12; font.weight: Font.Medium }
                }
                MouseArea {
                    id: zr
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: vue.ouvrirRecherche()
                }
                Accessible.role: Accessible.Button
                Accessible.name: Reglages.t("Ouvrir la recherche", "Open search")
            }

            Rectangle {
                objectName: "nc-essentiel-themes"
                width: 36
                height: 40
                radius: Couleurs.rayon(14, width, height)
                color: zt.containsMouse ? Couleurs.carteSurvol : Couleurs.carte
                border.width: 1
                border.color: Couleurs.bordureSubtile

                Ico { anchors.centerIn: parent; nom: "palette"; taille: 17; color: zt.containsMouse ? Couleurs.accent : Couleurs.texteSec }
                MouseArea {
                    id: zt
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: vue.ouvrirThemes()
                }
                Accessible.role: Accessible.Button
                Accessible.name: Reglages.t("Choisir un thème", "Choose a theme")
            }
        }
    }
}
