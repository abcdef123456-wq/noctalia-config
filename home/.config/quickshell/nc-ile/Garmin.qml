// Fenêtre « Santé Garmin » (Super + Alt + S si GARMIN_ACTIF=oui, ou `qs -c nc-ile ipc call ile garmin`). Une VRAIE fenêtre
// (FloatingWindow), titre « Garmin » (stable : les règles de Hyprland la reconnaissent à ce titre exact, regles.lua et
// automatismes.lua). Jauges et cartes du tableau (GarminTableau.qml) dans l'ordre choisi, avec un tiroir
// « Personnaliser » (GarminTiroir.qml) et une carte d'accueil hors connexion (GarminAccueil.qml).
// Rien ne tourne fermé ; Échap ferme. Verre : fond de la palette à 62 % (92 % sans flou) ; bordure et coins : ceux de Hyprland.
import QtQuick
import Quickshell

FloatingWindow {
    id: garmin
    signal fermer()
    title: Reglages.t("Garmin", "Garmin")           // le même mot dans les deux langues : la règle de Hyprland vise ce titre exact
    color: "transparent"
    implicitWidth: garmin.largeurCarte
    implicitHeight: Math.min(780, Math.round(garmin.hauteurEcran * 0.9), contenu.implicitHeight + 50)
    minimumSize: Qt.size(420, 260)
    onClosed: garmin.fermer()
    onVisibleChanged: if (!visible) garmin.fermer()

    readonly property real largeurEcran: garmin.screen ? garmin.screen.width : 1600
    readonly property real hauteurEcran: garmin.screen ? garmin.screen.height : 1000
    readonly property bool verre: Reglages.val("FENETRES_FLOU", "oui") !== "non" && !Reglages.sobre
    readonly property int largeurCarte: Math.min(900, Math.round(largeurEcran * 0.92))
    property bool tiroir: false

    function quitter() { garmin.fermer() }
    Component.onCompleted: GarminEtat.panneauOuvert = true
    Component.onDestruction: GarminEtat.panneauOuvert = false

    readonly property string sousTitre: {
        const t = Reglages.t
        if (!GarminEtat.lu) return t("Chargement…", "Loading…")
        if (!GarminEtat.actif) return t("Fonction désactivée", "Disabled")
        if (GarminEtat.masque) return t("Indicateurs masqués (partage d'écran)", "Metrics hidden (screen sharing)")
        if (!GarminEtat.pret) return t("Connecteur non officiel · Aucun compte connecté", "Unofficial connector · No account connected")
        let statut = GarminEtat.demo ? t("Données de démonstration", "Demo data") : "Garmin Connect"
        if (!GarminEtat.demo && GarminEtat.maj > 0)
            statut += " · " + t("Synchro ", "Synced ") + Qt.formatTime(new Date(GarminEtat.maj * 1000), "hh:mm")
        const n = GarminEtat.widgetsActifs.length
        return statut + " · " + n + (n === 1 ? t(" indicateur actif", " active widget") : t(" indicateurs actifs", " active widgets"))
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
                    id: entete
                    width: parent.width
                    readonly property bool empile: largeurTitre + actions.implicitWidth + 14 > width
                    readonly property real largeurTitre: Math.max(titre.implicitWidth, sousTitre.implicitWidth) + 36
                    readonly property real hauteurTitre: Math.max(52, libelle.implicitHeight)
                    height: empile ? hauteurTitre + actions.implicitHeight + 8
                                   : Math.max(hauteurTitre, actions.implicitHeight)

                    Item {
                        id: identite
                        width: entete.empile ? entete.width : entete.width - actions.width - 14
                        height: libelle.implicitHeight
                        y: entete.empile ? 0 : (entete.height - height) / 2

                        GarminIcone {
                            taille: 26
                            anchors.verticalCenter: parent.verticalCenter
                            color: GarminEtat.pret ? Couleurs.accent : Couleurs.gris5
                        }
                        Column {
                            id: libelle
                            x: 36; width: parent.width - x; spacing: 2
                            Row {
                                id: titre
                                spacing: 8
                                Texte {
                                    objectName: "nc-garmin-titre"
                                    text: Reglages.t("Santé Garmin", "Garmin Health")
                                    font.pixelSize: 24; font.weight: Font.Bold
                                }
                                Rectangle {
                                    visible: GarminEtat.demo && GarminEtat.actif
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: demo.implicitWidth + 14; height: 20
                                    radius: Couleurs.rayon(10, width, height)
                                    color: Qt.alpha(Couleurs.orange, 0.22)
                                    border.width: 1; border.color: Qt.alpha(Couleurs.orange, 0.5)
                                    Texte {
                                        id: demo
                                        anchors.centerIn: parent
                                        text: Reglages.t("DÉMO", "DEMO")
                                        font.pixelSize: 10; font.weight: Font.Bold; color: Couleurs.orange
                                    }
                                }
                            }
                            Texte {
                                id: sousTitre
                                objectName: "nc-garmin-sous-titre"
                                width: parent.width
                                text: garmin.sousTitre; secondaire: true; font.pixelSize: 12
                            }
                        }
                    }

                    Row {
                        id: actions
                        anchors.right: parent.right
                        y: entete.empile ? entete.hauteurTitre + 8 : (entete.height - implicitHeight) / 2
                        spacing: 8
                        readonly property bool compact: entete.width < 430

                        GarminBouton {
                            objectName: "nc-garmin-perso"
                            visible: GarminEtat.actif
                            texte: Reglages.t("Personnaliser", "Customize")
                            icone: actions.compact ? "" : "tune"
                            choisi: garmin.tiroir
                            onClic: garmin.tiroir = !garmin.tiroir
                        }
                        GarminBouton {
                            objectName: "nc-garmin-actualiser"
                            visible: GarminEtat.actif && GarminEtat.pret
                            enabled: !GarminEtat.occupe
                            texte: GarminEtat.occupe ? Reglages.t("Synchro…", "Syncing…") : Reglages.t("Actualiser", "Refresh")
                            icone: actions.compact ? "" : "refresh"
                            onClic: GarminEtat.actualiser()
                        }
                        BoutonReglages {
                            objectName: "nc-garmin-reglages"
                            taille: 32
                            section: "Santé Garmin"
                        }
                        GarminBouton {
                            objectName: "nc-garmin-fermer"
                            texte: Reglages.t("Fermer", "Close")
                            icone: actions.compact ? "" : "close"
                            onClic: garmin.quitter()
                        }
                    }
                }

                Texte {
                    objectName: "nc-garmin-erreur"
                    visible: GarminEtat.erreur !== ""
                    width: parent.width; wrapMode: Text.Wrap; color: Couleurs.rouge; text: GarminEtat.erreur
                }
                GarminTiroir {
                    objectName: "nc-garmin-tiroir"
                    visible: garmin.tiroir && GarminEtat.actif; width: parent.width
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
                GarminTableau { objectName: "nc-garmin-tableau"; width: parent.width }
            }
        }
    }
}
