// Un widget du bureau (WidgetsTheme.qml) : son contenu selon le type, posé dans une carte selon le style.
//   texte : sans carte, texte en relief posé sur le fond (le défaut, l'allure d'avant) ;
//   carte : fond « carte » de la palette, rayon de l'île (Couleurs.rayon, donc ILE_RAYON), filet discret (aucun si
//           ILE_CONTOUR=aucun) ;
//   carte-ronde : un cercle (météo, date, anneau) ;
//   brutal : contour de 3 px et ombre DURE décalée de 6 px, couleur du texte, coins vifs.
// Ombre = un Rectangle décalé : ni flou ni effet. Rien à montrer (pas de musique, pas de météo, pas de citation) : taille
// nulle, rien n'est dessiné et WidgetsTheme.qml ne lui garde pas de place. Aucun minuteur ici.
import QtQuick

Item {
    id: cw
    property var donnees: null                   // WidgetsTheme : lignes de texte, jauges, échelles
    property var widget: ({})                    // { type, coin, taille, style }
    property real k: 1                           // échelle de l'écran
    property real hauteurEcran: 1600
    property real largeurMax: 1000
    readonly property string type: widget.type || ""
    readonly property string style: widget.style || "texte"
    readonly property bool carte: style !== "texte"
    readonly property bool ronde: style === "carte-ronde"
    readonly property bool brutal: style === "brutal"
    readonly property real echelle: donnees ? (donnees.echelle[widget.taille] || 1) : 1
    readonly property real t: echelle * k
    readonly property int marge: carte ? Math.round(24 * t) : 0
    readonly property int decal: brutal ? 6 : 0
    readonly property real largeurUtile: Math.max(40, largeurMax - 2 * marge - decal)
    readonly property int aligne: ronde || widget.coin === "centre" ? Text.AlignHCenter
                                  : (!carte && String(widget.coin).indexOf("droite") >= 0 ? Text.AlignRight : Text.AlignLeft)
    function ax(pw, w) { return aligne === Text.AlignRight ? pw - w : (aligne === Text.AlignHCenter ? (pw - w) / 2 : 0) }
    readonly property int relief: carte ? Text.Normal : Text.Raised
    readonly property var d: Etat.minute
    readonly property bool vide: !contenu.item || contenu.item.vide === true
    // Cercle : il contient la diagonale du contenu (un anneau, son diamètre) ; 240 px au moins, pour des cartes rondes égales
    readonly property real diagonale: contenu.item && contenu.item.rond ? contenu.implicitWidth
                                      : Math.sqrt(contenu.implicitWidth * contenu.implicitWidth + contenu.implicitHeight * contenu.implicitHeight)
    readonly property int cote: Math.min(largeurMax, Math.ceil(Math.max(240 * t, diagonale + marge)))
    implicitWidth: vide ? 0 : (ronde ? cote : Math.ceil(contenu.implicitWidth) + 2 * marge + decal)
    implicitHeight: vide ? 0 : (ronde ? cote : Math.ceil(contenu.implicitHeight) + 2 * marge + decal)

    Rectangle {
        objectName: "nc-widget-ombre"
        visible: cw.brutal && !cw.vide
        x: cw.decal; y: cw.decal
        width: fond.width; height: fond.height
        color: Couleurs.texte
    }
    Rectangle {
        id: fond
        visible: cw.carte && !cw.vide
        width: cw.width - cw.decal; height: cw.height - cw.decal
        radius: cw.brutal ? 0 : (cw.ronde ? width / 2 : Couleurs.rayon(26 * cw.t, width, height))
        color: Qt.rgba(Couleurs.carte.r, Couleurs.carte.g, Couleurs.carte.b, cw.brutal ? 1 : Couleurs.verre)
        border.width: cw.brutal ? 3 : (Couleurs.contour === "aucun" ? 0 : 1)
        border.color: cw.brutal ? Couleurs.texte : Couleurs.gris3
    }
    // Le contenu à la marge (au milieu d'un cercle) ; l'Item qui le porte bouge, jamais le Loader (sa taille suit son contenu)
    Item {
        x: cw.ronde || !cw.carte ? Math.round((fond.width - contenu.width) / 2) : cw.marge
        y: Math.round((fond.height - contenu.height) / 2)
        Loader {
            id: contenu
            sourceComponent: ({ "horloge-geante": wGeante, "date": wDate, "meteo": wMeteo, "anneau": wAnneau, "musique": wMusique,
                                "accueil": wAccueil, "jauges": cw.carte ? wJauges : null,
                                "calendrier": cw.carte ? wCalendrier : null })[cw.type] || wTextes
        }
    }

    // Horloges fine, en mots, à segments, calendrier, citation, jauges : des lignes de texte (WidgetsTheme.lignes)
    Component {
        id: wTextes
        Column {
            readonly property var lignes: cw.donnees.lignes(cw.type)
            readonly property bool vide: lignes.length === 0
            readonly property bool mono: cw.type === "calendrier" || cw.type === "jauges" || cw.type === "horloge-segments"
            spacing: 2
            Repeater {
                model: parent.lignes
                Texte {
                    required property string modelData
                    required property int index
                    x: cw.ax(parent.width, width)
                    width: Math.min(implicitWidth, cw.largeurUtile)
                    horizontalAlignment: cw.aligne
                    text: modelData
                    font.pixelSize: Math.round((cw.donnees.base[cw.type] || 20) * cw.t * (index === 0 || parent.mono ? 1 : 0.6))
                    font.weight: cw.type === "horloge-fine" ? Font.ExtraLight : (cw.type === "horloge-segments" ? Font.Bold : Font.Normal)
                    font.family: parent.mono ? "monospace" : Couleurs.police
                    secondaire: index > 0 || cw.type === "citation"
                    wrapMode: cw.type === "citation" ? Text.WordWrap : Text.NoWrap
                    elide: cw.type === "citation" ? Text.ElideNone : Text.ElideRight
                    style: cw.relief; styleColor: Qt.rgba(0, 0, 0, 0.35)
                }
            }
        }
    }
    // Jauges en carte : trois chiffres en grand, chacun sur sa barre de points (le texte d'avant sans carte)
    Component {
        id: wJauges
        Row {
            readonly property bool vide: false
            spacing: Math.round(34 * cw.t)
            Repeater {
                model: [["CPU", cw.donnees.cpu], ["RAM", cw.donnees.ram], [Reglages.t("Disque", "Disk"), cw.donnees.disque]]
                Column {
                    required property var modelData
                    spacing: Math.round(4 * cw.t)
                    Texte {
                        text: parent.modelData[0]
                        secondaire: true
                        font.pixelSize: Math.round(11 * cw.t)
                        font.capitalization: Font.AllUppercase
                        font.letterSpacing: Math.round(3 * cw.t)
                    }
                    Texte {
                        text: cw.donnees.pct(parent.modelData[1])
                        font.pixelSize: Math.round(34 * cw.t)
                        font.weight: Font.Bold
                    }
                    Row {
                        spacing: Math.round(3 * cw.t)
                        Repeater {
                            model: 10
                            Rectangle {
                                required property int index
                                width: Math.max(3, Math.round(5 * cw.t)); height: width; radius: width / 2
                                color: index < Math.round(Math.max(0, Math.min(1, parent.parent.modelData[1])) * 10) ? Couleurs.jauge : Couleurs.gris3
                            }
                        }
                    }
                }
            }
        }
    }
    // Calendrier en carte : le mois, puis une grille ; aujourd'hui dans une pastille de l'accent
    Component {
        id: wCalendrier
        Column {
            readonly property bool vide: false
            readonly property int premier: (new Date(cw.d.getFullYear(), cw.d.getMonth(), 1).getDay() + 6) % 7
            readonly property int jours: new Date(cw.d.getFullYear(), cw.d.getMonth() + 1, 0).getDate()
            readonly property int case_: Math.round(30 * cw.t)
            spacing: Math.round(8 * cw.t)
            Texte {
                text: Etat.mois[cw.d.getMonth()] + " " + cw.d.getFullYear()
                font.pixelSize: Math.round(16 * cw.t)
                font.weight: Font.DemiBold
            }
            Grid {
                columns: 7
                Repeater {
                    model: (Reglages.en ? ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"] : ["Lu", "Ma", "Me", "Je", "Ve", "Sa", "Di"])
                           .concat(Array(parent.parent.premier).fill(""))
                           .concat(Array.from({ length: parent.parent.jours }, (x, i) => String(i + 1)))
                    Item {
                        required property string modelData
                        required property int index
                        readonly property bool aujourdhui: modelData === String(cw.d.getDate()) && index >= 7
                        width: parent.parent.case_; height: width
                        Rectangle {
                            anchors.centerIn: parent
                            width: parent.width - 4; height: width
                            radius: Couleurs.rayon(width / 2, width, height)
                            color: Couleurs.accent
                            visible: parent.aujourdhui
                        }
                        Texte {
                            anchors.centerIn: parent
                            text: parent.modelData
                            color: parent.aujourdhui ? Couleurs.surAccent : (parent.index < 7 ? Couleurs.texteSec : Couleurs.texte)
                            font.pixelSize: Math.round(13 * cw.t)
                            font.weight: parent.aujourdhui ? Font.Bold : Font.Normal
                        }
                    }
                }
            }
        }
    }
    // Horloge géante : l'heure sur environ 1/6 de la hauteur de l'écran (taille « grand »), la date espacée dessous.
    // Police de l'île (ILE_POLICE, une liste : la première installée ; une recette met « Doto, JetBrains Mono »)
    Component {
        id: wGeante
        Column {
            readonly property bool vide: false
            spacing: Math.round(6 * cw.t)
            Texte {
                x: cw.ax(parent.width, width)
                text: cw.donnees.heure(cw.d)
                font.pixelSize: Math.round(Math.min(cw.hauteurEcran / 6 / 0.72 * cw.echelle / 1.5, cw.largeurUtile / 3.2))
                font.weight: Font.Bold
                font.variableAxes: ({ "ROND": 100 })     // police à points (Doto) : des points ronds ; sans effet ailleurs
                style: cw.relief; styleColor: Qt.rgba(0, 0, 0, 0.35)
            }
            Texte {
                x: cw.ax(parent.width, width)
                text: Etat.jours[cw.d.getDay()] + "  ·  " + cw.d.getDate() + " " + Etat.mois[cw.d.getMonth()]
                secondaire: true
                font.pixelSize: Math.round(15 * cw.t)
                font.capitalization: Font.AllUppercase
                font.letterSpacing: Math.round(4 * cw.t)
                style: cw.relief; styleColor: Qt.rgba(0, 0, 0, 0.35)
            }
        }
    }
    // Date : le mois, le jour en grand, l'initiale des jours de la semaine (aujourd'hui souligné)
    Component {
        id: wDate
        Column {
            readonly property bool vide: false
            spacing: Math.round(4 * cw.t)
            Texte {
                x: cw.ax(parent.width, width)
                text: Etat.mois[cw.d.getMonth()]
                secondaire: true
                font.pixelSize: Math.round(13 * cw.t)
                font.capitalization: Font.AllUppercase
                font.letterSpacing: Math.round(3 * cw.t)
                style: cw.relief; styleColor: Qt.rgba(0, 0, 0, 0.35)
            }
            Texte {
                x: cw.ax(parent.width, width)
                text: cw.d.getDate()
                font.pixelSize: Math.round(72 * cw.t)
                font.weight: Font.Bold
                style: cw.relief; styleColor: Qt.rgba(0, 0, 0, 0.35)
            }
            Row {
                x: cw.ax(parent.width, width)
                spacing: Math.round(11 * cw.t)
                Repeater {
                    model: Reglages.en ? ["M", "T", "W", "T", "F", "S", "S"] : ["L", "M", "M", "J", "V", "S", "D"]
                    Texte {
                        required property string modelData
                        required property int index
                        readonly property bool aujourdhui: index === (cw.d.getDay() + 6) % 7
                        text: modelData
                        secondaire: !aujourdhui
                        font.underline: aujourdhui
                        font.weight: aujourdhui ? Font.Bold : Font.Normal
                        font.pixelSize: Math.round(12 * cw.t)
                        style: cw.relief; styleColor: Qt.rgba(0, 0, 0, 0.35)
                    }
                }
            }
        }
    }
    // Météo : celle que l'île lit déjà (nc-meteo, Etat.meteo) ; aucune quand la pilule n'en a pas (ILE_METEO=non, hors ligne)
    Component {
        id: wMeteo
        Column {
            readonly property bool vide: !Etat.meteoPilule
            spacing: Math.round(2 * cw.t)
            Ico {
                x: cw.ax(parent.width, width)
                nom: Etat.meteo.icone || "cloud"
                taille: Math.round(40 * cw.t)
                style: cw.relief; styleColor: Qt.rgba(0, 0, 0, 0.35)
            }
            Texte {
                x: cw.ax(parent.width, width)
                text: (Etat.meteo.temp !== undefined ? Etat.meteo.temp : "") + "°"
                font.pixelSize: Math.round(52 * cw.t)
                font.weight: Font.Bold
                style: cw.relief; styleColor: Qt.rgba(0, 0, 0, 0.35)
            }
            Texte {
                x: cw.ax(parent.width, width)
                width: Math.min(implicitWidth, cw.largeurUtile)
                text: [Reglages.en ? "" : (Etat.meteo.texte || ""),
                       Etat.meteo.min !== undefined && Etat.meteo.max !== undefined ? Etat.meteo.min + "° / " + Etat.meteo.max + "°" : ""]
                      .filter(s => s !== "").join("  ·  ")
                visible: text !== ""
                secondaire: true
                font.pixelSize: Math.round(12 * cw.t)
                font.capitalization: Font.AllUppercase
                font.letterSpacing: Math.round(2 * cw.t)
                style: cw.relief; styleColor: Qt.rgba(0, 0, 0, 0.35)
            }
        }
    }
    // Anneau : le processeur (échantillonnage partagé des jauges), la mémoire en dessous
    Component {
        id: wAnneau
        Anneau {
            readonly property bool vide: false
            readonly property bool rond: true
            valeur: cw.donnees.cpu
            libelle: "CPU · RAM " + cw.donnees.pct(cw.donnees.ram)
            diametre: Math.round(200 * cw.t)
            relief: !cw.carte
        }
    }
    // Musique : pochette (ou icône du lecteur), titre et artiste ; ce qu'Etat lit déjà par MPRIS
    Component {
        id: wMusique
        Row {
            readonly property bool vide: !Etat.aMusique
            readonly property real texteMax: Math.min(cw.largeurUtile - pochette.width - spacing, 320 * cw.t)
            spacing: Math.round(18 * cw.t)
            Rectangle {
                id: pochette
                width: Math.round(96 * cw.t); height: width
                radius: Couleurs.rayon(14 * cw.t, width, height)
                color: Etat.pochette === "" && Etat.iconeLecteur !== "" ? "transparent" : Couleurs.gris2
                clip: true
                Image { anchors.fill: parent; source: Etat.pochette; fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize: Qt.size(192, 192) }
                Image {
                    anchors.fill: parent
                    source: Etat.pochette === "" ? Etat.iconeLecteur : ""
                    visible: Etat.pochette === ""
                    sourceSize: Qt.size(192, 192)
                }
                Ico { anchors.centerIn: parent; nom: "music_note"; taille: Math.round(40 * cw.t); color: Couleurs.texteSec; visible: Etat.pochette === "" && Etat.iconeLecteur === "" }
            }
            Column {
                anchors.verticalCenter: parent.verticalCenter
                spacing: Math.round(3 * cw.t)
                Texte {
                    width: Math.min(implicitWidth, parent.parent.texteMax)
                    text: Reglages.t("En lecture", "Now playing")
                    secondaire: true
                    font.pixelSize: Math.round(11 * cw.t)
                    font.capitalization: Font.AllUppercase
                    font.letterSpacing: Math.round(3 * cw.t)
                    style: cw.relief; styleColor: Qt.rgba(0, 0, 0, 0.35)
                }
                Texte {
                    width: Math.min(implicitWidth, parent.parent.texteMax)
                    text: Etat.titre
                    font.pixelSize: Math.round(24 * cw.t)
                    font.weight: Font.DemiBold
                    style: cw.relief; styleColor: Qt.rgba(0, 0, 0, 0.35)
                }
                Texte {
                    width: Math.min(implicitWidth, parent.parent.texteMax)
                    text: Etat.artiste
                    visible: text !== ""
                    secondaire: true
                    font.pixelSize: Math.round(16 * cw.t)
                    style: cw.relief; styleColor: Qt.rgba(0, 0, 0, 0.35)
                }
            }
        }
    }
    // Accueil : « Bonjour » ou « Bonsoir » selon l'heure (Etat.minute), sans nom de personne
    Component {
        id: wAccueil
        Texte {
            readonly property bool vide: false
            width: Math.min(implicitWidth, cw.largeurUtile)
            text: cw.donnees.accueil(cw.d)
            font.pixelSize: Math.round(60 * cw.t)
            font.weight: Font.Light
            style: cw.relief; styleColor: Qt.rgba(0, 0, 0, 0.35)
        }
    }
}
