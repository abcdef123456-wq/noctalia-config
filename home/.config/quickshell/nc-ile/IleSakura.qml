pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Shapes

Item {
    id: sakura
    objectName: "nc-sakura"
    required property string variante
    required property string page
    required property int largeurMax
    signal basculerPage(string nom)
    signal replier()

    readonly property bool separee: variante === "bourgeons"
    readonly property bool ticket: variante === "ticket"
    readonly property bool deployee: page === "notifications" || page === "musique"
    property string pageSatellite: ""
    // Garder le contenu pendant le repli ; la hauteur animée décide quand le décharger.
    onPageChanged: if (page === "notifications" || page === "musique") pageSatellite = page
    readonly property bool afficheCarte: separee && (deployee || (pageSatellite !== "" && height > dessusCarte))
    readonly property bool montreMusique: page === "musique" || (Etat.aMusique && Etat.vues.includes("musique"))
    readonly property bool montreNotifs: page === "notifications" || (!Partage.silence && Notifs.liste.length > 0
                                                                    && Etat.vues.includes("notifications"))
    readonly property int nonLues: Partage.silence ? 0 : Notifs.nonLues
    readonly property bool aContexte: montreMusique || montreNotifs
    readonly property color papier: ticket ? "#fff4e9" : "#fff8f5"
    readonly property color encre: "#4a1f2c"
    readonly property color secondaire: "#74505a"
    readonly property color accent: "#a32f57"
    readonly property color rose: "#fde4ec"
    readonly property color filet: ticket ? "#dca7a7" : "#ebcad2"

    readonly property int marge: separee ? 12 : 14
    readonly property int dessusCarte: separee ? 38 : 51
    readonly property int largeurCarte: Math.min(separee ? 316 : ticket ? 338 : 340, largeurMax)
    readonly property real largeurHorloge: reperes.implicitWidth + 24
    readonly property real xContexte: largeurHorloge / 2 + 7
    readonly property real bordDroit: Math.min(largeurMax / 2, xContexte + (aContexte ? contexte.implicitWidth + 12 : 0))
    // Le noyau est centré à l'écran même si la carte est alignée au bord droit du satellite.
    readonly property real gaucheCarte: Math.max(-largeurMax / 2, bordDroit - largeurCarte)
    readonly property real largeurRepos: Math.min(largeurMax, separee
        ? (aContexte ? 2 * bordDroit : largeurHorloge)
        : Math.max(110, reperes.implicitWidth + (aContexte ? contexte.implicitWidth + 10 : 0) + 24))
    implicitWidth: !deployee ? largeurRepos : separee ? Math.max(largeurRepos, -2 * gaucheCarte, 2 * bordDroit) : largeurCarte
    implicitHeight: !deployee ? 30 : dessusCarte + (contenu.item?.implicitHeight ?? 0) + (separee ? 20 : 12)

    readonly property Item zonePrincipale: separee ? pastilleHeure : fond
    readonly property Item zoneContexte: separee && aContexte ? pastilleContexte : null
    readonly property Item zoneCarte: separee && deployee && surfaceCarte.height > 0 ? surfaceCarte : null

    Item {
        id: fond
        anchors.fill: parent
        visible: !sakura.separee
        Rectangle {
            anchors.fill: parent
            visible: !sakura.ticket
            radius: sakura.deployee ? 22 : 15
            color: sakura.papier
            border { color: sakura.filet; width: 1 }
        }
        Shape {
            id: papierDecoupe
            anchors.fill: parent
            visible: sakura.ticket
            preferredRendererType: Shape.CurveRenderer
            readonly property real taille: Math.min(4, height / 8)
            readonly property real pli: Math.min(sakura.deployee ? 42 : 15, height / 2)
            ShapePath {
                fillColor: sakura.papier; strokeColor: sakura.filet; strokeWidth: 1
                PathSvg {
                    path: {
                        const w = Math.max(20, papierDecoupe.width) - .5, h = Math.max(20, papierDecoupe.height) - .5
                        const n = papierDecoupe.taille, y = papierDecoupe.pli
                        return `M8,.5 H${w-8} Q${w},.5 ${w},8 V${y-n} Q${w-2*n},${y} ${w},${y+n} V${h-8} Q${w},${h} ${w-8},${h} H8 Q.5,${h} .5,${h-8} V${y+n} Q${2*n},${y} .5,${y-n} V8 Q.5,.5 8,.5 Z`
                    }
                }
            }
        }
    }

    Rectangle {
        id: pastilleHeure
        objectName: "nc-sakura-noyau"
        visible: sakura.separee
        width: sakura.largeurHorloge; height: 30; x: (sakura.width - width) / 2
        radius: 15; color: sakura.papier; border { color: sakura.filet; width: 1 }
    }
    Rectangle {
        id: pastilleContexte
        objectName: "nc-sakura-satellite"
        visible: sakura.separee && sakura.aContexte
        x: sakura.width / 2 + sakura.xContexte
        width: contexte.implicitWidth + 12; height: 30
        radius: 15; color: sakura.rose; border { color: sakura.filet; width: 1 }
    }
    Rectangle {
        id: surfaceCarte
        objectName: "nc-sakura-carte-satellite"
        property real decalage: 0
        // Garder le bord de la carte pendant le repli, même si un bouton réapparaît dans le satellite.
        Binding on decalage { value: sakura.gaucheCarte; when: sakura.deployee; restoreMode: Binding.RestoreNone }
        visible: sakura.afficheCarte && height > 0
        x: sakura.width / 2 + decalage; y: sakura.dessusCarte
        width: sakura.largeurCarte; height: Math.max(0, sakura.height - y)
        opacity: Math.min(1, height / Math.max(1, contenu.height + 20))
        radius: 16; color: sakura.papier; border { color: sakura.filet; width: 1 }
    }

    Item {
        id: bandeau
        width: parent.width; height: sakura.deployee && !sakura.separee ? 42 : 30
        Row {
            id: reperes
            objectName: "nc-sakura-reperes"
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            x: sakura.separee ? (parent.width - implicitWidth) / 2 : sakura.deployee ? sakura.marge
                : (parent.width - implicitWidth - (sakura.aContexte ? contexte.implicitWidth + 10 : 0)) / 2
            Ico {
                visible: !sakura.separee
                anchors.verticalCenter: parent.verticalCenter
                nom: "local_florist"; taille: 15; color: "#b84d71"
            }
            Texte {
                objectName: "nc-sakura-heure"
                anchors.verticalCenter: parent.verticalCenter
                text: Etat.heure; color: sakura.encre; font.pixelSize: 16; font.weight: Font.DemiBold
                font.features: ({ "tnum": 1 })
            }
            Row {
                anchors.verticalCenter: parent.verticalCenter
                visible: Etat.meteoPilule; spacing: 3
                Ico { anchors.verticalCenter: parent.verticalCenter; nom: Etat.meteo.icone || "cloud"; taille: 14; color: sakura.secondaire }
                Texte {
                    objectName: "nc-sakura-meteo"
                    anchors.verticalCenter: parent.verticalCenter
                    text: Etat.meteo.temp + "°"; color: sakura.secondaire; font.pixelSize: 12
                }
            }
        }
        ControleAction {
            x: reperes.x; y: 0; width: reperes.width; height: bandeau.height
            visible: sakura.page !== ""
            text: Reglages.t("Replier l’île", "Collapse island")
            onClicked: sakura.replier()
        }
        Row {
            id: contexte
            anchors.verticalCenter: parent.verticalCenter
            visible: sakura.aContexte
            spacing: 4
            x: sakura.separee ? pastilleContexte.x + 6 : sakura.deployee
                ? Math.max(reperes.x + reperes.width + 6, parent.width - implicitWidth - sakura.marge)
                : reperes.x + reperes.width + 10
            Rectangle {
                visible: !sakura.separee && !sakura.deployee
                anchors.verticalCenter: parent.verticalCenter
                width: 1; height: 13; color: sakura.filet
            }
            BoutonSakura {
                objectName: "nc-sakura-ouvrir-musique"
                visible: sakura.montreMusique
                actif: sakura.page === "musique"
                symbole: "music_note"
                libelle: (!sakura.deployee || sakura.separee) ? Etat.titre : sakura.ticket ? Reglages.t("Musique", "Music") : ""
                longueur: Math.max(24, Math.min(112, (sakura.largeurMax - 230) / (sakura.separee ? 2 : 1)))
                text: Reglages.t("Ouvrir le lecteur musical", "Open music player")
                onClicked: sakura.basculerPage("musique")
            }
            BoutonSakura {
                objectName: "nc-sakura-pause-pilule"
                visible: sakura.montreMusique && !sakura.deployee && (Etat.lecteur?.canTogglePlaying ?? false)
                symbole: Etat.joue ? "pause" : "play_arrow"
                text: Etat.joue ? "Pause" : Reglages.t("Lire", "Play")
                onClicked: Etat.lecturePause()
            }
            BoutonSakura {
                objectName: "nc-sakura-ouvrir-notifications"
                visible: sakura.montreNotifs
                actif: sakura.page === "notifications"
                symbole: "notifications"
                libelle: sakura.nonLues > 99 ? "99+" : sakura.nonLues > 0 ? String(sakura.nonLues) : ""
                text: Reglages.t("Ouvrir les notifications", "Open notifications")
                onClicked: sakura.basculerPage("notifications")
            }
        }
    }

    Shape {
        visible: sakura.deployee && !sakura.separee
        x: sakura.marge; y: 42; width: Math.max(0, parent.width - 2 * x); height: 1
        ShapePath {
            strokeColor: sakura.filet; strokeWidth: 1; fillColor: "transparent"
            strokeStyle: sakura.ticket ? ShapePath.DashLine : ShapePath.SolidLine
            dashPattern: [2, 2]; startY: .5
            PathLine { x: sakura.width - 2 * sakura.marge; y: .5 }
        }
    }
    Item {
        x: (sakura.separee ? surfaceCarte.x : (sakura.width - sakura.largeurCarte) / 2) + sakura.marge
        y: sakura.dessusCarte + (sakura.separee ? 10 : 0)
        width: Math.max(1, sakura.largeurCarte - 2 * sakura.marge)
        height: sakura.separee ? Math.max(0, surfaceCarte.height - 10) : contenu.height
        clip: sakura.separee
        opacity: sakura.separee ? surfaceCarte.opacity : (sakura.height >= y + height - 1 ? 1 : 0)
        visible: opacity > 0
        Loader {
            id: contenu
            active: sakura.deployee || sakura.afficheCarte
            enabled: sakura.deployee
            width: parent.width
            height: item?.implicitHeight ?? 0
            sourceComponent: ContenuSakura {
                variante: sakura.variante
                page: sakura.separee && !sakura.deployee ? sakura.pageSatellite : sakura.page
            }
        }
    }

    component BoutonSakura: ControleAction {
        id: bouton
        required property string symbole
        property string libelle: ""
        property real longueur: 112
        property bool actif: false
        width: libelle === "" ? 24 : rang.implicitWidth + 10
        height: 24
        anchors.verticalCenter: parent.verticalCenter
        background: Rectangle {
            radius: 12
            color: bouton.actif || bouton.contientPointeur || bouton.symbole === "pause" || bouton.symbole === "play_arrow"
                   ? sakura.rose : "transparent"
        }
        contentItem: Item {
            Row {
                id: rang
                anchors.centerIn: parent; spacing: 3
                Ico { anchors.verticalCenter: parent.verticalCenter; nom: bouton.symbole; taille: 15; color: sakura.accent }
                Texte {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: bouton.libelle !== ""; text: bouton.libelle
                    width: Math.min(implicitWidth, bouton.longueur); font.pixelSize: 11; color: sakura.encre
                }
            }
        }
    }
}
