import QtQuick

Item {
    id: reglages
    property bool modelesOuverts: false
    function defiler(dy) {
        defile.contentY=Math.max(0,Math.min(Math.max(0,defile.contentHeight-defile.height),defile.contentY+dy))
        return true
    }
    Flickable {
        id:defile
        anchors.top:parent.top; anchors.bottom:message.top; anchors.bottomMargin:8
        width:parent.width; clip:true; contentHeight:contenu.implicitHeight
        boundsBehavior:Flickable.StopAtBounds
        Column {
            id: contenu
            width: parent.width; spacing: 10
            Texte { text: Reglages.t("Réglages rapides", "Quick settings"); font.weight: Font.Bold }
            Texte { width:parent.width; text:Reglages.t("Communs à l’île, Telegram et Discord.", "Shared with Telegram and Discord."); secondaire:true; wrapMode:Text.Wrap }
            Flow {
                width:parent.width; spacing:6
                Repeater {
                    model: AssistantEtat.moteurs
                    JarvisBouton {
                        required property var modelData
                        texte:modelData.name; primaire:AssistantEtat.moteur===modelData.id
                        enabled:AssistantEtat.reglagesDisponibles && !AssistantEtat.enCours && !AssistantEtat.reglagesEnCours && modelData.installed
                        onClic:AssistantEtat.choisirMoteur(modelData.id)
                    }
                }
            }
            Texte { width:parent.width; visible:AssistantEtat.reglagesDisponibles; text:Reglages.t("Grisé : CLI absent sur l’hôte JARVIS.", "Disabled: CLI absent on the JARVIS host."); secondaire:true; wrapMode:Text.Wrap; font.pixelSize:11 }
            JarvisChamp {
                width:parent.width; titre:Reglages.t("Modèle (vide : défaut du moteur)", "Model (empty: engine default)")
                texte:AssistantEtat.modele; enabled:AssistantEtat.reglagesDisponibles && !AssistantEtat.reglagesEnCours && !AssistantEtat.enCours
                onChange: (valeur) => { AssistantEtat.modele = valeur; AssistantEtat.effort = "" }
            }
            JarvisBouton { texte:Reglages.t("Choisir un modèle…", "Choose a model…"); visible:AssistantEtat.modeles.length>0; onClic:reglages.modelesOuverts=!reglages.modelesOuverts }
            Flow {
                visible:reglages.modelesOuverts; height:visible?implicitHeight:0
                width:parent.width; spacing:6
                Repeater {
                    model:AssistantEtat.modeles.slice(0,12)
                    JarvisBouton {
                        required property var modelData
                        texte:modelData.name || modelData.id; primaire:AssistantEtat.modele===modelData.id
                        enabled:!AssistantEtat.enCours && !AssistantEtat.reglagesEnCours
                        onClic:{AssistantEtat.modele=modelData.id;AssistantEtat.effort=""}
                    }
                }
            }
            Texte { text:Reglages.t("Réflexion", "Reasoning"); font.weight:Font.DemiBold }
            Flow {
                width:parent.width; spacing:6
                Repeater {
                    model:[""].concat(AssistantEtat.efforts)
                    JarvisBouton {
                        required property string modelData
                        texte:modelData || Reglages.t("Défaut", "Default"); primaire:AssistantEtat.effort===modelData
                        enabled:AssistantEtat.reglagesDisponibles && !AssistantEtat.reglagesEnCours && !AssistantEtat.enCours
                        onClic:AssistantEtat.effort=modelData
                    }
                }
            }
            Texte { width:parent.width; visible:AssistantEtat.moteur==="opencode"; text:Reglages.t("OpenCode : saisis provider/modèle#variante pour une réflexion spécifique.", "OpenCode: enter provider/model#variant for specific reasoning."); secondaire:true; wrapMode:Text.Wrap }
        }
    }
    Texte {
        id:message
        anchors.bottom:actions.top; anchors.bottomMargin:6; width:parent.width
        height:text?48:0; maximumLineCount:3; elide:Text.ElideRight
        text:AssistantEtat.reglagesEnCours ? Reglages.t("Chargement…", "Loading…") : AssistantEtat.erreurReglages
        wrapMode:Text.Wrap; color:AssistantEtat.erreurReglages?Couleurs.rouge:Couleurs.texteSec; textFormat:Text.PlainText
    }
    Flow {
        id:actions
        anchors.bottom:parent.bottom
        width:parent.width; spacing:8
        JarvisBouton { texte:Reglages.t("Appliquer", "Apply"); primaire:true; enabled:AssistantEtat.reglagesDisponibles && !AssistantEtat.reglagesEnCours && !AssistantEtat.enCours; onClic:AssistantEtat.appliquerReglages() }
        JarvisBouton { texte:Reglages.t("Actualiser", "Refresh"); enabled:!AssistantEtat.reglagesEnCours; onClic:AssistantEtat.lireReglages() }
        JarvisBouton { texte:Reglages.t("Connexion…", "Connection…"); onClic:AssistantEtat.configurer() }
    }
}
