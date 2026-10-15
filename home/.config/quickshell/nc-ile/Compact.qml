// Contenu de la pilule (île fermée) :
//   repos   : heure et date ;  musique : pochette, heure, onde sonore (en pause : symbole lecture et titre)
//   réactions (2 à 3 s) : volume, luminosité, nouveau morceau, chargeur, profil d'énergie, mode jeu
// largeur : largeur voulue de la pilule ; l'île s'y ajuste avec un ressort.
import QtQuick
import Quickshell.Widgets
import Quickshell.Services.UPower

Item {
    id: c
    readonly property string mode: Etat.activiteType !== "" ? Etat.activiteType
                                   : (Etat.aMusique ? "musique" : (Etat.minuteurFin > 0 ? "minuteur" : "repos"))
    readonly property real largeur: Math.max(110, actif.implicitWidth + 32)
    implicitHeight: 30

    readonly property Item actif: ({ repos: repos, musique: musique, volume: jauge, luminosite: jauge,
                                      piste: piste, charge: charge, profil: profil, jeu: jeu,
                                      minuteur: minuteur, "minuteur-fini": fini })[mode] || repos

    component Fondu: Row {
        property bool montre: false
        anchors.centerIn: parent
        spacing: 9
        opacity: montre ? 1 : 0
        visible: opacity > 0.01
        Behavior on opacity { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
    }

    // ── Repos : heure et date ──
    Fondu {
        id: repos
        montre: c.mode === "repos"
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.heure; font.weight: Font.DemiBold }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.dateCourte; secondaire: true }
    }

    // ── Musique : pochette | heure (et titre en pause) | onde ──
    Fondu {
        id: musique
        montre: c.mode === "musique"
        ClippingRectangle {
            width: 20; height: 20; radius: 6; color: Etat.pochette === "" && Etat.iconeLecteur !== "" ? "transparent" : "#2c2c2e"
            anchors.verticalCenter: parent.verticalCenter
            Image { anchors.fill: parent; source: Etat.pochette; fillMode: Image.PreserveAspectCrop; asynchronous: true }
            Image { anchors.fill: parent; source: Etat.pochette === "" ? Etat.iconeLecteur : ""; sourceSize: Qt.size(40, 40); visible: Etat.pochette === "" }
            Ico { anchors.centerIn: parent; nom: "music_note"; taille: 14; visible: Etat.pochette === "" && Etat.iconeLecteur === "" }
        }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.heure; font.weight: Font.DemiBold }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.titre; secondaire: true; visible: !Etat.joue; width: Math.min(implicitWidth, 150) }
        Row {
            visible: Etat.joue
            spacing: 2
            anchors.verticalCenter: parent.verticalCenter
            Repeater {
                model: 5
                Rectangle {
                    required property int index
                    width: 3; radius: 1.5
                    height: 6 + Etat.bandes[index] * 10
                    anchors.verticalCenter: parent.verticalCenter
                    color: "white"
                    Behavior on height { NumberAnimation { duration: 70 } }
                }
            }
        }
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "play_arrow"; taille: 16; color: "#98989d"; visible: !Etat.joue }
    }

    // ── Minuteur en cours : décompte orange ──
    Fondu {
        id: minuteur
        montre: c.mode === "minuteur"
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "timer"; taille: 17; color: "#ff9f0a" }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.duree(Etat.minuteurReste); font.weight: Font.DemiBold; color: "#ff9f0a"; font.features: { "tnum": 1 } }
    }
    Fondu {
        id: fini
        montre: c.mode === "minuteur-fini"
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "alarm"; taille: 18; color: "#ff9f0a" }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: "Minuteur terminé"; font.weight: Font.DemiBold }
    }

    // ── Volume / luminosité : jauge blanche ──
    Fondu {
        id: jauge
        readonly property bool vol: c.mode === "volume"
        readonly property real valeur: vol ? (Etat.muet ? 0 : Etat.volume) : Etat.luminosite
        montre: c.mode === "volume" || c.mode === "luminosite"
        Ico {
            anchors.verticalCenter: parent.verticalCenter
            nom: jauge.vol ? (Etat.muet ? "volume_off" : (Etat.volume < 0.34 ? "volume_mute" : (Etat.volume < 0.67 ? "volume_down" : "volume_up"))) : "light_mode"
            taille: 18; color: jauge.vol && Etat.muet ? "#98989d" : "white"
        }
        Rectangle {
            width: 130; height: 6; radius: 3; color: "#3a3a3c"
            anchors.verticalCenter: parent.verticalCenter
            Rectangle {
                width: parent.width * Math.max(0, Math.min(1, jauge.valeur)); height: parent.height; radius: 3; color: "white"
                Behavior on width { SpringAnimation { spring: 5; damping: 0.5 } }
            }
        }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Math.round(jauge.valeur * 100) + " %"; font.weight: Font.DemiBold; width: 42; horizontalAlignment: Text.AlignRight }
    }

    // ── Nouveau morceau ──
    Fondu {
        id: piste
        montre: c.mode === "piste"
        ClippingRectangle {
            width: 22; height: 22; radius: 6; color: Etat.pochette === "" && Etat.iconeLecteur !== "" ? "transparent" : "#2c2c2e"
            anchors.verticalCenter: parent.verticalCenter
            Image { anchors.fill: parent; source: Etat.pochette !== "" ? Etat.pochette : Etat.iconeLecteur; sourceSize: Qt.size(44, 44); fillMode: Image.PreserveAspectCrop; asynchronous: true }
        }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.titre; font.weight: Font.DemiBold; width: Math.min(implicitWidth, 200) }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.artiste; secondaire: true; width: Math.min(implicitWidth, 140); visible: Etat.artiste !== "" }
    }

    // ── Chargeur ──
    Fondu {
        id: charge
        montre: c.mode === "charge"
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: Etat.branche ? "bolt" : "battery_full"; taille: 18; color: Etat.branche ? "#30d158" : "white" }
        Texte {
            anchors.verticalCenter: parent.verticalCenter
            text: (Etat.branche ? "En charge · " : "Sur batterie · ") + Etat.pourcent + " %"
            font.weight: Font.DemiBold; color: Etat.branche ? "#30d158" : "white"
        }
    }

    // ── Profil d'énergie ──
    Fondu {
        id: profil
        montre: c.mode === "profil"
        Ico {
            anchors.verticalCenter: parent.verticalCenter
            nom: Etat.profil === PowerProfile.PowerSaver ? "eco" : (Etat.profil === PowerProfile.Performance ? "bolt" : "balance")
            taille: 18
            color: Etat.profil === PowerProfile.PowerSaver ? "#30d158" : (Etat.profil === PowerProfile.Performance ? "#ff9f0a" : "white")
        }
        Texte {
            anchors.verticalCenter: parent.verticalCenter
            text: Etat.profil === PowerProfile.PowerSaver ? "Économie" : (Etat.profil === PowerProfile.Performance ? "Performance" : "Équilibré")
            font.weight: Font.DemiBold
        }
    }

    // ── Mode jeu ──
    Fondu {
        id: jeu
        montre: c.mode === "jeu"
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "sports_esports"; taille: 19; color: Etat.jeu ? "#ff9f0a" : "#98989d" }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.jeu ? "Mode jeu" : "Mode jeu désactivé"; font.weight: Font.DemiBold }
    }
}
