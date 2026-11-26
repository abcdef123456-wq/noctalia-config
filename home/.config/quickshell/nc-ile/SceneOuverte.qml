pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import Quickshell.Widgets
import "LecteursAtelier.js" as Atelier
import "LecteursStation.js" as Station
import "LecteursStudio.js" as Studio
import "ScenesIle.js" as Scenes
import "TouchesIle.js" as Touches

Item {
    id: scene
    required property string page
    required property string rubrique
    property string filtre: "toutes"
    signal choisirFiltre(string valeur)
    signal ouvrirControle()
    signal ouvrirRecherche()
    signal ouvrirThemes()
    readonly property bool estDracula: Couleurs.themeActif === "dracula"
    readonly property var papier: estDracula || breve ? null : (chargeurIllustration.item?.planche ?? null)
    readonly property bool musique: page === "musique"
    readonly property bool boite: page === "notifications"
    readonly property bool breve: page !== "essentiel" && !boite && !musique
    readonly property real facteur: width / 480
    implicitHeight: estDracula
        ? (chargeurDracula.item ? chargeurDracula.item.implicitHeight : (breve ? 40 : 146))
        : (breve ? 70 : 176) * facteur
    clip: !estDracula

    Loader {
        id: chargeurDracula
        active: scene.estDracula
        anchors.fill: parent
        sourceComponent: SceneDracula {
            page: scene.page
            rubrique: scene.rubrique
            filtre: scene.filtre
            onChoisirFiltre: valeur => scene.choisirFiltre(valeur)
            onOuvrirControle: scene.ouvrirControle()
            onOuvrirRecherche: scene.ouvrirRecherche()
            onOuvrirThemes: scene.ouvrirThemes()
        }
    }

    Loader {
        id: chargeurIllustration
        active: !scene.estDracula
        sourceComponent: Illustration {}
    }
    component Legende: Text {
        required property var zone
        required property var planche
        x: zone[0]; y: zone[1]; width: zone[2]
        font.family: planche.font; font.pixelSize: zone[3]
        color: planche.ink; textFormat: Text.PlainText
        elide: Text.ElideRight; maximumLineCount: 1
    }
    component Illustration: Item {
        id: feuille
        readonly property var planche: scene.musique ? (Atelier.pour(Couleurs.themeActif)
            || Studio.pour(Couleurs.themeActif) || Station.pour(Couleurs.themeActif)
            || Station.pour("noctalia")) : Scenes.pour(Couleurs.themeActif)
        width: 480; height: scene.breve ? 70 : 176
        scale: scene.facteur; transformOrigin: Item.TopLeft
        Image {
            objectName: "nc-scene-dessin"
            width: 480; height: 176; y: scene.breve ? -30 : 0
            source: feuille.planche.image || ""; sourceSize: Qt.size(960, 352)
            cache: false
        }
        Loader {
            active: scene.musique
            readonly property var cadre: feuille.planche.cover || [0, 0, 0, 0]
            x: cadre[0]; y: cadre[1]; width: cadre[2]; height: width
            sourceComponent: ControleAction {
                id: disque
                text: Reglages.t("Ouvrir le lecteur", "Open player")
                enabled: !!Etat.lecteur && Etat.lecteur.canRaise
                padding: 0
                background: Rectangle {
                    color: feuille.planche.paper
                    radius: feuille.planche.cover?.[3] ?? 0
                    ClippingRectangle {
                        anchors.fill: parent; radius: parent.radius; color: "transparent"
                        visible: art.status === Image.Ready
                        Image {
                            id: art
                            anchors.fill: parent; fillMode: Image.PreserveAspectCrop
                            source: Etat.pochette; asynchronous: true
                            sourceSize: Qt.size(256, 256)
                        }
                    }
                    Image {
                        id: app
                        anchors.centerIn: parent; width: parent.width * .55; height: width
                        source: art.status !== Image.Ready ? Etat.iconeLecteur : ""
                        visible: status === Image.Ready
                    }
                    Ico {
                        anchors.centerIn: parent; nom: "music_note"; taille: parent.width * .48
                        color: feuille.planche.accent; visible: art.status !== Image.Ready && !app.visible
                    }
                    Rectangle {
                        anchors.fill: parent; radius: parent.radius; color: "transparent"
                        border.color: feuille.planche.accent; border.width: disque.visualFocus ? 3 : 1
                    }
                }
                contentItem: Item {}
                onClicked: { Etat.lecteur.raise(); Etat.fermer() }
            }
        }
        // Sur l'atlas, une étoile parcourt le limbe en une heure. Sur la station
        // océanique, c'est l'aiguille du cadran qui indique la minute locale.
        Loader {
            active: scene.page === "essentiel" && ["ocean", "noctalia"].includes(Couleurs.themeActif)
            x: Couleurs.themeActif === "ocean" ? 93 : 112
            y: Couleurs.themeActif === "ocean" ? 87 : 90
            sourceComponent: Item {
                rotation: Etat.maintenant.getMinutes() * 6
                Rectangle {
                    x: -1; y: -64; width: 2; height: Couleurs.themeActif === "ocean" ? 64 : 6
                    color: feuille.planche.ink
                }
                Rectangle { x: -3; y: -66; width: 6; height: 6; radius: 3; color: feuille.planche.ink }
            }
        }
        Legende {
            planche: feuille.planche
            zone: feuille.planche.caption || [0, 0, 0, 12]; y: scene.breve ? 4 : zone[1]
            text: Reglages.t(feuille.planche.name, feuille.planche.en)
            font.weight: Font.DemiBold; font.letterSpacing: 1
        }
        Legende {
            planche: feuille.planche
            id: titre
            objectName: "nc-scene-titre"
            zone: feuille.planche.title || [0, 0, 0, 12]; y: scene.breve ? 24 : zone[1]
            font.pixelSize: scene.breve ? 28 : (scene.musique || scene.boite ? Math.min(zone[3], 31) : zone[3])
            fontSizeMode: scene.page === "essentiel" ? Text.HorizontalFit : Text.FixedSize
            minimumPixelSize: 23
            font.weight: feuille.planche.font === "serif" ? Font.Normal : Font.DemiBold
            font.features: ({ "tnum": 1 })
            text: scene.breve ? scene.rubrique : scene.musique ? (Etat.titre || (Etat.lecteur ? Reglages.t("Sans titre", "Untitled") : Reglages.t("Aucun lecteur", "No player")))
                : scene.boite ? (Notifs.nonLues ? String(Notifs.nonLues) + Reglages.t(" non lues", " unread") : Reglages.t("Tout est lu", "All caught up")) : Etat.heure
        }
        Legende {
            planche: feuille.planche
            zone: feuille.planche.legend || [0, 0, 0, 12]
            visible: !scene.breve
            text: scene.musique ? (Etat.artiste || (Etat.lecteur ? Etat.lecteur.identity : ""))
                : scene.boite ? Reglages.t("Boîte de réception", "Inbox")
                : Reglages.val("ILE_DATE", "oui") === "non" ? "" : Etat.dateLongue
        }
        Repeater {
            model: scene.breve ? 0 : 3
            delegate: ControleAction {
                id: touche
                required property int index
                readonly property var rect: feuille.planche.keys[index]
                readonly property string selection: ["toutes", "nonlues", "urgentes"][index]
                readonly property bool choisie: scene.boite && scene.filtre === selection
                objectName: scene.boite ? "nc-notifs-filtre-" + selection : (scene.musique ? "nc-transport-" : "nc-essentiel-") + (scene.musique ? ["precedent", "lecture", "suivant"] : ["controle", "recherche", "themes"])[index]
                x: rect[0]; y: rect[1]; width: rect[2]; height: rect[3]
                enabled: !scene.musique || (!!Etat.lecteur && [Etat.lecteur.canGoPrevious, Etat.lecteur.canTogglePlaying, Etat.lecteur.canGoNext][index])
                opacity: enabled ? 1 : .52
                text: scene.musique ? [Reglages.t("Précédent", "Previous"), Etat.joue ? "Pause" : Reglages.t("Lecture", "Play"), Reglages.t("Suivant", "Next")][index]
                    : scene.boite ? [Reglages.t("Toutes", "All"), Reglages.t("Non lues", "Unread"), Reglages.t("Urgentes", "Urgent")][index]
                    : [Reglages.t("Contrôle", "Control"), Reglages.t("Recherche", "Search"), Reglages.t("Thèmes", "Themes")][index]
                ToolTip.visible: hovered && width < 94; ToolTip.text: text; ToolTip.delay: 400
                Accessible.checkable: scene.boite; Accessible.checked: choisie
                background: Item {
                    Image {
                        anchors.fill: parent
                        source: Touches.dessin(Couleurs.themeActif, feuille.planche, touche.index, touche.rect[2], touche.rect[3])
                        sourceSize: Qt.size(touche.rect[2] * 2, touche.rect[3] * 2)
                    }
                    Rectangle {
                        anchors.fill: parent; radius: feuille.planche.round
                        color: touche.contientPointeur || touche.choisie ? feuille.planche.ink : "transparent"
                        border.width: touche.visualFocus ? 2 : 0; border.color: feuille.planche.accent
                    }
                }
                contentItem: Row {
                    spacing: 5; leftPadding: Math.max(0,(touche.width - symbole.width - (label.visible ? label.implicitWidth + spacing : 0))/2)
                    Ico {
                        id: symbole; anchors.verticalCenter: parent.verticalCenter; taille: 16
                        nom: scene.musique ? ["skip_previous", Etat.joue ? "pause" : "play_arrow", "skip_next"][touche.index]
                            : scene.boite ? ["inbox", "mark_email_unread", "priority_high"][touche.index] : ["tune", "search", "palette"][touche.index]
                        color: touche.contientPointeur || touche.choisie ? feuille.planche.paper : feuille.planche.ink
                    }
                    Text {
                        id: label; anchors.verticalCenter: parent.verticalCenter; visible: touche.width >= 94
                        text: touche.text; font.family: feuille.planche.font; font.pixelSize: 12; color: symbole.color
                    }
                }
                onClicked: {
                    if (scene.boite) scene.choisirFiltre(selection)
                    else if (scene.musique) {
                        if (index === 0) Etat.lecteur.previous()
                        else if (index === 1) Etat.lecturePause()
                        else Etat.lecteur.next()
                    } else if (index === 0) scene.ouvrirControle()
                    else if (index === 1) scene.ouvrirRecherche()
                    else scene.ouvrirThemes()
                }
            }
        }
    }
}
