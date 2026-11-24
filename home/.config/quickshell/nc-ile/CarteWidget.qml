// Un widget du bureau (WidgetsTheme.qml) : son contenu selon le type, posé dans une carte selon le style.
//   texte : sans carte, sur un voile discret de la couleur du fond de la palette (0,55 au moins, plus opaque si le texte
//           n'aurait pas 4,5:1 sur un fond d'écran très clair ou très sombre), au rayon du thème ;
//   carte : fond « carte » de la palette, rayon de l'île (Couleurs.rayon, donc ILE_RAYON), filet discret (aucun si
//           ILE_CONTOUR=aucun) ;
//   carte-ronde : un cercle (météo, date, anneau) ;
//   brutal : contour de 3 px et ombre DURE décalée de 6 px, couleur du texte, coins vifs.
// Lisibilité : chaque texte a au moins 4,5:1 sur le pire fond possible derrière lui (pri, sec, lisible) et 11 px au moins
// (px). Ombre = un Rectangle décalé : ni flou ni effet. Rien à montrer (pas de musique qui joue, pas de météo, pas de
// citation) : taille nulle, rien n'est dessiné et WidgetsTheme.qml ne lui garde pas de place. Aucun minuteur ici.
// Chiffres d'une horloge : le fichier Chiffres<Nom>.qml du champ « chiffres » (fin, points, segments, mots, aiguille),
// chargé par son nom ; un nouveau style = un nouveau fichier et son nom dans WIDGETS_CHIFFRES de nc-reglages.
import QtQuick

