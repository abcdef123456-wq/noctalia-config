// Page « Claude Code » de l'île (activité, comme la musique) : la demande en cours, puis chaque session suivie, de Claude
// ou d'Antigravity (projet, état, ce qu'il fait, ses dernières étapes, lignes ajoutées / retirées) ; bouton : y aller.
import QtQuick

Item {
    id: p
    function defiler(dy) { return defil.defiler(dy) }

    Item {
        id: tete
        width: parent.width; height: 34
        Row {
            anchors.verticalCenter: parent.verticalCenter; leftPadding: 4; spacing: 9
            Etincelle { anchors.verticalCenter: parent.verticalCenter; taille: 20; tourne: Agents.travaille
                        agent: Agents.titreAgent || "claude" }
            Texte { anchors.verticalCenter: parent.verticalCenter; text: Agents.titre; font.pixelSize: 20; font.weight: Font.Bold }
        }
        Texte {
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            text: Agents.sessionsVisibles.length > 1 ? Agents.sessionsVisibles.length + " sessions" : ""; secondaire: true
        }
    }

    Defilement {
        id: defil
        anchors.top: tete.bottom; anchors.topMargin: 10; anchors.bottom: parent.bottom
        width: parent.width
        contentHeight: liste.implicitHeight

        Column {
            id: liste
            width: p.width; spacing: 10
            readonly property real voulue: 34 + 10 + implicitHeight
            onVoulueChanged: Etat.annoncerHauteur("claude", voulue)
            Component.onCompleted: Etat.annoncerHauteur("claude", voulue)

            // Demande en cours
            Rectangle {
                visible: Agents.demande !== null
                width: parent.width; height: visible ? dem.implicitHeight : 0; radius: 20; color: Couleurs.carte
                border.width: 1; border.color: Qt.alpha(Agents.couleur, 0.5)
                DemandeClaude { id: dem; anchors.fill: parent }
            }

            Repeater {
                model: Agents.sessionsPage.slice(0, 4)
                Rectangle {
                    id: carte
                    required property var modelData
                    readonly property var s: modelData
                    readonly property bool enCours: s.etat === "travail" || s.etat === "demande" || s.etat === "terminal"
                    width: liste.width; height: col.implicitHeight + 24; radius: 18; color: Couleurs.carte

                    Column {
                        id: col
                        x: 14; y: 12; width: parent.width - 28; spacing: 6
                        // Projet, état, bouton Terminal
                        Item {
                            width: parent.width; height: 24
                            Row {
                                anchors.verticalCenter: parent.verticalCenter; spacing: 8
                                Rectangle {
                                    anchors.verticalCenter: parent.verticalCenter; width: 8; height: 8; radius: 4
                                    color: carte.s.etat === "fini" ? Couleurs.vert : (carte.s.etat === "demande" || carte.s.etat === "terminal"
                                           ? Couleurs.orange : (carte.enCours ? Agents.couleurDe(carte.s) : Couleurs.gris5))
                                }
                                Etincelle { anchors.verticalCenter: parent.verticalCenter; taille: 14; agent: Agents.agent(carte.s)
                                            tourne: carte.s.etat === "travail" }
                                Texte { anchors.verticalCenter: parent.verticalCenter; text: carte.s.projet || Agents.nom(carte.s); textFormat: Text.PlainText; font.pixelSize: 15; font.weight: Font.DemiBold
                                        width: Math.min(implicitWidth, col.width - 232) }
                                Texte { anchors.verticalCenter: parent.verticalCenter; text: Agents.libelle(carte.s); secondaire: true; font.pixelSize: 12 }
                            }
                            Rectangle {
                                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                visible: (carte.s.terminal || 0) > 0
                                width: 30; height: 24; radius: 12; color: zt.containsMouse ? Couleurs.gris4 : Couleurs.gris2
                                Ico { anchors.centerIn: parent; nom: /kitty|term|foot|alacritty|ghostty|konsole|wezterm|tilix|ptyxis/i.test(carte.s.classe || "kitty") ? "terminal" : "code"; taille: 15 }
                                MouseArea { id: zt; anchors.fill: parent; hoverEnabled: true; onClicked: {
                                    Agents.allerTerminal(carte.s.terminal, carte.s.shell)
                                    Etat.fermer()
                                } }
                            }
                        }
                        // Sa question, en entier (notification « Voir », clic sur la pilule) : elle se répond dans son
                        // terminal ; le bouton y mène
                        Rectangle {
                            id: question
                            readonly property var q: carte.s.question || null
                            objectName: "nc-question-" + carte.s.id
                            visible: q !== null && (carte.s.etat === "terminal" || carte.s.etat === "attente" || carte.s.etat === "demande")
                            width: parent.width; height: visible ? colQ.implicitHeight + 20 : 0; radius: 14; color: Couleurs.gris2
                            border.width: 1; border.color: Qt.alpha(Couleurs.orange, 0.45)
                            Column {
                                id: colQ
                                x: 12; y: 10; width: parent.width - 24; spacing: 8
                                Row {
                                    spacing: 6
                                    Ico { anchors.verticalCenter: parent.verticalCenter; nom: "help"; taille: 15; color: Couleurs.orange }
                                    Texte { anchors.verticalCenter: parent.verticalCenter; font.pixelSize: 12; font.weight: Font.DemiBold
                                            color: Couleurs.orange; text: question.q ? question.q.titre || "" : ""
                                            width: Math.min(implicitWidth, colQ.width - 24) }
                                }
                                Texte {
                                    objectName: "nc-question-texte"
                                    width: parent.width; text: question.q ? question.q.texte || "" : ""; font.pixelSize: 13
                                    wrapMode: Text.Wrap; elide: Text.ElideNone; textFormat: Text.PlainText
                                }
                                Rectangle {
                                    visible: (carte.s.terminal || 0) > 0
                                    anchors.right: parent.right
                                    width: rq.implicitWidth + 28; height: 30; radius: 15
                                    color: zq.containsMouse ? Qt.lighter(Agents.couleurDe(carte.s), 1.12) : Agents.couleurDe(carte.s)
                                    scale: zq.pressed ? 0.94 : 1
                                    Behavior on scale { SpringAnimation { spring: 6; damping: 0.4 } }
                                    Row {
                                        id: rq; anchors.centerIn: parent; spacing: 6
                                        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "terminal"; taille: 15; color: "#ffffff" }
                                        Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Aller au terminal", "Go to the terminal")
                                                font.pixelSize: 13; font.weight: Font.DemiBold; color: "#ffffff" }
                                    }
                                    MouseArea { id: zq; anchors.fill: parent; hoverEnabled: true; onClicked: {
                                        Agents.allerTerminal(carte.s.terminal, carte.s.shell)
                                        Etat.fermer()
                                    } }
                                }
                            }
                        }
                        // Dernières étapes (la plus récente en bas, en clair)
                        Repeater {
                            model: (carte.s.etapes || []).slice(carte.enCours ? -4 : -2)
                            Row {
                                required property var modelData
                                required property int index
                                readonly property bool derniere: index === Math.min(carte.enCours ? 4 : 2, (carte.s.etapes || []).length) - 1
                                spacing: 8; opacity: derniere ? 1 : 0.55
                                Ico { anchors.verticalCenter: parent.verticalCenter; nom: parent.modelData.icone || "build"; taille: 15
                                      color: parent.derniere && carte.enCours ? Agents.couleurDe(carte.s) : Couleurs.texteSec }
                                Texte { anchors.verticalCenter: parent.verticalCenter; text: parent.modelData.texte; textFormat: Text.PlainText; font.pixelSize: 13
                                        width: Math.min(implicitWidth, col.width - 90) }
                                Texte { anchors.verticalCenter: parent.verticalCenter; visible: (parent.modelData.diff || "") !== ""
                                        text: parent.modelData.diff || ""; font.pixelSize: 12; color: Couleurs.vert }
                            }
                        }
                        Row {
                            visible: (carte.s.ajouts || 0) + (carte.s.retraits || 0) > 0
                            spacing: 8
                            Texte { text: "+" + (carte.s.ajouts || 0); color: Couleurs.vert; font.pixelSize: 12; font.weight: Font.DemiBold }
                            Texte { text: "−" + (carte.s.retraits || 0); color: Couleurs.rouge; font.pixelSize: 12; font.weight: Font.DemiBold }
                            Texte { text: Reglages.t("lignes", "lines"); secondaire: true; font.pixelSize: 12 }
                        }
                        // Pas possible pour ce terminal (kitty ouvert avant la mise à jour, ou autre terminal) : on dit pourquoi
                        Row {
                            visible: carte.s.ecrire !== true && (carte.s.terminal || 0) > 0
                                     && /kitty|term|foot|alacritty|ghostty|konsole|wezterm|tilix|ptyxis/i.test(carte.s.classe || "")
                            spacing: 6
                            Ico { anchors.verticalCenter: parent.verticalCenter; nom: "edit_off"; taille: 14; color: Couleurs.texteSec }
                            Texte { anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.pixelSize: 12
                                    width: Math.min(implicitWidth, col.width - 24); elide: Text.ElideRight
                                    text: Reglages.t("Pour lui écrire d'ici : lance-le dans un nouveau terminal", "To write to it from here, start it in a new terminal") }
                        }
                        // Lui écrire (agent lancé dans kitty) : Entrée envoie, comme dans son terminal
                        Rectangle {
                            visible: carte.s.ecrire === true
                            width: parent.width; height: 36; radius: 18; color: Couleurs.gris2
                            border.width: msg.activeFocus ? 1.5 : 0; border.color: Agents.couleurDe(carte.s)
                            TextInput {
                                id: msg
                                anchors.left: parent.left; anchors.leftMargin: 14; anchors.right: envoi.left; anchors.rightMargin: 6
                                anchors.verticalCenter: parent.verticalCenter
                                color: Couleurs.texte; selectionColor: Agents.couleurDe(carte.s); font.pixelSize: 13; clip: true
                                onAccepted: { Agents.ecrire(carte.s.id, text); text = "" }
                                Keys.onEscapePressed: { text = ""; focus = false }
                                Texte { visible: msg.text === ""; anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.pixelSize: 13
                                        text: (carte.enCours ? Reglages.t("Ajouter une consigne pour ", "Add an instruction for ") : Reglages.t("Répondre à ", "Reply to ")) + Agents.nom(carte.s) + "…" }
                            }
                            Rectangle {
                                id: envoi
                                anchors.right: parent.right; anchors.rightMargin: 4; anchors.verticalCenter: parent.verticalCenter
                                width: 28; height: 28; radius: 14
                                color: msg.text !== "" ? Agents.couleurDe(carte.s) : Couleurs.gris4
                                Ico { anchors.centerIn: parent; nom: "arrow_upward"; taille: 16; color: "#ffffff" }
                                MouseArea { anchors.fill: parent; onClicked: { Agents.ecrire(carte.s.id, msg.text); msg.text = "" } }
                            }
                        }
                    }
                }
            }
        }
    }
}
