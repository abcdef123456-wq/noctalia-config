// Emblème fourni dans pfp.mp4 : 161 images en 64 ou 128 px, même mouvement et cadence que la vidéo.
// Atlas PNG : QtQuick seul, sans QtMultimedia, codec vidéo ni lecteur externe sur les autres distributions.
import QtQuick

AnimatedSprite {
    id: logo
    objectName: "nc-assistant-logo"
    property bool anime: false
    property bool grand: false
    source: grand ? "assets/jarvis-animation.png" : "assets/assistant-animation.png"
    frameWidth: grand ? 128 : 64
    frameHeight: grand ? 128 : 64
    frameCount: 161
    frameRate: 100 / 3
    interpolate: false
    running: anime && visible
    onRunningChanged: if (!running) currentFrame = 0
}
