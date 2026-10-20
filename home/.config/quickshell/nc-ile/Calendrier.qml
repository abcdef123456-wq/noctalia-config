// Page « Calendrier » : mois en cours (ou feuilleté avec les flèches), aujourd'hui entouré de rouge comme sur iPhone.
// Google Agenda (nc-reglages → Intégration Google ; par JARVIS, voir GoogleAgenda) : un point coloré sous les jours qui
// ont des événements (une couleur par calendrier), le prochain événement sous le titre, et au clic sur un jour son
// agenda (heure, titre, lieu, calendrier ; « Toute la journée » d'abord). Lu seulement quand la page est ouverte,
// gardé 5 minutes ; « Actualiser » relit ; « + » ouvre JARVIS avec une demande de création à compléter.
// Sans le réglage : la page d'avant, telle quelle, sans aucun appel.
import QtQuick

Item {
    id: ca
    property int decalage: 0
    property int jourChoisi: 0                  // jour montré en détail (0 : aucun)
    readonly property date premier: new Date(Etat.maintenant.getFullYear(), Etat.maintenant.getMonth() + decalage, 1)
    readonly property int nbJours: new Date(premier.getFullYear(), premier.getMonth() + 1, 0).getDate()
    readonly property int debut: (premier.getDay() + 6) % 7          // lundi en premier
    readonly property bool google: Reglages.val("GOOGLE_INTEGRATION", "non") === "oui" && Reglages.val("GOOGLE_CALENDRIER", "oui") !== "non"
    readonly property string cle: GoogleAgenda.cle(premier)
    readonly property var mois: google ? (GoogleAgenda.cache[cle] || null) : null
    readonly property var evenements: mois ? mois.events : []
    readonly property bool chargement: google && GoogleAgenda.enCours === cle
    readonly property string erreur: google ? GoogleAgenda.erreur(cle) : ""
    readonly property var prochain: google && GoogleAgenda.cache !== undefined ? GoogleAgenda.prochain(Etat.maintenant) : null
    readonly property var duJour: jourChoisi > 0 ? evenementsDu(jourChoisi) : []
    function defiler(dy) { return defil.defiler(dy) }
    function iso(j) { return GoogleAgenda.iso(new Date(premier.getFullYear(), premier.getMonth(), j)) }
    // Les événements d'un jour : ceux qui commencent ce jour, et les journées entières qui le couvrent (fin exclue)
    function evenementsDu(j) {
        var d = iso(j)
        return evenements.filter(e => e.journee ? (e.fin ? (e.debut <= d && d < e.fin) : e.debut === d) : e.debut.slice(0, 10) === d)
            .sort((a, b) => a.journee !== b.journee ? (a.journee ? -1 : 1) : (a.debut < b.debut ? -1 : (a.debut > b.debut ? 1 : 0)))
    }
    function couleurs(j) {
        var l = [], ev = evenementsDu(j)
        for (var i = 0; i < ev.length && l.length < 3; i++) if (l.indexOf(ev[i].couleur) < 0) l.push(ev[i].couleur)
        return l
    }
    function heure(e) { return e.journee ? Reglages.t("Toute la journée", "All day") : e.debut.slice(11, 16) + (e.fin && !e.journee ? " – " + e.fin.slice(11, 16) : "") }
    function jourCourt(e) {
        var d = new Date(e.debut.slice(0, 4), e.debut.slice(5, 7) - 1, e.debut.slice(8, 10))
        return Reglages.en ? Reglages.locale.dayName(d.getDay(), Locale.ShortFormat) + " " + d.getDate()
                           : ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."][d.getDay()] + " " + d.getDate()
    }
    // La date est recalculée ici : au changement de mois, la liaison « premier » n'est pas forcément déjà à jour
    function charger(force) { if (google && visible) GoogleAgenda.charger(new Date(Etat.maintenant.getFullYear(), Etat.maintenant.getMonth() + decalage, 1), force) }
    // « + » : JARVIS, avec une demande de création prête à compléter (le jour choisi, sinon aujourd'hui)
    function creer() {
        var j = jourChoisi > 0 ? iso(jourChoisi) : GoogleAgenda.iso(Etat.maintenant)
        AssistantEtat.brouillon = Reglages.t("Crée un événement dans mon Google Agenda le " + j + " : ", "Create an event in my Google Calendar on " + j + ": ")
        Etat.aller("assistant")
    }
    onVisibleChanged: { if (visible) { decalage = 0; jourChoisi = 0; charger(false) } }
    onDecalageChanged: { jourChoisi = 0; charger(false) }
    onGoogleChanged: charger(false)

    Item {
        id: tete
        width: parent.width; height: 34
        Texte {
            anchors.verticalCenter: parent.verticalCenter
            text: Reglages.en ? Reglages.locale.standaloneMonthName(ca.premier.getMonth(), Locale.LongFormat) + " " + ca.premier.getFullYear()
                  : Etat.mois[ca.premier.getMonth()].charAt(0).toUpperCase() + Etat.mois[ca.premier.getMonth()].slice(1) + " " + ca.premier.getFullYear()
            font.pixelSize: 20; font.weight: Font.Bold
        }
        Row {
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 6
            Rond { objectName: "nc-cal-plus"; taille: 32; icone: "add"; visible: ca.google; onClic: ca.creer()
                   Accessible.name: Reglages.t("Créer un événement avec JARVIS", "Create an event with JARVIS") }
            Rond { objectName: "nc-cal-actualiser"; taille: 32; icone: "refresh"; visible: ca.google; onClic: ca.charger(true)
                   Accessible.name: Reglages.t("Actualiser Google Agenda", "Refresh Google Calendar") }
            Rond { taille: 32; icone: "chevron_left"; onClic: ca.decalage-- }
            Rond { taille: 32; icone: "today"; visible: ca.decalage !== 0; onClic: ca.decalage = 0 }
            Rond { taille: 32; icone: "chevron_right"; onClic: ca.decalage++ }
        }
    }

    Defilement {
        id: defil
        anchors.top: tete.bottom; anchors.topMargin: 10; anchors.bottom: parent.bottom
        width: parent.width
        contentHeight: colonne.implicitHeight

        Column {
            id: colonne
            width: ca.width; spacing: 8
            readonly property real voulue: 34 + 10 + implicitHeight
            onVoulueChanged: if (ca.google) Etat.annoncerHauteur("calendrier", voulue)

            // Prochain événement (Google)
            Row {
                objectName: "nc-cal-prochain"
                visible: ca.google && ca.prochain !== null
                spacing: 8; leftPadding: 4
                Rectangle { anchors.verticalCenter: parent.verticalCenter; width: 8; height: 8; radius: 4; color: ca.prochain ? ca.prochain.couleur : "transparent" }
                Texte {
                    text: ca.prochain ? Reglages.t("Prochain : ", "Next: ") + ca.heure(ca.prochain) + " · " + ca.prochain.titre + " (" + ca.jourCourt(ca.prochain) + ")" : ""
                    secondaire: true; font.pixelSize: 12; width: ca.width - 24; elide: Text.ElideRight
                }
            }

            Grid {
                id: grille
                columns: 7; columnSpacing: 0; rowSpacing: 4
                Repeater {
                    model: Reglages.en ? [1, 2, 3, 4, 5, 6, 0].map(j => Reglages.locale.dayName(j, Locale.NarrowFormat))
                                       : ["L", "M", "M", "J", "V", "S", "D"]
                    Texte { required property string modelData; width: ca.width / 7; height: 22; text: modelData; secondaire: true; horizontalAlignment: Text.AlignHCenter; font.weight: Font.DemiBold; font.pixelSize: 12 }
                }
                Repeater {
                    model: ca.debut + ca.nbJours
                    Item {
                        id: cellule
                        required property int index
                        readonly property int jour: index - ca.debut + 1
                        readonly property bool aujourdhui: ca.decalage === 0 && jour === Etat.maintenant.getDate()
                        readonly property bool choisi: ca.google && jour > 0 && jour === ca.jourChoisi
                        readonly property var points: ca.google && jour > 0 ? ca.couleurs(jour) : []
                        objectName: jour > 0 ? "nc-cal-jour-" + jour : ""
                        width: ca.width / 7; height: 40
                        Rectangle {
                            anchors.centerIn: parent; width: 34; height: 34; radius: 17
                            color: cellule.aujourdhui ? Couleurs.rouge : (cellule.choisi ? Couleurs.gris3 : "transparent")
                            border.width: cellule.choisi && cellule.aujourdhui ? 2 : 0; border.color: Couleurs.texte
                        }
                        Texte {
                            anchors.centerIn: parent; visible: cellule.jour > 0
                            text: cellule.jour; font.pixelSize: 15
                            font.weight: cellule.aujourdhui ? Font.Bold : Font.Normal
                            color: cellule.aujourdhui ? Couleurs.surCouleur : ((index % 7) >= 5 ? Couleurs.texteSec : Couleurs.texte)
                        }
                        // Points des calendriers (Google)
                        Row {
                            objectName: "nc-cal-points"
                            anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 1; spacing: 2
                            visible: cellule.points.length > 0
                            Repeater {
                                model: cellule.points
                                Rectangle { required property string modelData; width: 5; height: 5; radius: 2.5; color: modelData }
                            }
                        }
                        MouseArea {
                            anchors.fill: parent; enabled: ca.google && cellule.jour > 0
                            onClicked: ca.jourChoisi = ca.jourChoisi === cellule.jour ? 0 : cellule.jour
                        }
                    }
                }
            }

            // État Google : chargement, erreur ; puis l'agenda du jour choisi
            Column {
                id: agenda
                objectName: "nc-cal-agenda"
                visible: ca.google
                width: parent.width; spacing: 6
                Row {
                    visible: ca.chargement && !ca.mois
                    spacing: 8; leftPadding: 4
                    Ico { anchors.verticalCenter: parent.verticalCenter; nom: "progress_activity"; taille: 16; color: Couleurs.texteSec
                          RotationAnimation on rotation { from: 0; to: 360; duration: 1200; loops: Animation.Infinite; running: ca.chargement } }
                    Texte { text: Reglages.t("Chargement de Google Agenda…", "Loading Google Calendar…"); secondaire: true; font.pixelSize: 12 }
                }
                Column {
                    objectName: "nc-cal-erreur"
                    visible: ca.erreur !== "" && !ca.chargement
                    width: parent.width; spacing: 4; leftPadding: 4
                    Texte { width: parent.width - 8; text: ca.erreur; color: Couleurs.rouge; font.pixelSize: 12; wrapMode: Text.Wrap }
                    Texte {
                        text: Reglages.t("Actualiser", "Refresh"); color: zr.containsMouse ? Couleurs.accentClair : Couleurs.accent; font.pixelSize: 12
                        MouseArea { id: zr; anchors.fill: parent; anchors.margins: -4; hoverEnabled: true; onClicked: ca.charger(true) }
                    }
                }
                Texte {
                    visible: ca.mois !== null && ca.jourChoisi === 0 && ca.erreur === ""
                    leftPadding: 4; secondaire: true; font.pixelSize: 12
                    text: ca.evenements.length === 0 ? Reglages.t("Aucun événement ce mois-ci", "No events this month")
                        : Reglages.t("Clique sur un jour pour son agenda", "Click a day for its agenda")
                }
                Texte {
                    visible: ca.jourChoisi > 0
                    leftPadding: 4; text: ca.jourChoisi > 0 ? ca.jourCourt({ debut: ca.iso(ca.jourChoisi) }) : ""; font.weight: Font.DemiBold; font.pixelSize: 13
                }
                Texte {
                    visible: ca.jourChoisi > 0 && ca.duJour.length === 0 && ca.mois !== null
                    leftPadding: 4; text: Reglages.t("Aucun événement", "No events"); secondaire: true; font.pixelSize: 12
                }
                Repeater {
                    model: ca.duJour
                    Rectangle {
                        id: ev
                        required property var modelData
                        width: agenda.width; height: 50; radius: 14; color: Couleurs.carte
                        Rectangle { x: 12; y: 10; width: 4; height: 30; radius: 2; color: ev.modelData.couleur }
                        Column {
                            x: 24; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 36; spacing: 1
                            Texte { width: parent.width; elide: Text.ElideRight; font.pixelSize: 13; font.weight: Font.DemiBold
                                    text: ca.heure(ev.modelData) + " · " + ev.modelData.titre }
                            Texte { width: parent.width; elide: Text.ElideRight; secondaire: true; font.pixelSize: 11
                                    text: (ev.modelData.lieu ? ev.modelData.lieu + " · " : "") + ev.modelData.calendrier }
                        }
                    }
                }
            }
        }
    }
}
