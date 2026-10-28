// Réglages d'UN mode Concentration (page PageConcentration.qml) : Ne pas déranger, profil d'énergie (ceux de nc-energie),
// fond du jour ou de la nuit, IA sur les notifications, nom et suppression. Chaque choix passe par Modes.regler (nc-modes valide
// tout). La liste des profils d'énergie est lue une fois, à l'ouverture de l'éditeur (nc-energie liste --json) ; sans profil ou
// sans nc-energie, la ligne n'existe pas. Le fond n'est proposé que si FONDS_JOUR_NUIT est allumé, l'IA que si elle est permise.
import QtQuick
import Quickshell.Io

Column {
    id: e
    required property var mode
    property var profils: []
    readonly property bool libre: !Modes.occupe
    spacing: 8

    Component.onCompleted: if (!lecteur.running) lecteur.running = true
    Process {
        id: lecteur
        command: [Etat.bin + "nc-energie", "liste", "--json"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var r = JSON.parse(text)
                    if (r && Array.isArray(r.profils)) e.profils = r.profils.filter(p => p.valide === true && /^[a-z0-9-]{1,40}$/.test(String(p.id)))
                } catch (x) { }
            }
        }
    }

    ChoixMode {
        width: parent.width; actif: e.libre
        titre: Reglages.t("Ne pas déranger", "Do Not Disturb"); valeur: e.mode.dnd
        options: [{ valeur: "garder", texte: Reglages.t("Inchangé", "Unchanged") }, { valeur: "oui", texte: Reglages.t("Activé", "On") },
                  { valeur: "non", texte: Reglages.t("Désactivé", "Off") }]
        onChoisi: v => Modes.regler(e.mode.id, "dnd", v)
    }
    ChoixMode {
        width: parent.width; actif: e.libre; visible: e.profils.length > 0
        titre: Reglages.t("Profil d'énergie", "Power profile"); valeur: e.mode.energie
        options: [{ valeur: "", texte: Reglages.t("Inchangé", "Unchanged") }].concat(e.profils.map(p => ({ valeur: String(p.id), texte: String(p.nom) })))
        onChoisi: v => Modes.regler(e.mode.id, "energie", v)
    }
    ChoixMode {
        width: parent.width; actif: e.libre; visible: Modes.fondActif
        titre: Reglages.t("Fond d'écran", "Wallpaper"); valeur: e.mode.fond
        options: [{ valeur: "garder", texte: Reglages.t("Inchangé", "Unchanged") }, { valeur: "jour", texte: Reglages.t("Jour", "Day") },
                  { valeur: "nuit", texte: Reglages.t("Nuit", "Night") }]
        onChoisi: v => Modes.regler(e.mode.id, "fond", v)
    }
    ChoixMode {
        width: parent.width; actif: e.libre; visible: !Modes.iaCoupee
        titre: Reglages.t("IA sur les notifications", "AI on notifications"); valeur: e.mode.notifs_ia
        options: [{ valeur: "garder", texte: Reglages.t("Inchangé", "Unchanged") }, { valeur: "oui", texte: Reglages.t("En marche", "On") },
                  { valeur: "non", texte: Reglages.t("Coupée", "Off") }]
        onChoisi: v => Modes.regler(e.mode.id, "notifs_ia", v)
    }
    Rectangle {
        width: parent.width; height: 34; radius: 17; color: Couleurs.gris2
        border.width: 1; border.color: nom.activeFocus ? Couleurs.accent : "transparent"
        TextInput {
            id: nom
            objectName: "nomMode"
            anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 14
            verticalAlignment: TextInput.AlignVCenter
            clip: true; maximumLength: 24; selectByMouse: true
            color: Couleurs.texte; selectionColor: Couleurs.accent; font.pixelSize: 13
            text: e.mode.nom
            onEditingFinished: if (text.trim() !== "" && text.trim() !== e.mode.nom) Modes.renommer(e.mode.id, text.trim())
        }
    }
    Flow {
        width: parent.width; spacing: 8
        BoutonEnergie {
            objectName: "supprimerMode"
            texte: Reglages.t("Supprimer", "Delete"); icone: "delete"
            actif: e.libre && Modes.actif !== e.mode.id
            onClic: Modes.supprimer(e.mode.id)
        }
        Texte {
            visible: Modes.actif === e.mode.id; secondaire: true; font.pixelSize: 11; anchors.verticalCenter: undefined
            text: Reglages.t("Désactive le mode pour le supprimer.", "Turn the mode off to delete it.")
        }
    }
}
