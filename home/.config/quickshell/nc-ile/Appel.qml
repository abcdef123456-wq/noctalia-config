pragma Singleton
// Appel en cours (activité en direct, comme sur iPhone) : une appli enregistre le micro (Discord, navigateur WebRTC,
// Zoom, Teams…) depuis plus de 2,5 s. Pilule : icône de l'appli, durée de l'appel et niveau du micro ; page Appel
// (PageAppel.qml) : nom de l'appli, durée, bouton couper / réactiver le micro, rappel « mode appel : son mono » quand la
// source est un casque Bluetooth en profil appel (HFP).
// Détection par les événements de PipeWire (Etat.fluxMicro, Quickshell.Services.Pipewire) : rien ne sonde, aucun
// processus ; sans PipeWire, la liste des flux reste vide et rien ne s'affiche.
// La source du micro qu'utilise l'appli (lien PipeWire du flux, sinon la source par défaut), son état coupé et son
// profil viennent d'AppelSource.qml, chargé par son chemin seulement pendant un appel : si ce fichier ne se charge pas
// (Quickshell plus ancien), l'activité reste, avec la source par défaut.
// Le niveau du micro (NiveauMicro.qml, PwNodePeakMonitor de Quickshell) est un chiffre par image, jamais le son :
// mesuré seulement pendant qu'il s'affiche (pilule en mode appel ou page Appel), écran vu, hors Économie et micro actif.
// Micro coupé au début d'un appel (le bug classique : on parle, personne n'entend) : réaction « Micro coupé » dans la
// pilule, puis le mode appel garde un micro barré orange tant que la source est coupée.
// Réglage ILE_APPEL (nc-reglages → Île) : non = rien de tout ça.
import QtQuick
import Quickshell

Singleton {
    id: a

    readonly property bool reglage: Reglages.val("ILE_APPEL", "oui") !== "non"
    property int delai: 2500               // ms d'enregistrement continu avant de parler d'appel (pas un clic de dictée)
    // Les flux qui enregistrent, sans les outils de dictée (parec, pw-record, arecord : une dictée n'est pas un appel),
    // ni les traitements du son toujours branchés sur le micro (EasyEffects, rnnoise, PulseEffects, JamesDSP, Carla,
    // boucles et flux passifs : un « appel » sans fin), ni OBS (il capte pour enregistrer, pas pour parler), ni la mesure
    // de niveau de l'île elle-même (flux de Quickshell, « stream.monitor »)
    readonly property var flux: reglage ? Etat.fluxMicro.filter(n => !/^(parec|pw-record|pw-cat|arecord)$/i.test(n.name || "")
                                                                   && !/quickshell|peak|easyeffects|easy effects|pulseeffects|rnnoise|noise|jamesdsp|carla|loopback|\bobs\b/i.test((n.name || "") + " " + (n.description || ""))
                                                                   && !(n.properties && (n.properties["stream.monitor"] === "true" || n.properties["node.passive"] === "true"))) : []
    readonly property var noeud: flux.length ? flux[0] : null
    readonly property bool presence: noeud !== null
    readonly property string appli: noeud ? Etat.nomJoli(noeud.description || noeud.name || "") : ""
    // Icône de l'appli (thème d'icônes), sinon vide : la pilule montre un combiné
    readonly property string icone: {
        if (!noeud) return ""
        var n = ((noeud.name || "") + " " + (noeud.description || "")).trim()
        if (/WEBRTC VoiceEngine|discord/i.test(n)) return Quickshell.iconPath("discord", true) || ""
        var entier = (noeud.name || "").toLowerCase().replace(/\s+/g, "-"), premier = entier.split(/[-:.]/)[0]
        return (entier !== "" ? Quickshell.iconPath(entier, true) : "") || (premier !== "" ? Quickshell.iconPath(premier, true) : "") || ""
    }

    // ── L'appel ──
    property bool enCours: false
    property real debut: 0                  // ms
    property string derniereAppli: ""       // l'appel qui vient de finir (réaction « Appel terminé »)
    property int derniereDuree: 0           // s
    readonly property int duree: enCours ? Math.max(0, Math.floor((Etat.maintenant.getTime() - debut) / 1000)) : 0
    readonly property string dureeTexte: Etat.duree(duree)
    onPresenceChanged: {
        if (presence) { if (!enCours) attente.restart() }
        else { attente.stop(); if (enCours) terminer() }
    }
    Timer { id: attente; interval: a.delai; onTriggered: if (a.presence && !a.enCours) a.commencer() }
    function commencer() {
        debut = Date.now() - delai
        enCours = true
        derniereAppli = appli
        if (muet) Etat.activite("appel-muet", 5000)
    }
    function terminer() {
        derniereDuree = Math.max(0, Math.floor((Date.now() - debut) / 1000))
        enCours = false; debut = 0
        if (reglage) Etat.activite("appel-fini", 4000)
    }
    onReglageChanged: if (!reglage) { attente.stop(); enCours = false; debut = 0 }

    // ── Source du micro (AppelSource.qml, chargée pendant l'appel seulement) ──
    Loader { id: lien; source: "AppelSource.qml"; active: a.enCours }
    readonly property var source: lien.item ? lien.item.source : null
    readonly property bool lie: lien.item ? lien.item.lie : false
    // Sans le lien : l'état de la source par défaut (Etat.qml la suit déjà)
    readonly property bool muet: lien.item ? lien.item.muet : Etat.microMuet
    readonly property bool monoBt: lien.item ? lien.item.monoBt : false
    readonly property string nomSource: lien.item ? lien.item.nomSource : ""
    // Couper ou réactiver le micro : sur la source liée au flux de l'appli, sinon sur la source par défaut
    function basculerMicro() { if (lien.item && lien.item.lie) lien.item.basculer(); else Etat.basculerMicro() }

    // ── Niveau du micro (NiveauMicro.qml), seulement pendant qu'il se voit ──
    readonly property bool affiche: Etat.ecranOuvert === "" ? (Etat.activiteType === "" && !Etat.enregistre && !Partage.indicateur
                                                               && AssistantEtat.activitePilule === "")
                                                            : Etat.vueActive === "appel"
    readonly property bool niveauVoulu: enCours && !muet && affiche && Etat.ecranVu && !Reglages.sobre
    Loader { id: mesure; source: "NiveauMicro.qml"; active: a.niveauVoulu }
    Binding { target: mesure.item; property: "source"; value: a.source; when: mesure.item !== null }
    Binding { target: mesure.item; property: "actif"; value: a.niveauVoulu; when: mesure.item !== null }
    readonly property real niveau: mesure.item ? mesure.item.niveau : 0
}
