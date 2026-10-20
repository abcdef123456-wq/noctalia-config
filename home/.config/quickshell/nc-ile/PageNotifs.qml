// Page « Notifications » de l'île : l'historique en cartes, comme le centre de notifications de l'iPhone, groupé par
// appli (compteur, groupe repliable d'un clic sur son titre). Filtres Toutes / Non lues / Urgentes, recherche (titre,
// texte, appli). Clic sur une carte : action de l'appli ; croix (au survol) ou clic droit : la retirer ; sur une carte :
// marquer lue, reporter (15 min, 1 h, demain), masquer l'appli (1 h, toujours), réponse rapide si l'appli le permet ;
// « Tout marquer comme lu », « Tout effacer ». Clavier : ↑ ↓ choisir, Entrée ouvrir, Suppr retirer, / chercher, Échap.
import QtQuick
import Quickshell.Widgets

Item {
    id: p
    property string recherche: ""
    property string filtre: "toutes"          // toutes, nonlues, urgentes
    property var replies: ({})               // appli repliée
    property var menus: ({})                 // id -> "reporter" | "masquer" | "repondre"
    property int choix: -1
    readonly property var filtrees: Notifs.liste.filter(x => Notifs.correspond(x, recherche, filtre))
    readonly property var groupes: Notifs.groupes(filtrees)
    // Les cartes visibles, dans l'ordre (groupe replié : seulement la plus récente)
    readonly property var visibles: groupes.reduce((l, g) => l.concat(replies[g.cle] ? [g.notifs[0]] : g.notifs), [])
    function defiler(dy) { return defil.defiler(dy) }
    function replier(cle) { var r = Object.assign({}, replies); if (r[cle]) delete r[cle]; else r[cle] = true; replies = r; choix = -1 }
    function menu(x, nom) { var m = Object.assign({}, menus); if (m[x.id] === nom) delete m[x.id]; else m[x.id] = nom; menus = m }
    onVisibleChanged: { if (visible) { choix = -1; forceActiveFocus() } }
    onVisiblesChanged: if (choix >= visibles.length) choix = visibles.length - 1

    Keys.onPressed: e => {
        if (e.key === Qt.Key_Down && visibles.length) { choix = Math.min(visibles.length - 1, choix + 1); e.accepted = true }
        else if (e.key === Qt.Key_Up && visibles.length) { choix = Math.max(0, choix - 1); e.accepted = true }
        else if ((e.key === Qt.Key_Return || e.key === Qt.Key_Enter) && choix >= 0 && choix < visibles.length) { Notifs.ouvrir(visibles[choix]); Etat.fermer(); e.accepted = true }
        else if (e.key === Qt.Key_Delete && choix >= 0 && choix < visibles.length) { Notifs.fermer(visibles[choix]); e.accepted = true }
        else if (e.key === Qt.Key_Escape && (recherche !== "" || champ.activeFocus)) { recherche = ""; champ.text = ""; p.forceActiveFocus(); e.accepted = true }
        else if (e.key === Qt.Key_Slash || (e.key === Qt.Key_F && (e.modifiers & Qt.ControlModifier))) { champ.forceActiveFocus(); e.accepted = true }
    }

    Item {
        id: tete
        width: parent.width; height: 34
        Texte { anchors.verticalCenter: parent.verticalCenter; leftPadding: 4; text: "Notifications" + (Notifs.nonLues ? "  ·  " + Notifs.nonLues : ""); font.pixelSize: 20; font.weight: Font.Bold }
        Row {
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 12
            Texte {
                objectName: "nc-notifs-tout-lu"
                visible: Notifs.nonLues > 0
                text: Reglages.t("Tout lu", "Read all"); color: zl.containsMouse ? Couleurs.accentClair : Couleurs.accent
                MouseArea { id: zl; anchors.fill: parent; anchors.margins: -6; hoverEnabled: true; onClicked: Notifs.toutLire() }
                Accessible.role: Accessible.Button
                Accessible.name: Reglages.t("Tout marquer comme lu", "Mark all as read")
            }
            Texte {
                objectName: "nc-notifs-tout-effacer"
                visible: Notifs.liste.length > 0
                text: Reglages.t("Tout effacer", "Clear All"); color: ze.containsMouse ? Couleurs.accentClair : Couleurs.accent
                MouseArea { id: ze; anchors.fill: parent; anchors.margins: -6; hoverEnabled: true; onClicked: Notifs.toutEffacer() }
                Accessible.role: Accessible.Button
                Accessible.name: Reglages.t("Tout effacer", "Clear all")
            }
        }
    }

    // Filtres, recherche, applis masquées
    Column {
        id: outils
        anchors.top: tete.bottom; anchors.topMargin: 8
        width: parent.width; spacing: 6
        visible: Notifs.liste.length > 0 || Notifs.applisMasquees.length > 0 || recherche !== ""
        Item {
            width: parent.width; height: 30
            Row {
                id: filtres
                anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; spacing: 4
                Repeater {
                    model: [{ id: "toutes", nom: Reglages.t("Toutes", "All") }, { id: "nonlues", nom: Reglages.t("Non lues", "Unread") }, { id: "urgentes", nom: Reglages.t("Urgentes", "Urgent") }]
                    Rectangle {
                        id: pf
                        required property var modelData
                        objectName: "nc-notifs-filtre-" + modelData.id
                        width: lf.implicitWidth + 18; height: 26; radius: 13
                        color: p.filtre === modelData.id ? Couleurs.accent : (zf.containsMouse ? Couleurs.gris3 : Couleurs.gris2)
                        Texte { id: lf; anchors.centerIn: parent; text: pf.modelData.nom; font.pixelSize: 12; font.weight: Font.DemiBold; color: p.filtre === pf.modelData.id ? Couleurs.surAccent : Couleurs.texte }
                        MouseArea { id: zf; anchors.fill: parent; hoverEnabled: true; onClicked: { p.filtre = pf.modelData.id; p.choix = -1 } }
                        Accessible.role: Accessible.Button
                        Accessible.name: pf.modelData.nom
                    }
                }
            }
            Rectangle {
                anchors.left: filtres.right; anchors.leftMargin: 8; anchors.right: parent.right; height: 30; radius: 15
                color: Couleurs.gris2; border.width: 1; border.color: champ.activeFocus ? Couleurs.accent : "transparent"
                Ico { x: 9; anchors.verticalCenter: parent.verticalCenter; nom: "search"; taille: 15; color: Couleurs.texteSec }
                TextInput {
                    id: champ
                    objectName: "nc-notifs-recherche"
                    anchors.left: parent.left; anchors.leftMargin: 28; anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
                    color: Couleurs.texte; font.pixelSize: 13; clip: true; selectByMouse: true
                    onTextChanged: { p.recherche = text; p.choix = -1 }
                    Keys.onPressed: e => { if (e.key === Qt.Key_Down || e.key === Qt.Key_Up || e.key === Qt.Key_Return || e.key === Qt.Key_Enter || e.key === Qt.Key_Escape) e.accepted = false }
                    Keys.forwardTo: [p]
                    Texte { anchors.fill: parent; visible: !champ.text && !champ.activeFocus; text: Reglages.t("Rechercher", "Search"); secondaire: true; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter }
                }
            }
        }
        Flow {
            width: parent.width; spacing: 6
            visible: Notifs.applisMasquees.length > 0
            Texte { text: Reglages.t("Masquées :", "Hidden:"); secondaire: true; font.pixelSize: 12; height: 26; verticalAlignment: Text.AlignVCenter }
            Repeater {
                model: Notifs.applisMasquees
                Rectangle {
                    id: pm
                    required property string modelData
                    objectName: "nc-notifs-masquee-" + modelData
                    width: lm.implicitWidth + 36; height: 26; radius: 13; color: zm.containsMouse ? Couleurs.gris3 : Couleurs.gris2
                    Texte { id: lm; x: 10; anchors.verticalCenter: parent.verticalCenter; font.pixelSize: 12
                            text: pm.modelData + (Notifs.masques[pm.modelData] < 0 ? "" : " · " + Qt.formatTime(new Date(Notifs.masques[pm.modelData]), "hh:mm")) }
                    Ico { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; nom: "close"; taille: 13; color: Couleurs.texteSec }
                    MouseArea { id: zm; anchors.fill: parent; hoverEnabled: true; onClicked: Notifs.demasquerAppli(pm.modelData) }
                    Accessible.role: Accessible.Button
                    Accessible.name: Reglages.t("Montrer de nouveau ", "Show again ") + pm.modelData
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
            width: p.width; spacing: 8
            readonly property real voulue: 34 + (outils.visible ? outils.height + 8 : 0) + 10 + implicitHeight
            onVoulueChanged: Etat.annoncerHauteur("notifications", voulue)
            Component.onCompleted: Etat.annoncerHauteur("notifications", voulue)

            Item {
                visible: p.visibles.length === 0
                width: parent.width; height: 110
                Column {
                    anchors.centerIn: parent; spacing: 6
                    Ico { anchors.horizontalCenter: parent.horizontalCenter; nom: Notifs.liste.length ? "search_off" : (Notifs.concentration ? "dark_mode" : "notifications"); taille: 30; color: Couleurs.gris4 }
                    Texte {
                        anchors.horizontalCenter: parent.horizontalCenter; secondaire: true
                        text: Notifs.liste.length ? Reglages.t("Rien ne correspond", "Nothing matches")
                            : (Notifs.concentration ? Reglages.t("Concentration activée", "Focus is on") : Reglages.t("Aucune notification", "No Notifications"))
                    }
                }
            }

            Repeater {
                model: p.groupes
                Column {
                    id: groupe
                    required property var modelData
                    readonly property bool replie: !!p.replies[modelData.cle]
                    objectName: "nc-notifs-groupe-" + modelData.cle
                    width: liste.width; spacing: 6
                    // Titre du groupe : appli, compteur, chevron
                    Item {
                        objectName: "nc-notifs-groupe-" + groupe.modelData.cle + "-titre"
                        width: parent.width; height: 26
                        Row {
                            anchors.left: parent.left; anchors.leftMargin: 4; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                            Texte { text: groupe.modelData.nom; font.pixelSize: 12; font.weight: Font.DemiBold; secondaire: true }
                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter; width: lc.implicitWidth + 12; height: 18; radius: 9
                                color: groupe.modelData.nonLues ? Couleurs.accent : Couleurs.gris3
                                Texte { id: lc; anchors.centerIn: parent; text: groupe.modelData.notifs.length; font.pixelSize: 11; font.weight: Font.DemiBold; color: groupe.modelData.nonLues ? Couleurs.surAccent : Couleurs.texteSec }
                            }
                        }
                        Ico { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; nom: groupe.replie ? "expand_more" : "expand_less"; taille: 18; color: Couleurs.texteSec }
                        MouseArea { anchors.fill: parent; onClicked: p.replier(groupe.modelData.cle) }
                        Accessible.role: Accessible.Button
                        Accessible.name: (groupe.replie ? Reglages.t("Déplier ", "Expand ") : Reglages.t("Replier ", "Collapse ")) + groupe.modelData.nom
                    }
                    Repeater {
                        model: groupe.replie ? [groupe.modelData.notifs[0]] : groupe.modelData.notifs
                        Rectangle {
                            id: carte
                            required property var modelData
                            readonly property bool lue: !!Notifs.lus[modelData.id]
                            readonly property bool choisie: p.choix >= 0 && p.visibles[p.choix] === modelData
                            readonly property string menu: p.menus[modelData.id] || ""
                            objectName: "nc-notif-" + modelData.id
                            width: liste.width
                            height: contenu.implicitHeight + 24
                            radius: 18
                            color: zc.containsMouse || choisie ? Couleurs.gris2 : Couleurs.carte
                            border.width: choisie ? 1.5 : 0; border.color: Couleurs.accent
                            Behavior on color { ColorAnimation { duration: 120 } }
                            scale: zc.pressed ? 0.98 : 1
                            Behavior on scale { SpringAnimation { spring: 6; damping: 0.45 } }

                            MouseArea {
                                id: zc
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                onClicked: e => {
                                    if (e.button === Qt.RightButton) { Notifs.fermer(carte.modelData); return }
                                    Notifs.ouvrir(carte.modelData); Etat.fermer()
                                }
                            }

                            ClippingRectangle {
                                id: ic
                                x: 12; y: 12; width: 34; height: 34; radius: 9
                                color: im.status === Image.Ready ? "transparent" : Couleurs.gris2
                                Image { id: im; anchors.fill: parent; source: Notifs.icone(carte.modelData); sourceSize: Qt.size(68, 68); fillMode: Image.PreserveAspectCrop }
                                Ico { anchors.centerIn: parent; nom: "notifications"; taille: 18; visible: im.status !== Image.Ready }
                            }
                            // Point bleu : non lue
                            Rectangle { x: 8; y: 8; width: 9; height: 9; radius: 4.5; color: Couleurs.accent; visible: !carte.lue; border.width: 1.5; border.color: Couleurs.carte }
                            Column {
                                id: contenu
                                anchors.left: ic.right; anchors.leftMargin: 10; anchors.right: parent.right; anchors.rightMargin: 14
                                y: 12; spacing: 1
                                Item {
                                    width: parent.width; height: 16
                                    Texte { text: (groupe.replie && groupe.modelData.notifs.length > 1 ? "+" + (groupe.modelData.notifs.length - 1) + "  " : "") + Notifs.quand(carte.modelData, Etat.maintenant.getTime()); secondaire: true; font.pixelSize: 12; visible: !zc.containsMouse && !carte.choisie }
                                    // Actions au survol : lue, reporter, masquer l'appli, répondre
                                    Row {
                                        anchors.right: parent.right; spacing: 2; visible: zc.containsMouse || carte.choisie || carte.menu !== ""
                                        Repeater {
                                            model: [
                                                { id: "lue", icone: "done_all", aide: Reglages.t("Marquer lue", "Mark as read"), visible: !carte.lue },
                                                { id: "reporter", icone: "snooze", aide: Reglages.t("Reporter", "Snooze"), visible: true },
                                                { id: "masquer", icone: "notifications_off", aide: Reglages.t("Masquer cette application", "Hide this application"), visible: true },
                                                { id: "repondre", icone: "reply", aide: Reglages.t("Répondre", "Reply"), visible: !!carte.modelData.hasInlineReply },
                                                { id: "fermer", icone: "close", aide: Reglages.t("Retirer", "Remove"), visible: true }
                                            ]
                                            Item {
                                                id: ba
                                                required property var modelData
                                                objectName: "nc-notif-" + carte.modelData.id + "-" + modelData.id
                                                width: 22; height: 16; visible: modelData.visible
                                                Ico { anchors.centerIn: parent; nom: ba.modelData.icone; taille: 15; color: carte.menu === ba.modelData.id ? Couleurs.accent : (zba.containsMouse ? Couleurs.texte : Couleurs.texteSec) }
                                                MouseArea { id: zba; anchors.fill: parent; anchors.margins: -3; hoverEnabled: true
                                                            onClicked: ba.modelData.id === "lue" ? Notifs.lire(carte.modelData) : (ba.modelData.id === "fermer" ? Notifs.fermer(carte.modelData) : p.menu(carte.modelData, ba.modelData.id)) }
                                                Accessible.role: Accessible.Button
                                                Accessible.name: ba.modelData.aide
                                            }
                                        }
                                    }
                                }
                                Texte { width: parent.width; text: carte.modelData.summary; font.pixelSize: 14; font.weight: carte.lue ? Font.Normal : Font.DemiBold }
                                Texte {
                                    width: parent.width
                                    text: (carte.modelData.body || "").replace(/<[^>]*>/g, "")
                                    visible: text !== ""
                                    font.pixelSize: 13; color: Couleurs.texteDoux
                                    wrapMode: Text.Wrap; maximumLineCount: 3
                                }
                                Row {
                                    visible: Notifs.boutons(carte.modelData).length > 0
                                    topPadding: 8; spacing: 8
                                    Repeater {
                                        model: Notifs.boutons(carte.modelData)
                                        Rectangle {
                                            required property var modelData
                                            width: lbc.implicitWidth + 24; height: 28; radius: 14
                                            color: zbc.pressed ? Couleurs.gris4 : Couleurs.gris3
                                            Texte { id: lbc; anchors.centerIn: parent; text: parent.modelData.text; font.pixelSize: 13; font.weight: Font.DemiBold }
                                            MouseArea { id: zbc; anchors.fill: parent; onClicked: Notifs.agir(carte.modelData, parent.modelData) }
                                        }
                                    }
                                }
                                // Menus : reporter (15 min, 1 h, demain), masquer (1 h, toujours), répondre (champ)
                                Row {
                                    visible: carte.menu === "reporter" || carte.menu === "masquer"
                                    topPadding: 8; spacing: 6
                                    Repeater {
                                        model: carte.menu === "reporter" ? [{ id: "15m", nom: "15 min" }, { id: "1h", nom: "1 h" }, { id: "demain", nom: Reglages.t("Demain", "Tomorrow") }]
                                             : carte.menu === "masquer" ? [{ id: "1h", nom: "1 h" }, { id: "toujours", nom: Reglages.t("Toujours", "Always") }] : []
                                        Rectangle {
                                            id: choixMenu
                                            required property var modelData
                                            objectName: "nc-notif-" + carte.modelData.id + "-" + carte.menu + "-" + modelData.id
                                            width: lcm.implicitWidth + 22; height: 26; radius: 13
                                            color: zcm.containsMouse ? Couleurs.gris4 : Couleurs.gris3
                                            Texte { id: lcm; anchors.centerIn: parent; text: choixMenu.modelData.nom; font.pixelSize: 12; font.weight: Font.DemiBold }
                                            MouseArea { id: zcm; anchors.fill: parent; hoverEnabled: true
                                                        // Le menu se ferme avant l'action : la carte peut disparaître avec elle (délégué détruit)
                                                        onClicked: { var n = carte.modelData, c = choixMenu.modelData.id, reporter = carte.menu === "reporter"; p.menus = {}; if (reporter) Notifs.reporter(n, c); else Notifs.masquerAppli(n, c) } }
                                            Accessible.role: Accessible.Button
                                            Accessible.name: (carte.menu === "reporter" ? Reglages.t("Reporter : ", "Snooze: ") : Reglages.t("Masquer : ", "Hide: ")) + choixMenu.modelData.nom
                                        }
                                    }
                                }
                                Rectangle {
                                    visible: carte.menu === "repondre"
                                    width: parent.width; height: 32; radius: 16; color: Couleurs.gris3
                                    border.width: 1; border.color: reponse.activeFocus ? Couleurs.accent : "transparent"
                                    onVisibleChanged: if (visible) reponse.forceActiveFocus()
                                    TextInput {
                                        id: reponse
                                        objectName: "nc-notif-" + carte.modelData.id + "-reponse"
                                        anchors.left: parent.left; anchors.leftMargin: 12; anchors.right: envoyer.left; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter
                                        color: Couleurs.texte; font.pixelSize: 13; clip: true; selectByMouse: true
                                        onAccepted: { var n = carte.modelData, t = text; text = ""; p.menus = {}; Notifs.repondre(n, t) }
                                        Keys.onEscapePressed: p.menus = {}
                                        Texte { anchors.fill: parent; visible: !reponse.text && !reponse.activeFocus; text: carte.modelData.inlineReplyPlaceholder || Reglages.t("Réponse rapide", "Quick reply"); secondaire: true; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter }
                                    }
                                    Ico { id: envoyer; anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter; nom: "send"; taille: 16; color: Couleurs.accent
                                          MouseArea { anchors.fill: parent; anchors.margins: -6; onClicked: reponse.accepted() } }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
