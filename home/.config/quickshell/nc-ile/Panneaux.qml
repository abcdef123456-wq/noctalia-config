import QtQuick
import QtQml.Models
import Quickshell
import Quickshell.Hyprland
import "DispositionPanneaux.js" as Disposition

Scope {
    id: ecranPanneaux
    required property var ecran
    required property var modele
    required property var palette
    required property rect obstacle
    property int reserveIleHaut: 0
    readonly property string descriptionEcran: Hyprland.monitorFor(ecran)?.lastIpcObject?.description ?? ""
    readonly property var barresActives: (modele.barres || []).map(barre => {
        for (const [identifiant, options] of Object.entries(barre.monitor || {})) {
            const nom = options.match ?? identifiant
            if (nom && (ecran.name === nom || descriptionEcran.includes(nom))) return Object.assign({}, barre, options, { id: barre.id })
        }
        return barre
    })
    readonly property var barresContinues: barresActives.filter(b => b.enabled !== false && (b.background_opacity ?? 0) > 0)
    readonly property var blocs: Disposition.blocs(barresActives)
    readonly property var reservesMap: Disposition.reserves(barresActives, reserveIleHaut)
    readonly property var reservesListe: ["top", "bottom", "left", "right"]
        .filter(b => reservesMap[b] > 0)
        .map(b => ({ bord: b, zone: reservesMap[b] }))
    readonly property var places: {
        panneaux.revision
        const tailles = blocs.map((_, i) => panneaux.objectAt(i)?.mesure)
        return Disposition.placer(blocs, tailles, ecran.width, ecran.height, obstacle)
    }

    function teinte(role, defaut) {
        if (!role || role === "none") return defaut
        // Noctalia accepte le hexadécimal CSS ; Qt attend l'alpha avant le RGB.
        if (role.startsWith("#")) {
            let hex = role.slice(1)
            if (hex.length === 3 || hex.length === 4) hex = hex.split("").map(c => c + c).join("")
            return "#" + (hex.length === 8 ? hex.slice(6) + hex.slice(0, 6) : hex)
        }
        const cle = "m" + role.split("_").map(s => s.charAt(0).toUpperCase() + s.slice(1)).join("")
        return palette[cle] ?? (role.startsWith("surface_container") ? (palette.mSurfaceVariant ?? defaut) : defaut)
    }

    Instantiator {
        model: ecranPanneaux.reservesListe
        delegate: ReservePanneau {
            required property var modelData
            screen: ecranPanneaux.ecran
            bord: modelData.bord
            zone: modelData.zone
        }
    }

    Instantiator {
        model: ecranPanneaux.barresContinues
        delegate: BarreContinue {
            required property var modelData
            screen: ecranPanneaux.ecran
            barre: modelData
            definitions: ecranPanneaux.modele.widgets || ({})
            police: ecranPanneaux.modele.police || ""
            teinte: ecranPanneaux.teinte
            obstacle: ecranPanneaux.obstacle
        }
    }

    Instantiator {
        id: panneaux
        property int revision: 0
        model: ecranPanneaux.blocs
        onObjectAdded: revision++
        onObjectRemoved: revision++
        delegate: Panneau {
            required property var modelData
            required property int index
            bloc: modelData
            screen: ecranPanneaux.ecran
            definitions: ecranPanneaux.modele.widgets || ({})
            police: ecranPanneaux.modele.police || ""
            teinte: ecranPanneaux.teinte
            placement: ecranPanneaux.places[index] || null
            limiteLargeur: {
                if (modelData.cote !== "start" || modelData.barre.position !== "top") return 0
                const axe = ecranPanneaux.ecran.width
                const marge = Math.round(typeof modelData.barre.margin_ends === "string"
                    ? axe * parseFloat(modelData.barre.margin_ends) / 100 : (modelData.barre.margin_ends ?? 0))
                const bordIle = Math.min(axe / 2 - 120, ecranPanneaux.obstacle.width > 0 ? ecranPanneaux.obstacle.x - 10 : axe / 2)
                return Math.max(80, Math.min(240, bordIle - marge - 130))
            }
            compact: {
                if (modelData.cote !== "end" || modelData.barre.position !== "top") return false
                if (ecranPanneaux.ecran.width < 1450) return true
                const pastilles = Disposition.pastillesCote(modelData.barre, "end")
                let nb = 0
                for (const p of pastilles) nb += p.membres.length
                return nb >= 9
            }
        }
    }
}
