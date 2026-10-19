// Emblème fourni dans pfp.mp4 : 161 images de 64 px, même mouvement et cadence que la vidéo.
// Atlas PNG : QtQuick seul, sans QtMultimedia, codec vidéo ni lecteur externe sur les autres distributions.
import QtQuick

AnimatedSprite {
    id: logo
    objectName: "nc-assistant-logo"
    property bool anime: false
    source: "assets/assistant-animation.png"
    frameWidth: 64
    frameHeight: 64
    frameCount: 161
    frameRate: 100 / 3
    interpolate: false
    running: anime && visible
    onRunningChanged: if (!running) currentFrame = 0
}
