import QtQuick
import QtQuick.Window
import Quickshell

Window {
    id: fen
    title: "JARVIS"
    visible: true
    visibility: Window.FullScreen
    width: 1280; height: 800; minimumWidth: 860; minimumHeight: 600
    color: Couleurs.fond
    property bool pret: false
    property string page: "accueil"
    property var selection: ({})
    property var valeurs: ({})
    property var attente: null
    property string moduleId: ""
    property string resultatOp: ""
    readonly property var moduleCourant: JarvisEtat.modules.find(m => m.id === moduleId) || ({})
    readonly property bool materielDisponible: !(moduleCourant.hardware || moduleCourant.requires_local_hardware) || JarvisEtat.etat.deploy_mode !== "server" || JarvisEtat.etat.pc_agent_connected === true
    readonly property var navigation: [
        {id:"accueil",nom:Reglages.t("Vue d’ensemble", "Overview"),icone:"space_dashboard"},
        {id:"chat",nom:"Conversation",icone:"chat"}, {id:"modules",nom:Reglages.t("Modules", "Tools"),icone:"extension"},
        {id:"session",nom:Reglages.t("Modèle et session", "Model and session"),icone:"neurology"},
        {id:"memoire",nom:Reglages.t("Mémoire", "Memory"),icone:"psychology"},
        {id:"conversations",nom:Reglages.t("Conversations", "Conversations"),icone:"history"},
        {id:"rappels",nom:Reglages.t("Rappels", "Reminders"),icone:"notifications_active"},
        {id:"configuration",nom:Reglages.t("Bots et réglages", "Bots and settings"),icone:"tune"},
        {id:"services",nom:"Services",icone:"dns"},
        {id:"deploiement",nom:Reglages.t("Déploiement", "Deployment"),icone:"cloud_upload"}
    ]
    Component.onCompleted: { pret = true; JarvisEtat.ouvert = true; JarvisEtat.actualiser() }
    onVisibleChanged: { JarvisEtat.ouvert = visible; if (pret && visible) JarvisEtat.actualiser() }
    onClosing: { JarvisEtat.ouvert = false; attente = null }
    function surEcran(nom) {
        var ecrans = Qt.application.screens
        for (var i=0;i<ecrans.length;i++) if (ecrans[i].name===nom) { screen=ecrans[i]; return }
    }
    function ouvrir(id) {
        page = id; selection = {}; valeurs = {}; resultatOp = ""
        var op = ({session:"models",memoire:"memory",conversations:"conversations",rappels:"reminders",services:"services"})[id]
        if (op) { resultatOp = op; JarvisEtat.executer(op, {}, false) }
    }
    function formulaire(op, titre, champs, initial) {
        selection = {op:op,titre:titre,champs:champs || []}; valeurs = initial || {}; resultatOp = op
    }
    function champ(cle, titre, type, secret) { return {key:cle,label:titre,kind:type || "text",secret:secret || false} }
    function soumettre() {
        var p = Object.assign({}, valeurs)
        if (selection.op === "action") {
            var params = {}
            for (var i=0;i<selection.champs.length;i++) {
                var f=selection.champs[i], v=p[f.key]
                if (v === undefined || v === "") continue
                if (f.kind === "number") { v=Number(v); if (!isFinite(v)) return }
                params[f.key]=v
            }
            p={tool:moduleId, action:selection.action, params:params}
        } else if (selection.op === "config.update") p={values:p}
        if (selection.op === "action" && selection.lecture === true) { JarvisEtat.executer("action",p,true); return }
        attente={op:selection.op,params:p,titre:selection.titre}
    }
    function resumeConfirmation() {
        if (!attente) return ""
        var p=attente.params.values || attente.params.params || attente.params
        return Object.keys(p).map(k=>{
            var f=JarvisEtat.champs.find(x=>x.key===k) || (selection.champs||[]).find(x=>x.key===k) || {}
            var v=f.secret ? (p[k] ? Reglages.t("Remplacer (masqué)", "Replace (hidden)") : Reglages.t("Conserver", "Keep")) : String(p[k]).slice(0,180)
            return (f.label||k)+" : "+v
        }).join("\n")
    }
    function configurerGroupe(groupe) {
        var fields=JarvisEtat.champs.filter(f => f.group === groupe)
        var initial={}
        fields.forEach(f => initial[f.key]=f.value || "")
        formulaire("config.update", Reglages.t("Enregistrer les réglages", "Save settings"), fields, initial)
    }
    Connections {
        target: JarvisEtat
        function onTermine(op, succes) {
            if (op === "config.update" && succes) { fen.valeurs = {}; fen.selection = {} }
            if ((op === "session.reset" || op === "conversation.resume") && succes) AssistantEtat.effacer()
        }
    }
    Shortcut { sequence: "F11"; onActivated: fen.visibility = fen.visibility === Window.FullScreen ? Window.Maximized : Window.FullScreen }
    Shortcut { sequence: "Escape"; onActivated: { if (fen.attente) fen.attente = null; else fen.close() } }

    component Note: Texte { width: parent.width; wrapMode: Text.Wrap; elide: Text.ElideNone; textFormat: Text.PlainText; secondaire: true }
    component Section: Texte { width: parent.width; font.pixelSize: 22; font.weight: Font.Bold; textFormat: Text.PlainText }
    component Action: JarvisBouton { property bool modifie: true; enabled: !JarvisEtat.enCours && (!modifie || !AssistantEtat.enCours) }
    component Resultat: JarvisResultat {
        operation: fen.resultatOp
        donnees: JarvisEtat.resultats[operation] || ({})
        onChoisir: (op, params, lecture) => {
            fen.resultatOp = op
            if (lecture) JarvisEtat.executer(op, params, false)
            else fen.attente = {op:op,params:params,titre:Reglages.t("Appliquer cette action : ", "Apply action: ")+op}
        }
    }
    component Liste: Flickable {
        clip:true; contentWidth:width; boundsBehavior:Flickable.StopAtBounds
        WheelHandler { onWheel: e => { parent.contentY = Math.max(0, Math.min(Math.max(0,parent.contentHeight-parent.height),parent.contentY-e.angleDelta.y)); e.accepted=true } }
    }

    Rectangle {
        id: tete
        width: parent.width; height: 76; color: Couleurs.carte
        Row {
            anchors.left:parent.left; anchors.leftMargin:24; anchors.verticalCenter:parent.verticalCenter; spacing:14
            Etincelle { taille:38; agent:"assistant"; tourne:fen.visible && (AssistantEtat.enCours || JarvisEtat.enCours) }
            Column {
                Texte { text:"JARVIS"; font.pixelSize:24; font.weight:Font.Bold; font.letterSpacing:3 }
                Texte { text:Reglages.t("Ton assistant, sur tous tes écrans", "Your assistant, across your devices"); secondaire:true; font.pixelSize:12 }
            }
        }
        Row {
            anchors.right:parent.right; anchors.rightMargin:24; anchors.verticalCenter:parent.verticalCenter; spacing:10
            Texte { anchors.verticalCenter:parent.verticalCenter; text: JarvisEtat.enCours ? Reglages.t("Connexion…", "Connecting…") : (JarvisEtat.etat.online ? Reglages.t("En ligne", "Online") : Reglages.t("Non connecté", "Disconnected")); color:JarvisEtat.etat.online ? Couleurs.vert : Couleurs.texteSec }
            JarvisBouton { texte:Reglages.t("Actualiser", "Refresh"); enabled:!JarvisEtat.enCours; onClic:JarvisEtat.actualiser() }
            JarvisBouton { texte:"F11"; onClic:fen.visibility=fen.visibility===Window.FullScreen?Window.Maximized:Window.FullScreen }
            JarvisBouton { texte:"×"; onClic:fen.close() }
        }
    }
    Rectangle {
        id: barre
        anchors.top:tete.bottom; anchors.bottom:parent.bottom; width:210; color:Couleurs.carte
        Column {
            x:12; y:20; width:parent.width-24; spacing:5
            Repeater {
                model:fen.navigation
                Rectangle {
                    required property var modelData
                    width:parent.width; height:43; radius:12
                    color:fen.page===modelData.id ? Couleurs.gris3 : "transparent"
                    Row {
                        x:12; anchors.verticalCenter:parent.verticalCenter; spacing:10
                        Ico { nom:modelData.icone; taille:19; color:fen.page===modelData.id?Couleurs.accent:Couleurs.texteSec }
                        Texte { text:modelData.nom; font.weight:fen.page===modelData.id?Font.DemiBold:Font.Normal }
                    }
                    MouseArea { anchors.fill:parent; onClicked:fen.ouvrir(parent.modelData.id) }
                }
            }
        }
    }
    Item {
        id: zone
        anchors.left:barre.right; anchors.right:parent.right; anchors.top:tete.bottom; anchors.bottom:parent.bottom
        anchors.margins:24
        Column {
            id: messages
            width:parent.width; spacing:6
            Note { visible:JarvisEtat.erreur!==""; text:JarvisEtat.erreur; color:Couleurs.rouge }
            Note { visible:!JarvisEtat.administration && fen.page!=="chat"; text:Reglages.t("Connecte ton gateway, puis installe l’adaptateur de gestion depuis Déploiement. Le chat fonctionne aussi avec l’API d’origine.", "Connect your gateway and install the management adapter from Deployment. Chat also works with the original API.") }
        }
        Loader {
            anchors.top:messages.bottom; anchors.topMargin:16; anchors.bottom:parent.bottom; width:parent.width
            sourceComponent: ({accueil:accueil,chat:chat,modules:modules,session:session,memoire:memoire,
                               conversations:conversations,rappels:rappels,configuration:configuration,services:services,deploiement:deploiement})[fen.page]
        }
    }
    Component {
        id: accueil
        Liste {
            contentHeight: col.implicitHeight
            Column {
                id:col; width:parent.width; spacing:20
                Section { text:Reglages.t("À ton service.", "At your service."); font.pixelSize:36 }
                Note { text:Reglages.t("Continue ici la conversation de l’île, retrouve tes outils et garde Telegram et Discord à portée de main.", "Continue your island conversation here, find your tools and keep Telegram and Discord available.") }
                Row {
                    spacing:10
                    JarvisBouton { texte:Reglages.t("Parler à JARVIS", "Talk to JARVIS"); primaire:true; onClic:fen.ouvrir("chat") }
                    JarvisBouton { texte:Reglages.t("Configurer la connexion", "Configure connection"); onClic:AssistantEtat.configurer() }
                }
                Repeater {
                    model:[
                        {t:Reglages.t("Moteur", "Engine"),v:JarvisEtat.etat.online?Reglages.t("Disponible", "Available"):Reglages.t("À connecter", "Connect first")},
                        {t:"Telegram",v:(JarvisEtat.etat.gateway||{}).telegram_configured?Reglages.t("Configuré", "Configured"):Reglages.t("Non configuré", "Not configured")},
                        {t:"Discord",v:(JarvisEtat.etat.gateway||{}).discord_configured?Reglages.t("Configuré", "Configured"):Reglages.t("Non configuré", "Not configured")},
                        {t:Reglages.t("Hébergement", "Hosting"),v:JarvisEtat.etat.deploy_mode||"—"},
                        {t:Reglages.t("Relais PC", "PC relay"),v:JarvisEtat.etat.pc_agent_connected?Reglages.t("Connecté", "Connected"):Reglages.t("Non connecté", "Not connected")}
                    ]
                    Rectangle {
                        required property var modelData
                        width:col.width; height:64; radius:16; color:Couleurs.carte
                        Texte { x:18; anchors.verticalCenter:parent.verticalCenter; text:parent.modelData.t; font.weight:Font.DemiBold }
                        Texte { anchors.right:parent.right; anchors.rightMargin:18; anchors.verticalCenter:parent.verticalCenter; text:parent.modelData.v; secondaire:true }
                    }
                }
                Note { text:Reglages.t("La session moteur est partagée entre le bureau, Telegram et Discord. Un changement de modèle ou une remise à zéro affecte ces accès. « Configuré » ne prouve pas qu’un bot reçoit les messages.", "The engine session is shared across desktop, Telegram and Discord. Model changes and resets affect these clients. Configured does not mean a bot is receiving messages.") }
                JarvisBouton { texte:Reglages.t("Briefing du jour", "Daily briefing"); enabled:!JarvisEtat.enCours; onClic:{fen.resultatOp="briefing";fen.attente={op:"briefing",params:{},titre:Reglages.t("Générer le briefing", "Generate briefing")}} }
                Resultat { visible:fen.resultatOp!=="" }
            }
        }
    }
    Component { id:chat; Assistant { dansDashboard:true; animationsActives:fen.visible } }
    Component {
        id:modules
        Liste {
            contentHeight:col.implicitHeight
            Column {
                id:col; width:parent.width; spacing:16
                Section { text:Reglages.t("Tes modules", "Your tools") }
                Flow {
                    width:parent.width; spacing:8
                    Repeater {
                        model:JarvisEtat.modules
                        JarvisBouton {
                            required property var modelData
                            texte:(modelData.enabled?"● ":"○ ")+modelData.name
                            primaire:fen.moduleId===modelData.id
                            onClic:{fen.moduleId=modelData.id;fen.selection={};fen.valeurs={}}
                        }
                    }
                }
                Note { text:(JarvisEtat.modules.find(m=>m.id===fen.moduleId)||{}).description||"" }
                Note { visible:fen.moduleId!=="" && fen.moduleCourant.enabled!==true; text:Reglages.t("Module désactivé : active-le dans ses réglages, puis redémarre le gateway pour appliquer le changement.", "Tool disabled: enable it in settings, then restart the gateway to apply the change.") }
                Note { visible:fen.moduleId!=="" && !fen.materielDisponible; text:Reglages.t("Ce module demande le relais matériel du PC. Prépare-le depuis Déploiement, puis vérifie sa connexion au serveur.", "This tool needs the PC hardware relay. Prepare it from Deployment, then check its server connection.") }
                JarvisBouton { visible:fen.moduleId!==""; texte:Reglages.t("Configurer ce module", "Configure this tool"); enabled:JarvisEtat.administration; onClic:fen.configurerGroupe(fen.moduleId) }
                Flow {
                    width:parent.width; spacing:8
                    Repeater {
                        model:JarvisEtat.catalogue[fen.moduleId]||[]
                        Action {
                            required property var modelData
                            texte:modelData.label
                            modifie:modelData.readonly!==true
                            enabled:!JarvisEtat.enCours && (modelData.readonly===true || !AssistantEtat.enCours) && fen.moduleCourant.enabled===true && fen.materielDisponible
                            onClic:{fen.formulaire("action",modelData.label,modelData.fields);var a=Object.assign({},fen.selection);a.action=modelData.id;a.lecture=modelData.readonly===true;fen.selection=a}
                        }
                    }
                }
                Note { visible:fen.moduleId!=="" && !(JarvisEtat.catalogue[fen.moduleId]||[]).length; text:Reglages.t("Ce module fournit ses réglages mais n’annonce pas d’action bureau dans le catalogue. Ses commandes de chat restent disponibles si le serveur les prend en charge.", "This tool provides settings but no desktop action catalogue. Its chat commands remain available when supported by the server.") }
                Loader { width:parent.width; active:!!fen.selection.op; sourceComponent:pFormulaire }
                Resultat { visible:!!JarvisEtat.resultats[fen.resultatOp] }
            }
        }
    }
    Component {
        id:session
        Liste {
            contentHeight:col.implicitHeight
            Column {
                id:col; width:parent.width; spacing:16
                Section { text:Reglages.t("Modèle et conversation active", "Model and active conversation") }
                Note { text:Reglages.t("Ces réglages concernent aussi les bots mobiles. Les modèles disponibles sont fournis par ton moteur, sans liste codée en dur.", "These settings also affect mobile bots. Available models come from your engine.") }
                Flow {
                    width:parent.width; spacing:8
                    Action { texte:Reglages.t("Voir les modèles", "Available models"); onClic:{fen.resultatOp="models";JarvisEtat.executer("models",{},false)} }
                    Action { texte:Reglages.t("Session active", "Active session"); onClic:{fen.resultatOp="session";JarvisEtat.executer("session",{},false)} }
                    Action { texte:Reglages.t("Consommation", "Usage"); onClic:{fen.resultatOp="usage";JarvisEtat.executer("usage",{},false)} }
                    Action { texte:Reglages.t("Changer les réglages", "Change settings"); onClic:fen.formulaire("session.update",Reglages.t("Appliquer à la session partagée", "Apply to shared session"),[fen.champ("model","Modèle"),fen.champ("effort","Effort (low, medium, high, xhigh, max)"),fen.champ("mode","Mode (auto, plan, accept-edits)"),fen.champ("permission_mode","Permissions (request-review, always-proceed)")]) }
                    Action { texte:Reglages.t("Nouvelle conversation", "New conversation"); onClic:{fen.resultatOp="session.reset";fen.attente={op:"session.reset",params:{},titre:Reglages.t("Réinitialiser la session partagée", "Reset shared session")}} }
                }
                Loader { width:parent.width; active:!!fen.selection.op; sourceComponent:pFormulaire }
                Resultat {}
            }
        }
    }
    Component {
        id:memoire
        Liste {
            contentHeight:col.implicitHeight
            Column {
                id:col; width:parent.width; spacing:16
                Section { text:Reglages.t("Mémoire durable", "Long-term memory") }
                Flow {
                    width:parent.width; spacing:8
                    Action { texte:Reglages.t("Actualiser", "Refresh"); onClic:{fen.resultatOp="memory";JarvisEtat.executer("memory",{},false)} }
                    Action { texte:Reglages.t("Ajouter un souvenir", "Add memory"); onClic:fen.formulaire("memory.add",Reglages.t("Enregistrer ce souvenir", "Save memory"),[fen.champ("text","Souvenir")]) }
                    Action { texte:Reglages.t("Supprimer un souvenir", "Delete memory"); onClic:fen.formulaire("memory.delete",Reglages.t("Supprimer ce souvenir", "Delete memory"),[fen.champ("id","Identifiant")]) }
                    Action { texte:Reglages.t("Préférence du profil", "Profile preference"); onClic:fen.formulaire("profile.set",Reglages.t("Enregistrer la préférence", "Save preference"),[fen.champ("key","Clé"),fen.champ("value","Valeur")]) }
                    Action { texte:Reglages.t("Retirer une préférence", "Remove preference"); onClic:fen.formulaire("profile.delete",Reglages.t("Supprimer la préférence", "Delete preference"),[fen.champ("key","Clé")]) }
                }
                Loader { width:parent.width; active:!!fen.selection.op; sourceComponent:pFormulaire }
                Resultat {}
            }
        }
    }
    Component {
        id:conversations
        Liste {
            contentHeight:col.implicitHeight
            Column {
                id:col; width:parent.width; spacing:16
                Section { text:Reglages.t("Conversations", "Conversations") }
                Flow {
                    width:parent.width; spacing:8
                    Action { texte:Reglages.t("Actualiser", "Refresh"); onClic:{fen.resultatOp="conversations";JarvisEtat.executer("conversations",{},false)} }
                    Action { texte:Reglages.t("Reprendre", "Resume"); onClic:fen.formulaire("conversation.resume",Reglages.t("Reprendre cette conversation pour tous les clients", "Resume this conversation for all clients"),[fen.champ("id","Identifiant")]) }
                    Action { texte:Reglages.t("Supprimer", "Delete"); onClic:fen.formulaire("conversation.delete",Reglages.t("Supprimer cette conversation", "Delete conversation"),[fen.champ("id","Identifiant (all = toutes)")]) }
                }
                Loader { width:parent.width; active:!!fen.selection.op; sourceComponent:pFormulaire }
                Resultat {}
            }
        }
    }
    Component {
        id:rappels
        Liste {
            contentHeight:col.implicitHeight
            Column {
                id:col; width:parent.width; spacing:16
                Section { text:Reglages.t("Rappels", "Reminders") }
                Note { text:Reglages.t("Les rappels créés ici sont envoyés à Telegram ou Discord. Choisis l’identifiant du chat ou du salon pour les recevoir sur le téléphone ; ils restent conservés sur le serveur.", "Reminders created here are sent to Telegram or Discord. Choose a chat or channel ID to receive them on your phone; reminders remain stored on the server.") }
                Flow {
                    width:parent.width; spacing:8
                    Action { texte:Reglages.t("Actualiser", "Refresh"); onClic:{fen.resultatOp="reminders";JarvisEtat.executer("reminders",{},false)} }
                    Action { texte:Reglages.t("Créer", "Create"); onClic:fen.formulaire("reminder.create",Reglages.t("Créer ce rappel", "Create reminder"),[fen.champ("platform","Plateforme (telegram, discord)"),fen.champ("chat_id","Destination (chat ou salon)"),fen.champ("message","Message"),fen.champ("delay","Dans combien de temps (15m, 2h…)"),fen.champ("recurrence","Récurrence facultative (daily, weekdays…)")],{platform:"telegram"}) }
                    Action { texte:Reglages.t("Annuler un rappel", "Cancel reminder"); onClic:fen.formulaire("reminder.cancel",Reglages.t("Annuler ce rappel", "Cancel reminder"),[fen.champ("id","Identifiant")]) }
                }
                Loader { width:parent.width; active:!!fen.selection.op; sourceComponent:pFormulaire }
                Resultat {}
            }
        }
    }
    Component {
        id:configuration
        Liste {
            contentHeight:col.implicitHeight
            Column {
                id:col; width:parent.width; spacing:16
                Section { text:Reglages.t("Bots, briefing et connexion", "Bots, briefing and connection") }
                Note { text:Reglages.t("Les clés sont masquées et ne sont jamais renvoyées par le serveur. Un champ secret laissé vide conserve sa valeur. Les services doivent être redémarrés pour appliquer les réglages.", "Keys are masked and never returned by the server. An empty secret field keeps its value. Restart the services to apply settings.") }
                Flow {
                    width:parent.width; spacing:8
                    JarvisBouton { texte:Reglages.t("Connexion du bureau", "Desktop connection"); onClic:AssistantEtat.configurer() }
                    JarvisBouton { texte:Reglages.t("Configurer Telegram et Discord", "Configure Telegram and Discord"); enabled:JarvisEtat.administration; onClic:fen.configurerGroupe("bots") }
                    JarvisBouton { texte:Reglages.t("Configurer le briefing", "Configure briefing"); enabled:JarvisEtat.administration; onClic:fen.configurerGroupe("briefing") }
                    Action { texte:Reglages.t("Retirer le jeton Telegram", "Remove Telegram token"); visible:JarvisEtat.administration; onClic:{fen.resultatOp="config.clear";fen.attente={op:"config.clear",params:{keys:["TELEGRAM_TOKEN"]},titre:Reglages.t("Retirer le jeton Telegram des réglages du serveur", "Remove Telegram token from server settings")}} }
                    Action { texte:Reglages.t("Retirer le jeton Discord", "Remove Discord token"); visible:JarvisEtat.administration; onClic:{fen.resultatOp="config.clear";fen.attente={op:"config.clear",params:{keys:["DISCORD_TOKEN"]},titre:Reglages.t("Retirer le jeton Discord des réglages du serveur", "Remove Discord token from server settings")}} }
                }
                Loader { width:parent.width; active:!!fen.selection.op; sourceComponent:pFormulaire }
                Resultat { visible:!!JarvisEtat.resultats[fen.resultatOp] }
            }
        }
    }
    Component {
        id:services
        Liste {
            contentHeight:col.implicitHeight
            Column {
                id:col; width:parent.width; spacing:16
                Section { text:Reglages.t("Services et journaux", "Services and logs") }
                Note { text:Reglages.t("Ces commandes visent la machine du gateway et ses services utilisateur. Aucun redémarrage n’est automatique. Les journaux peuvent contenir tes conversations.", "These commands target the gateway host and its user services. Restarts are manual. Logs may contain your conversations.") }
                Action { texte:Reglages.t("Actualiser les services", "Refresh services"); onClic:{fen.resultatOp="services";JarvisEtat.executer("services",{},false)} }
                Resultat {}
            }
        }
    }
    Component {
        id:deploiement
        Liste {
            contentHeight:col.implicitHeight
            Column {
                id:col; width:parent.width; spacing:20
                Section { text:Reglages.t("Choisis où vit JARVIS", "Choose where JARVIS lives") }
                Note { text:Reglages.t("Sur ce PC : moteur, gateway et bots utilisent la machine tant qu’elle reste allumée. Sur serveur : les bots restent accessibles depuis le téléphone même quand le PC est éteint.", "On this PC: the engine, gateway and bots use this machine while it is on. On a server: bots remain available on your phone while the PC is off.") }
                Flow {
                    width:parent.width; spacing:10
                    JarvisBouton { texte:Reglages.t("Déployer sur ce PC…", "Deploy on this PC…"); primaire:true; onClic:JarvisEtat.terminal("deployer") }
                    JarvisBouton { texte:Reglages.t("Déployer sur un serveur SSH…", "Deploy on an SSH server…"); onClic:JarvisEtat.terminal("serveur") }
                    JarvisBouton { texte:Reglages.t("Connecter un serveur existant…", "Connect an existing server…"); onClic:AssistantEtat.configurer() }
                    JarvisBouton { texte:Reglages.t("Relier le matériel de ce PC…", "Connect this PC’s hardware…"); onClic:JarvisEtat.terminal("agent") }
                }
                Section { text:Reglages.t("Un backend, plusieurs accès", "One backend, multiple clients") }
                Note { text:Reglages.t("Les assistants d’installation s’ouvrent dans un terminal pour les clés et l’authentification SSH. Ils préparent les environnements Python, conservent les fichiers existants et proposent les services utilisateur. Rien ne démarre en ouvrant ce tableau de bord.", "Setup opens in a terminal for keys and SSH authentication. It prepares Python environments, preserves existing files and proposes user services. Opening this dashboard starts no backend.") }
                Note { text:Reglages.t("Le gateway écoute sur 127.0.0.1:8000 ; le runner reste privé sur 8080. Pour le bureau distant : tunnel HTTPS ou VPN vers le gateway. Telegram en polling et Discord utilisent des connexions sortantes.", "The gateway binds to 127.0.0.1:8000; the runner stays private on 8080. For a remote desktop: use an HTTPS tunnel or VPN to the gateway. Telegram polling and Discord use outbound connections.") }
                Note { text:Reglages.t("Prérequis du moteur : Python 3.11+, Git et Antigravity CLI authentifié sur l’hôte du runner. L’agent matériel PC est facultatif ; il n’est jamais activé automatiquement.", "Engine prerequisites: Python 3.11+, Git and authenticated Antigravity CLI on the runner host. The PC hardware agent is optional and never enabled automatically.") }
            }
        }
    }
    Component {
        id:pFormulaire
        Column {
            id:form
            width:parent.width; spacing:12
            visible:!!fen.selection.op
            height:visible?implicitHeight:0
            Section { text:fen.selection.titre||"" }
            Repeater {
                model:fen.selection.champs||[]
                JarvisChamp {
                    required property var modelData
                    width:form.width; titre:modelData.label; secret:modelData.secret||false; booleen:modelData.kind === "bool"
                    aide:secret ? (modelData.configured?Reglages.t("Configuré · vide pour conserver", "Configured · empty to keep"):Reglages.t("Non renseigné", "Not set")):""
                    texte:String(fen.valeurs[modelData.key]===undefined?"":fen.valeurs[modelData.key])
                    onChange:valeur=>{var copie=Object.assign({},fen.valeurs);copie[modelData.key]=valeur;fen.valeurs=copie}
                }
            }
            Action { texte:Reglages.t("Continuer", "Continue"); primaire:true; onClic:fen.soumettre() }
        }
    }
    Rectangle {
        anchors.fill:parent; visible:fen.attente!==null; color:"#b0000000"; z:100
        onVisibleChanged: if (visible) annuler.forceActiveFocus()
        MouseArea { anchors.fill:parent }
        Rectangle {
            anchors.centerIn:parent; width:Math.min(520,fen.width-48); height:confirmCol.implicitHeight+48
            radius:24; color:Couleurs.carte
            Column {
                id:confirmCol; x:24; y:24; width:parent.width-48; spacing:20
                Section { text:Reglages.t("Confirmer l’action", "Confirm action") }
                Note { text:fen.attente?fen.attente.titre:""; color:Couleurs.texte }
                Note { text:fen.resumeConfirmation() }
                Note { text:Reglages.t("Cette action sera envoyée au backend partagé avec tes accès mobiles.", "This action will be sent to the backend shared with your mobile clients.") }
                Row {
                    spacing:10
                    JarvisBouton { id:annuler; texte:Reglages.t("Annuler", "Cancel"); onClic:fen.attente=null }
                    Action { texte:Reglages.t("Confirmer", "Confirm"); primaire:true; onClic:{var demande=fen.attente;fen.attente=null;JarvisEtat.executer(demande.op,demande.params,true)} }
                }
            }
        }
    }
}
