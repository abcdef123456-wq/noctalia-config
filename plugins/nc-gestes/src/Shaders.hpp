#pragma once

#include <hyprland/src/render/Shader.hpp>

namespace NcGestes {
    // Programme de la goutte et emplacements de ses uniformes.
    struct SGoutteShader {
        SP<CShader> shader;
        GLint       tex = -1, canvas = -1, texOrigin = -1, texSize = -1, full = -1, inner = -1, anchor = -1, t = -1, scale = -1, radius = -1;
    };

    // Compile au premier appel (contexte EGL courant requis). nullptr si la compilation a échoué.
    SGoutteShader* goutteShader();
    bool           goutteShaderFailed();
    // Libère le programme ; l'appelant rend le contexte EGL courant.
    void destroyShaders();
}
