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
    required property rect obstacleRepos
    property rect empriseLive: obstacle
    property rect empriseStable: obstacle
    property int reserveIleHaut: 0
    readonly property var mouv: Mouvement.pourEcran(ecran ? ecran.name : "")
    readonly property string descriptionEcran: Hyprland.monitorFor(ecran)?.lastIpcObject?.description ?? ""
    readonly property var barresActives: Disposition.barresPourEcran(modele.barres || [], ecran.name, descriptionEcran)
    readonly property var barresContinues: barresActives.filter(b => b.enabled !== false && (b.background_opacity ?? 0) > 0)
    readonly property var barresFlottantes: Disposition.barresFlottantes(barresActives)
    readonly property var reservesMap: Disposition.reserves(barresActives, reserveIleHaut)
    readonly property var reservesListe: ["top", "bottom", "left", "right"]
        .filter(b => reservesMap[b] > 0)
        .map(b => ({ bord: b, zone: reservesMap[b] }))

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
            obstacleRepos: ecranPanneaux.obstacleRepos
            empriseLive: ecranPanneaux.empriseLive
            empriseStable: ecranPanneaux.empriseStable
            mouv: ecranPanneaux.mouv
        }
    }

    Instantiator {
        model: ecranPanneaux.barresFlottantes
        delegate: BarreFlottante {
            required property var modelData
            screen: ecranPanneaux.ecran
            barre: modelData
            definitions: ecranPanneaux.modele.widgets || ({})
            police: ecranPanneaux.modele.police || ""
            teinte: ecranPanneaux.teinte
            empriseLive: ecranPanneaux.empriseLive
            empriseStable: ecranPanneaux.empriseStable
            obstacleRepos: ecranPanneaux.obstacleRepos
            mouv: ecranPanneaux.mouv
        }
    }
}
