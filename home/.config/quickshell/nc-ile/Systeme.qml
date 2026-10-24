// Page « Système et batterie » : processeur, mémoire, température, disque ; batterie (autonomie, santé) ;
// modes d'énergie ; écrans. Mesures lues par nc-ile-etat systeme toutes les 2 s tant que la page est affichée.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.UPower

Item {
    id: sy
    function defiler(dy) { return defil.defiler(dy) }
    function val(k) {
        var l = Etat.liste
        for (let i = 0; i < l.length; i++) if (l[i].genre === k) return l[i].champs[0]
        return ""
    }
    readonly property var ecrans: Etat.liste.filter(e => e.genre === "ecran")
    function heures(s) {
        if (s <= 0) return ""
        var h = Math.floor(s / 3600), m = String(Math.floor((s % 3600) / 60)).padStart(2, "0")
        return Reglages.en ? h + "h " + m + "m" : h + " h " + m
    }
    readonly property string pc: Reglages.t(" %", "%")     // « 42 % » en français, « 42% » en anglais

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
                Texte { text: Reglages.t("Système", "System"); font.pixelSize: 20; font.weight: Font.Bold; anchors.verticalCenter: parent.verticalCenter }
                Texte { text: sy.val("cpu_nom"); secondaire: true; anchors.verticalCenter: parent.verticalCenter; width: sy.width - 170 }
            }
            Grid {
                columns: 2; spacing: 10
                Mesure { icone: "speed"; titre: Reglages.t("Processeur", "CPU"); valeur: (sy.val("cpu") || "0") + sy.pc; taux: (parseInt(sy.val("cpu")) || 0) / 100 }
                Mesure {
                    icone: "memory_alt"; titre: Reglages.t("Mémoire", "Memory"); valeur: (sy.val("ram") || "0") + sy.pc; taux: (parseInt(sy.val("ram")) || 0) / 100
                    detail: Reglages.en ? sy.val("ram_utilisee") + " / " + sy.val("ram_totale") + " GB"
                                        : sy.val("ram_utilisee").replace(".", ",") + " / " + sy.val("ram_totale").replace(".", ",") + " Go"
                }
                Mesure {
                    readonly property int t: parseInt(sy.val("temperature")) || 0
                    icone: "device_thermostat"; titre: Reglages.t("Température", "Temperature"); valeur: t + Reglages.t(" °C", "°C"); taux: t / 100
                    couleur: t >= 85 ? Couleurs.rouge : (t >= 70 ? Couleurs.orange : Couleurs.vert)
                }
                Mesure {
                    icone: "hard_drive"; titre: Reglages.t("Disque", "Disk"); valeur: (sy.val("disque") || "0") + sy.pc; taux: (parseInt(sy.val("disque")) || 0) / 100
                    detail: sy.val("disque_libre") + Reglages.t(" Go libres", " GB free")
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
                        Texte { text: Reglages.t("Batterie · ", "Battery · ") + Etat.pourcent + sy.pc; font.weight: Font.DemiBold; font.pixelSize: 14 }
                        Texte {
                            secondaire: true
                            text: (Etat.branche ? (Etat.batterie && Etat.batterie.timeToFull > 0 ? Reglages.t("Pleine dans ", "Full in ") + sy.heures(Etat.batterie.timeToFull)
                                                                                                   : Reglages.t("Sur secteur", "Power Adapter"))
                                                : (Etat.batterie && Etat.batterie.timeToEmpty > 0 ? Reglages.t("Encore ", "") + sy.heures(Etat.batterie.timeToEmpty) + Reglages.t("", " left")
                                                                                                   : Reglages.t("Sur batterie", "On battery")))
                                  + (sy.val("sante") !== "" ? Reglages.t("  ·  santé ", "  ·  health ") + sy.val("sante") + sy.pc : "")
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
                    Texte { text: Reglages.t("Protéger la batterie", "Protect Battery"); font.weight: Font.DemiBold; font.pixelSize: 14 }
                    Texte { text: Reglages.t("Charge arrêtée vers 80 %, conseillé si le PC reste souvent branché", "Stops charging around 80%, recommended if your computer is often plugged in"); secondaire: true; font.pixelSize: 11; width: parent.width }
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
                    { nom: Reglages.t("Économie", "Power saver"), detail: Reglages.t("Autonomie maximale, sans effets", "Longest battery life, no effects"), icone: "battery_saver", couleur: Couleurs.jaune, texte: Couleurs.surCouleur, p: PowerProfile.PowerSaver },
                    { nom: Reglages.t("Équilibré", "Balanced"), detail: Reglages.t("Le bon compromis au quotidien", "The right balance for every day"), icone: "battery_full", couleur: Couleurs.gris3, texte: Couleurs.texte, p: PowerProfile.Balanced },
                    { nom: "Performance", detail: Reglages.t("Puissance maximale, carte NVIDIA", "Maximum power, NVIDIA graphics"), icone: "bolt", couleur: Couleurs.orange, texte: Couleurs.surCouleur, p: PowerProfile.Performance }
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
            Texte { text: Reglages.t("Outils", "Tools"); font.pixelSize: 12; font.weight: Font.DemiBold; secondaire: true; height: 24; verticalAlignment: Text.AlignBottom; leftPadding: 8 }
            // Mode graphique d'un portable à MUX (nc-gpu-mode json, ModeGraphique.qml) : relu quand la page s'affiche,
            // sans sondage ; seulement s'il y a un mode à choisir. Un clic ferme l'île et ouvre la carte de confirmation
            // (le changement redémarre le PC)
            Ligne {
                objectName: "nc-mode-graphique"
                visible: ModeGraphique.possible
                width: sy.width; icone: "developer_board"; actif: ModeGraphique.mode === "dediee"
                titre: Reglages.t("Mode graphique : ", "Graphics mode: ") + ModeGraphique.nom(ModeGraphique.mode)
                sous: ModeGraphique.mode === "hybride"
                      ? Reglages.t("Clic : passer en Dédiée, plus fluide sur secteur", "Click to switch to Discrete, smoother when plugged in")
                      : Reglages.t("Clic : passer en Hybride, pour la batterie", "Click to switch to Hybrid, for battery life")
                droite: "chevron_right"
                onClic: { Etat.fermer(); ModeGraphique.demander("") }
                Component.onCompleted: ModeGraphique.lire()
                Connections { target: sy; function onVisibleChanged() { if (sy.visible) ModeGraphique.lire() } }
            }
            Ligne {
                width: sy.width; icone: "coffee"; titre: Reglages.t("Rester éveillé", "Stay Awake"); actif: Etat.cafe
                sous: Etat.cafe ? Reglages.t("L'écran ne se met pas en veille", "The screen won't go to sleep") : Reglages.t("Désactivé", "Off")
                onClic: Etat.basculerCafe()
            }
            Ligne {
                width: sy.width; icone: "graphic_eq"; titre: Reglages.t("Halo sonore", "Sound Halo"); actif: Etat.sys.halo === "1"
                sous: Etat.sys.halo === "1" ? Reglages.t("Le bord de l'écran suit la musique", "The screen edge follows the music") : Reglages.t("Désactivé", "Off")
                onClic: Etat.faire(["systemctl", "--user", Etat.sys.halo === "1" ? "stop" : "start", "nc-pouls"])
            }
            // Mises à jour du système (nc-paquets, comptées chaque heure au plus, sur secteur seulement : nc-paquets.service a
            // ConditionACPower) : un clic, tout mettre à jour dans un terminal. Le nombre est la première ligne de
            // $XDG_CACHE_HOME/nc/paquets, relu à chaque réécriture (le recompte après la mise à jour) et quand la page revient à l'écran
            Ligne {
                id: maj
                objectName: "nc-paquets"
                property int n: 0
                readonly property string cache: (Quickshell.env("XDG_CACHE_HOME") || Quickshell.env("HOME") + "/.cache") + "/nc/"
                visible: Reglages.val("MAJ_SYSTEME", "ile") !== "non" && paquets.loaded
                width: sy.width; icone: "system_update"; actif: n > 0 || vieux > 0
                // paquets-erreur (la dernière vérification n'a pas abouti) : jamais « Système à jour » faute de réponse
                property bool echec: false
                // non_synchro_jours de paquets.json (apt, zypper : la liste des dépôts date de plusieurs jours) : une vieille
                // liste vide n'est pas « à jour », et « Mettre à jour » la synchronise
                property int vieux: 0
                readonly property string cadence: (({ "3h": Reglages.t("Vérifié toutes les 3 heures", "Checked every 3 hours"),
                                                      "6h": Reglages.t("Vérifié toutes les 6 heures", "Checked every 6 hours"),
                                                      "jour": Reglages.t("Vérifié une fois par jour", "Checked once a day") })[Reglages.val("MAJ_FREQUENCE", "1h")]
                                                   || Reglages.t("Vérifié chaque heure", "Checked every hour"))
                                                  + (Etat.aBatterie ? Reglages.t(", sur secteur", ", when plugged in") : "")
                titre: verif.running ? Reglages.t("Recherche des mises à jour…", "Checking for updates…")
                     : n > 0 ? n + (n > 1 ? Reglages.t(" mises à jour du système", " system updates") : Reglages.t(" mise à jour du système", " system update"))
                     : echec ? Reglages.t("Vérification impossible", "Could not check for updates")
                     : vieux > 0 ? Reglages.t("Dépôts non synchronisés", "Repositories not synced")
                     : Reglages.t("Système à jour", "System up to date")
                sous: verif.running ? cadence
                    : n > 0 ? (echec ? Reglages.t("Dernier état connu (pas de réponse) · clic : tout mettre à jour", "Last known state (no answer) · click to update everything")
                                     : Reglages.t("Clic : tout mettre à jour (ton mot de passe sera demandé)", "Click to update everything (you'll be asked for your password)"))
                    : echec ? Reglages.t("Pas de réponse (réseau ou dépôt) · clic : réessayer", "No answer (network or repository) · click to retry")
                    : vieux > 0 ? Reglages.t("Depuis " + vieux + " j, des mises à jour peuvent manquer · clic : synchroniser", "For " + vieux + " d, updates may be missing · click to sync")
                    : cadence
                onClic: {
                    if (verif.running) return
                    if (n > 0 || (vieux > 0 && !echec)) { Etat.fermer(); Quickshell.execDetached([Etat.bin + "nc-paquets", "mettre-a-jour"]) }
                    else if (echec) verif.running = true
                }
                Process { id: verif; command: [Etat.bin + "nc-paquets", "verifier"] }
                FileView {
                    id: paquets
                    path: maj.cache + "paquets"
                    watchChanges: true; printErrors: false
                    onFileChanged: reload()
                    onLoaded: maj.n = parseInt(text().split("\n")[0]) || 0
                }
                FileView {
                    id: paquetsErreur
                    path: maj.cache + "paquets-erreur"
                    watchChanges: true; printErrors: false
                    onFileChanged: reload()
                    onLoaded: maj.echec = text().trim() !== ""
                    onLoadFailed: maj.echec = false
                }
                FileView {
                    id: paquetsDetail
                    path: maj.cache + "paquets.json"
                    watchChanges: true; printErrors: false
                    onFileChanged: reload()
                    onLoaded: { try { maj.vieux = JSON.parse(text()).non_synchro_jours || 0 } catch (e) { maj.vieux = 0 } }
                    onLoadFailed: maj.vieux = 0
                }
                Connections { target: sy; function onVisibleChanged() { if (sy.visible) { paquets.reload(); paquetsErreur.reload(); paquetsDetail.reload() } } }
            }
            // Éclairage du clavier (s'il est réglable) : un clic, palier suivant puis éteint
            Ligne {
                readonly property var niv: (Etat.sys.clavier || "").split("/").map(x => parseInt(x) || 0)
                visible: (Etat.sys.clavier || "") !== ""
                width: sy.width; icone: "keyboard"; titre: Reglages.t("Éclairage du clavier", "Keyboard Backlight"); actif: niv[0] > 0
                sous: niv[0] === 0 ? Reglages.t("Éteint · Super + Ctrl + Espace", "Off · Super + Ctrl + Space")
                      : (niv[1] <= 4 ? Reglages.t("Niveau " + niv[0] + " sur " + niv[1], "Level " + niv[0] + " of " + niv[1])
                      : Math.round(niv[0] * 100 / niv[1]) + sy.pc)
                onClic: Etat.faire([Etat.bin + "nc-touches", "clavier", "bascule"])
            }
            Repeater {
                model: [
                    { icone: "contrast", titre: Reglages.t("Thème clair ou sombre", "Light or Dark Theme"), cmd: ["noctalia", "msg", "theme-mode-toggle"], ferme: false },
                    { icone: "screenshot_region", titre: Reglages.t("Capture d'une zone", "Capture an Area"), cmd: ["sh", "-c", "sleep 0.4; ~/.local/bin/nc-capture zone"], ferme: true },
                    { icone: "text_select_start", titre: Reglages.t("Copier le texte de l'écran", "Copy Text from Screen"), cmd: ["sh", "-c", "sleep 0.4; ~/.local/bin/nc-capture texte"], ferme: true },
                    { icone: "content_paste", titre: Reglages.t("Presse-papiers", "Clipboard"), cmd: ["noctalia", "msg", "panel-toggle", "launcher", "/clipboard"], ferme: true },
                    { icone: "wallpaper", titre: Reglages.t("Fonds d'écran", "Wallpapers"), cmd: [Etat.bin + "nc-shell-msg", "wallpapers"], ferme: true }
                ]
                Ligne {
                    required property var modelData
                    width: sy.width; icone: modelData.icone; titre: modelData.titre
                    droite: modelData.ferme ? "chevron_right" : ""
                    onClic: { if (modelData.ferme) { Etat.fermer(); Quickshell.execDetached(modelData.cmd) } else Etat.faire(modelData.cmd) }
                }
            }
            // Session (anciens boutons du bas du centre de contrôle)
            Texte { text: Reglages.t("Session", "Session"); font.pixelSize: 12; font.weight: Font.DemiBold; secondaire: true; height: 24; verticalAlignment: Text.AlignBottom; leftPadding: 8 }
            Repeater {
                model: [
                                        { icone: "keyboard", titre: Reglages.t("Changer la disposition du clavier", "Switch Keyboard Layout"), cmd: ["noctalia", "msg", "keyboard-layout-cycle"], ferme: false },
                    { icone: "settings", titre: Reglages.t("Réglages de la barre", "Bar Settings"), cmd: ["noctalia", "msg", "settings-open"], ferme: true },
                    { icone: "lock", titre: Reglages.t("Verrouiller", "Lock"), cmd: ["noctalia", "msg", "session", "lock"], ferme: true },
                    { icone: "power_settings_new", titre: Reglages.t("Éteindre, redémarrer…", "Shut Down, Restart…"), cmd: ["noctalia", "msg", "panel-toggle", "session"], ferme: true }
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
                    text: Reglages.t("Écran " + modelData.champs[0] + " : ", "Display " + modelData.champs[0] + ": ") + modelData.champs[1] + " · " + modelData.champs[2]
                          + Reglages.t(" · échelle ", " · scale ") + modelData.champs[3]
                }
            }
            Texte { text: Reglages.t("Allumé depuis " + sy.val("allume"), "Up for " + sy.val("allume").replace(/^(\d+) h (\d+)$/, "$1h $2m")); secondaire: true; font.pixelSize: 12; visible: sy.val("allume") !== "" }
        }
    }
}