Item {
    id: cw
    property var donnees: null                   // WidgetsTheme : lignes de texte, jauges, échelles, couleurs lisibles
    property var widget: ({})                    // { type, coin, taille, style, chiffres, variante }
    property real k: 1                           // échelle de l'écran
    property real hauteurEcran: 1600
    property real largeurMax: 1000
    readonly property string type: widget.type || ""
    readonly property string style: widget.style || "texte"
    readonly property string variante: widget.variante || ""
    readonly property string chiffres: widget.chiffres || ({ "horloge-mots": "mots", "horloge-segments": "segments" })[type] || "fin"
    readonly property url fichierChiffres: Qt.resolvedUrl("Chiffres" + chiffres.charAt(0).toUpperCase() + chiffres.slice(1) + ".qml")
    readonly property bool carte: style !== "texte"
    readonly property bool ronde: style === "carte-ronde"
    readonly property bool brutal: style === "brutal"
    readonly property real echelle: donnees ? (donnees.echelle[widget.taille] || 1) : 1
    readonly property real t: echelle * k
    readonly property int marge: Math.round((carte ? 24 : 16) * t)
    readonly property int decal: brutal ? 6 : 0
    readonly property real largeurUtile: Math.max(40, largeurMax - 2 * marge - decal)
    readonly property int aligne: ronde || widget.coin === "centre" ? Text.AlignHCenter
                                  : (!carte && String(widget.coin).indexOf("droite") >= 0 ? Text.AlignRight : Text.AlignLeft)
    function ax(pw, w) { return aligne === Text.AlignRight ? pw - w : (aligne === Text.AlignHCenter ? (pw - w) / 2 : 0) }
    // Taille d'un texte : jamais sous 11 px (lisible même à l'échelle 1,6 et en « petit »)
    function px(n) { return Math.max(11, Math.round(n * t)) }
    readonly property var d: Etat.minute
    readonly property string police: donnees ? donnees.police : Couleurs.police
    readonly property string policePetite: donnees ? donnees.policePetite : Couleurs.police
    function policeDe(taille) { return taille >= 30 ? police : policePetite }
    // Taille de l'heure (chiffres) : environ 1/6 de la hauteur de l'écran pour l'horloge géante en « grand »
    readonly property real tailleHeure: type === "horloge-geante" ? Math.min(hauteurEcran / 6 / 0.72 * echelle / 1.5, largeurUtile / 3.2)
                                                                  : (donnees ? donnees.base[type] || 20 : 20) * t
    // Fond derrière le texte au pire : la carte (ou le voile) mêlée au fond d'écran le plus gênant, à travers son opacité
    readonly property color base: carte ? Couleurs.carte : Couleurs.fond
    readonly property color pire: donnees && donnees.lum(Couleurs.texte) > donnees.lum(base) ? "#ffffff" : "#000000"
    readonly property real opacite: brutal ? 1 : (carte ? Couleurs.verre : (donnees ? donnees.voile(Couleurs.texte, base, pire) : 1))
    readonly property color fondPire: donnees ? donnees.melange(base, pire, 1 - opacite) : base
    readonly property color pri: donnees ? donnees.lisible(Couleurs.texte, fondPire) : Couleurs.texte
    readonly property color sec: donnees ? donnees.lisible(Couleurs.texteSec, fondPire) : Couleurs.texteSec
    readonly property color accent: donnees ? donnees.lisible(Couleurs.accent, fondPire) : Couleurs.accent
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
        objectName: "nc-widget-fond"
        visible: !cw.vide
        width: cw.width - cw.decal; height: cw.height - cw.decal
        radius: cw.brutal ? 0 : (cw.ronde ? width / 2 : Couleurs.rayon(26 * cw.t, width, height))
        color: Qt.rgba(cw.base.r, cw.base.g, cw.base.b, cw.opacite)
        border.width: cw.brutal ? 3 : (!cw.carte || Couleurs.contour === "aucun" ? 0 : 1)
        border.color: cw.brutal ? Couleurs.texte : Couleurs.gris3
    }
    // Le contenu à la marge (au milieu d'un cercle) ; l'Item qui le porte bouge, jamais le Loader (sa taille suit son contenu)
    Item {
        x: cw.ronde ? Math.round((fond.width - contenu.width) / 2) : cw.marge
        y: Math.round((fond.height - contenu.height) / 2)
        Loader {
            id: contenu
            sourceComponent: ({ "horloge-geante": wGeante, "horloge-fine": wHorloge, "horloge-mots": wHorloge, "horloge-segments": wHorloge,
                                "date": wDate, "meteo": cw.variante === "phrase" ? wMeteoPhrase : wMeteo, "anneau": wAnneau,
                                "jauge-aiguille": wJaugeAiguille, "musique": wMusique, "accueil": wAccueil,
                                "jauges": cw.carte ? wJauges : null,
                                "calendrier": cw.variante === "ligne" ? wCalLigne : (cw.carte ? wCalendrier : null) })[cw.type] || wTextes
        }
    }

    // Calendrier et jauges sans carte, citation : des lignes de texte (WidgetsTheme.lignes)
    Component {
        id: wTextes
        Column {
            readonly property var lignes: cw.donnees.lignes(cw.type)
            readonly property bool vide: lignes.length === 0
            readonly property bool mono: cw.type === "calendrier" || cw.type === "jauges"
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
                    color: index > 0 || cw.type === "citation" ? cw.sec : cw.pri
                    font.pixelSize: cw.px((cw.donnees.base[cw.type] || 20) * (index === 0 || parent.mono ? 1 : 0.6))
                    font.family: parent.mono ? "monospace" : cw.police
                    wrapMode: cw.type === "citation" ? Text.WordWrap : Text.NoWrap
                    elide: cw.type === "citation" ? Text.ElideNone : Text.ElideRight
                }
            }
        }
    }
    // Horloges fine, en mots, à segments : seulement les chiffres (le style du champ « chiffres »)
    Component {
        id: wHorloge
        Loader {
            readonly property bool vide: false
            Component.onCompleted: setSource(cw.fichierChiffres, { "carte": cw })
            onStatusChanged: if (status === Loader.Error) setSource(Qt.resolvedUrl("ChiffresFin.qml"), { "carte": cw })
        }
    }
    // Jauges en carte : trois chiffres en grand, chacun sur sa barre de points (le texte d'avant sans carte)
    Component {
        id: wJauges
        Row {
            readonly property bool vide: false
            spacing: Math.round(34 * cw.t)
            Repeater {
                model: ["cpu", "ram", "disque"]
                Column {
                    id: mesure
                    required property string modelData
                    readonly property real valeur: cw.donnees[modelData]
                    spacing: Math.round(4 * cw.t)
                    Texte {
                        text: ({ cpu: "CPU", ram: "RAM", disque: Reglages.t("Disque", "Disk") })[mesure.modelData]
                        color: cw.sec
                        font.family: cw.policeDe(cw.px(11))
                        font.pixelSize: cw.px(11)
                        font.capitalization: Font.AllUppercase
                        font.letterSpacing: Math.round(3 * cw.t)
                    }
                    Texte {
                        text: cw.donnees.pct(mesure.valeur)
                        color: cw.pri
                        font.family: cw.policeDe(cw.px(34))
                        font.pixelSize: cw.px(34)
                        font.weight: Font.Bold
                    }
                    Row {
                        spacing: Math.round(3 * cw.t)
                        Repeater {
                            model: 10
                            Rectangle {
                                required property int index
                                width: Math.max(3, Math.round(5 * cw.t)); height: width; radius: width / 2
                                color: index < Math.round(mesure.valeur * 10) ? Couleurs.jauge : Couleurs.gris3
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
            readonly property int case_: Math.max(26, Math.round(30 * cw.t))
            spacing: Math.round(8 * cw.t)
            Texte {
                text: Etat.mois[cw.d.getMonth()] + " " + cw.d.getFullYear()
                color: cw.pri
                font.family: cw.policeDe(cw.px(16))
                font.pixelSize: cw.px(16)
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
                            color: parent.aujourdhui ? cw.donnees.lisible(Couleurs.surAccent, Couleurs.accent) : (parent.index < 7 ? cw.sec : cw.pri)
                            font.family: cw.policeDe(cw.px(13))
                            font.pixelSize: cw.px(13)
                            font.weight: parent.aujourdhui ? Font.Bold : Font.Normal
                        }
                    }
                }
            }
        }
    }
    // Calendrier en ligne (variante « ligne ») : tout le mois sur une ligne, l'initiale du jour au-dessus du numéro,
    // les dimanches dans l'accent, aujourd'hui en gras et souligné
    Component {
        id: wCalLigne
        Column {
            readonly property bool vide: false
            readonly property int jours: new Date(cw.d.getFullYear(), cw.d.getMonth() + 1, 0).getDate()
            readonly property real case_: Math.min(Math.max(22, Math.round(28 * cw.t)), cw.largeurUtile / jours)
            spacing: Math.round(8 * cw.t)
            Texte {
                x: cw.ax(parent.width, width)
                text: Etat.mois[cw.d.getMonth()] + " " + cw.d.getFullYear()
                color: cw.pri
                font.family: cw.policeDe(cw.px(16))
                font.pixelSize: cw.px(16)
                font.weight: Font.DemiBold
            }
            Row {
                Repeater {
                    model: parent.parent.jours
                    Column {
                        required property int index
                        readonly property int jour: new Date(cw.d.getFullYear(), cw.d.getMonth(), index + 1).getDay()
                        readonly property bool aujourdhui: index + 1 === cw.d.getDate()
                        width: parent.parent.case_
                        spacing: Math.round(4 * cw.t)
                        Texte {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: (Reglages.en ? "SMTWTFS" : "DLMMJVS").charAt(parent.jour)
                            color: parent.jour === 0 ? cw.accent : cw.sec
                            font.family: cw.policeDe(cw.px(11))
                            font.pixelSize: cw.px(11)
                        }
                        Texte {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: parent.index + 1
                            color: parent.jour === 0 ? cw.accent : cw.pri
                            font.family: cw.policeDe(cw.px(13))
                            font.pixelSize: cw.px(13)
                            font.weight: parent.aujourdhui ? Font.Black : Font.Normal
                            font.underline: parent.aujourdhui
                        }
                    }
                }
            }
        }
    }
    // Horloge géante : l'heure sur environ 1/6 de la hauteur de l'écran (taille « grand »), la date espacée dessous.
    // Variantes : « quart » (un filet, puis la date au quart de la taille de l'heure), « empilee » (les heures au-dessus
    // des minutes, extra-grasses, les minutes dans l'accent). Police des widgets (WIDGETS_POLICE, sinon celle de l'île)
    Component {
        id: wGeante
        Column {
            id: geante
            readonly property bool vide: false
            readonly property bool empilee: cw.variante === "empilee"
            readonly property bool quart: cw.variante === "quart"
            readonly property var hm: cw.donnees.heure(cw.d).split(":")
            // les chiffres dessinés n'ont pas l'interligne d'un texte : un écart à leur mesure
            spacing: Math.round(cw.chiffres === "fin" || empilee ? 6 * cw.t : Math.max(6 * cw.t, cw.tailleHeure * 0.12))
            Loader {
                id: chiffresGeante
                x: cw.ax(parent.width, width)
                active: !geante.empilee
                Component.onCompleted: setSource(cw.fichierChiffres, { "carte": cw })
                onStatusChanged: if (status === Loader.Error) setSource(Qt.resolvedUrl("ChiffresFin.qml"), { "carte": cw })
            }
            Repeater {
                model: geante.empilee ? 2 : 0
                Texte {
                    required property int index
                    x: cw.ax(parent.width, width)
                    height: Math.round(cw.tailleHeure * 0.82)
                    text: geante.hm[index] || ""
                    color: index === 0 ? cw.pri : cw.accent
                    font.family: cw.policeDe(Math.round(cw.tailleHeure))
                    font.pixelSize: Math.round(cw.tailleHeure)
                    font.weight: Font.Black
                }
            }
            Rectangle {
                x: cw.ax(parent.width, width)
                visible: geante.quart
                width: chiffresGeante.width; height: Math.max(1, Math.round(cw.t))
                color: cw.sec
            }
            Texte {
                x: cw.ax(parent.width, width)
                text: Etat.jours[cw.d.getDay()] + "  ·  " + cw.d.getDate() + " " + Etat.mois[cw.d.getMonth()]
                color: cw.sec
                font.family: cw.policeDe(geante.quart ? Math.max(11, Math.round(cw.tailleHeure / 4)) : cw.px(15))
                font.pixelSize: geante.quart ? Math.max(11, Math.round(cw.tailleHeure / 4)) : cw.px(15)
                font.capitalization: Font.AllUppercase
                font.letterSpacing: Math.round((geante.quart ? 2 : 4) * cw.t)
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
                color: cw.sec
                font.family: cw.policeDe(cw.px(13))
                font.pixelSize: cw.px(13)
                font.capitalization: Font.AllUppercase
                font.letterSpacing: Math.round(3 * cw.t)
            }
            Texte {
                x: cw.ax(parent.width, width)
                text: cw.d.getDate()
                color: cw.pri
                font.family: cw.policeDe(cw.px(72))
                font.pixelSize: cw.px(72)
                font.weight: Font.Bold
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
                        color: aujourdhui ? cw.pri : cw.sec
                        font.family: cw.policePetite
                        font.underline: aujourdhui
                        font.weight: aujourdhui ? Font.Bold : Font.Normal
                        font.pixelSize: cw.px(12)
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
                color: cw.pri
            }
            Texte {
                x: cw.ax(parent.width, width)
                text: (Etat.meteo.temp !== undefined ? Etat.meteo.temp : "") + "°"
                color: cw.pri
                font.family: cw.policeDe(cw.px(52))
                font.pixelSize: cw.px(52)
                font.weight: Font.Bold
            }
            Texte {
                x: cw.ax(parent.width, width)
                width: Math.min(implicitWidth, cw.largeurUtile)
                text: [Reglages.en ? "" : (Etat.meteo.texte || ""),
                       Etat.meteo.min !== undefined && Etat.meteo.max !== undefined ? Etat.meteo.min + "° / " + Etat.meteo.max + "°" : ""]
                      .filter(s => s !== "").join("  ·  ")
                visible: text !== ""
                color: cw.sec
                font.family: cw.policeDe(cw.px(12))
                font.pixelSize: cw.px(12)
                font.capitalization: Font.AllUppercase
                font.letterSpacing: Math.round(2 * cw.t)
            }
        }
    }
    // Météo en phrase (variante « phrase ») : « 13° et nuageux »
    Component {
        id: wMeteoPhrase
        Texte {
            readonly property bool vide: !Etat.meteoPilule
            width: Math.min(implicitWidth, cw.largeurUtile)
            text: cw.donnees.phraseMeteo(Etat.meteo)
            color: cw.pri
            font.family: cw.policeDe(cw.px(34))
            font.pixelSize: cw.px(34)
        }
    }
    // Anneau : la charge du processeur au centre, la mémoire en dessous.
    Component {
        id: wAnneau
        Anneau {
            readonly property bool vide: false
            readonly property bool rond: true
            valeur: cw.donnees.cpu
            libelle: "CPU · RAM " + cw.donnees.pct(cw.donnees.ram)
            diametre: Math.round(200 * cw.t)
            couleur: cw.pri; couleurSec: cw.sec; police: cw.police; policePetite: cw.policePetite; taillePetite: cw.px(15)
        }
    }
    // Jauge à aiguille : la même charge CPU sur un demi-cercle.
    Component {
        id: wJaugeAiguille
        JaugeAiguille {
            readonly property bool vide: false
            valeur: cw.donnees.cpu
            libelle: "CPU"
            diametre: Math.round(200 * cw.t)
            couleur: cw.pri; couleurSec: cw.sec; police: cw.police; policePetite: cw.policePetite; taillePetite: cw.px(13)
        }
    }
    // Musique : pochette (ou icône du lecteur), titre et artiste ; ce qu'Etat lit déjà par MPRIS. Rien quand rien ne joue.
    // Variante « bandeau » : l'heure en grand à droite
    Component {
        id: wMusique
        Row {
            readonly property bool vide: !cw.donnees.musique
            readonly property real texteMax: Math.min(cw.largeurUtile - pochette.width - spacing - (heure.visible ? heure.width + spacing : 0), 320 * cw.t)
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
                Ico { anchors.centerIn: parent; nom: "music_note"; taille: Math.round(40 * cw.t); color: cw.sec; visible: Etat.pochette === "" && Etat.iconeLecteur === "" }
            }
            Column {
                anchors.verticalCenter: parent.verticalCenter
                spacing: Math.round(3 * cw.t)
                Texte {
                    width: Math.min(implicitWidth, parent.parent.texteMax)
                    text: Reglages.t("En lecture", "Now playing")
                    color: cw.sec
                    font.family: cw.policeDe(cw.px(11))
                    font.pixelSize: cw.px(11)
                    font.capitalization: Font.AllUppercase
                    font.letterSpacing: Math.round(3 * cw.t)
                }
                Texte {
                    width: Math.min(implicitWidth, parent.parent.texteMax)
                    text: Etat.titre
                    color: cw.pri
                    font.family: cw.policeDe(cw.px(24))
                    font.pixelSize: cw.px(24)
                    font.weight: Font.DemiBold
                }
                Texte {
                    width: Math.min(implicitWidth, parent.parent.texteMax)
                    text: Etat.artiste
                    visible: text !== ""
                    color: cw.sec
                    font.family: cw.policeDe(cw.px(16))
                    font.pixelSize: cw.px(16)
                }
            }
            Texte {
                id: heure
                anchors.verticalCenter: parent.verticalCenter
                visible: cw.variante === "bandeau"
                text: cw.donnees.heure(cw.d)
                color: cw.pri
                font.family: cw.policeDe(cw.px(56))
                font.pixelSize: cw.px(56)
                font.weight: Font.Bold
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
            color: cw.pri
            font.family: cw.policeDe(cw.px(64))
            font.pixelSize: cw.px(64)
            // Doto (police à points) : graisse par son axe « wght » seul (avec un font.weight en plus, Qt la rend fine), points ronds
            font.weight: cw.police === "Doto" ? Font.Normal : Font.Medium
            font.variableAxes: cw.police === "Doto" ? ({ "ROND": 100, "wght": 800 }) : ({})
        }
    }
}
