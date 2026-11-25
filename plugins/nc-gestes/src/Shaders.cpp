#include "Shaders.hpp"

#include <optional>
#include <string>

namespace {
    // Quadrilatère plein cadre : CShader crée le VAO dès qu'il trouve l'attribut « pos » (0..1).
    const std::string VERT = R"GLSL(#version 300 es
precision highp float;
in vec2 pos;
void main() {
    gl_Position = vec4(pos * 2.0 - 1.0, 0.0, 1.0);
}
)GLSL";

    // Toutes les grandeurs sont en pixels du moniteur, origine en haut à gauche, y vers le bas.
    // Le tampon de sortie suit la même orientation que la texture d'entrée : aucune inversion.
    const std::string FRAG = R"GLSL(#version 300 es
precision highp float;

uniform sampler2D tex;
uniform vec2  u_canvas;     // origine du tampon de sortie
uniform vec2  u_texOrigin;  // origine de la texture d'entrée
uniform vec2  u_texSize;    // taille de la texture d'entrée
uniform vec4  u_full;       // boîte complète de la fenêtre (bordure, ombre)
uniform vec4  u_inner;      // surface de la fenêtre, à sa place finale
uniform vec4  u_anchor;     // pilule de l'île
uniform float u_t;          // progression 0..1
uniform float u_scale;      // échelle du moniteur
uniform float u_radius;     // arrondi de la fenêtre

out vec4 fragColor;

const float PI        = 3.14159265;
const float T_RUPTURE = 0.5;
const float LARGEUR_RUPTURE = 0.66; // part de la largeur finale atteinte avant la rupture

