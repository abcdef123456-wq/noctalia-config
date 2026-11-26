#pragma once

#include <hyprland/src/render/Shader.hpp>

namespace NcGestes {
    // Programme des gestes (un seul, choisi par u_mode) et emplacements de ses uniformes.
    struct SGesteShader {
        SP<CShader> shader;
        GLint tex = -1, canvas = -1, texOrigin = -1, texSize = -1, full = -1, inner = -1, anchor = -1, t = -1, scale = -1, radius = -1, mode = -1;
    };

    // Compile au premier appel (contexte EGL courant requis). nullptr si la compilation a échoué.
    SGesteShader* gesteShader();
    bool          gesteShaderFailed();
    // Libère le programme ; l'appelant rend le contexte EGL courant.
    void destroyShaders();
}
