// Page « Santé » : températures (processeur, carte graphique si elle est réveillée — jamais réveillée pour ça —, SSD,
// mémoire, Wi-Fi), charge et programme le plus gourmand, ventilateurs, profil d'énergie avec bascule (le service de
// profils, comme le centre de contrôle : jamais /sys), lus par nc-ile-etat sante toutes les 2 s tant que la page est
// affichée et l'écran allumé (Etat.ecranVu). Jauges en arc (JaugeSante.qml) qui virent à l'orange puis au rouge.
// L'alerte de surchauffe (Chaleur.qml) s'affiche en tête avec ses causes et ses gestes. Sans capteur, la page n'existe pas.
import QtQuick
import Quickshell.Io
import Quickshell.Services.UPower

Item {
    id: sa
    function defiler(dy) { return defil.defiler(dy) }
    readonly property string pc: Reglages.t(" %", "%")

    // ── Mesures ──
    property var m: ({ temps: [], fans: [] })
    readonly property var ordre: ["cpu", "gpu", "ssd", "ram", "wifi", "carte"]
    readonly property var temps: m.temps.slice().sort((a, b) => ordre.indexOf(a.id) - ordre.indexOf(b.id))
    readonly property var fans: m.fans
    readonly property bool aCharge: m.cpu !== undefined
    // Relevé seulement quand la page est vraiment affichée (même garde que la page Batterie : à sa création dans un
    // Loader, elle se croit visible le temps d'une image) et l'écran allumé
    property bool affichee: false
    onVisibleChanged: if (visible) attente.restart(); else { attente.stop(); affichee = false }
    Timer { id: attente; interval: 150; onTriggered: sa.affichee = sa.visible }
    Component.onCompleted: { Etat.annoncerHauteur("sante", hauteur); if (visible) attente.restart() }
    Process {
        id: mesure
        command: [Etat.bin + "nc-ile-etat", "sante"]
        stdout: StdioCollector {
            onStreamFinished: {
                var t = { temps: [], fans: [] }
                text.split("\n").forEach(l => {
                    var p = l.indexOf("=")
                    if (p <= 0) return
                    var k = l.slice(0, p), c = l.slice(p + 1).split("\t")
                    if (k === "temp") t.temps.push({ id: c[0], deg: parseInt(c[1]) || 0, max: parseInt(c[2]) || 0 })
                    else if (k === "fan") t.fans.push({ n: parseInt(c[0]) || 0, rpm: parseInt(c[1]) || 0, max: parseInt(c[2]) || 0 })
                    else t[k] = c.join("\t")
                })
                if (t.gpu === "veille" && !t.temps.some(x => x.id === "gpu")) t.temps.push({ id: "gpu", deg: 0, max: 0, veille: true })
                sa.noter(t)
            }
        }
    }
    // ── Historique de 10 minutes (en mémoire seulement) ──
    // Alimenté par le relevé que la page fait déjà (toutes les 2 s, page affichée et écran allumé) : aucun relevé de plus.
    // Borné à 300 points (10 min). Vidé quand la page se ferme : rien ne se mesure pendant ce temps, et recoller des
    // points séparés par des heures dessinerait une fausse courbe continue.
    readonly property int maxPoints: 300
    property var histoTemp: []
    property var histoCharge: []
    onAfficheeChanged: if (!affichee) { histoTemp = []; histoCharge = []; chaudLectures = 0; chaudNom = "" }
    function empiler(tab, v) { var r = tab.length >= maxPoints ? tab.slice(tab.length - maxPoints + 1) : tab.slice(); r.push(v); return r }

    // ── Conseil en cas de chauffe au repos ──
    // Processeur au-dessus de seuilConseil alors que la charge totale reste modérée et qu'UN programme en prend une
    // grosse part, sur plusieurs relevés de suite avec le même programme (un pic court ne dit rien).
    readonly property int seuilConseil: 85
    readonly property int chargeModeree: 70     // % de charge totale au plus
    readonly property int partGrosse: 20        // % du processeur au moins pour le programme
    property int lecturesConseil: 5             // relevés de suite (2 s chacun) avant d'afficher
    property int chaudLectures: 0
    property string chaudNom: ""
    readonly property var cpuTemp: m.temps.filter(x => x.id === "cpu")[0]
    readonly property int topPct: parseInt(String(m.top || "").split("\t")[1]) || 0
    readonly property bool conseilVisible: chaudLectures >= lecturesConseil && !Partage.silence && chaudNom !== ""
    function noter(t) {
        var cpu = t.temps.filter(x => x.id === "cpu")[0]
        var charge = parseInt(t.cpu)
        if (cpu && cpu.deg > 0) histoTemp = empiler(histoTemp, cpu.deg)
        if (!isNaN(charge)) histoCharge = empiler(histoCharge, charge)
        var nom = String(t.top || "").split("\t")[0], pct = parseInt(String(t.top || "").split("\t")[1]) || 0
        var cas = cpu && cpu.deg >= seuilConseil && !isNaN(charge) && charge <= chargeModeree && nom !== "" && pct >= partGrosse
                  && pct * 100 >= charge * 50
        if (cas && (nom === chaudNom || chaudLectures === 0)) { chaudNom = nom; chaudLectures++ }
        else { chaudLectures = cas ? 1 : 0; chaudNom = cas ? nom : "" }
        m = t
    }
    // Le nom est le comm déjà lu (15 caractères), jamais la ligne de commande ; affiché en texte brut (Texte)
    function conseil() {
        var n = chaudNom, p = topPct
        if (/discord/i.test(n))
            return Reglages.t(n + " prend " + p + " % du processeur : redémarre-le, ou coupe son accélération matérielle.",
                              n + " takes " + p + "% of the CPU: restart it, or turn off its hardware acceleration.")
        if (/firefox|chrom|brave|vivaldi|opera|librewolf|zen|epiphany|web/i.test(n))
            return Reglages.t(n + " prend " + p + " % du processeur : ferme les onglets qui ne servent pas, ou redémarre le navigateur.",
                              n + " takes " + p + "% of the CPU: close the tabs you don't need, or restart the browser.")
        if (/electron|slack|teams|spotify|obsidian|signal|code|element|notion|zoom/i.test(n))
            return Reglages.t(n + " prend " + p + " % du processeur : redémarre-le, ou coupe son accélération matérielle dans ses réglages.",
                              n + " takes " + p + "% of the CPU: restart it, or turn off hardware acceleration in its settings.")
        return Reglages.t(n + " prend " + p + " % : ferme-le s'il ne sert pas.", n + " takes " + p + "%: close it if you don't need it.")
    }
    Timer { interval: 2000; repeat: true; running: sa.affichee && Etat.ecranVu; triggeredOnStart: true; onTriggered: if (!mesure.running) mesure.running = true }

    // Noms, icônes et seuils (orange, rouge) de chaque capteur ; le maximum donné par le noyau (temp*_crit) l'emporte
    readonly property var noms: ({ cpu: ["Processeur", "CPU"], gpu: ["Carte graphique", "GPU"], ssd: ["SSD", "SSD"], ram: ["Mémoire", "Memory"],
                                   wifi: ["Wi-Fi", "Wi-Fi"], carte: ["Carte mère", "Mainboard"] })
    readonly property var icones: ({ cpu: "memory", gpu: "developer_board", ssd: "hard_drive", ram: "memory_alt", wifi: "wifi", carte: "device_thermostat" })
    readonly property var seuils: ({ cpu: [75, 90], gpu: [75, 88], ssd: [55, 70], ram: [65, 80], wifi: [70, 85], carte: [70, 85] })
    function nom(id) { var n = noms[id]; return n ? Reglages.t(n[0], n[1]) : id }
    function rouge(e) { return e.max > 0 ? e.max : (seuils[e.id] || [70, 85])[1] }
    function orange(e) { return e.max > 0 ? e.max - 15 : (seuils[e.id] || [70, 85])[0] }
    function teinte(e) { return e.deg >= rouge(e) ? Couleurs.rouge : (e.deg >= orange(e) ? Couleurs.orange : Couleurs.vert) }
    function teinteCharge(c) { return c >= 90 ? Couleurs.rouge : (c >= 60 ? Couleurs.orange : Couleurs.accent) }
    function teinteFan(f) { var r = f.max > 0 ? f.rpm / f.max : f.rpm / 6000; return r >= 0.9 ? Couleurs.orange : Couleurs.accent }
    function trMin(n) { return Reglages.t(n + " tr/min", n + " rpm") }

    readonly property var profils: [
        { nom: Reglages.t("Économie", "Power saver"), icone: "battery_saver", couleur: Couleurs.jaune, p: PowerProfile.PowerSaver },
        { nom: Reglages.t("Équilibré", "Balanced"), icone: "battery_full", couleur: Couleurs.gris4, p: PowerProfile.Balanced },
        { nom: "Performance", icone: "bolt", couleur: Couleurs.orange, p: PowerProfile.Performance }
    ]
    readonly property string firmware: m.profil_firmware || ""
    // Profil du firmware (platform_profile) quand il dit autre chose que le service de profils (max-power, custom…)
    readonly property bool firmwareAPart: ["", "balanced", "performance", "power-saver", "low-power"].indexOf(firmware) < 0

    // L'île prend la hauteur du contenu
    readonly property real hauteur: col.implicitHeight
    onHauteurChanged: Etat.annoncerHauteur("sante", hauteur)

    Defilement {
        id: defil
        anchors.fill: parent
        contentHeight: col.implicitHeight
        Column {
            id: col
            width: sa.width; spacing: 10
            Row {
                spacing: 10; height: 34
                Ico { nom: "monitor_heart"; taille: 24; color: Chaleur.alerte ? Couleurs.rouge : Couleurs.vert; anchors.verticalCenter: parent.verticalCenter }
                Texte { text: Reglages.t("Santé", "Health"); font.pixelSize: 20; font.weight: Font.Bold; anchors.verticalCenter: parent.verticalCenter }
                // Programme le plus gourmand : caché pendant un partage d'écran (Partage.silence), comme le presse-papiers
                Texte {
                    objectName: "programmeGourmand"
                    visible: sa.m.top !== undefined && !Partage.silence
                    text: Reglages.t("le plus gourmand : ", "busiest: ") + String(sa.m.top || "").split("\t")[0]
                    secondaire: true; anchors.verticalCenter: parent.verticalCenter; width: sa.width - 120
                }
            }
            // Alerte de surchauffe en cours : causes et gestes, bouton Performance (réversible : le profil d'énergie)
            Module {
                objectName: "alerteChaleur"
                visible: Chaleur.alerte
                width: sa.width; radius: 18
                height: colAlerte.implicitHeight + 24
                color: Qt.rgba(Couleurs.rouge.r, Couleurs.rouge.g, Couleurs.rouge.b, 0.16)
                Column {
                    id: colAlerte
                    x: 14; y: 12; width: parent.width - 28; spacing: 6
                    Row {
                        spacing: 8
                        Ico { nom: "local_fire_department"; taille: 20; color: Couleurs.rouge; anchors.verticalCenter: parent.verticalCenter }
                        Texte { text: Chaleur.titre(); font.weight: Font.DemiBold; font.pixelSize: 15; color: Couleurs.rouge; anchors.verticalCenter: parent.verticalCenter }
                    }
                    Texte { width: parent.width; wrapMode: Text.WordWrap; text: Chaleur.situation(); font.pixelSize: 12 }
                    Texte { width: parent.width; wrapMode: Text.WordWrap; text: Chaleur.causes(); secondaire: true; font.pixelSize: 12 }
                    Texte { width: parent.width; wrapMode: Text.WordWrap; text: Chaleur.gestes(); secondaire: true; font.pixelSize: 12 }
                    Rectangle {
                        objectName: "boutonPerformance"
                        visible: Chaleur.performancePossible
                        width: perfTexte.implicitWidth + 36; height: 32; radius: 16; color: Couleurs.orange
                        scale: zonePerf.pressed ? 0.95 : 1
                        Behavior on scale { SpringAnimation { spring: 6; damping: 0.45 } }
                        Row {
                            anchors.centerIn: parent; spacing: 6
                            Ico { nom: "bolt"; taille: 16; color: Couleurs.surCouleur; anchors.verticalCenter: parent.verticalCenter }
                            Texte { id: perfTexte; text: Reglages.t("Passer en Performance", "Switch to Performance"); color: Couleurs.surCouleur; font.weight: Font.DemiBold; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                        }
                        MouseArea { id: zonePerf; anchors.fill: parent; onClicked: Etat.choisirProfil(PowerProfile.Performance) }
                    }
                }
            }
            // Jauges : charge du processeur, puis chaque température connue
            Grid {
                id: grille
                columns: 3; spacing: 10
                readonly property real l: (sa.width - 20) / 3
                JaugeSante {
                    objectName: "jaugeCharge"
                    visible: sa.aCharge
                    width: grille.l; icone: "speed"; titre: Reglages.t("Charge", "Load")
                    valeur: (sa.m.cpu || "0") + sa.pc; taux: (parseInt(sa.m.cpu) || 0) / 100; teinte: sa.teinteCharge(parseInt(sa.m.cpu) || 0)
                }
                Repeater {
                    model: sa.temps
                    JaugeSante {
                        required property var modelData
                        objectName: "jaugeTemp"
                        width: grille.l; icone: sa.icones[modelData.id] || "device_thermostat"; titre: sa.nom(modelData.id)
                        sans: modelData.veille === true
                        valeur: sans ? Reglages.t("en veille", "asleep") : modelData.deg + Reglages.t(" °C", "°C")
                        taux: modelData.deg / Math.max(1, sa.rouge(modelData) + 10)
                        teinte: sa.teinte(modelData)
                    }
                }
            }
            // Conseil : un programme fait chauffer le processeur au repos (nom caché pendant un partage d'écran)
            Module {
                objectName: "conseilChauffe"
                visible: sa.conseilVisible
                width: sa.width; radius: 18
                height: texteConseil.implicitHeight + 24
                color: Qt.rgba(Couleurs.orange.r, Couleurs.orange.g, Couleurs.orange.b, 0.16)
                Row {
                    x: 14; y: 12; width: parent.width - 28; spacing: 8
                    Ico { nom: "lightbulb"; taille: 18; color: Couleurs.orange; y: 1 }
                    Texte { id: texteConseil; width: parent.width - 28; wrapMode: Text.WordWrap; elide: Text.ElideNone; font.pixelSize: 12; text: sa.conseilVisible ? sa.conseil() : "" }
                }
            }
            // « Pourquoi ça chauffe ? » (IA du bureau, réglage IA_CHALEUR) : seulement quand la chaleur est haute et que l'IA peut
            // répondre ; sans IA le bouton n'existe pas et le conseil local ci-dessus reste
            PourquoiChaleur {
                objectName: "pourquoiChaleur"
                width: sa.width
                actif: !Partage.silence && (Chaleur.alerte || sa.conseilVisible || (sa.cpuTemp !== undefined && sa.cpuTemp.deg >= sa.seuilConseil))
                deg: sa.cpuTemp ? sa.cpuTemp.deg : 0
                charge: sa.aCharge ? (parseInt(sa.m.cpu) || 0) : -1
                fans: sa.fans
                profil: { var x = sa.profils.filter(q => q.p === Etat.profil)[0]; return x ? x.nom : "" }
                surBatterie: UPower.onBattery
            }
            // Dix dernières minutes : température et charge du processeur (courbes lisses, couleur selon le seuil)
            Module {
                objectName: "blocCourbes"
                visible: sa.histoTemp.length >= 2 || sa.histoCharge.length >= 2
                width: sa.width; radius: 18
                height: colCourbes.implicitHeight + 24
                Column {
                    id: colCourbes
                    x: 14; y: 12; width: parent.width - 28; spacing: 6
                    Texte { text: Reglages.t("Les 10 dernières minutes", "Last 10 minutes"); font.weight: Font.DemiBold; font.pixelSize: 14 }
                    Texte { visible: sa.histoTemp.length >= 2; text: sa.nom("cpu") + Reglages.t(" : température", ": temperature"); secondaire: true; font.pixelSize: 11 }
                    Courbe {
                        objectName: "courbeTemp"
                        visible: sa.histoTemp.length >= 2
                        width: parent.width; valeurs: sa.histoTemp; echelleAuto: true
                        teinte: sa.cpuTemp ? sa.teinte(sa.cpuTemp) : Couleurs.vert
                    }
                    Texte { visible: sa.histoCharge.length >= 2; text: Reglages.t("Charge", "Load"); secondaire: true; font.pixelSize: 11 }
                    Courbe {
                        objectName: "courbeCharge"
                        visible: sa.histoCharge.length >= 2
                        width: parent.width; valeurs: sa.histoCharge; mini: 0; maxi: 100
                        teinte: sa.teinteCharge(parseInt(sa.m.cpu) || 0)
                    }
                }
            }
            // Ventilateurs : vitesse et part du maximum connu (barre arrondie qui suit)
            Module {
                objectName: "blocFans"
                visible: sa.fans.length > 0
                width: sa.width; radius: 18
                height: colFans.implicitHeight + 24
                Column {
                    id: colFans
                    x: 14; y: 12; width: parent.width - 28; spacing: 8
                    Texte { text: Reglages.t("Ventilateurs", "Fans"); font.weight: Font.DemiBold; font.pixelSize: 14 }
                    Repeater {
                        model: sa.fans
                        Item {
                            id: fan
                            required property var modelData
                            objectName: "fan"
                            readonly property real part: modelData.max > 0 ? Math.min(1, modelData.rpm / modelData.max) : Math.min(1, modelData.rpm / 6000)
                            width: colFans.width; height: 30
                            Ico { id: icoFan; nom: "mode_fan"; taille: 16; color: Couleurs.texteSec; y: 1 }
                            Texte { anchors.left: icoFan.right; anchors.leftMargin: 8; y: 0; text: Reglages.t("Ventilateur ", "Fan ") + fan.modelData.n; font.pixelSize: 13 }
                            Texte {
                                anchors.right: parent.right; y: 0; secondaire: true; font.pixelSize: 12; font.features: { "tnum": 1 }
                                text: fan.modelData.rpm === 0 ? Reglages.t("à l'arrêt", "stopped") : sa.trMin(fan.modelData.rpm) + (fan.modelData.max > 0 ? " / " + fan.modelData.max : "")
                            }
                            Rectangle {
                                anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                                height: 5; radius: 2.5; color: Couleurs.gris3
                                Rectangle {
                                    height: parent.height; radius: 2.5; color: sa.teinteFan(fan.modelData)
                                    width: parent.width * fan.part
                                    Behavior on width { enabled: !Reglages.sobre; NumberAnimation { duration: 650; easing.type: Easing.OutCubic } }
                                }
                            }
                        }
                    }
                }
            }
            // Profil d'énergie : trois pastilles, la bascule passe par le service de profils (comme le centre) ; sans
            // service qui propose Performance, rien (un clic ne ferait rien)
            Module {
                objectName: "blocProfil"
                visible: Etat.performanceDisponible
                width: sa.width; radius: 18
                height: colProfil.implicitHeight + 24
                Column {
                    id: colProfil
                    x: 14; y: 12; width: parent.width - 28; spacing: 8
                    Item {
                        width: parent.width; height: 20
                        Texte { anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Profil d'énergie", "Power profile"); font.weight: Font.DemiBold; font.pixelSize: 14 }
                        Texte {
                            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.pixelSize: 12
                            visible: sa.firmwareAPart
                            text: Reglages.t("firmware : ", "firmware: ") + sa.firmware
                        }
                    }
                    Row {
                        spacing: 8
                        Repeater {
                            model: sa.profils
                            Rectangle {
                                id: pastille
                                required property var modelData
                                objectName: "profil"
                                readonly property bool actif: Etat.profil === modelData.p
                                width: (colProfil.width - 16) / 3; height: 36; radius: 18
                                color: actif ? modelData.couleur : (zoneP.containsMouse ? Couleurs.gris3 : Couleurs.gris2)
                                Behavior on color { ColorAnimation { duration: 160 } }
                                scale: zoneP.pressed ? 0.95 : 1
                                Behavior on scale { SpringAnimation { spring: 6; damping: 0.45 } }
                                Row {
                                    anchors.centerIn: parent; spacing: 6
                                    Ico { nom: pastille.modelData.icone; taille: 16; color: pastille.actif ? Couleurs.surCouleur : Couleurs.texte; anchors.verticalCenter: parent.verticalCenter; rotation: pastille.modelData.icone === "bolt" ? 0 : 90 }
                                    Texte { text: pastille.modelData.nom; font.pixelSize: 12; font.weight: Font.DemiBold; color: pastille.actif ? Couleurs.surCouleur : Couleurs.texte; anchors.verticalCenter: parent.verticalCenter; width: Math.min(implicitWidth, pastille.width - 40) }
                                }
                                MouseArea { id: zoneP; anchors.fill: parent; hoverEnabled: true; onClicked: Etat.choisirProfil(pastille.modelData.p) }
                            }
                        }
                    }
                    Texte {
                        width: parent.width; wrapMode: Text.WordWrap; secondaire: true; font.pixelSize: 11
                        text: Chaleur.lenovo
                              ? Reglages.t("Performance pousse les ventilateurs ; Fn + Q change aussi le mode du constructeur. Sur batterie, Équilibré suffit.",
                                           "Performance pushes the fans; Fn + Q also switches the vendor mode. On battery, Balanced is enough.")
                              : Reglages.t("Performance pousse les ventilateurs. Sur batterie, Équilibré suffit.", "Performance pushes the fans. On battery, Balanced is enough.")
                    }
                }
            }
            // Profils d'énergie poussés (nc-energie) : proposés par l'IA ou par des règles, aperçu, Appliquer, Revenir
            EnergieProfils { width: sa.width; affichee: sa.affichee }
            Texte {
                visible: Chaleur.seuil > 0 && Chaleur.fichierCpu !== ""
                width: sa.width; wrapMode: Text.WordWrap; secondaire: true; font.pixelSize: 11; leftPadding: 8
                text: Reglages.t("Veille de surchauffe : au-delà de " + Chaleur.seuil + " °C pendant plus d'une minute, l'île prévient une fois (nc-reglages → Île).",
                                 "Overheating watch: above " + Chaleur.seuil + "°C for over a minute, the island warns once (nc-settings → Island).")
            }
        }
    }
}
