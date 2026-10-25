// Page « Batterie » : pourcentage, temps avant la charge complète (ou avant vide) ; ce qui consomme (puissance lissée,
// programmes qui prennent le plus de processeur, carte NVIDIA) et santé de la batterie, lus par nc-conso. Page normale
// juste après le centre sur un PC à batterie ; pendant une recharge, en tête comme activité (Etat.vues).
// nc-conso ne tourne que pendant que la page est affichée (une ligne JSON toutes les 2 s) ; une valeur absente
// (pas de batterie, pas de NVIDIA, champ inconnu du pilote) : sa ligne est masquée. Sur batterie en décharge, le bouton
// « Pourquoi ça se vide ? » (Pourquoi.qml) explique et propose, sur clic, au plus 3 actions confirmées ; ouvert, il
// prend la place de la liste des programmes, de la carte NVIDIA et de la santé (l'île ne dépasse pas 580 px).
import QtQuick
import Quickshell.Io
import Quickshell.Services.UPower

Item {
    id: charge
    readonly property real restant: Etat.batterie ? Etat.batterie.timeToFull : 0
    readonly property real avantVide: Etat.batterie ? Etat.batterie.timeToEmpty : 0

    // ── Mesures de nc-conso ──
    property var mesure: ({})
    readonly property var bat: mesure.batterie || null
    readonly property var programmes: mesure.top || []
    readonly property var rtx: mesure.rtx || null
    readonly property var sante: mesure.sante || null
    readonly property bool decharge: bat !== null && bat.statut === "Discharging"
    readonly property bool aWatts: bat !== null && typeof bat.watts === "number" && bat.watts >= 0.05
                                   && (bat.statut === "Discharging" || bat.statut === "Charging")
    // Relevé seulement quand la page est vraiment affichée : un instant après être devenue visible (à sa création dans
    // un Loader, avant d'être rangée dans sa page encore cachée, elle se croit visible le temps d'une image)
    property bool affichee: false
    onVisibleChanged: if (visible) attente.restart(); else { attente.stop(); affichee = false }
    Timer { id: attente; interval: 150; onTriggered: charge.affichee = charge.visible }
    Process {
        running: charge.affichee
        command: [Etat.bin + "nc-conso", "suivre"]
        stdout: SplitParser {
            onRead: data => { try { charge.mesure = JSON.parse(data) || {} } catch (e) {} }
        }
    }

    // « 12,3 » (une décimale, virgule en français)
    function nb(x) { const s = Number(x).toFixed(1); return Reglages.en ? s : s.replace(".", ",") }
    function duree(s) {
        const m = Math.round(s / 60)
        if (m < 1) return "< 1 min"
        if (m < 60) return m + " min"
        return Math.floor(m / 60) + " h " + String(m % 60).padStart(2, "0")
    }
    function valeurProgramme(p) {
        if (typeof p.watts === "number") return Reglages.t("environ ", "about ") + nb(p.watts) + " W"
        if (typeof p.pct !== "number") return ""
        return (p.pct < 0.1 ? "< " + nb(0.1) : nb(p.pct)) + Reglages.t(" % du processeur", "% of CPU")
    }

    // L'île prend la hauteur du contenu (lignes masquées comprises)
    onHauteurChanged: Etat.annoncerHauteur("charge", hauteur)
    Component.onCompleted: { Etat.annoncerHauteur("charge", hauteur); if (visible) attente.restart() }
    readonly property real hauteur: contenu.implicitHeight

    Column {
        id: contenu
        width: parent.width
        // Seul (avant la première mesure, ou rien à montrer) : le haut de la page reste centré, comme avant
        y: Math.max(0, (parent.height - implicitHeight) / 2)
        spacing: 10
        Row {
            spacing: 18
            // Sur secteur : l'éclair vert ; sur batterie : la pile, dans les couleurs du texte
            Rectangle {
                width: 76; height: 76; radius: 38; color: Etat.branche ? Couleurs.fondVert : Couleurs.gris3
                Ico {
                    anchors.centerIn: parent; nom: Etat.branche ? "bolt" : "battery_full"; taille: 40
                    color: Etat.branche ? Couleurs.vert : Couleurs.texte; rotation: Etat.branche ? 0 : 90
                }
            }
            Column {
                anchors.verticalCenter: parent.verticalCenter; spacing: 3
                Texte { text: Etat.enCharge ? Reglages.t("En charge", "Charging") : Reglages.t("Batterie", "Battery"); secondaire: true; font.pixelSize: 14 }
                Texte { text: Etat.pourcent + Reglages.t(" %", "%"); font.pixelSize: 38; font.weight: Font.DemiBold; color: Etat.branche ? Couleurs.vert : Couleurs.texte }
                Texte {
                    secondaire: true
                    text: Etat.enCharge && charge.restant > 60
                          ? Reglages.t("Pleine dans ", "Full in ") + Math.floor(charge.restant / 3600) + Reglages.t(" h ", ":") + String(Math.floor((charge.restant % 3600) / 60)).padStart(2, "0")
                          : Etat.branche ? Reglages.t("Branchée sur secteur", "Plugged in")
                          : charge.avantVide > 60 ? Reglages.t("Encore ", "") + charge.duree(charge.avantVide) + Reglages.t("", " left")
                          : Reglages.t("Sur batterie", "On battery")
                }
            }
        }

        // Ce qui consomme : puissance lissée sur 5 s, puis les programmes (30 dernières secondes)
        Module {
            objectName: "blocConso"
            visible: charge.aWatts || charge.programmes.length > 0
            width: contenu.width; radius: 18
            height: colConso.implicitHeight + 24
            Column {
                id: colConso
                x: 14; y: 12; width: parent.width - 28; spacing: 6
                Item {
                    objectName: "conso"
                    visible: charge.aWatts
                    width: parent.width; height: 20
                    Texte {
                        anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                        text: charge.decharge ? Reglages.t("Consommation", "Power Use") : Reglages.t("Recharge", "Charging")
                        font.weight: Font.DemiBold; font.pixelSize: 14
                    }
                    Texte {
                        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                        text: !charge.bat ? "" : charge.decharge
                              ? nb(charge.bat.watts) + " W" + (typeof charge.bat.restant === "number"
                                    ? Reglages.t(" · encore ", " · ") + duree(charge.bat.restant) + Reglages.t("", " left") : "")
                              : "+" + nb(charge.bat.watts) + " W"
                        font.pixelSize: 14
                    }
                }
                Texte {
                    visible: charge.programmes.length > 0 && !pourquoi.ouvert
                    text: Reglages.t("Programmes les plus gourmands (30 s)", "Busiest apps (last 30 s)")
                    secondaire: true; font.pixelSize: 12
                }
                Repeater {
                    model: pourquoi.ouvert ? [] : charge.programmes      // la réponse de « Pourquoi ça se vide ? » prend leur place
                    Item {
                        id: prog
                        required property var modelData
                        objectName: "programme"
                        readonly property string valeur: charge.valeurProgramme(modelData)
                        width: colConso.width; height: 20
                        Texte {
                            anchors.left: parent.left; anchors.right: val.left; anchors.rightMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            text: prog.modelData.nom || "?"
                        }
                        Texte {
                            id: val
                            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                            text: prog.valeur; secondaire: true
                        }
                    }
                }
            }
        }

        // Carte NVIDIA d'un PC hybride : endormie (0 W) ou allumée, et pourquoi
        Module {
            objectName: "rtx"
            readonly property bool dort: charge.rtx !== null && charge.rtx.etat === "endormie"
            readonly property string texte: charge.rtx === null ? ""
                : dort ? Reglages.t("Carte NVIDIA : endormie (0 W)", "NVIDIA GPU: asleep (0 W)")
                : Reglages.t("Carte NVIDIA : allumée", "NVIDIA GPU: on") + (charge.rtx.cause ? " — " + charge.rtx.cause : "")
            visible: texte !== "" && !pourquoi.ouvert
            width: contenu.width; height: 44; radius: 18
            Ico {
                id: icoRtx
                anchors.left: parent.left; anchors.leftMargin: 14; anchors.verticalCenter: parent.verticalCenter
                nom: "memory"; taille: 20; color: parent.dort ? Couleurs.vert : Couleurs.orange
            }
            Texte {
                anchors.left: icoRtx.right; anchors.leftMargin: 10; anchors.right: parent.right; anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                text: parent.texte
            }
        }

        // « Pourquoi ça se vide ? » : seulement sur batterie en décharge (sans batterie ou sur secteur, ni bouton ni place)
        Pourquoi {
            id: pourquoi
            width: contenu.width
            actif: charge.decharge && charge.affichee
        }

        // Santé de la batterie : capacité gardée, cycles, limite de charge
        Module {
            id: blocSante
            objectName: "blocSante"
            readonly property var s: charge.sante || {}
            readonly property var lim: s.limite || null
            visible: (typeof s.garde === "number" || typeof s.cycles === "number" || lim !== null) && !pourquoi.ouvert
            width: contenu.width; radius: 18
            height: colSante.implicitHeight + 24
            Column {
                id: colSante
                x: 14; y: 12; width: parent.width - 28; spacing: 4
                Texte { text: Reglages.t("Santé de la batterie", "Battery Health"); font.weight: Font.DemiBold; font.pixelSize: 14 }
                Texte {
                    objectName: "garde"
                    visible: typeof blocSante.s.garde === "number"
                    width: parent.width; wrapMode: Text.WordWrap
                    text: Reglages.t("Ta batterie garde " + blocSante.s.garde + " % de sa capacité d'origine",
                                     "Your battery keeps " + blocSante.s.garde + "% of its original capacity")
                }
                Texte {
                    objectName: "cycles"
                    readonly property int n: blocSante.s.cycles || 0
                    visible: n > 0
                    secondaire: true
                    text: n + (n > 1 ? Reglages.t(" cycles de charge", " charge cycles") : Reglages.t(" cycle de charge", " charge cycle"))
                }
                Texte {
                    objectName: "limite"
                    readonly property var lim: blocSante.lim
                    visible: lim !== null
                    width: parent.width; wrapMode: Text.WordWrap
                    secondaire: true
                    text: lim === null ? ""
                          : !lim.active ? Reglages.t("Charge jusqu'à 100 %", "Charges to 100%")
                          : lim.seuil ? Reglages.t("Charge limitée à " + lim.seuil + " % pour la ménager", "Charge limited to " + lim.seuil + "% to protect it")
                          : Reglages.t("Charge limitée pour ménager la batterie", "Charge limited to protect the battery")
                }
            }
        }
    }
}
