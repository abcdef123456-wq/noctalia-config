// Tiroirs utilitaires natifs du Centre de contrôle (Système, Batterie, Santé, Concentration, Météo,
// Agenda, Presse-papiers, Minuteur, Fenêtres, Mode jeu) — tous dessinés dans le langage visuel unifié
// du Centre de contrôle (sans recycler d'anciennes pages de l'île).
import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Services.UPower

Item {
    id: vue
    property string section: "systeme"
    signal fermerPanneau()

    readonly property bool actif: visible && Etat.controleOuvert && Etat.ecranVu
    readonly property bool masque: Partage.silence
    readonly property bool estBrut: Couleurs.styleBrut || Couleurs.styleTerminal
    readonly property bool estEditorial: Couleurs.styleEditorial
    readonly property bool meteoActive: Reglages.val("ILE_METEO", "oui") !== "non"
    readonly property bool agendaActif: !masque && Reglages.val("GOOGLE_INTEGRATION", "non") === "oui"
                                         && Reglages.val("GOOGLE_CALENDRIER", "oui") !== "non"
    readonly property string eq: "—"
    readonly property string pc: Reglages.t(" %", "%")

    readonly property var systeme: {
        const m = {}
        if (section === "systeme") for (const e of Etat.liste) m[e.genre] = e.champs[0]
        return m
    }
    property var mesures: ({})
    property var conso: ({})
    readonly property var bat: conso.batterie || null
    readonly property var niveauBat: bat ? bat.pct : Etat.aBatterie ? Etat.pourcent : undefined
    readonly property bool chargeReelle: bat ? bat.statut === "Charging" : Etat.enCharge
    readonly property bool secteur: bat ? bat.statut !== "Discharging" : Etat.branche
    readonly property var profils: [
        { id: PowerProfile.PowerSaver, nom: Reglages.t("Économie", "Power saver") },
        { id: PowerProfile.Balanced, nom: Reglages.t("Équilibré", "Balanced") },
        { id: PowerProfile.Performance, nom: "Performance" }
    ]
    readonly property string commandeMesure: section === "sante" && Etat.capteursSante ? "sante" : section === "jeu" && Etat.jeu ? "jeu" : ""
    onCommandeMesureChanged: mesures = ({})
    Process {
        id: telemetry
        property string typeMesure: ""
        command: [Etat.bin + "nc-ile-etat", typeMesure]
        stdout: StdioCollector {
            onStreamFinished: {
                if (telemetry.typeMesure !== vue.commandeMesure) return
                const r = { temperatures: [], ventilateurs: [] }
                for (const ligne of text.split("\n")) {
                    const p = ligne.indexOf("=")
                    if (p < 1) continue
                    const k = ligne.slice(0, p), v = ligne.slice(p + 1)
                    if (k === "temp") r.temperatures.push(v.split("\t"))
                    else if (k === "fan") r.ventilateurs.push(v.split("\t"))
                    else r[k] = v
                }
                vue.mesures = r
            }
        }
    }
    Timer {
        interval: 2000; repeat: true; triggeredOnStart: true
        running: vue.actif && vue.commandeMesure !== ""
        onTriggered: if (!telemetry.running) {
            telemetry.typeMesure = vue.commandeMesure
            telemetry.running = true
        }
    }
    Process {
        running: vue.actif && vue.section === "charge" && Etat.batteriePc
        command: [Etat.bin + "nc-conso", "suivre"]
        stdout: SplitParser { onRead: ligne => { try { vue.conso = JSON.parse(ligne) || ({}) } catch (_) {} } }
    }

    function pct(n) { return n !== undefined && n !== "" ? n + pc : eq }
    function deg(n) { return n !== undefined && n !== "" ? n + " °C" : eq }
    function go(n) { return n !== undefined && n !== "" ? n + Reglages.t(" Go", " GB") : "" }
    function capteur(n) {
        switch (n) {
        case "cpu": return Reglages.t("Processeur", "Processor")
        case "gpu": return Reglages.t("Carte graphique", "Graphics card")
        case "ram": return Reglages.t("Mémoire", "Memory")
        case "carte": return Reglages.t("Carte mère", "Mainboard")
        default: return n === "wifi" ? "Wi-Fi" : n.toUpperCase()
        }
    }
    function duree(secondes) {
        const m = Math.ceil(secondes / 60)
        return m < 60 ? m + " min" : Math.floor(m / 60) + " h " + String(m % 60).padStart(2, "0")
    }
    function lancerMinuteur(minutes) {
        if (Etat.pomodoro) Etat.arreterMinuteur()
        Etat.lancerMinuteur(minutes)
    }

    // Calendrier local : aucune requête tant que l'intégration n'est pas activée et le tiroir visible.
    property int decalageMois: 0
    property int jourChoisi: 0
    readonly property date premier: new Date(Etat.minute.getFullYear(), Etat.minute.getMonth() + decalageMois, 1)
    readonly property int decalageJours: (premier.getDay() + 6) % 7
    readonly property int nbJours: new Date(premier.getFullYear(), premier.getMonth() + 1, 0).getDate()
    readonly property int jourAffiche: jourChoisi || (decalageMois === 0 ? Etat.minute.getDate() : 1)
    readonly property string cleMois: GoogleAgenda.cle(premier)
    readonly property var agenda: agendaActif && section === "calendrier" ? GoogleAgenda.cache[cleMois] || null : null
    readonly property var evenementsJour: evenements(jourAffiche)
    readonly property bool calendrierOuvert: actif && section === "calendrier" && agendaActif
    onCalendrierOuvertChanged: if (calendrierOuvert) chargerAgenda(false)
    onCleMoisChanged: if (calendrierOuvert) chargerAgenda(false)
    function changerMois(delta) { jourChoisi = 0; decalageMois += delta }
    function chargerAgenda(force) { if (calendrierOuvert) GoogleAgenda.charger(premier, force) }
    function dateMois(jour) { return new Date(premier.getFullYear(), premier.getMonth(), jour) }
    function evenements(jour) {
        if (!agenda) return []
        const d = GoogleAgenda.iso(dateMois(jour))
        return agenda.events.filter(e => e.journee && e.fin ? e.debut <= d && d < e.fin : e.debut.slice(0, 10) === d)
    }
    function heureAgenda(e) {
        return e.journee ? Reglages.t("Toute la journée", "All day")
            : e.debut.slice(11, 16) + (e.fin ? " – " + e.fin.slice(11, 16) : "")
    }
    function ouvrirFenetre(t) {
        if (masque || !t || !t.address) return
        const adresse = String(t.address)
        Quickshell.execDetached([Etat.bin + "nc-fenetre", "aller", adresse.startsWith("0x") ? adresse : "0x" + adresse])
        fermerPanneau()
    }
    onSectionChanged: {
        if (defilement) defilement.contentY = 0
        if (section === "presse" && PressePapiers.active && !masque) PressePapiers.purger()
        if (section === "fenetres" && !masque) Hyprland.refreshToplevels()
    }
    onMasqueChanged: if (!masque && section === "presse" && PressePapiers.active) PressePapiers.purger()
    Component.onCompleted: {
        if (section === "presse" && PressePapiers.active && !masque) PressePapiers.purger()
        if (section === "fenetres" && !masque) Hyprland.refreshToplevels()
    }

    component CarteBloc: Rectangle {
        default property alias contenu: colBloc.data
        width: parent.width
        height: colBloc.implicitHeight + 24
        radius: Couleurs.rayon(Couleurs.rayonBloc, width, height)
        color: vue.estEditorial ? "transparent" : Couleurs.surfaceDouce
        border.width: 1; border.color: Couleurs.bordureSubtile
        Column { id: colBloc; x: 12; y: 12; width: parent.width - 24; spacing: 8 }
    }
    component Entete: Texte {
        width: parent.width; font.pixelSize: 13; font.weight: Font.DemiBold
    }
    component Note: Texte {
        width: parent.width; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 11
    }
    component Valeur: Item {
        id: ligne
        property string libelle: ""
        property string valeur: ""
        property color teinte: Couleurs.texte
        width: parent.width; height: 20
        Texte {
            anchors.left: parent.left; anchors.right: chiffre.left; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter
            text: ligne.libelle; secondaire: true; font.pixelSize: 11
        }
        Texte {
            id: chiffre
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            width: Math.min(implicitWidth, parent.width * 0.60)
            horizontalAlignment: Text.AlignRight
            text: ligne.valeur; color: ligne.teinte; font.pixelSize: 12; font.weight: Font.DemiBold
            font.features: ({ "tnum": 1 })
        }
    }
    component BarreJauge: Column {
        id: jauge
        property string libelle: ""
        property string valeur: ""
        property real ratio: 0
        property color teinte: Couleurs.accent
        width: parent.width; spacing: 4
        Valeur { libelle: jauge.libelle; valeur: jauge.valeur; teinte: jauge.teinte }
        Rectangle {
            width: parent.width; height: vue.estBrut ? 6 : 8
            radius: Couleurs.rayon(vue.estBrut ? 1 : 4, width, height)
            color: Qt.alpha(Couleurs.voile, 0.10)
            Rectangle {
                width: parent.width * Math.max(0, Math.min(1, jauge.ratio))
                height: parent.height; radius: parent.radius; color: jauge.teinte
            }
        }
    }
    component Bouton: ControleAction {
        id: bouton
        property string glyphe: ""
        property string nomAccessible: text
        property bool choisi: false
        property bool critique: false
        Accessible.name: nomAccessible
        width: parent.width; height: 32
        background: Rectangle {
            radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
            color: bouton.choisi || bouton.contientPointeur ? Couleurs.accentDoux : "transparent"
            border.width: 1; border.color: bouton.choisi ? Couleurs.accent : Couleurs.bordureSubtile
        }
        contentItem: Item {
            opacity: bouton.enabled ? 1 : 0.5
            Ico {
                id: ic
                anchors.left: parent.left; anchors.leftMargin: bouton.text ? 9 : (parent.width - width) / 2
                anchors.verticalCenter: parent.verticalCenter
                visible: bouton.glyphe !== ""; nom: bouton.glyphe; taille: 15
                color: bouton.critique ? Couleurs.rouge : Couleurs.accent
            }
            Texte {
                anchors.left: bouton.glyphe === "" ? parent.left : ic.right; anchors.leftMargin: 6
                anchors.right: parent.right; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter
                horizontalAlignment: bouton.glyphe === "" ? Text.AlignHCenter : Text.AlignLeft
                text: bouton.text; font.pixelSize: 11; font.weight: bouton.choisi ? Font.Bold : Font.Medium
                color: bouton.critique ? Couleurs.rouge : (bouton.choisi ? Couleurs.accent : Couleurs.texte)
            }
        }
    }
    component ChoixProfil: Flow {
        width: parent.width; spacing: 6
        visible: !Etat.profilsAbsents
        Repeater {
            model: parent.visible ? vue.profils : []
            Bouton {
                required property var modelData
                visible: modelData.id !== PowerProfile.Performance || Etat.performanceDisponible
                width: (parent.width - 12) / 3
                choisi: Etat.profil === modelData.id
                text: modelData.nom
                onClicked: Etat.choisirProfil(modelData.id)
            }
        }
    }

    Flickable {
        id: defilement
        anchors.fill: parent
        contentWidth: width; contentHeight: col.implicitHeight + 6
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: col
            width: defilement.width; spacing: 10

            CarteBloc {
                visible: vue.section === "systeme"
                Entete { text: vue.systeme.cpu_nom || Reglages.t("Ressources", "Resources") }
                BarreJauge {
                    libelle: Reglages.t("Processeur (CPU)", "Processor (CPU)")
                    valeur: vue.pct(vue.systeme.cpu); ratio: (Number(vue.systeme.cpu) || 0) / 100
                    teinte: ratio > 0.8 ? Couleurs.rouge : Couleurs.accent
                }
                BarreJauge {
                    libelle: Reglages.t("Mémoire (RAM)", "Memory (RAM)")
                    valeur: vue.pct(vue.systeme.ram); ratio: (Number(vue.systeme.ram) || 0) / 100
                    teinte: ratio > 0.85 ? Couleurs.orange : Couleurs.bleu
                }
                Valeur {
                    visible: !!vue.systeme.ram_totale
                    libelle: Reglages.t("Mémoire utilisée / totale", "Memory used / total")
                    valeur: vue.go(vue.systeme.ram_utilisee) + " / " + vue.go(vue.systeme.ram_totale)
                }
                BarreJauge {
                    libelle: Reglages.t("Disque principal", "Root disk")
                    valeur: vue.pct(vue.systeme.disque); ratio: (Number(vue.systeme.disque) || 0) / 100
                    teinte: ratio > 0.9 ? Couleurs.rouge : Couleurs.vert
                }
                Valeur { visible: !!vue.systeme.disque_libre; libelle: Reglages.t("Espace disponible", "Free space"); valeur: vue.go(vue.systeme.disque_libre) }
            }
            CarteBloc {
                visible: vue.section === "systeme"
                Valeur { libelle: Reglages.t("Température du processeur", "CPU temperature"); valeur: vue.deg(vue.systeme.temperature) }
                Valeur { visible: !!vue.systeme.allume; libelle: Reglages.t("Allumé depuis", "Uptime"); valeur: vue.systeme.allume || "" }
                Valeur { libelle: Reglages.t("Thème actif", "Active theme"); valeur: Couleurs.nomThemeAffiche; teinte: Couleurs.accent }
            }

            CarteBloc {
                visible: vue.section === "charge"
                Note { visible: vue.niveauBat === undefined; text: Reglages.t("Aucune mesure de batterie disponible.", "Battery information unavailable.") }
                BarreJauge {
                    visible: vue.niveauBat !== undefined
                    libelle: vue.chargeReelle ? Reglages.t("En charge", "Charging")
                        : vue.secteur ? Reglages.t("Branchée sur secteur", "Plugged in") : Reglages.t("Sur batterie", "On battery")
                    valeur: vue.pct(vue.niveauBat); ratio: (vue.niveauBat || 0) / 100
                    teinte: vue.chargeReelle ? Couleurs.vert : ratio <= 0.2 ? Couleurs.rouge : Couleurs.accent
                }
                Valeur {
                    visible: typeof (vue.bat && vue.bat.watts) === "number"
                    libelle: vue.chargeReelle ? Reglages.t("Puissance de charge", "Charging power") : Reglages.t("Consommation", "Power use")
                    valeur: visible ? vue.bat.watts + " W" : ""
                }
                Valeur {
                    readonly property real restant: vue.bat && vue.bat.restant > 0 ? vue.bat.restant
                        : Etat.batterie ? Number(vue.chargeReelle ? Etat.batterie.timeToFull : Etat.batterie.timeToEmpty) || 0 : 0
                    visible: restant > 0
                    libelle: vue.chargeReelle ? Reglages.t("Pleine dans", "Full in") : Reglages.t("Autonomie restante", "Time remaining")
                    valeur: vue.duree(restant)
                }
                ChoixProfil {}
            }

            CarteBloc {
                visible: vue.section === "sante"
                Entete {
                    text: Chaleur.alerte ? Reglages.t("Alerte thermique", "Thermal warning") : Reglages.t("Capteurs & thermique", "Thermal & sensors")
                    color: Chaleur.alerte ? Couleurs.rouge : Couleurs.texte
                }
                Note {
                    visible: !(vue.mesures.temperatures || []).length && !(vue.mesures.ventilateurs || []).length
                    text: Etat.capteursSante ? Reglages.t("Aucune mesure de capteur disponible.", "No sensor readings available.")
                        : Reglages.t("Aucun capteur détecté.", "No sensors found.")
                }
                BarreJauge {
                    visible: vue.mesures.cpu !== undefined
                    libelle: Reglages.t("Charge CPU", "CPU load")
                    valeur: vue.pct(vue.mesures.cpu); ratio: (Number(vue.mesures.cpu) || 0) / 100
                }
                Repeater {
                    model: vue.section === "sante" ? vue.mesures.temperatures || [] : []
                    Valeur {
                        required property var modelData
                        libelle: vue.capteur(modelData[0])
                        valeur: vue.deg(modelData[1]) + (modelData[2] ? " / " + vue.deg(modelData[2]) : "")
                        teinte: Number(modelData[1]) >= (Number(modelData[2]) || 90) - 15 ? Couleurs.orange : Couleurs.texte
                    }
                }
                Valeur { visible: vue.mesures.gpu === "veille"; libelle: vue.capteur("gpu"); valeur: Reglages.t("En veille", "Asleep") }
                Repeater {
                    model: vue.section === "sante" ? vue.mesures.ventilateurs || [] : []
                    Valeur {
                        required property var modelData
                        libelle: Reglages.t("Ventilateur ", "Fan ") + modelData[0]
                        valeur: modelData[1] + Reglages.t(" tr/min", " rpm")
                    }
                }
                Valeur {
                    visible: !vue.masque && !!vue.mesures.top
                    libelle: Reglages.t("Processus le plus actif", "Busiest process")
                    valeur: visible ? vue.mesures.top.split("\t")[0] : ""
                }
                Valeur {
                    visible: !!vue.mesures.profil_firmware
                    libelle: Reglages.t("Profil du micrologiciel", "Firmware profile"); valeur: vue.mesures.profil_firmware || ""
                }
                ChoixProfil {}
            }

            CarteBloc {
                visible: vue.section === "concentration"
                Bouton {
                    glyphe: Notifs.concentration ? "do_not_disturb_on" : "notifications"
                    choisi: Notifs.concentration
                    text: Notifs.concentration ? Reglages.t("Ne pas déranger · Activé", "Do Not Disturb · On") : Reglages.t("Ne pas déranger · Désactivé", "Do Not Disturb · Off")
                    onClicked: Notifs.basculerConcentration()
                }
                Entete { visible: Modes.reglage && !vue.masque; text: Reglages.t("Modes personnalisés", "Custom modes") }
                Note { visible: Modes.reglage && !vue.masque && !Modes.aModes; text: Reglages.t("Aucun mode personnalisé.", "No custom modes.") }
                Repeater {
                    model: vue.section === "concentration" && Modes.reglage && !vue.masque ? Modes.modes : []
                    Bouton {
                        required property var modelData
                        glyphe: modelData.icone || "psychology"; choisi: Modes.actif === modelData.id
                        text: modelData.nom
                        enabled: !Modes.occupe
                        onClicked: Modes.basculer(modelData.id)
                    }
                }
                Note { visible: Modes.reglage && !vue.masque && Modes.message !== ""; text: visible ? Modes.message : "" }
                Bouton {
                    glyphe: "timer"; text: Reglages.t("Démarrer un Pomodoro", "Start Pomodoro")
                    enabled: !Etat.pomodoro
                    onClicked: { Etat.lancerPomodoro(); Etat.allerControle("minuteur") }
                }
                Row {
                    width: parent.width; spacing: 6
                    Repeater {
                        model: [15, 25, 45]
                        Bouton {
                            required property int modelData
                            width: (parent.width - 12) / 3; text: modelData + " min"
                            onClicked: { vue.lancerMinuteur(modelData); Etat.allerControle("minuteur") }
                        }
                    }
                }
            }

            CarteBloc {
                visible: vue.section === "meteo"
                Note {
                    visible: !vue.meteoActive
                    text: Reglages.t("La météo est désactivée.", "Weather is disabled.")
                }
                Row {
                    width: parent.width; spacing: 12; visible: vue.meteoActive && Etat.meteo.temp !== undefined
                    Ico { anchors.verticalCenter: parent.verticalCenter; nom: Etat.meteo.icone || "cloud"; taille: 34; color: Couleurs.accent }
                    Column {
                        width: parent.width - 46; spacing: 3
                        Entete { text: !vue.masque && Etat.meteo.ville ? Etat.meteo.ville : Reglages.t("Météo locale", "Local weather") }
                        Texte { text: vue.deg(Etat.meteo.temp); color: Couleurs.accent; font.pixelSize: 27; font.weight: Font.Bold }
                        Note { visible: !Reglages.en && !!Etat.meteo.texte; text: Etat.meteo.texte || "" }
                        Note { text: Reglages.t("Ressenti ", "Feels like ") + vue.deg(Etat.meteo.ressenti) + " · " + vue.deg(Etat.meteo.min) + " / " + vue.deg(Etat.meteo.max) }
                    }
                }
                Note {
                    visible: vue.meteoActive && (Etat.meteo.temp === undefined || !!Etat.meteo.perime)
                    text: Etat.meteoErreur ? Reglages.t("Ville introuvable.", "City not found.")
                        : Etat.meteo.perime ? Reglages.t("Hors ligne · météo ancienne", "Offline · stale weather")
                        : Reglages.t("Aucune prévision disponible.", "No forecast available.")
                }
                Row {
                    id: previsions
                    visible: vue.meteoActive && modelHeures.count > 0; width: parent.width
                    Repeater {
                        id: modelHeures
                        model: vue.section === "meteo" && vue.meteoActive ? Etat.meteo.heures || [] : []
                        Column {
                            id: heureMeteo
                            required property var modelData
                            width: previsions.width / Math.max(1, modelHeures.count); spacing: 3
                            Texte { anchors.horizontalCenter: parent.horizontalCenter; text: heureMeteo.modelData.h; secondaire: true; font.pixelSize: 11 }
                            Ico { anchors.horizontalCenter: parent.horizontalCenter; nom: heureMeteo.modelData.icone; taille: 18 }
                            Texte { anchors.horizontalCenter: parent.horizontalCenter; text: heureMeteo.modelData.t + "°"; font.pixelSize: 12; font.weight: Font.DemiBold }
                        }
                    }
                }
                Repeater {
                    model: vue.section === "meteo" && vue.meteoActive ? (Etat.meteo.jours || []).slice(1) : []
                    Valeur {
                        required property var modelData
                        libelle: Reglages.en
                            ? ({ "lun.": "Mon", "mar.": "Tue", "mer.": "Wed", "jeu.": "Thu", "ven.": "Fri", "sam.": "Sat", "dim.": "Sun" })[modelData.jour] || modelData.jour
                            : modelData.jour
                        valeur: modelData.min + "° / " + modelData.max + "°"
                    }
                }
            }

            CarteBloc {
                visible: vue.section === "calendrier"
                Note { text: Etat.dateLongue + " · " + Etat.heure }
                Entete {
                    text: Reglages.locale.standaloneMonthName(vue.premier.getMonth(), Locale.LongFormat) + " " + vue.premier.getFullYear()
                    font.capitalization: Font.Capitalize; font.pixelSize: 16
                }
                Row {
                    width: parent.width; spacing: 6
                    Bouton {
                        width: 32; glyphe: "chevron_left"; nomAccessible: Reglages.t("Mois précédent", "Previous month")
                        onClicked: vue.changerMois(-1)
                    }
                    Bouton {
                        width: 94; text: Reglages.t("Aujourd’hui", "Today")
                        onClicked: { vue.jourChoisi = 0; vue.decalageMois = 0 }
                    }
                    Bouton {
                        width: 32; glyphe: "chevron_right"; nomAccessible: Reglages.t("Mois suivant", "Next month")
                        onClicked: vue.changerMois(1)
                    }
                    Bouton {
                        visible: vue.agendaActif; width: 32; glyphe: "refresh"; nomAccessible: Reglages.t("Actualiser Google Agenda", "Refresh Google Calendar")
                        enabled: GoogleAgenda.enCours !== vue.cleMois
                        onClicked: vue.chargerAgenda(true)
                    }
                }
                Grid {
                    width: parent.width; columns: 7; spacing: 2
                    readonly property real cellule: (width - 12) / 7
                    Repeater {
                        model: vue.section !== "calendrier" ? [] : Reglages.en ? ["M", "T", "W", "T", "F", "S", "S"] : ["L", "M", "M", "J", "V", "S", "D"]
                        Texte { required property string modelData; width: parent.cellule; horizontalAlignment: Text.AlignHCenter; text: modelData; secondaire: true }
                    }
                    Repeater { model: vue.section === "calendrier" ? vue.decalageJours : 0; Item { width: parent.cellule; height: 28 } }
                    Repeater {
                        model: vue.section === "calendrier" ? vue.nbJours : 0
                        Bouton {
                            id: jour
                            required property int index
                            readonly property int numero: index + 1
                            readonly property var evenements: vue.evenements(numero)
                            width: parent.cellule; height: 28; text: String(numero)
                            nomAccessible: Qt.formatDate(vue.dateMois(numero), "dd/MM/yyyy")
                            choisi: vue.jourAffiche === numero
                            onClicked: vue.jourChoisi = numero
                            Rectangle {
                                visible: jour.evenements.length > 0
                                width: 4; height: 4; radius: 2; color: Couleurs.accent
                                anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 3
                            }
                        }
                    }
                }
                Note { visible: vue.masque; text: Reglages.t("Agenda masqué pendant le partage d’écran.", "Calendar events hidden during screen sharing.") }
                Note {
                    visible: vue.agendaActif
                    text: visible ? GoogleAgenda.enCours === vue.cleMois ? Reglages.t("Chargement de Google Agenda…", "Loading Google Calendar…")
                        : GoogleAgenda.erreur(vue.cleMois) || (vue.agenda && !vue.evenementsJour.length ? Reglages.t("Aucun événement ce jour.", "No events on this day.") : "") : ""
                }
                Repeater {
                    model: vue.evenementsJour
                    Column {
                        required property var modelData
                        width: parent.width; spacing: 3
                        Entete { text: parent.modelData.titre || Reglages.t("Événement", "Event") }
                        Note {
                            text: [vue.heureAgenda(parent.modelData), parent.modelData.lieu, parent.modelData.calendrier].filter(s => !!s).join(" · ")
                        }
                    }
                }
            }

            CarteBloc {
                id: clips
                visible: vue.section === "presse"
                readonly property bool disponible: visible && PressePapiers.active && !vue.masque
                Entete { text: Reglages.t("Historique récent", "Recent clips") }
                Note {
                    visible: !clips.disponible || !PressePapiers.liste.length
                    text: vue.masque ? Reglages.t("Historique masqué pendant le partage d’écran.", "History hidden during screen sharing.")
                        : !PressePapiers.active ? Reglages.t("Historique désactivé.", "Clipboard history is disabled.")
                        : !PressePapiers.prete ? Reglages.t("Chargement…", "Loading…") : Reglages.t("Presse-papiers vide.", "Clipboard is empty.")
                }
                Repeater {
                    model: clips.disponible ? PressePapiers.liste : []
                    Row {
                        id: clipLigne
                        required property var modelData
                        width: parent.width; spacing: 4
                        Bouton {
                            width: parent.width - 68
                            glyphe: clipLigne.modelData.genre === "image" ? "image" : "content_copy"
                            text: clipLigne.modelData.genre === "image" ? Reglages.t("Image copiée", "Copied image")
                                : String(clipLigne.modelData.texte || "").replace(/\s+/g, " ").slice(0, 140)
                            onClicked: if (clips.disponible) { PressePapiers.recopier(clipLigne.modelData); vue.fermerPanneau() }
                        }
                        Bouton {
                            width: 30; glyphe: "push_pin"; choisi: clipLigne.modelData.epingle
                            nomAccessible: choisi ? Reglages.t("Désépingler", "Unpin") : Reglages.t("Épingler", "Pin")
                            onClicked: if (clips.disponible) PressePapiers.epingler(clipLigne.modelData)
                        }
                        Bouton {
                            width: 30; glyphe: "delete"; critique: true
                            nomAccessible: Reglages.t("Supprimer cette entrée", "Delete this entry")
                            onClicked: if (clips.disponible) PressePapiers.supprimer(clipLigne.modelData)
                        }
                    }
                }
                Bouton {
                    visible: clips.disponible && PressePapiers.liste.some(e => !e.epingle)
                    text: Reglages.t("Effacer les entrées non épinglées", "Clear unpinned clips"); critique: true
                    onClicked: if (clips.disponible) PressePapiers.toutEffacer()
                }
            }

            CarteBloc {
                visible: vue.section === "minuteur"
                Entete {
                    text: !Etat.pomodoro ? Reglages.t("Minuteur", "Timer")
                        : (Etat.pomoPause ? Reglages.t("Pause · ", "Break · ") : "") + "Pomodoro " + Etat.pomoSeance
                }
                Texte {
                    visible: Etat.minuteurFin > 0; width: parent.width; horizontalAlignment: Text.AlignHCenter
                    text: Etat.duree(Etat.minuteurReste)
                    font.pixelSize: 32; font.weight: Font.Bold; font.features: ({ "tnum": 1 }); color: Couleurs.accent
                }
                Row {
                    visible: Etat.minuteurFin > 0; width: parent.width; spacing: 6
                    Bouton { width: (parent.width - 6) / 2; text: "+1 min"; onClicked: Etat.ajouterMinute() }
                    Bouton { width: (parent.width - 6) / 2; text: Reglages.t("Arrêter", "Stop"); critique: true; onClicked: Etat.arreterMinuteur() }
                }
                Grid {
                    width: parent.width; columns: 3; spacing: 6
                    Repeater {
                        model: [1, 5, 10, 15, 25, 45]
                        Bouton {
                            required property int modelData
                            width: (parent.width - 12) / 3; text: modelData + " min"
                            onClicked: vue.lancerMinuteur(modelData)
                        }
                    }
                }
            }

            CarteBloc {
                visible: vue.section === "fenetres"
                Entete { text: Reglages.t("Fenêtres ouvertes", "Open windows") }
                Note { visible: vue.masque; text: Reglages.t("Fenêtres masquées pendant le partage d’écran.", "Windows hidden during screen sharing.") }
                Note { visible: !vue.masque && fenetres.count === 0; text: Reglages.t("Aucune fenêtre ouverte.", "No open windows.") }
                Repeater {
                    id: fenetres
                    model: vue.section === "fenetres" && !vue.masque ? Hyprland.toplevels.values : []
                    Bouton {
                        required property var modelData
                        glyphe: modelData.workspace && modelData.workspace.name === "special:reduites" ? "visibility_off" : "web_asset"
                        text: modelData.title || (modelData.lastIpcObject || {}).class || Reglages.t("Fenêtre", "Window")
                        choisi: Hyprland.activeToplevel === modelData
                        onClicked: vue.ouvrirFenetre(modelData)
                    }
                }
            }

            CarteBloc {
                visible: vue.section === "jeu"
                Bouton {
                    glyphe: "sports_esports"; choisi: Etat.jeu
                    text: Etat.jeu ? Reglages.t("Désactiver le mode jeu", "Turn Game Mode off") : Reglages.t("Activer le mode jeu", "Turn Game Mode on")
                    onClicked: Etat.faire(["hyprctl", "eval", "nc.mode_jeu()"])
                }
                BarreJauge {
                    visible: vue.mesures.cpu !== undefined
                    libelle: Reglages.t("Charge CPU", "CPU load")
                    valeur: vue.pct(vue.mesures.cpu); ratio: (Number(vue.mesures.cpu) || 0) / 100
                }
                Valeur {
                    visible: vue.mesures.cpu_temp !== undefined
                    libelle: Reglages.t("Température du processeur", "CPU temperature"); valeur: vue.deg(vue.mesures.cpu_temp)
                }
                Valeur {
                    visible: vue.mesures.gpu !== undefined
                    libelle: vue.mesures.gpu_nom || vue.capteur("gpu")
                    valeur: vue.mesures.gpu === "veille" ? Reglages.t("En veille", "Asleep")
                        : vue.pct(vue.mesures.gpu) + (vue.mesures.gpu_temp ? " · " + vue.deg(vue.mesures.gpu_temp) : "")
                }
            }
        }
    }
}
