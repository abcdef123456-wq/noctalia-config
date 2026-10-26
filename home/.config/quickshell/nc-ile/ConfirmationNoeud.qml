// Carte de confirmation de JARVIS qui pilote ce PC (Noeud.qml, nc-noeud) : l'île fermée s'étire en carte, comme pour le
// mode graphique (ConfirmationGpu.qml). « JARVIS (depuis <serveur>) veut : <ce qui sera fait exactement> », le texte
// concerné en police de terminal (commande entière, aperçu du fichier, texte à copier), coupé à 400 caractères avec
// « Voir tout », puis [Refuser] et [Autoriser] ; rien n'est fait avant Autoriser. Refus tout seul à la fin du
// compte à rebours, qui part du délai de cette action (12 s pour un fichier, une capture ou le presse-papiers, 17 s
// pour une action relayée, jusqu'à 25 s pour une commande : toujours 3 s avant que le serveur abandonne). Autoriser
// au-delà : « Trop tard : JARVIS a déjà abandonné », rien n'est fait.
// Fichier à part (pas un composant interne d'Ile.qml) : le rechargement à chaud de Quickshell ne connaît pas les
// nouveaux composants internes d'un fichier déjà chargé.
import QtQuick

Item {
    id: c
    implicitHeight: col.y + col.implicitHeight + 16
    // Gardée dessinée pendant que l'île se referme
    property var vue: null
    readonly property var dem: Noeud.demande
    onDemChanged: if (dem) vue = dem
    Component.onCompleted: vue = dem
    // Le texte montré : en entier (« Voir tout »), ou coupé à « court » caractères avec « … »
    readonly property string texte: vue ? String(vue.texte || "") : ""
    readonly property int court: vue && vue.court > 0 ? vue.court : 400
    // Nombre de lignes du texte d'origine (nc-noeud en compte avant de regrouper les lignes vides)
    readonly property int lignes: vue && vue.lignes > 0 ? vue.lignes : (texte === "" ? 0 : texte.split("\n").length)
    // « Voir tout » dès que le texte dépasse la zone (hauteur mesurée sur le texte entier), pas seulement au-delà de « court »
    readonly property bool debordeCourt: mesure.implicitHeight > 150
    readonly property bool coupe: texte.length > court || debordeCourt
    readonly property string texteMontre: texte.length > court && !Noeud.toutVoir ? texte.slice(0, court) + "…" : texte
    // Mesure du texte entier (jamais affichée)
    Text {
        id: mesure
        visible: false; width: c.width - 56
        text: c.texte; textFormat: Text.PlainText; wrapMode: Text.WrapAnywhere
        font.family: "monospace"; font.pixelSize: 12
    }

    // En-tête : icône, « JARVIS · serveur », compte à rebours
    Row {
        x: 18; y: 14; spacing: 8
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "smart_toy"; taille: 16; color: Couleurs.texteSec }
        Texte {
            anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.pixelSize: 12
            text: "JARVIS · " + (c.vue ? c.vue.serveur : "")
            width: Math.min(implicitWidth, c.width - 120)
        }
    }
    Texte {
        objectName: "nc-noeud-reste"
        anchors.right: parent.right; anchors.rightMargin: 18; y: 14
        secondaire: true; font.pixelSize: 12
        text: Noeud.reste > 0 && !Noeud.tropTard ? Noeud.reste + " s" : ""
    }
    Column {
        id: col
        x: 18; y: 40; width: c.width - 36; spacing: 8
        Texte {
            objectName: "nc-noeud-titre"
            width: parent.width; font.pixelSize: 15; font.weight: Font.DemiBold
            textFormat: Text.PlainText; wrapMode: Text.Wrap; maximumLineCount: 4; elide: Text.ElideNone
            text: c.vue ? Reglages.t("JARVIS (depuis " + c.vue.serveur + ") veut : ", "JARVIS (from " + c.vue.serveur + ") wants to: ")
                          + c.vue.resume : ""
        }
        // Ce qui sera exécuté ou écrit, tel quel (jamais interprété : texte brut)
        Rectangle {
            visible: c.texte !== ""
            width: parent.width; height: defile.height + 14; radius: 10; color: Couleurs.gris2
            Flickable {
                id: defile
                x: 10; y: 7; width: parent.width - 20
                height: Math.min(det.implicitHeight, Noeud.toutVoir ? 260 : 150)
                contentHeight: det.implicitHeight; contentWidth: width
                clip: true; boundsBehavior: Flickable.StopAtBounds
                interactive: contentHeight > height
                Text {
                    id: det
                    objectName: "nc-noeud-detail"
                    width: defile.width
                    text: c.texteMontre
                    textFormat: Text.PlainText; wrapMode: Text.WrapAnywhere
                    font.family: "monospace"; font.pixelSize: 12; color: Couleurs.texteDoux
                }
            }
            // Barre de défilement toujours visible dès que le texte dépasse la zone
            Rectangle {
                objectName: "nc-noeud-barre"
                visible: defile.contentHeight > defile.height + 1
                x: parent.width - 6; width: 3; radius: 1.5; color: Couleurs.texteSec
                y: 7 + defile.visibleArea.yPosition * defile.height
                height: Math.max(12, defile.visibleArea.heightRatio * defile.height)
            }
        }
        // Autorisé après l'échéance : rien n'est fait, la carte le dit avant de se fermer
        Texte {
            objectName: "nc-noeud-trop-tard"
            visible: Noeud.tropTard
            width: parent.width; height: 34; verticalAlignment: Text.AlignVCenter
            font.pixelSize: 13; font.weight: Font.DemiBold
            text: Reglages.t("Trop tard : JARVIS a déjà abandonné.", "Too late: JARVIS already gave up.")
        }
        // Voir tout · Refuser · Autoriser (le bouton principal en clair, à droite comme sur iPhone)
        Item {
            objectName: "nc-noeud-boutons"
            visible: !Noeud.tropTard
            width: parent.width; height: 34
            Rectangle {
                objectName: "nc-noeud-voir-tout"
                visible: c.coupe
                anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                width: lv.implicitWidth + 24; height: 28; radius: 14
                color: zv.containsMouse ? Couleurs.gris4 : "transparent"
                Texte {
                    id: lv; anchors.centerIn: parent; font.pixelSize: 12; color: Couleurs.texteSec
                    text: (c.lignes > 1 ? c.lignes + Reglages.t(" lignes · ", " lines · ") : "")
                          + (Noeud.toutVoir ? Reglages.t("Voir moins", "Show less") : Reglages.t("Voir tout", "Show all"))
                }
                MouseArea { id: zv; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: Noeud.toutVoir = !Noeud.toutVoir }
                Accessible.role: Accessible.Button
                Accessible.name: lv.text
            }
            Texte {
                objectName: "nc-noeud-lignes"
                visible: !c.coupe && c.lignes > 1
                anchors.left: parent.left; anchors.leftMargin: 4; anchors.verticalCenter: parent.verticalCenter
                secondaire: true; font.pixelSize: 12
                text: c.lignes + Reglages.t(" lignes", " lines")
            }
            Row {
                anchors.right: parent.right; spacing: 8
                Repeater {
                    model: [{ nom: "nc-noeud-refuser", texte: Reglages.t("Refuser", "Deny"), principal: false },
                            { nom: "nc-noeud-autoriser", texte: Reglages.t("Autoriser", "Allow"), principal: true }]
                    Rectangle {
                        id: b
                        required property var modelData
                        objectName: modelData.nom
                        width: Math.max(96, lb.implicitWidth + 30); height: 34; radius: 17
                        color: modelData.principal ? (zb.containsMouse ? Couleurs.texteDoux : Couleurs.texte)
                                                   : (zb.containsMouse ? Couleurs.gris3 : Couleurs.gris2)
                        scale: zb.pressed ? 0.95 : 1
                        Behavior on scale { enabled: !Reglages.sobre; SpringAnimation { spring: 6; damping: 0.45 } }
                        Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
                        Texte {
                            id: lb; anchors.centerIn: parent; text: b.modelData.texte
                            font.pixelSize: 13; font.weight: Font.DemiBold
                            color: b.modelData.principal ? Couleurs.fond : Couleurs.texte
                        }
                        MouseArea {
                            id: zb; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: b.modelData.principal ? Noeud.autoriser() : Noeud.refuser()
                        }
                        Accessible.role: Accessible.Button
                        Accessible.name: modelData.texte
                    }
                }
            }
        }
    }
}
