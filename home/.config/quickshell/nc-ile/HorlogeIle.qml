import QtQuick
import "IdentitesIle.js" as Identites

Item {
    id: ensemble
    property var plan: Identites.pour(Couleurs.themeActif)
    property string temps: Etat.heure
    property string jour: Etat.dateCourte
    property bool dateVisible: Reglages.val("ILE_DATE", "oui") !== "non"
    readonly property var composition: plan.cadre(heure.implicitWidth, dateVisible ? date.implicitWidth : 0,
                                                   plan.signe !== "" ? signe.implicitWidth : 0)
    implicitWidth: composition.largeur
    implicitHeight: 30
    objectName: "nc-ile-horloge-" + plan.dessin

    function encre(position, largeur, normale) {
        const centre = position[0] + largeur / 2
        for (const b of composition.blocs) {
            if (b.ton === "plein" && centre >= b.x && centre < b.x + b.largeur
                    && position[1] >= b.y && position[1] < b.y + b.hauteur) return Couleurs.surAccent
        }
        return normale
    }

    Repeater {
        model: ensemble.composition.blocs
        Rectangle {
            required property var modelData
            x: modelData.x; y: modelData.y
            width: modelData.largeur; height: modelData.hauteur
            radius: modelData.rayon
            color: modelData.ton === "plein" || modelData.ton === "encre" ? Couleurs.accent
                 : modelData.ton === "contour" ? "transparent" : Couleurs.surfaceActive
            border.width: modelData.ton === "contour" ? 1 : 0
            border.color: Couleurs.accentBord
        }
    }

    Texte {
        id: heure
        objectName: "nc-ile-repos-heure"
        x: ensemble.composition.temps[0]; y: ensemble.composition.temps[1] - height / 2
        text: ensemble.temps
        font.pixelSize: ensemble.plan.tailles[0]
        font.features: ({ "tnum": 1 })
        font.weight: ensemble.plan.tailles[0] >= 18 ? Font.Black : Font.DemiBold
        color: ensemble.encre(ensemble.composition.temps, implicitWidth, Couleurs.texte)
    }
    Texte {
        id: date
        objectName: "nc-ile-repos-date"
        x: ensemble.composition.date[0]; y: ensemble.composition.date[1] - height / 2
        text: ensemble.jour
        visible: ensemble.dateVisible
        font.pixelSize: ensemble.plan.tailles[1]
        color: ensemble.encre(ensemble.composition.date, implicitWidth, Couleurs.texteDoux)
    }
    Texte {
        id: signe
        x: ensemble.composition.signe[0]; y: ensemble.composition.signe[1] - height / 2
        text: ensemble.plan.signe
        visible: text !== ""
        font.pixelSize: Math.max(1, ensemble.plan.tailles[2])
        font.weight: Font.Bold
        color: ensemble.encre(ensemble.composition.signe, implicitWidth, Couleurs.accentClair)
    }
}
