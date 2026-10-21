// Page « Presse-papiers » de l'île (Super + Maj + V) : ce que tu as copié (PressePapiers : gardé d'une session à l'autre,
// 50 textes et 12 images au plus, épinglés d'abord). Recherche, filtre Tout / Textes / Images ; un clic recopie
// (Ctrl + V pour coller) ; sur une carte : épingler, coller en texte brut dans la fenêtre active, supprimer ; un texte
// long se déplie d'un clic sur sa flèche ; « Effacer » vide l'historique (les épinglés restent).
// Clavier : ↑ ↓ choisir, Entrée recopier, Suppr supprimer, Échap vider la recherche.
import QtQuick
import Quickshell.Widgets

Item {
    id: p
    property string recherche: ""
    property string filtre: "tout"           // tout, textes, images
    property int choix: -1                   // carte choisie au clavier
    property var deplies: ({})               // id → texte long déplié
    readonly property var visibles: PressePapiers.liste.filter(e => PressePapiers.correspond(e, recherche, filtre))
    readonly property int nbTextes: PressePapiers.liste.filter(e => e.genre === "texte").length
    readonly property int nbImages: PressePapiers.liste.length - nbTextes
    function defiler(dy) { return defil.defiler(dy) }
    function apercu(e) { return e.texte.replace(/\s+/g, " ").trim() }
    function longue(e) { return e.genre === "texte" && (e.texte.length > 160 || e.texte.split("\n").length > 2) }
    function deplier(e) { var d = Object.assign({}, deplies); if (d[e.id]) delete d[e.id]; else d[e.id] = true; deplies = d }
    onVisibleChanged: { if (visible) { choix = -1; forceActiveFocus() } }
    onVisiblesChanged: if (choix >= visibles.length) choix = visibles.length - 1

    Keys.onPressed: e => {
        if (e.key === Qt.Key_Down && visibles.length) { choix = Math.min(visibles.length - 1, choix + 1); e.accepted = true }
        else if (e.key === Qt.Key_Up && visibles.length) { choix = Math.max(0, choix - 1); e.accepted = true }
        else if ((e.key === Qt.Key_Return || e.key === Qt.Key_Enter) && choix >= 0 && choix < visibles.length) { PressePapiers.recopier(visibles[choix]); e.accepted = true }
        else if (e.key === Qt.Key_Delete && choix >= 0 && choix < visibles.length) { PressePapiers.supprimer(visibles[choix]); e.accepted = true }
        else if (e.key === Qt.Key_Escape && (recherche !== "" || champ.activeFocus)) { recherche = ""; champ.text = ""; p.forceActiveFocus(); e.accepted = true }
        else if (e.key === Qt.Key_Slash || (e.key === Qt.Key_F && (e.modifiers & Qt.ControlModifier))) { champ.forceActiveFocus(); e.accepted = true }
    }

    Item {
        id: tete
        width: parent.width; height: 34
        Texte { anchors.verticalCenter: parent.verticalCenter; leftPadding: 4; text: Reglages.t("Presse-papiers", "Clipboard"); font.pixelSize: 20; font.weight: Font.Bold }
        Texte {
            objectName: "nc-presse-effacer"
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            visible: PressePapiers.liste.length > 0
            text: Reglages.t("Effacer", "Clear"); color: ze.containsMouse ? Couleurs.accentClair : Couleurs.accent
            MouseArea { id: ze; anchors.fill: parent; anchors.margins: -6; hoverEnabled: true; onClicked: PressePapiers.toutEffacer() }
            Accessible.role: Accessible.Button
            Accessible.name: Reglages.t("Effacer l'historique (les épinglés restent)", "Clear history (pinned items stay)")
        }
    }

    // Recherche et filtres
    Item {
        id: outils
        anchors.top: tete.bottom; anchors.topMargin: 8
        width: parent.width; height: 32
        visible: PressePapiers.liste.length > 0
        Rectangle {
            id: zoneRecherche
            anchors.left: parent.left; anchors.right: filtres.left; anchors.rightMargin: 8; height: 32; radius: 16
            color: Couleurs.gris2; border.width: 1; border.color: champ.activeFocus ? Couleurs.accent : "transparent"
            Ico { x: 10; anchors.verticalCenter: parent.verticalCenter; nom: "search"; taille: 16; color: Couleurs.texteSec }
            TextInput {
                id: champ
                objectName: "nc-presse-recherche"
                anchors.left: parent.left; anchors.leftMargin: 32; anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
                color: Couleurs.texte; font.pixelSize: 13; clip: true; selectByMouse: true
                onTextChanged: { p.recherche = text; p.choix = -1 }
                Keys.onPressed: e => { if (e.key === Qt.Key_Down || e.key === Qt.Key_Up || e.key === Qt.Key_Return || e.key === Qt.Key_Enter || e.key === Qt.Key_Escape) { e.accepted = false } }
                Keys.forwardTo: [p]
                Texte { anchors.fill: parent; visible: !champ.text && !champ.activeFocus; text: Reglages.t("Rechercher", "Search"); secondaire: true; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter }
            }
        }
        Row {
            id: filtres
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 4
            Repeater {
                model: [{ id: "tout", nom: Reglages.t("Tout", "All") }, { id: "textes", nom: Reglages.t("Textes", "Text") }, { id: "images", nom: "Images" }]
                Rectangle {
                    id: pf
                    required property var modelData
                    objectName: "nc-presse-filtre-" + modelData.id
                    width: lf.implicitWidth + 18; height: 26; radius: 13
                    color: p.filtre === modelData.id ? Couleurs.accent : (zf.containsMouse ? Couleurs.gris3 : Couleurs.gris2)
                    Texte { id: lf; anchors.centerIn: parent; text: pf.modelData.nom; font.pixelSize: 12; font.weight: Font.DemiBold; color: p.filtre === pf.modelData.id ? Couleurs.surAccent : Couleurs.texte }
                    MouseArea { id: zf; anchors.fill: parent; hoverEnabled: true; onClicked: { p.filtre = pf.modelData.id; p.choix = -1 } }
                    Accessible.role: Accessible.Button
                    Accessible.name: pf.modelData.nom
                }
            }
        }
    }

    Defilement {
        id: defil
        anchors.top: outils.visible ? outils.bottom : tete.bottom; anchors.topMargin: 10; anchors.bottom: parent.bottom
        width: parent.width
        contentHeight: liste.implicitHeight

        Column {
            id: liste
            width: p.width; spacing: 6
            readonly property real voulue: 34 + (outils.visible ? 40 : 0) + 10 + implicitHeight
            onVoulueChanged: Etat.annoncerHauteur("presse", voulue)
            Component.onCompleted: Etat.annoncerHauteur("presse", voulue)

            Item {
                visible: p.visibles.length === 0
                width: parent.width; height: 100
                Column {
                    anchors.centerIn: parent; spacing: 6
                    Ico { anchors.horizontalCenter: parent.horizontalCenter; nom: PressePapiers.liste.length ? "search_off" : "content_paste"; taille: 30; color: Couleurs.gris4 }
                    Texte {
                        anchors.horizontalCenter: parent.horizontalCenter; secondaire: true
                        text: PressePapiers.liste.length ? Reglages.t("Rien ne correspond", "Nothing matches") : Reglages.t("Ce que tu copies apparaîtra ici", "Things you copy will appear here")
                    }
                }
            }
            Repeater {
                model: p.visibles
                Rectangle {
                    id: el
                    required property var modelData
                    required property int index
                    readonly property bool image: modelData.genre === "image"
                    readonly property bool choisi: p.choix === index
                    readonly property bool deplie: !!p.deplies[modelData.id]
                    objectName: "nc-presse-" + modelData.id
                    width: liste.width; height: image ? 86 : Math.min(deplie ? 320 : 64, txt.implicitHeight + 20); radius: 14
                    color: zone.containsMouse || choisi ? Couleurs.carteSurvol : Couleurs.carte
                    border.width: choisi ? 1.5 : 0; border.color: Couleurs.accent
                    property bool copie: false
                    Texte {
                        id: txt
                        visible: !el.image
                        x: 14; y: 10; width: parent.width - 110
                        text: el.image ? "" : (el.deplie ? el.modelData.texte : p.apercu(el.modelData))
                        wrapMode: Text.Wrap; maximumLineCount: el.deplie ? 14 : 2; elide: Text.ElideRight; font.pixelSize: 13
                    }
                    ClippingRectangle {
                        visible: el.image
                        x: 10; y: 8; width: 110; height: 70; radius: 9; color: Couleurs.gris2
                        Image { anchors.fill: parent; source: el.image ? "file://" + el.modelData.chemin : ""; fillMode: Image.PreserveAspectCrop
                                asynchronous: true; sourceSize: Qt.size(220, 140) }
                    }
                    Texte { visible: el.image; x: 132; anchors.verticalCenter: parent.verticalCenter; text: "Image" + (el.modelData.octets ? " · " + Math.round(el.modelData.octets / 1024) + " Ko" : ""); secondaire: true }
                    // Actions à droite : déplier (texte long), épingler, coller en brut, supprimer, puis l'état copié
                    Row {
                        anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter; spacing: 2
                        Repeater {
                            model: [
                                { id: "deplier", icone: el.deplie ? "expand_less" : "expand_more", aide: Reglages.t("Aperçu complet", "Full preview"), visible: p.longue(el.modelData), fixe: true },
                                { id: "epingler", icone: "push_pin", aide: el.modelData.epingle ? Reglages.t("Désépingler", "Unpin") : Reglages.t("Épingler", "Pin"), visible: true, fixe: el.modelData.epingle },
                                { id: "ia", icone: "auto_awesome", aide: el.image ? Reglages.t("Expliquer l'image avec l'IA", "Explain the image with AI") : Reglages.t("L'IA sur ce texte (résumer, traduire…)", "AI on this text (summarize, translate…)"),
                                  visible: !Reglages.iaCoupee && Reglages.val(el.image ? "IA_CAPTURE" : "IA_TEXTE", "oui") !== "non", fixe: false },
                                { id: "coller", icone: "keyboard_return", aide: Reglages.t("Coller en texte brut dans la fenêtre active", "Paste as plain text in the active window"), visible: !el.image, fixe: false },
                                { id: "supprimer", icone: "close", aide: Reglages.t("Supprimer", "Delete"), visible: true, fixe: false }
                            ]
                            Item {
                                id: action
                                required property var modelData
                                objectName: "nc-presse-" + el.modelData.id + "-" + modelData.id
                                width: 26; height: 26
                                visible: modelData.visible && (modelData.fixe || zone.containsMouse || el.choisi || za.containsMouse)
                                Ico { anchors.centerIn: parent; nom: action.modelData.icone; taille: 16
                                      color: action.modelData.id === "epingler" && el.modelData.epingle ? Couleurs.accent : (za.containsMouse ? Couleurs.texte : Couleurs.texteSec) }
                                MouseArea {
                                    id: za; anchors.fill: parent; hoverEnabled: true
                                    onClicked: {
                                        if (action.modelData.id === "deplier") p.deplier(el.modelData)
                                        else if (action.modelData.id === "epingler") PressePapiers.epingler(el.modelData)
                                        else if (action.modelData.id === "coller") PressePapiers.coller(el.modelData)
                                        else if (action.modelData.id === "ia") PressePapiers.demanderIA(el.modelData)
                                        else PressePapiers.supprimer(el.modelData)
                                    }
                                }
                                Accessible.role: Accessible.Button
                                Accessible.name: action.modelData.aide
                            }
                        }
                        Ico {
                            width: 26; height: 26; nom: el.copie ? "check" : (el.index === 0 && p.filtre === "tout" && !p.recherche ? "content_paste" : "content_copy"); taille: 16
                            color: el.copie ? Couleurs.vert : Couleurs.texteSec
                            visible: !(zone.containsMouse || el.choisi) || el.copie
                        }
                    }
                    Timer { id: fin; interval: 1200; onTriggered: el.copie = false }
                    MouseArea {
                        id: zone; anchors.fill: parent; anchors.rightMargin: 120; hoverEnabled: true; z: -1
                        onClicked: { p.choix = el.index; PressePapiers.recopier(el.modelData); el.copie = true; fin.restart() }
                    }
                }
            }
        }
    }
}
