import QtQuick
import Quickshell.Widgets

WidgetBarreLibelle {
    id: media
    readonly property var options: barre.definition
    readonly property bool imageSeule: barre.vertical || options.album_art_only === true
    readonly property real tailleArt: Math.min(42, Number(options.art_size ?? barre.tailleIcone))
    readonly property string morceau: !Etat.lecteur ? Reglages.t("Rien en lecture", "Not Playing") : !Etat.artiste || options.hide_artist === true ? Etat.titre
        : options.artist_first === true ? Etat.artiste + " — " + Etat.titre : Etat.titre + " — " + Etat.artiste
    affiche: (Etat.lecteur !== null || options.hide_when_no_media !== true) && (options.hide_when_idle !== true || Etat.joue)
              && largeurContenu > 0 && hauteurContenu > 0
    visuel: options.hide_album_art !== true || imageSeule ? pochette : null
    libelle: imageSeule ? "" : morceau
    infobulle: morceau
    minimum: Math.max(0, Number(options.min_length ?? 80) - largeurIcone - espace)
    maximum: Math.max(0, Number(options.max_length ?? 220) - largeurIcone - espace)
    defilement: options.title_scroll || "none"
    gauche: () => barre.page("musique", "son")
    droit: () => Etat.lecturePause()
    retour: () => { if (Etat.lecteur && Etat.lecteur.canGoPrevious) Etat.lecteur.previous() }
    avance: () => { if (Etat.lecteur && Etat.lecteur.canGoNext) Etat.lecteur.next() }

    Component {
        id: pochette
        Item {
            implicitWidth: media.tailleArt; implicitHeight: implicitWidth
            ClippingRectangle {
                anchors.fill: parent
                radius: media.options.circular_album_art !== false ? width / 2 : Math.min(width / 2, Number(media.options.capsule_radius ?? 4))
                color: "transparent"
                Image {
                    id: art
                    anchors.fill: parent
                    source: Etat.pochette
                    asynchronous: true; fillMode: Image.PreserveAspectCrop
                    sourceSize: Qt.size(width * 2, height * 2)
                    readonly property bool anime: !Reglages.sobre && media.options.rotate_album_art === true
                                                  && Etat.joue && status === Image.Ready && media.visible
                    RotationAnimation on rotation {
                        from: 0; to: 360; duration: 13000
                        running: art.anime; loops: Animation.Infinite
                    }
                }
                Image { id: appli; anchors.fill: parent; source: art.status !== Image.Ready ? Etat.iconeLecteur : ""; fillMode: Image.PreserveAspectFit; sourceSize: Qt.size(width * 2, height * 2) }
                Ico { anchors.centerIn: parent; visible: art.status !== Image.Ready && appli.status !== Image.Ready; nom: "music_note"; taille: media.tailleArt; color: media.barre.premierPlan }
            }
        }
    }
}
