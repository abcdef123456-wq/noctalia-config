import QtQuick
import QtQuick.Shapes

Item {
    id: motif
    required property string dessin
    readonly property real cote: Math.min(width, height)
    Shape {
        width: 100; height: 100
        x: (motif.width - width) / 2; y: (motif.height - height) / 2
        scale: Math.max(0, motif.cote / 100)
        ShapePath {
            fillColor: "transparent"
            strokeColor: Couleurs.accent
            strokeWidth: 2.3
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: motif.dessin }
        }
    }
}
