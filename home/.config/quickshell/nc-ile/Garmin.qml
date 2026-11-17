// Fenêtre « Santé Garmin » (Super + Alt + S si GARMIN_ACTIF=oui, ou `qs -c nc-ile ipc call ile garmin`). Une VRAIE fenêtre
// (FloatingWindow), titre « Garmin » (stable : les règles de Hyprland la reconnaissent à ce titre exact, regles.lua et
// automatismes.lua). Connecteur NON OFFICIEL. Une grille de cartes (GarminCarte.qml) dans l'ordre choisi, un tiroir
// « Personnaliser » (GarminTiroir.qml), une carte d'accueil hors connexion (GarminAccueil.qml). Tout vient de nc-garmin par
// GarminEtat.qml : seules les valeurs de GarminEtat.metriquesVisibles sont lues ici (vides pendant un partage d'écran).
// Rien ne tourne fermé ; Échap ferme. Verre : fond de la palette à 62 % (92 % sans flou) ; bordure et coins : ceux de Hyprland.
import QtQuick
import Quickshell

FloatingWindow {
    id: garmin
    signal fermer()
    title: Reglages.t("Garmin", "Garmin")           // le même mot dans les deux langues : la règle de Hyprland vise ce titre exact
    color: "transparent"
    implicitWidth: garmin.largeurCarte
    implicitHeight: Math.min(Math.round(garmin.hauteurEcran * 0.9), contenu.implicitHeight + 48)
    minimumSize: Qt.size(420, 260)
    onClosed: garmin.fermer()
    onVisibleChanged: if (!visible) garmin.fermer()

    readonly property real largeurEcran: garmin.screen ? garmin.screen.width : 1600
    readonly property real hauteurEcran: garmin.screen ? garmin.screen.height : 1000
    readonly property bool verre: Reglages.val("FENETRES_FLOU", "oui") !== "non" && !Reglages.sobre
    readonly property int largeurCarte: Math.min(760, Math.round(largeurEcran * 0.92))
    property bool tiroir: false
    readonly property var m: GarminEtat.metriquesVisibles

    function quitter() { garmin.fermer() }
    Component.onCompleted: GarminEtat.panneauOuvert = true
    Component.onDestruction: GarminEtat.panneauOuvert = false

    function nb(v) { return v === undefined || v === null ? "—" : String(v) }
    function heures(s) { return s === undefined || s === null ? "—" : Math.floor(s / 3600) + " h " + String(Math.floor(s % 3600 / 60)).padStart(2, "0") }
    function fiche(id) {
        var m = garmin.m
        if (GarminEtat.masque) return { titre: GarminEtat.nomDe(id), valeur: "—", sous: Reglages.t("Masqué pendant le partage d'écran", "Hidden while sharing the screen"), jauge: -1, couleur: Couleurs.gris4 }
        var un = Reglages.t
        switch (id) {
        case "body_battery": return { titre: GarminEtat.nomDe(id), valeur: nb(m.body_battery), sous: "", jauge: (m.body_battery || 0) / 100, couleur: Couleurs.vert }
        case "frequence_cardiaque": return { titre: GarminEtat.nomDe(id), valeur: nb(m.fc_repos) + " bpm", sous: un("Max ", "Max ") + nb(m.fc_max), jauge: -1, couleur: Couleurs.rouge }
        case "sommeil": return { titre: GarminEtat.nomDe(id), valeur: heures(m.sommeil_s), sous: un("Score ", "Score ") + nb(m.sommeil_score), jauge: (m.sommeil_score || 0) / 100, couleur: Couleurs.violet }
        case "stress": return { titre: GarminEtat.nomDe(id), valeur: nb(m.stress_moyen), sous: "", jauge: (m.stress_moyen || 0) / 100, couleur: Couleurs.orange }
        case "pas": return { titre: GarminEtat.nomDe(id), valeur: nb(m.pas), sous: m.pas_objectif ? un("Objectif ", "Goal ") + m.pas_objectif : "", jauge: m.pas_objectif ? m.pas / m.pas_objectif : -1, couleur: Couleurs.bleu }
        case "vfc": return { titre: GarminEtat.nomDe(id), valeur: nb(m.vfc_nuit) + " ms", sous: "", jauge: -1, couleur: Couleurs.rose }
        case "activite": return { titre: GarminEtat.nomDe(id), valeur: m.activite_nom || "—", sous: m.activite_minutes ? m.activite_minutes + " min" : "", jauge: -1, couleur: Couleurs.vert }
        case "calories": return { titre: GarminEtat.nomDe(id), valeur: nb(m.calories_actives) + " kcal", sous: un("Étages ", "Floors ") + nb(m.etages) + " · " + nb(m.minutes_intenses) + " min", jauge: -1, couleur: Couleurs.orange }
        case "oxygene": return { titre: GarminEtat.nomDe(id), valeur: nb(m.spo2) + " %", sous: un("Respiration ", "Breathing ") + nb(m.respiration), jauge: (m.spo2 || 0) / 100, couleur: Couleurs.bleu }
        case "forme": return { titre: GarminEtat.nomDe(id), valeur: nb(m.readiness), sous: "VO2 max " + nb(m.vo2max), jauge: (m.readiness || 0) / 100, couleur: Couleurs.jaune }
        case "hydratation": return { titre: GarminEtat.nomDe(id), valeur: nb(m.hydratation_ml) + " ml", sous: "", jauge: -1, couleur: Couleurs.bleu }
        }
        return { titre: GarminEtat.nomDe(id), valeur: "—", sous: "", jauge: -1, couleur: Couleurs.accent }
    }

    Item {
        id: carte
        anchors.fill: parent
        Keys.onEscapePressed: garmin.quitter()
        // Un seul fond, plein, sans arrondi ni contour : Hyprland dessine la bordure et découpe les coins
        Rectangle {
            id: fondVerre
            anchors.fill: parent
            color: Qt.alpha(Couleurs.fond, garmin.verre ? 0.62 : 0.92)
        }

        // Le focus clavier de départ
        Item { id: clavier; objectName: "nc-garmin-clavier"; anchors.fill: parent; focus: true }

        Flickable {
            id: defile
            objectName: "nc-garmin-defile"
            anchors.fill: parent; anchors.margins: 1
            contentWidth: width; contentHeight: contenu.implicitHeight + 48
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            flickableDirection: Flickable.VerticalFlick
        Column {
            id: contenu
            objectName: "nc-garmin-contenu"
            x: 26; y: 24; width: defile.width - 52
            spacing: 14

            Item {
                width: parent.width; height: 34
                GarminIcone { id: ico; anchors.verticalCenter: parent.verticalCenter; taille: 26 }
                Texte {
                    anchors.verticalCenter: parent.verticalCenter; x: 36
                    text: Reglages.t("Santé", "Health"); font.pixelSize: 20; font.weight: Font.DemiBold
                }
                Row {
                    anchors.verticalCenter: parent.verticalCenter; anchors.right: parent.right; spacing: 8
                    Rectangle {
                        visible: GarminEtat.actif && GarminEtat.pret
                        objectName: "nc-garmin-actualiser"
                        height: 30; width: tAct.implicitWidth + 24; radius: 15; color: Couleurs.carteSurvol
                        Texte { id: tAct; anchors.centerIn: parent; text: Reglages.t("Actualiser", "Refresh") }
                        MouseArea { anchors.fill: parent; onClicked: GarminEtat.actualiser() }
                    }
                    Rectangle {
                        visible: GarminEtat.actif
                        objectName: "nc-garmin-perso"
                        height: 30; width: tPer.implicitWidth + 24; radius: 15
                        color: garmin.tiroir ? Couleurs.accent : Couleurs.carteSurvol
                        Texte { id: tPer; anchors.centerIn: parent; text: Reglages.t("Personnaliser", "Customize"); color: garmin.tiroir ? Couleurs.surAccent : Couleurs.texte }
                        MouseArea { anchors.fill: parent; onClicked: garmin.tiroir = !garmin.tiroir }
                    }
                    BoutonReglages { section: "Santé Garmin" }
                    Rectangle {
                        height: 30; width: tFer.implicitWidth + 24; radius: 15; color: Couleurs.carteSurvol
                        Texte { id: tFer; anchors.centerIn: parent; text: Reglages.t("Fermer", "Close") }
                        MouseArea { anchors.fill: parent; onClicked: garmin.quitter() }
                    }
                }
            }

            Texte {
                visible: GarminEtat.erreur !== ""
                width: parent.width; wrapMode: Text.Wrap; color: Couleurs.rouge; text: GarminEtat.erreur
            }

            GarminAccueil {
                objectName: "nc-garmin-accueil"
                visible: GarminEtat.lu && (!GarminEtat.actif || !GarminEtat.pret)
                width: parent.width
            }
            Texte {
                visible: GarminEtat.lu && !GarminEtat.actif
                width: parent.width; wrapMode: Text.Wrap; secondaire: true
                text: Reglages.t("La santé Garmin est désactivée dans les réglages.", "Garmin health is turned off in the settings.")
            }

            GarminTiroir { visible: garmin.tiroir && GarminEtat.actif; width: parent.width }
            GarminTableau { objectName: "nc-garmin-tableau" }

            Flow {
                id: grille
                objectName: "nc-garmin-grille"
                visible: GarminEtat.actif && GarminEtat.pret
                width: parent.width; spacing: 12
                readonly property int cols: width > 600 ? 3 : 2
                Repeater {
                    model: GarminEtat.actif && GarminEtat.pret ? GarminEtat.widgetsActifs : []
                    delegate: GarminCarte {
                        id: cc
                        required property string modelData
                        readonly property var f: garmin.fiche(modelData)
                        objectName: "nc-garmin-carte-" + modelData
                        width: Math.floor((grille.width - grille.spacing * (grille.cols - 1)) / grille.cols)
                        titre: f.titre; valeur: f.valeur; sous: f.sous; jauge: f.jauge; couleur: f.couleur
                        Rectangle {
                            visible: cc.modelData === "hydratation"
                            height: 28; width: 64; radius: 14; color: Couleurs.carteSurvol
                            Texte { anchors.centerIn: parent; text: "+250" }
                            MouseArea { anchors.fill: parent; onClicked: GarminEtat.hydrater("+250") }
                        }
                        Rectangle {
                            visible: cc.modelData === "hydratation"
                            height: 28; width: 64; radius: 14; color: Couleurs.carteSurvol
                            Texte { anchors.centerIn: parent; text: "+500" }
                            MouseArea { anchors.fill: parent; onClicked: GarminEtat.hydrater("+500") }
                        }
                    }
                }
            }
        }
        }
    }
}
