import QtQuick
import QtQuick.Controls

CloudCarte {
    id: fichiers
    objectName: "nc-cloud-mes-fichiers"
    required property Item fantome
    required property var taille
    required property string aRenommer
    signal finirGlisser()
    property string creation: ""

    function ouvrirCreation(type) {
        if (creation === type) { creation = ""; return }
        nomNouveau.text = ""
        creation = type
        nomNouveau.forceActiveFocus()
    }
    Connections {
        target: CloudEtat
        function onDossierChanged() { fichiers.creation = ""; nomNouveau.text = ""; liste.contentY = 0 }
        function onDeplacementChanged() { if (CloudEtat.deplacement) fichiers.creation = "" }
    }
    Flow {
        id: enteteFichiers
        width: parent.width; spacing: 6
        Texte {
            width: Math.max(120, parent.width - commandes.implicitWidth - parent.spacing)
            height: 30; verticalAlignment: Text.AlignVCenter
            text: Reglages.t("Mes fichiers", "My files"); font.pixelSize: 17; font.weight: Font.DemiBold
        }
        Row {
            id: commandes
            spacing: 6
            CloudBouton {
                objectName: "nc-cloud-nouveau-fichier"; icone: "note_add"; principal: fichiers.creation === "fichier"
                texte: Reglages.t("Fichier", "File"); enabled: !CloudEtat.occupe && !CloudEtat.deplacement
                onClic: fichiers.ouvrirCreation("fichier")
            }
            CloudBouton {
                objectName: "nc-cloud-nouveau-dossier"; icone: "create_new_folder"; principal: fichiers.creation === "dossier"
                texte: Reglages.t("Dossier", "Folder"); enabled: !CloudEtat.occupe && !CloudEtat.deplacement
                onClic: fichiers.ouvrirCreation("dossier")
            }
        }
    }
    Rectangle {
        width: parent.width; height: nav.implicitHeight + 8
        color: Qt.alpha(Couleurs.texte, 0.05); radius: Couleurs.rayon(12, width, height)
        Flow {
            id: nav
            x: 4; y: 4; width: parent.width - 8; spacing: 6
            CloudBouton {
                objectName: "nc-cloud-parent"
                enabled: !CloudEtat.occupe && CloudEtat.chemin.length > 1
                icone: "arrow_upward"; width: 36
                border.width: cibleParent.containsDrag ? 2 : 0; border.color: Couleurs.accent
                onClic: CloudEtat.remonter(CloudEtat.chemin.length - 2)
                Accessible.name: Reglages.t("Dossier parent", "Parent folder")
                DropArea {
                    id: cibleParent
                    objectName: "nc-cloud-cible-parent"
                    anchors.fill: parent
                    keys: ["nc-cloud-entree"]
                    readonly property string vers: CloudEtat.chemin.length > 1 ? CloudEtat.chemin[CloudEtat.chemin.length - 2].id : ""
                    onEntered: drag => { if (!CloudEtat.deposable(fichiers.fantome.entree, vers)) drag.accepted = false }
                    onDropped: drop => { if (CloudEtat.deposable(fichiers.fantome.entree, vers)) { drop.accept(Qt.MoveAction); CloudEtat.deplacerVers(fichiers.fantome.entree, vers) } }
                }
            }
            Repeater {
                model: CloudEtat.chemin
                CloudBouton {
                    required property var modelData
                    required property int index
                    objectName: "nc-cloud-chemin-" + index
                    width: Math.min(implicitWidth, nav.width)
                    texte: index > 0 ? "› " + modelData.nom : "/"
                    Accessible.name: modelData.nom
                    principal: index === CloudEtat.chemin.length - 1
                    onClic: CloudEtat.remonter(index)
                }
            }
        }
    }
    Flow {
        visible: fichiers.creation !== ""
        width: parent.width; spacing: 6
        Rectangle {
            width: Math.min(220, parent.width - 6); height: 30
            radius: Couleurs.rayon(15, width, height); color: Couleurs.gris2
            border.width: 1; border.color: nomNouveau.activeFocus ? Couleurs.accent : "transparent"
            TextInput {
                id: nomNouveau
                objectName: "nc-cloud-nom-dossier"
                anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12
                verticalAlignment: TextInput.AlignVCenter; clip: true; selectByMouse: true; maximumLength: 120
                color: Couleurs.texte; selectionColor: Couleurs.accent; font.pixelSize: 12
                Accessible.name: fichiers.creation === "dossier" ? Reglages.t("Nom du dossier", "Folder name") : Reglages.t("Nom du fichier", "File name")
                onAccepted: if (creer.enabled) creer.clic()
                Keys.onEscapePressed: { fichiers.creation = ""; text = "" }
                Texte { anchors.verticalCenter: parent.verticalCenter; visible: nomNouveau.text === "" && !nomNouveau.activeFocus
                        text: nomNouveau.Accessible.name; secondaire: true; font.pixelSize: 12 }
            }
        }
        CloudBouton {
            id: creer
            objectName: fichiers.creation === "fichier" ? "nc-cloud-creer-fichier" : "nc-cloud-creer"
            texte: Reglages.t("Créer", "Create"); principal: true
            enabled: fichiers.creation !== "" && nomNouveau.text.trim() !== "" && !CloudEtat.occupe
            onClic: if (enabled) {
                if (fichiers.creation === "fichier") CloudEtat.creerFichier(nomNouveau.text)
                else CloudEtat.creerDossier(nomNouveau.text)
                nomNouveau.text = ""; fichiers.creation = ""
            }
        }
    }
    Column {
        objectName: "nc-cloud-vide"
        visible: CloudEtat.lu && CloudEtat.entrees.length === 0
        width: parent.width; spacing: 6
        Ico { anchors.horizontalCenter: parent.horizontalCenter; nom: "folder_open"; taille: 32; color: Couleurs.texteSec }
        Texte { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: Reglages.t("Dossier vide.", "Empty folder."); secondaire: true }
    }
    Flickable {
        id: liste
        width: parent.width; height: Math.min(contentHeight, 300)
        visible: CloudEtat.entrees.length > 0
        contentWidth: width; contentHeight: lignes.implicitHeight
        clip: true; boundsBehavior: Flickable.StopAtBounds; flickableDirection: Flickable.VerticalFlick
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        Column {
            id: lignes
            width: parent.width - (liste.contentHeight > liste.height ? 12 : 0); spacing: 4
            Repeater {
                model: CloudEtat.entrees
                Rectangle {
                    id: ligne
                    required property var modelData
                    readonly property bool fichier: modelData.kind === "file"
                    readonly property bool choisie: CloudEtat.selection === modelData.id && !CloudEtat.deplacement
                    objectName: "nc-cloud-entree-" + modelData.id
                    width: parent.width; height: 48; radius: Couleurs.rayon(12, width, height)
                    color: choisie || activeFocus ? Qt.alpha(Couleurs.accent, 0.18)
                           : zoneLigne.containsMouse ? Qt.alpha(Couleurs.accent, 0.10) : "transparent"
                    border.width: cibleLigne.containsDrag ? 2 : (choisie ? 1 : 0); border.color: Couleurs.accent
                    activeFocusOnTab: true
                    onActiveFocusChanged: if (activeFocus) {
                        const haut = mapToItem(liste.contentItem, 0, 0).y
                        const bas = haut + height
                        if (haut < liste.contentY || bas > liste.contentY + liste.height) {
                            liste.cancelFlick()
                            liste.contentY = haut < liste.contentY ? haut : bas - liste.height
                        }
                    }
                    Accessible.role: Accessible.ListItem
                    Accessible.name: modelData.name
                    Accessible.selected: choisie
                    Accessible.onPressAction: CloudEtat.choisir(modelData)
                    Keys.onSpacePressed: CloudEtat.choisir(modelData)
                    Keys.onReturnPressed: CloudEtat.ouvrirEntree(modelData)
                    // Glisser (au-delà du seuil de Qt) : l'aperçu suit le pointeur ; lâché sur un dossier ou sur ↑, on déplace
                    MouseArea { id: zoneLigne; objectName: "nc-cloud-zone-" + ligne.modelData.id
                                anchors.fill: parent; hoverEnabled: true; z: -1; cursorShape: Qt.PointingHandCursor
                                readonly property bool glissable: CloudEtat.peutDeplacer && !!ligne.modelData.revision
                                                                  && fichiers.aRenommer !== ligne.modelData.id && !CloudEtat.deplacement
                                drag.target: glissable ? fichiers.fantome : null
                                preventStealing: glissable          // le défilement par la molette reste
                                // La MouseArea retient la place de sa cible avant onPressed : l'aperçu est recalé sous le pointeur
                                // à chaque mouvement (après le sien)
                                function placer(m) { var p = zoneLigne.mapToItem(fichiers.fantome.parent, m.x, m.y); fichiers.fantome.x = p.x - 16; fichiers.fantome.y = p.y - 17 }
                                onPressed: m => placer(m)
                                onPositionChanged: m => { if (drag.active) placer(m) }
                                // Qt émet released AVANT de couper le glisser : seul un vrai relâchement dépose. Une saisie
                                // perdue (canceled) coupe le glisser sans relâchement : il est annulé, rien ne bouge
                                onReleased: if (drag.active && fichiers.fantome.Drag.active) { fichiers.fantome.Drag.drop(); fichiers.finirGlisser() }
                                drag.onActiveChanged: {
                                    if (drag.active) { fichiers.fantome.entree = ligne.modelData; fichiers.fantome.Drag.active = true; return }
                                    fichiers.finirGlisser()
                                }
                                onClicked: CloudEtat.choisir(ligne.modelData)
                                onDoubleClicked: CloudEtat.ouvrirEntree(ligne.modelData) }
                    DropArea {
                        id: cibleLigne
                        objectName: "nc-cloud-cible-" + ligne.modelData.id
                        anchors.fill: parent
                        keys: ["nc-cloud-entree"]
                        enabled: !ligne.fichier
                        onEntered: drag => { if (!CloudEtat.deposable(fichiers.fantome.entree, ligne.modelData.id)) drag.accepted = false }
                        onDropped: drop => { if (CloudEtat.deposable(fichiers.fantome.entree, ligne.modelData.id)) {
                            drop.accept(Qt.MoveAction); CloudEtat.deplacerVers(fichiers.fantome.entree, ligne.modelData.id) } }
                    }
                    Rectangle {
                        x: 6; anchors.verticalCenter: parent.verticalCenter
                        width: 34; height: 34; radius: Couleurs.rayon(10, width, height)
                        color: Qt.alpha(ligne.fichier ? Couleurs.texte : Couleurs.accent, 0.08)
                        Ico { anchors.centerIn: parent; taille: 20
                              nom: ligne.fichier ? "description" : "folder"; color: ligne.fichier ? Couleurs.texteSec : Couleurs.accent }
                    }
                    Column {
                        x: 50; width: parent.width - x - 26; anchors.verticalCenter: parent.verticalCenter; spacing: 3
                        Texte { objectName: "nc-cloud-nom-" + ligne.modelData.id; width: parent.width
                                text: ligne.modelData.name; elide: Text.ElideMiddle; font.weight: Font.DemiBold }
                        Texte { text: ligne.fichier ? fichiers.taille(ligne.modelData.size) : Reglages.t("Ouvrir le dossier", "Open folder")
                                secondaire: true; font.pixelSize: 11 }
                    }
                    Ico { visible: !ligne.fichier; anchors.right: parent.right; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter
                          nom: "chevron_right"; taille: 20; color: Couleurs.texteSec }
                }
            }
        }
    }
    CloudBouton {
        objectName: "nc-cloud-suite"
        visible: CloudEtat.suite !== ""
        texte: Reglages.t("Afficher la suite", "Show more"); enabled: !CloudEtat.occupe
        onClic: CloudEtat.lister(true)
    }
    Texte {
        visible: CloudEtat.peutDeplacer && CloudEtat.entrees.length > 0
        width: parent.width; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 11
        text: Reglages.t("Glisse un fichier ou un dossier vers un dossier ou la flèche ↑ pour le déplacer.",
                         "Drag a file or folder onto a folder or the ↑ arrow to move it.")
    }
}
