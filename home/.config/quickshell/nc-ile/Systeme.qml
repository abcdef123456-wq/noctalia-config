// Page « Système et batterie » : processeur, mémoire, température, disque ; batterie (autonomie, santé) ;
// modes d'énergie ; écrans. Mesures lues par nc-ile-etat systeme toutes les 2 s tant que la page est affichée.
import QtQuick
import Quickshell
import Quickshell.Services.UPower

Item {
    id: sy
    function defiler(dy) { return defil.defiler(dy) }
    function val(k) {
        var l = Etat.liste
        for (var i = 0; i < l.length; i++) if (l[i].genre === k) return l[i].champs[0]
        return ""
    }
    readonly property var ecrans: Etat.liste.filter(e => e.genre === "ecran")
    function heures(s) { return s > 0 ? Math.floor(s / 3600) + " h " + String(Math.floor((s % 3600) / 60)).padStart(2, "0") : "" }

    component Mesure: Module {
        id: me
        property string icone
        property string titre
        property string valeur
        property string detail
        property real taux: 0
        property color couleur: Couleurs.texte
        width: (sy.width - 10) / 2; height: 86; radius: 18
        // Même structure pour les quatre blocs (titre, chiffre, barre), centrée verticalement ; le détail éventuel
        // (« 7,4 / 30,6 Go », « 284 Go libres ») est sur la ligne du chiffre, à droite
        Column {
            anchors.left: parent.left; anchors.right: parent.right; anchors.margins: 12
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6
            Row {
                spacing: 6
                Ico { nom: me.icone; taille: 16; color: Couleurs.texteSec; anchors.verticalCenter: parent.verticalCenter }
                Texte { text: me.titre; secondaire: true; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
            }
            Item {
                width: parent.width; height: chiffre.implicitHeight
                Texte { id: chiffre; text: me.valeur; font.pixelSize: 20; font.weight: Font.DemiBold; color: me.couleur; font.features: { "tnum": 1 } }
                Texte {
                    anchors.right: parent.right; anchors.baseline: chiffre.baseline
                    width: Math.min(implicitWidth, parent.width - chiffre.implicitWidth - 8)
                    horizontalAlignment: Text.AlignRight
                    text: me.detail; secondaire: true; font.pixelSize: 11; visible: me.detail !== ""
                }
            }
            Rectangle {
                width: parent.width; height: 5; radius: 2.5; color: Couleurs.gris3
                Rectangle { height: parent.height; radius: 2.5; color: me.couleur; width: parent.width * Math.max(0, Math.min(1, me.taux)) }
            }
        }
    }

    Defilement {
        id: defil
        anchors.fill: parent
        contentHeight: col.implicitHeight
        Column {
            id: col
            width: sy.width; spacing: 10
            Row {
                spacing: 10; height: 34
                Ico { nom: "memory"; taille: 24; anchors.verticalCenter: parent.verticalCenter }
                Texte { text: "Système"; font.pixelSize: 20; font.weight: Font.Bold; anchors.verticalCenter: parent.verticalCenter }
                Texte { text: sy.val("cpu_nom"); secondaire: true; anchors.verticalCenter: parent.verticalCenter; width: sy.width - 170 }
            }
            Grid {
                columns: 2; spacing: 10
                Mesure { icone: "speed"; titre: "Processeur"; valeur: (sy.val("cpu") || "0") + " %"; taux: (parseInt(sy.val("cpu")) || 0) / 100 }
                Mesure {
                    icone: "memory_alt"; titre: "Mémoire"; valeur: (sy.val("ram") || "0") + " %"; taux: (parseInt(sy.val("ram")) || 0) / 100
                    detail: sy.val("ram_utilisee").replace(".", ",") + " / " + sy.val("ram_totale").replace(".", ",") + " Go"
                }
                Mesure {
                    readonly property int t: parseInt(sy.val("temperature")) || 0
                    icone: "device_thermostat"; titre: "Température"; valeur: t + " °C"; taux: t / 100
                    couleur: t >= 85 ? Couleurs.rouge : (t >= 70 ? Couleurs.orange : Couleurs.vert)
                }
                Mesure {
                    icone: "hard_drive"; titre: "Disque"; valeur: (sy.val("disque") || "0") + " %"; taux: (parseInt(sy.val("disque")) || 0) / 100
                    detail: sy.val("disque_libre") + " Go libres"
                }
            }
            // Batterie
            Module {
                visible: Etat.aBatterie
                width: sy.width; height: 64; radius: 18
                Row {
                    anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 12; spacing: 12
                    Rectangle {
                        width: 40; height: 40; radius: 20; color: Etat.branche ? Couleurs.fondVert : Couleurs.gris3
                        Ico { anchors.centerIn: parent; nom: Etat.branche ? "bolt" : "battery_full"; taille: 22; color: Etat.branche ? Couleurs.vert : Couleurs.texte; rotation: Etat.branche ? 0 : 90 }
                    }
                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        Texte { text: "Batterie · " + Etat.pourcent + " %"; font.weight: Font.DemiBold; font.pixelSize: 14 }
                        Texte {
                            secondaire: true
                            text: (Etat.branche ? (Etat.batterie && Etat.batterie.timeToFull > 0 ? "Pleine dans " + sy.heures(Etat.batterie.timeToFull) : "Sur secteur")
                                                : (Etat.batterie && Etat.batterie.timeToEmpty > 0 ? "Encore " + sy.heures(Etat.batterie.timeToEmpty) : "Sur batterie"))
                                  + (sy.val("sante") !== "" ? "  ·  santé " + sy.val("sante") + " %" : "")
                                  + (sy.val("cycles") !== "" ? " (" + sy.val("cycles") + " cycles)" : "")
                        }
                    }
                }
            }
            // Protection de la batterie (charge arrêtée vers 80 %) : seulement si l'utilitaire est installé
            Module {
                id: protection
                readonly property string v: sy.val("protection")
                property bool attente: false
                visible: v === "0" || v === "1"
                width: sy.width; height: 56; radius: 18
                onVChanged: attente = false
                onAttenteChanged: if (attente) finAttenteProtection.restart()
                Timer { id: finAttenteProtection; interval: 3000; onTriggered: protection.attente = false }
                Column {
                    anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 16
                    anchors.right: inter.left; anchors.rightMargin: 10
                    Texte { text: "Protéger la batterie"; font.weight: Font.DemiBold; font.pixelSize: 14 }
                    Texte { text: "Charge arrêtée vers 80 %, conseillé si le PC reste souvent branché"; secondaire: true; font.pixelSize: 11; width: parent.width }
                }
                Rectangle {
                    id: inter
                    readonly property bool allume: protection.v === "1"
                    anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
                    width: 46; height: 28; radius: 14; color: allume ? Couleurs.vert : Couleurs.gris3
                    opacity: protection.attente ? 0.5 : 1
                    Behavior on color { ColorAnimation { duration: 180 } }
                    Rectangle {
                        width: 24; height: 24; radius: 12; color: Couleurs.texte; y: 2; x: inter.allume ? 20 : 2
                        Behavior on x { SpringAnimation { spring: 5; damping: 0.5 } }
                    }
                    MouseArea {
                        anchors.fill: parent; anchors.margins: -6
                        onClicked: {
                            protection.attente = true
                            Etat.faire(["sudo", "-n", "/usr/local/bin/nc-limite-charge", inter.allume ? "off" : "on"])
                        }
                    }
                }
            }
            // Modes d'énergie
            Repeater {
                model: [
                    { nom: "Économie", detail: "Autonomie maximale, sans effets", icone: "battery_saver", couleur: Couleurs.jaune, texte: Couleurs.surCouleur, p: PowerProfile.PowerSaver },
                    { nom: "Équilibré", detail: "Le bon compromis au quotidien", icone: "battery_full", couleur: Couleurs.gris3, texte: Couleurs.texte, p: PowerProfile.Balanced },
                    { nom: "Performance", detail: "Puissance maximale, carte NVIDIA", icone: "bolt", couleur: Couleurs.orange, texte: Couleurs.surCouleur, p: PowerProfile.Performance }
                ]
                Module {
                    required property var modelData
                    width: sy.width; height: 56; radius: 16; cliquable: true
                    onClic: Etat.choisirProfil(modelData.p)
                    Row {
                        anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 12; spacing: 12
                        Rectangle {
                            width: 32; height: 32; radius: 16; color: modelData.couleur
                            Ico { anchors.centerIn: parent; nom: modelData.icone; taille: 18; color: modelData.texte; rotation: modelData.icone === "bolt" ? 0 : 90 }
                        }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            Texte { text: modelData.nom; font.weight: Font.DemiBold }
                            Texte { text: modelData.detail; secondaire: true; font.pixelSize: 11 }
                        }
                    }
                    Ico { anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter; nom: "check"; taille: 20; color: Couleurs.accent; visible: Etat.profil === modelData.p }
                }
            }
            // Outils (anciens raccourcis du centre de contrôle)
            Texte { text: "Outils"; font.pixelSize: 12; font.weight: Font.DemiBold; secondaire: true; height: 24; verticalAlignment: Text.AlignBottom; leftPadding: 8 }
            Ligne {
                width: sy.width; icone: "coffee"; titre: "Rester éveillé"; actif: Etat.cafe
                sous: Etat.cafe ? "L'écran ne se met pas en veille" : "Désactivé"
                onClic: Etat.basculerCafe()
            }
            Ligne {
                width: sy.width; icone: "graphic_eq"; titre: "Halo sonore"; actif: Etat.sys.halo === "1"
                sous: Etat.sys.halo === "1" ? "Le bord de l'écran suit la musique" : "Désactivé"
                onClic: Etat.faire(["systemctl", "--user", Etat.sys.halo === "1" ? "stop" : "start", "nc-pouls"])
            }
            Repeater {
                model: [
                    { icone: "contrast", titre: "Thème clair ou sombre", cmd: ["noctalia", "msg", "theme-mode-toggle"], ferme: false },
                    { icone: "screenshot_region", titre: "Capture d'une zone", cmd: ["sh", "-c", "sleep 0.4; ~/.local/bin/nc-capture zone"], ferme: true },
                    { icone: "content_paste", titre: "Presse-papiers", cmd: ["noctalia", "msg", "panel-toggle", "launcher", "/clipboard"], ferme: true },
                    { icone: "wallpaper", titre: "Fonds d'écran", cmd: [Etat.bin + "nc-shell-msg", "wallpapers"], ferme: true }
                ]
                Ligne {
                    required property var modelData
                    width: sy.width; icone: modelData.icone; titre: modelData.titre
                    droite: modelData.ferme ? "chevron_right" : ""
                    onClic: { if (modelData.ferme) { Etat.fermer(); Quickshell.execDetached(modelData.cmd) } else Etat.faire(modelData.cmd) }
                }
            }
            // Session (anciens boutons du bas du centre de contrôle)
            Texte { text: "Session"; font.pixelSize: 12; font.weight: Font.DemiBold; secondaire: true; height: 24; verticalAlignment: Text.AlignBottom; leftPadding: 8 }
            Repeater {
                model: [
                                        { icone: "keyboard", titre: "Changer la disposition du clavier", cmd: ["noctalia", "msg", "keyboard-layout-cycle"], ferme: false },
                    { icone: "settings", titre: "Réglages de la barre", cmd: ["noctalia", "msg", "settings-open"], ferme: true },
                    { icone: "lock", titre: "Verrouiller", cmd: ["noctalia", "msg", "session", "lock"], ferme: true },
                    { icone: "power_settings_new", titre: "Éteindre, redémarrer…", cmd: ["noctalia", "msg", "panel-toggle", "session"], ferme: true }
                ]
                Ligne {
                    required property var modelData
                    width: sy.width; icone: modelData.icone; titre: modelData.titre
                    droite: modelData.ferme ? "chevron_right" : ""
                    onClic: { if (modelData.ferme) Etat.fermer(); Etat.faire(modelData.cmd) }
                }
            }
            // Écrans et allumage
            Repeater {
                model: sy.ecrans
                Texte {
                    required property var modelData
                    width: sy.width; secondaire: true; font.pixelSize: 12
                    text: "Écran " + modelData.champs[0] + " : " + modelData.champs[1] + " · " + modelData.champs[2] + " · échelle " + modelData.champs[3]
                }
            }
            Texte { text: "Allumé depuis " + sy.val("allume"); secondaire: true; font.pixelSize: 12; visible: sy.val("allume") !== "" }
        }
    }
}