float sdBox(vec2 p, vec2 b, float r) {
    r = min(r, min(b.x, b.y));
    vec2 q = abs(p) - b + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

// Union lisse (polynôme cubique) : le liquide se raccorde sans arête.
float smin(float a, float b, float k) {
    k = max(k, 1e-3);
    float h = max(k - abs(a - b), 0.0) / k;
    return min(a, b) - h * h * h * k / 6.0;
}

// Filet vertical de y0 à y1, axe glissant de x0 à x1, demi-largeur a -> b pincée au milieu.
float sdCol(vec2 p, float x0, float y0, float x1, float y1, float a, float b, float pince) {
    float len = y1 - y0;
    if (abs(len) < 0.5 || max(a, b) <= 0.01)
        return 1e5;
    float u     = clamp((p.y - y0) / len, 0.0, 1.0);
    float axe   = mix(x0, x1, smoothstep(0.0, 1.0, u));
    float demi  = mix(a, b, u) * (1.0 - pince * sin(PI * u));
    float dx    = abs(p.x - axe) - demi;
    float dy    = abs(p.y - mix(y0, y1, u));
    vec2  d     = vec2(dx, dy);
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}

// Garde le corps dans la colonne de la fenêtre (donc à l'écran) ; le col s'incline vers lui.
float centreCorps(float x, float largeur, float gauche, float ww) {
    return clamp(x, gauche + largeur * 0.5, gauche + ww - largeur * 0.5);
}

vec4 echantillon(vec2 px) {
    return texture(tex, (px - u_texOrigin) / u_texSize);
}

void main() {
    vec2  p  = u_canvas + gl_FragCoord.xy;
    float s  = u_scale;
    float t  = clamp(u_t, 0.0, 1.0);

    vec2  innerPos  = u_inner.xy;
    vec2  innerSize = max(u_inner.zw, vec2(1.0));
    vec2  innerOff  = innerPos - u_full.xy;
    float ww = innerSize.x, wh = innerSize.y;
    vec2  winC = innerPos + innerSize * 0.5;
    vec2  aC   = u_anchor.xy + u_anchor.zw * 0.5;

    // La goutte pend sous l'île, ou monte au-dessus si la pilule est en bas.
    float dir      = winC.y >= aC.y ? 1.0 : -1.0;
    float bordIle  = dir > 0.0 ? u_anchor.y + u_anchor.w : u_anchor.y;
    float bordFen  = dir > 0.0 ? innerPos.y : innerPos.y + wh;
    float trajet   = abs(bordFen - bordIle);
    float rondFin  = max(u_radius, 22.0 * s);
    float ecartMax = min(68.0 * s, max(28.0 * s, trajet * 0.42));

    float dw, dh, cx, haut, rr, vol;
    float dCol = 1e5, dCap = 1e5, k = 0.0;

    // Collerette sous la pilule ; en grande partie cachée par l'île, au-dessus des fenêtres.
    float retrait = 1.0 - smoothstep(T_RUPTURE, T_RUPTURE + 0.12, t);
    float capDemi = min(u_anchor.z * 0.5 - 4.0 * s, 46.0 * s) * retrait;
    if (capDemi > 0.5)
        dCap = sdBox(p - vec2(aC.x, bordIle - dir * 4.0 * s), vec2(capDemi, 8.0 * s * max(retrait, 0.2)), 6.0 * s);

    if (t <= T_RUPTURE) {
        // Gonflement : la vraie fenêtre grossit sous l'île, avec du volume avant toute rupture.
        float g       = t / T_RUPTURE;
        float bud     = 1.0 - pow(1.0 - g, 3.0);
        float tension = smoothstep(0.24, T_RUPTURE, t);
        k             = pow(tension, 1.35);
        dw   = mix(0.14, LARGEUR_RUPTURE, bud) * ww;
        dh   = dw * (wh / ww) * (1.0 + 0.075 * sin(PI * g));
        float ecart = mix(4.0 * s, ecartMax, bud);
        cx   = centreCorps(mix(aC.x, winC.x, 0.18 * bud), dw, innerPos.x, ww);
        haut = bordIle + dir * ecart;
        rr   = mix(min(dw, dh) * 0.44, rondFin, bud);
        vol  = 1.0;
        // Col : large au départ, il s'amincit jusqu'à un fil avant de céder.
        dCol = sdCol(p, aC.x, bordIle, cx, haut + dir * 2.0 * s, mix(38.0, 5.0, k) * s, mix(34.0, 8.0, k) * s, mix(0.3, 0.92, k));
    } else {
        // Rupture puis chute : la fenêtre rejoint sa place réelle et sa taille réelle.
        float f      = (t - T_RUPTURE) / (1.0 - T_RUPTURE);
        float vol0   = 1.0 - pow(1.0 - f, 4.0);
        float dw0    = LARGEUR_RUPTURE * ww;
        dw   = mix(dw0, ww, vol0);
        dh   = mix(dw0 * wh / ww, wh, vol0) * (1.0 + 0.05 * sin(PI * vol0));
        cx   = mix(centreCorps(mix(aC.x, winC.x, 0.18), dw0, innerPos.x, ww), winC.x, vol0);
        haut = mix(bordIle + dir * ecartMax, bordFen, vol0);
        rr   = mix(rondFin, u_radius, vol0);
        vol  = 1.0 - vol0;
        // Ménisque resté sous l'île et queue du corps qui se résorbent.
        float queue = ecartMax * 0.4 * retrait;
        dCol = min(sdCol(p, aC.x, bordIle, aC.x, bordIle + dir * queue, 5.0 * s * retrait, 0.0, 0.0),
                   sdCol(p, cx, haut + dir * 2.0 * s, cx, haut - dir * queue, 7.0 * s * retrait, 0.0, 0.0));
    }

    vec2  corpsDemi = vec2(dw, dh) * 0.5;
    vec2  corpsC    = vec2(cx, haut + dir * corpsDemi.y);
    vec2  corpsTL   = corpsC - corpsDemi;
    float dCorps    = sdBox(p - corpsC, corpsDemi, rr);
    float d         = smin(dCorps, smin(dCap, dCol, 10.0 * s), mix(28.0, 4.0, k) * s);
    if (t > T_RUPTURE)
        d = min(smin(dCorps, dCol, 8.0 * s), smin(dCap, dCol, 6.0 * s));

    float masque      = 1.0 - smoothstep(-0.75, 0.75, d);
    float masqueCorps = 1.0 - smoothstep(-0.75, 0.75, dCorps);

    // Corps : la boîte complète de la fenêtre, mise à l'échelle pour que sa surface épouse le corps.
    vec2 ech  = vec2(dw, dh) / innerSize;
    vec2 uv   = (p - (corpsTL - innerOff * ech)) / (u_full.zw * ech);
    vec4 cWin = vec4(0.0);
    if (all(greaterThanEqual(uv, vec2(0.0))) && all(lessThanEqual(uv, vec2(1.0))))
        cWin = echantillon(u_full.xy + uv * u_full.zw);
    cWin *= mix(1.0, masqueCorps, vol); // silhouette de goutte, relâchée à l'atterrissage

    // Col et collerette : la bande de la fenêtre tournée vers l'île, sans texte étiré.
    float rx    = clamp((p.x - corpsTL.x) / dw, 0.15, 0.85);
    vec4  cBand = echantillon(innerPos + vec2(rx * ww, (dir > 0.0 ? 0.02 : 0.98) * wh));

    float aCol = masque * (1.0 - masqueCorps);
    fragColor  = cBand * aCol + cWin * (1.0 - aCol); // alpha prémultiplié
}
)GLSL";

    std::optional<NcGestes::SGoutteShader> g_goutte;
    bool                                   g_failed = false;
}

NcGestes::SGoutteShader* NcGestes::goutteShader() {
    if (g_goutte)
        return &*g_goutte;
    if (g_failed)
        return nullptr;

    SGoutteShader s;
    s.shader = makeShared<CShader>();
    // dynamic = true : un échec de compilation rend false au lieu d'arrêter Hyprland.
    if (!s.shader->createProgram(VERT, FRAG, true)) {
        g_failed = true;
        return nullptr;
    }

    const auto PROG = s.shader->program();
    s.tex           = glGetUniformLocation(PROG, "tex");
    s.canvas        = glGetUniformLocation(PROG, "u_canvas");
    s.texOrigin     = glGetUniformLocation(PROG, "u_texOrigin");
    s.texSize       = glGetUniformLocation(PROG, "u_texSize");
    s.full          = glGetUniformLocation(PROG, "u_full");
    s.inner         = glGetUniformLocation(PROG, "u_inner");
    s.anchor        = glGetUniformLocation(PROG, "u_anchor");
    s.t             = glGetUniformLocation(PROG, "u_t");
    s.scale         = glGetUniformLocation(PROG, "u_scale");
    s.radius        = glGetUniformLocation(PROG, "u_radius");
    g_goutte        = std::move(s);
    return &*g_goutte;
}

bool NcGestes::goutteShaderFailed() {
    return g_failed;
}

void NcGestes::destroyShaders() {
    g_goutte.reset();
    g_failed = false;
}
