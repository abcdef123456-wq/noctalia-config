import QtQuick

Column {
    id:r
    property var donnees: ({})
    property string operation: ""
    property bool details: false
    signal choisir(string op, var parametres, bool lecture)
    width:parent.width; spacing:12
    readonly property var contenuDonnees: donnees.memory || donnees.session || donnees.usage || donnees
    readonly property string message: (typeof donnees.message === "string" || typeof donnees.output === "string" || typeof donnees.text === "string") ? JarvisEtat.texte(donnees) : ""
    readonly property var lignes: {
        var list=[],kind=""
        for (let k of ["models","conversations","facts","reminders","services","history","messages"]) {
            if (Array.isArray(contenuDonnees[k])) { list=contenuDonnees[k];kind=k;break }
        }
        var rows=list.slice(0,100).map((x,i)=>({kind:kind,item:typeof x==="string"?{id:x,name:x}:x}))
        if (contenuDonnees.profile && typeof contenuDonnees.profile==="object") Object.keys(contenuDonnees.profile).forEach(k=>rows.push({kind:"profile",item:{id:k,name:k,text:String(contenuDonnees.profile[k])}}))
        if (!kind && !message) Object.keys(contenuDonnees).forEach(k=>{
            var v=contenuDonnees[k]
            if (v!==null && typeof v!=="object" && k!=="success") rows.push({kind:"value",item:{name:k.replace(/_/g," "),text:String(v)}})
        })
        return rows
    }
    Rectangle {
        visible:r.message!==""; width:parent.width; height:visible?texte.implicitHeight+32:0
        radius:18; color:Couleurs.carte
        TextEdit { id:texte; x:16;y:16;width:parent.width-32;height:contentHeight;text:AssistantEtat.formater(r.message)
                   color:Couleurs.texte; font.family:"Adwaita Sans";font.pixelSize:14;readOnly:true;selectByMouse:true;wrapMode:TextEdit.Wrap;textFormat:TextEdit.MarkdownText }
    }
    Repeater {
        model:r.lignes
        Rectangle {
            id:carte
            required property var modelData
            readonly property var item:modelData.item||{}
            readonly property string kind:modelData.kind
            width:r.width; height:col.implicitHeight+28; radius:16; color:Couleurs.carte
            Column {
                id:col;x:14;y:14;width:parent.width-28;spacing:8
                Texte { width:parent.width;text:AssistantEtat.formater(String(carte.item.name||carte.item.title||carte.item.prompt||carte.item.role||carte.item.text||carte.item.message||carte.item.unit||carte.item.id||"—"));textFormat:Text.MarkdownText;wrapMode:Text.Wrap;elide:Text.ElideNone;font.weight:Font.DemiBold;font.pixelSize:14 }
                Texte {
                    width:parent.width;secondaire:true;textFormat:Text.MarkdownText;wrapMode:Text.Wrap;elide:Text.ElideNone
                    text:carte.kind==="history"||carte.kind==="messages"?AssistantEtat.formater(String(carte.item.response||carte.item.content||"")):
                         carte.kind==="value"||carte.kind==="profile"?AssistantEtat.formater(String(carte.item.text||"")):
                         [carte.item.id!==undefined?"ID : "+carte.item.id:"",carte.item.desc||"",carte.item.platform||"",carte.item.remind_at||"",carte.item.state||"",carte.item.model||""].filter(x=>x!=="").join(" · ")
                    visible:text!==""
                }
                Flow {
                    width:parent.width;spacing:8
                    JarvisBouton { visible:carte.kind==="models"; texte:Reglages.t("Utiliser ce modèle", "Use model");enabled:!JarvisEtat.enCours&&!AssistantEtat.enCours;onClic:r.choisir("session.update",{model:String(carte.item.id)},false) }
                    JarvisBouton { visible:carte.kind==="conversations"; texte:Reglages.t("Reprendre", "Resume");enabled:!JarvisEtat.enCours&&!AssistantEtat.enCours;onClic:r.choisir("conversation.resume",{id:String(carte.item.id||carte.item.conversation_id)},false) }
                    JarvisBouton { visible:carte.kind==="conversations"; texte:Reglages.t("Historique", "History");enabled:!JarvisEtat.enCours;onClic:r.choisir("conversation.history",{id:String(carte.item.id||carte.item.conversation_id)},true) }
                    JarvisBouton { visible:["facts","profile","reminders","conversations"].indexOf(carte.kind)>=0; texte:Reglages.t("Retirer", "Remove");enabled:!JarvisEtat.enCours&&!AssistantEtat.enCours;onClic:{
                        var op=({facts:"memory.delete",profile:"profile.delete",reminders:"reminder.cancel",conversations:"conversation.delete"})[carte.kind]
                        r.choisir(op,carte.kind==="profile"?{key:String(carte.item.id)}:{id:String(carte.item.id||carte.item.conversation_id)},false)
                    } }
                    JarvisBouton { visible:carte.kind==="services"; texte:Reglages.t("Journaux", "Logs");enabled:!JarvisEtat.enCours;onClic:r.choisir("logs",{unit:String(carte.item.unit||"")},true) }
                    JarvisBouton { visible:carte.kind==="services"; texte:Reglages.t("Redémarrer", "Restart");enabled:!JarvisEtat.enCours&&!AssistantEtat.enCours;onClic:r.choisir("service.restart",{unit:String(carte.item.unit||"")},false) }
                }
            }
        }
    }
    JarvisBouton { visible:Object.keys(r.donnees).length>0;texte:r.details?Reglages.t("Masquer les détails", "Hide details"):Reglages.t("Détails techniques", "Technical details");onClic:r.details=!r.details }
    TextEdit { visible:r.details;width:parent.width;height:visible?contentHeight:0;text:JSON.stringify(r.donnees,null,2).slice(0,20000);color:Couleurs.texteSec;readOnly:true;selectByMouse:true;wrapMode:TextEdit.Wrap;textFormat:TextEdit.PlainText;font.family:"monospace";font.pixelSize:12 }
}
