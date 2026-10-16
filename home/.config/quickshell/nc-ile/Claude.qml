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
                        agent: Agents.titre === "Antigravity" ? "antigravity" : "claude" }
            Texte { anchors.verticalCenter: parent.verticalCenter; text: Agents.titre; font.pixelSize: 20; font.weight: Font.Bold }
        }
        Texte {
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            text: Agents.sessions.length > 1 ? Agents.sessions.length + " sessions" : ""; secondaire: true
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
                model: Agents.sessions.slice(0, 4)
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
                                Texte { anchors.verticalCenter: parent.verticalCenter; text: carte.s.projet || Agents.nom(carte.s); font.pixelSize: 15; font.weight: Font.DemiBold
                                        width: Math.min(implicitWidth, col.width - 232) }
                                Texte { anchors.verticalCenter: parent.verticalCenter; text: Agents.libelle(carte.s); secondaire: true; font.pixelSize: 12 }
                            }
                            Rectangle {
                                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                visible: (carte.s.terminal || 0) > 0
                                width: 30; height: 24; radius: 12; color: zt.containsMouse ? Couleurs.gris4 : Couleurs.gris2
                                Ico { anchors.centerIn: parent; nom: Agents.agent(carte.s) === "antigravity" ? "code" : "terminal"; taille: 15 }
                                MouseArea { id: zt; anchors.fill: parent; hoverEnabled: true; onClicked: { Agents.allerTerminal(carte.s.terminal); Etat.fermer() } }
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
                                Texte { anchors.verticalCenter: parent.verticalCenter; text: parent.modelData.texte; font.pixelSize: 13
                                        width: Math.min(implicitWidth, col.width - 90) }
                                Texte { anchors.verticalCenter: parent.verticalCenter; visible: (parent.modelData.diff || "") !== ""
                                        text: parent.modelData.diff || ""; font.pixelSize: 12; color: Couleurs.vert }
                            }
                        }
                        // Fin : son dernier message ; total des lignes modifiées
                        Texte {
                            visible: carte.s.etat === "fini" && (carte.s.message || "") !== ""
                            width: parent.width; text: carte.s.message || ""; color: Couleurs.texteDoux; font.pixelSize: 12
                            wrapMode: Text.Wrap; maximumLineCount: 2
                        }
                        Row {
                            visible: (carte.s.ajouts || 0) + (carte.s.retraits || 0) > 0
                            spacing: 8
                            Texte { text: "+" + (carte.s.ajouts || 0); color: Couleurs.vert; font.pixelSize: 12; font.weight: Font.DemiBold }
                            Texte { text: "−" + (carte.s.retraits || 0); color: Couleurs.rouge; font.pixelSize: 12; font.weight: Font.DemiBold }
                            Texte { text: "lignes"; secondaire: true; font.pixelSize: 12 }
                        }
                    }
                }
            }
        }
    }
}
