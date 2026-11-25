pragma Singleton
// Moteur de mouvement unifié de nc-ile (barre, île, tiroir JARVIS, lanceur) :
// une seule source pour les ressorts, durées, comportement sur batterie, vitesse globale,
// exceptions par écran et réaction de la barre. Zéro Timer à cadence fixe : les ressorts
// suivent le vsync du compositeur (60 → 144 → 240 Hz).
// Réglages (nc-reglages, ~/.config/nc/reglages.conf) :
//   ILE_ANIM=ressort | doux | vif | sec
//   ILE_ANIM_VITESSE=50..200 (défaut 100, %)
//   ILE_ANIM_BATTERIE=douces | aucune | continues (défaut douces)
//   ILE_ANIM_ECRANS=DP-1:vif,eDP-1:doux,HDMI-A-1:aucun (défaut "")
//   BARRE_REACTION=glisser | fondu (défaut glisser)
import QtQuick
import Quickshell
import Quickshell.Services.UPower

Singleton {
    id: m

    readonly property var profils: ({
        "ressort": { raideur: 3.4, amortiL: 0.34, amortiH: 0.36, duree: 280, dureeCourte: 120, dureeContour: 220, dureeSpot: 170, courbe: Easing.OutCubic },
        "doux":    { raideur: 2.2, amortiL: 0.7,  amortiH: 0.7,  duree: 400, dureeCourte: 170, dureeContour: 320, dureeSpot: 240, courbe: Easing.InOutQuad },
        "vif":     { raideur: 5.5, amortiL: 0.28, amortiH: 0.3,  duree: 200, dureeCourte: 90,  dureeContour: 150, dureeSpot: 120, courbe: Easing.OutBack },
        "sec":     { raideur: 8,   amortiL: 1,    amortiH: 1,    duree: 120, dureeCourte: 60,  dureeContour: 100, dureeSpot: 90,  courbe: Easing.Linear }
    })
    readonly property var nomsValides: ["ressort", "doux", "vif", "sec", "aucun"]

    readonly property string profilBase: {
        const v = Reglages.val("ILE_ANIM", "ressort")
        return Object.prototype.hasOwnProperty.call(profils, v) ? v : "ressort"
    }
    readonly property int vitessePct: {
        const brut = String(Reglages.val("ILE_ANIM_VITESSE", "100")).trim()
        if (!/^[0-9]+$/.test(brut)) return 100
        const n = parseInt(brut, 10)
        return n >= 50 && n <= 200 ? n : 100
    }
    readonly property string batterieMode: {
        const v = Reglages.val("ILE_ANIM_BATTERIE", "douces")
        return (v === "douces" || v === "aucune" || v === "continues") ? v : "douces"
    }
    readonly property string reactionBarreMode: Reglages.val("BARRE_REACTION", "glisser") === "fondu" ? "fondu" : "glisser"
    readonly property bool surBatterie: UPower.onBattery
    readonly property bool enPartage: Partage.silence || Partage.indicateur || Partage.sessions > 0

    readonly property var exceptionsEcrans: {
        const brut = String(Reglages.val("ILE_ANIM_ECRANS", "") || "")
        const exactes = {}
        const motifs = []
        if (!brut.trim()) return { exactes: exactes, motifs: motifs }
        const morceaux = brut.split(",")
        for (let i = 0; i < morceaux.length; ++i) {
            const entree = morceaux[i].trim()
            if (!entree) continue
            const sep = entree.indexOf(":")
            if (sep <= 0) continue
            const cle = entree.slice(0, sep).trim()
            const val = entree.slice(sep + 1).trim().toLowerCase()
            if (!cle || nomsValides.indexOf(val) < 0) continue
            if (cle.indexOf("*") >= 0) motifs.push({ motif: cle, val: val })
            else exactes[cle] = val
        }
        return { exactes: exactes, motifs: motifs }
    }

    function correspondMotif(nom, motif) {
        const parts = motif.split("*")
        let pos = 0
        for (let i = 0; i < parts.length; ++i) {
            const seg = parts[i]
            if (seg === "") continue
            if (i === 0) {
                if (!nom.startsWith(seg)) return false
                pos = seg.length
            } else if (i === parts.length - 1) {
                if (!nom.endsWith(seg) || nom.length - seg.length < pos) return false
                pos = nom.length
            } else {
                const idx = nom.indexOf(seg, pos)
                if (idx < 0) return false
                pos = idx + seg.length
            }
        }
        return true
    }

    function profilPourEcran(nomEcran) {
        const nom = String(nomEcran || "").trim()
        if (!nom) return profilBase
        const ex = exceptionsEcrans
        if (Object.prototype.hasOwnProperty.call(ex.exactes, nom)) return ex.exactes[nom]
        for (let i = 0; i < ex.motifs.length; ++i) {
            if (correspondMotif(nom, ex.motifs[i].motif)) return ex.motifs[i].val
        }
        return profilBase
    }

    function echelonnerDuree(base, facteur) {
        if (facteur === 1) return base
        return Math.max(40, Math.round(base / facteur))
    }

    function pourEcran(nomEcran) {
        const profil = profilPourEcran(nomEcran)
        const actif = !Reglages.sobre && !(surBatterie && batterieMode === "aucune") && profil !== "aucun"
        const base = Object.prototype.hasOwnProperty.call(profils, profil) ? profils[profil] : profils[profilBase]
        const f = vitessePct / 100
        let raideur = f === 1 ? base.raideur : Number((base.raideur * f).toFixed(3))
        let amortiL = base.amortiL
        let amortiH = base.amortiH
        let duree = echelonnerDuree(base.duree, f)
        let dureeCourte = echelonnerDuree(base.dureeCourte, f)
        let dureeContour = echelonnerDuree(base.dureeContour, f)
        let dureeSpot = echelonnerDuree(base.dureeSpot, f)

        if (surBatterie && batterieMode === "douces") {
            amortiL = Math.max(amortiL, 0.85)
            amortiH = Math.max(amortiH, 0.85)
            dureeCourte = Math.max(40, Math.round(dureeCourte * 0.8))
            dureeContour = Math.max(40, Math.round(dureeContour * 0.8))
            dureeSpot = Math.max(40, Math.round(dureeSpot * 0.8))
        }

        if (!actif) {
            duree = 0
            dureeCourte = 0
            dureeContour = 0
            dureeSpot = 0
        }

        return {
            profil: profil,
            actif: actif,
            morphActif: actif && !enPartage,
            reactionBarre: actif ? reactionBarreMode : "instantane",
            raideur: raideur,
            amortiL: amortiL,
            amortiH: amortiH,
            duree: duree,
            dureeCourte: dureeCourte,
            dureeContour: dureeContour,
            dureeSpot: dureeSpot,
            courbe: base.courbe,
            epsilonPx: 0.2,
            epsilonNorm: 0.0005
        }
    }
}
