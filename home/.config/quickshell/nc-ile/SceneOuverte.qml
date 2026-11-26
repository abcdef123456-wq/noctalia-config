pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import "ScenesIle.js" as Scenes

Item {
    id: scene
    required property string page
    required property string rubrique
    property string filtre: "toutes"
    signal choisirFiltre(string valeur)
    signal ouvrirControle()
    signal ouvrirRecherche()
    signal ouvrirThemes()
    readonly property var planche: Scenes.pour(Couleurs.themeActif)
    readonly property bool musique: page === "musique"
    readonly property bool boite: page === "notifications"
    readonly property bool breve: page !== "essentiel" && !boite && !musique
    readonly property real facteur: width / 480
    implicitHeight: (breve ? 70 : 176) * facteur
    clip: true

    Item {
        id: feuille
        width: 480; height: scene.breve ? 70 : 176
        scale: scene.facteur; transformOrigin: Item.TopLeft
        Image {
            objectName: "nc-scene-dessin"
            width: 480; height: 176; y: scene.breve ? -30 : 0
            source: scene.planche.image; sourceSize: Qt.size(960, 352)
            cache: false
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
                    color: scene.planche.ink
                }
                Rectangle { x: -3; y: -66; width: 6; height: 6; radius: 3; color: scene.planche.ink }
            }
        }
        component Legende: Text {
            required property var zone
            x: zone[0]; y: zone[1]; width: zone[2]
            font.family: scene.planche.font; font.pixelSize: zone[3]
            color: scene.planche.ink; textFormat: Text.PlainText
            elide: Text.ElideRight; maximumLineCount: 1
        }
        Legende {
            zone: scene.planche.caption; y: scene.breve ? 4 : zone[1]
            text: Reglages.t(scene.planche.name, scene.planche.en)
            font.weight: Font.DemiBold; font.letterSpacing: 1
        }
        Legende {
            id: titre
            objectName: "nc-scene-titre"
            zone: scene.planche.title; y: scene.breve ? 24 : zone[1]
            font.pixelSize: scene.breve ? 28 : (scene.musique || scene.boite ? Math.min(zone[3], 31) : zone[3])
            fontSizeMode: scene.page === "essentiel" ? Text.HorizontalFit : Text.FixedSize
            minimumPixelSize: 23
            horizontalAlignment: Couleurs.themeActif === "dracula" ? Text.AlignHCenter : Text.AlignLeft
            font.weight: scene.planche.font === "serif" ? Font.Normal : Font.DemiBold
            font.features: ({ "tnum": 1 })
            text: scene.breve ? scene.rubrique : scene.musique ? (Etat.titre || Reglages.t("Sans titre", "Untitled"))
                : scene.boite ? (Notifs.nonLues ? String(Notifs.nonLues) + Reglages.t(" non lues", " unread") : Reglages.t("Tout est lu", "All caught up")) : Etat.heure
        }
        Legende {
            zone: scene.planche.legend
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
                readonly property var rect: scene.planche.keys[index]
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
                background: Rectangle {
                    radius: scene.planche.round; border.width: touche.visualFocus ? 3 : 1
                    border.color: scene.planche.accent
                    color: touche.contientPointeur || touche.choisie ? scene.planche.ink : scene.planche.paper
                }
                contentItem: Row {
                    spacing: 5; leftPadding: Math.max(0,(touche.width - symbole.width - (label.visible ? label.implicitWidth + spacing : 0))/2)
                    Ico {
                        id: symbole; anchors.verticalCenter: parent.verticalCenter; taille: 16
                        nom: scene.musique ? ["skip_previous", Etat.joue ? "pause" : "play_arrow", "skip_next"][touche.index]
                            : scene.boite ? ["inbox", "mark_email_unread", "priority_high"][touche.index] : ["tune", "search", "palette"][touche.index]
                        color: touche.contientPointeur || touche.choisie ? scene.planche.paper : scene.planche.ink
                    }
                    Text {
                        id: label; anchors.verticalCenter: parent.verticalCenter; visible: touche.width >= 94
                        text: touche.text; font.family: scene.planche.font; font.pixelSize: 12; color: symbole.color
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
