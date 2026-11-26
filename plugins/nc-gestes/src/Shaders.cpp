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
uniform int   u_mode;       // geste : 1 goutte, 2..14 voir geste()

out vec4 fragColor;

const float PI        = 3.14159265;
const float T_RUPTURE = 0.6;
const float LARGEUR_RUPTURE = 0.8;  // part de la largeur finale atteinte avant la rupture
const float ETIREMENT   = 0.18;     // hauteur gagnée sous son poids juste avant la rupture
const float AFFAISSEMENT = 0.3;     // le col s'allonge d'autant pendant que la goutte s'alourdit

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

// 1 · Goutte (rose-aube) : née sous l'île, elle pend à un col liquide, se détache et tombe à sa place.
vec4 goutte(vec2 p, float t) {
    float s  = u_scale;

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

    // Collerette sous la pilule ; en grande partie cachée par l'île, au-dessus des fenêtres. Elle s'enfle avec la goutte.
    float retrait = 1.0 - smoothstep(T_RUPTURE, T_RUPTURE + 0.12, t);
    float enfle   = 1.0 + 0.22 * sin(PI * clamp(t / T_RUPTURE, 0.0, 1.0));
    float capDemi = min(u_anchor.z * 0.5 - 4.0 * s, 46.0 * s) * enfle * retrait;
    if (capDemi > 0.5)
        dCap = sdBox(p - vec2(aC.x, bordIle - dir * 4.0 * s), vec2(capDemi, 8.0 * s * max(retrait, 0.2)), 6.0 * s);

    if (t <= T_RUPTURE) {
        // Gonflement : la vraie fenêtre grossit sous l'île, puis pend en s'alourdissant pendant que le col s'amincit.
        float g       = t / T_RUPTURE;
        float bud     = 1.0 - pow(1.0 - g, 3.0);
        float poids   = smoothstep(0.35, 1.0, g);
        float tension = smoothstep(0.3, T_RUPTURE, t);
        k             = pow(tension, 1.35);
        dw   = mix(0.14, LARGEUR_RUPTURE, bud) * ww;
        dh   = dw * (wh / ww) * (1.0 + ETIREMENT * poids);
        float ecart = mix(4.0 * s, ecartMax, bud) * (1.0 + AFFAISSEMENT * poids);
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
        dh   = mix(dw0 * wh / ww * (1.0 + ETIREMENT), wh, vol0) * (1.0 + 0.05 * sin(PI * vol0));
        cx   = mix(centreCorps(mix(aC.x, winC.x, 0.18), dw0, innerPos.x, ww), winC.x, vol0);
        haut = mix(bordIle + dir * ecartMax * (1.0 + AFFAISSEMENT), bordFen, vol0);
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
    return cBand * aCol + cWin * (1.0 - aCol); // alpha prémultiplié
}

// ---- Gestes 2 à 14 : la fenêtre reste dans son cadre ----

float eo(float x) {
    x = clamp(x, 0.0, 1.0);
    return 1.0 - pow(1.0 - x, 3.0);
}

float segment(vec2 p, vec2 a, vec2 b) {
    vec2  pa = p - a, ba = b - a;
    float h  = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-4), 0.0, 1.0);
    return length(pa - ba * h);
}

float hash(float n) {
    return fract(sin(n * 12.9898) * 43758.5453);
}

float bayer4(vec2 cellule) {
    int m[16] = int[16](0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5);
    return float(m[int(mod(cellule.y, 4.0)) * 4 + int(mod(cellule.x, 4.0))]);
}

// Fenêtre (bordure et ombre comprises) au pixel px, transparente hors de sa boîte complète.
vec4 fenPx(vec2 px) {
    if (any(lessThan(px, u_full.xy)) || any(greaterThan(px, u_full.xy + u_full.zw)))
        return vec4(0.0);
    return echantillon(px);
}

// Même chose en coordonnées normalisées de la surface (0..1 = la surface, au-delà : bordure et ombre).
vec4 fen(vec2 q) {
    return fenPx(u_inner.xy + q * max(u_inner.zw, vec2(1.0)));
}

// Couleur de la bordure de la fenêtre (donc du thème), opaque et lisible ; gris clair si elle n'en a pas.
vec4 accent() {
    vec4 c = echantillon(vec2(u_inner.x + u_inner.z * 0.5, u_inner.y - 0.75 * u_scale));
    if (c.a < 0.3)
        return vec4(0.85, 0.85, 0.85, 1.0);
    vec3 rgb = c.rgb / c.a;
    if (dot(rgb, vec3(0.299, 0.587, 0.114)) < 0.2)
        rgb = mix(rgb, vec3(1.0), 0.6);
    return vec4(rgb, 1.0);
}

// Teinte une couleur prémultipliée sans toucher à son alpha (ni le dépasser).
vec4 teinte(vec4 c, float f) {
    return vec4(min(c.rgb * f, vec3(c.a)), c.a);
}

vec4 geste(int mode, vec2 p, float t) {
    float s  = u_scale;
    vec2  iS = max(u_inner.zw, vec2(1.0));
    vec2  q  = (p - u_inner.xy) / iS;
    vec2  winC = u_inner.xy + iS * 0.5;
    float e  = eo(t);
    float apparait = smoothstep(0.0, 0.18, t);

    if (mode == 2) {
        // Paravent (sakura) : deux volets pliés sur la ligne médiane se déplient vers le haut et vers le bas.
        float c = sin(e * PI * 0.5);
        if (c < 1e-3)
            return vec4(0.0);
        float dq  = q.y - 0.5;
        float src = dq / c;
        float d   = clamp(abs(src) / 0.5, 0.0, 1.0);
        float wf  = 1.0 + 0.12 * (1.0 - c) * d;
        float pli = exp(-abs(dq) * iS.y / (6.0 * s));
        vec4  col = fen(vec2(0.5 + (q.x - 0.5) / wf, 0.5 + src));
        return teinte(col, (1.0 - 0.45 * (1.0 - c) * d) * (1.0 - 0.25 * (1.0 - c) * pli)) * apparait;
    }
    if (mode == 3) {
        // Plan de coupe (solarized-clair) : deux repères en L tracent le cadre, puis le contenu le remplit en diagonale.
        float lp = eo(t / 0.55);
        vec2  a  = u_inner.xy, b = u_inner.xy + iS;
        float dl = min(min(segment(p, a, a + vec2(lp * iS.x, 0.0)), segment(p, a, a + vec2(0.0, lp * iS.y))),
                       min(segment(p, b, b - vec2(lp * iS.x, 0.0)), segment(p, b, b - vec2(0.0, lp * iS.y))));
        float trait  = (1.0 - smoothstep(0.75 * s - 0.5, 0.75 * s + 0.5, dl)) * (1.0 - smoothstep(0.8, 1.0, t));
        float f      = smoothstep(0.4, 1.0, t) * 1.3;
        float rempli = 1.0 - smoothstep(f - 0.1, f, (q.x + q.y) * 0.5);
        return accent() * trait + fen(q) * rempli * (1.0 - trait);
    }
    if (mode == 4) {
        // Horizon (nord) : la fenêtre remonte de derrière la ligne de son bord bas.
        if (p.y > u_inner.y + iS.y + 2.0 * s)
            return vec4(0.0);
        return fenPx(p - vec2(0.0, (1.0 - e) * 0.45 * iS.y)) * apparait;
    }
    if (mode == 5) {
        // Marée (ocean) : une ligne d'eau ondulante monte et découvre le contenu.
        float niveau = 1.12 - e * 1.3;
        float vague  = (0.02 * sin(q.x * 9.0 + t * 7.0) + 0.008 * sin(q.x * 23.0 - t * 11.0)) * (1.0 - t);
        float bord   = 6.0 * s / iS.y;
        return fen(q) * smoothstep(niveau + vague - bord, niveau + vague + bord, q.y);
    }
    if (mode == 6) {
        // Éventail (everforest) : les lames s'écartent depuis le milieu du bord bas.
        vec2  P    = vec2(winC.x, u_inner.y + iS.y);
        vec2  v    = p - P;
        float phi  = atan(v.x, -v.y);
        float phiS = phi / max(e, 1e-3);
        if (abs(phiS) > PI * 0.5 && e < 0.999)
            return vec4(0.0);
        float lame  = (phiS / PI + 0.5) * 5.0;
        float bordL = min(fract(lame), 1.0 - fract(lame));
        vec4  col   = fenPx(P + length(v) * vec2(sin(phiS), -cos(phiS)));
        return teinte(col, 1.0 - 0.35 * (1.0 - e) * (1.0 - smoothstep(0.0, 0.08, bordL))) * apparait;
    }
    if (mode == 7) {
        // Rideau (catppuccin) : un velours plissé s'ouvre depuis le centre et se tend.
        float sx    = max(e, 1e-3);
        float srcX  = 0.5 + (q.x - 0.5) / sx;
        float plis  = 1.0 - 0.18 * (1.0 - e) * (0.5 + 0.5 * cos(srcX * PI * 14.0));
        float reste = 0.5 * sx * u_full.z - abs(p.x - (u_full.x + 0.5 * u_full.z));
        float doux  = smoothstep(0.0, 10.0 * s * (1.0 - e) + 0.5, reste);
        return teinte(fen(vec2(srcX, q.y)), plis) * doux * apparait;
    }
    if (mode == 8) {
        // Ligne cathodique (vaporwave) : un trait s'étire en largeur, puis s'ouvre en écran, sans éclair blanc.
        float wl = eo(t / 0.35);
        float hp = eo((t - 0.35) / 0.65);
        float hf = max(mix(2.0 * s / iS.y, 1.0, hp), 1e-4);
        if (abs(p.x - (u_full.x + 0.5 * u_full.z)) > wl * 0.5 * u_full.z)
            return vec4(0.0);
        float balayage = 1.0 - 0.22 * (1.0 - hp) * (0.5 + 0.5 * sin(p.y * PI / (1.5 * s)));
        return teinte(fen(vec2(q.x, 0.5 + (q.y - 0.5) / hf)), balayage);
    }
    if (mode == 9) {
        // Point de fuite (synthwave) : la fenêtre avance depuis l'horizon, en perspective qui se redresse.
        float sc = mix(0.18, 1.0, e);
        vec2  c  = mix(vec2(winC.x, u_inner.y + 0.1 * iS.y), winC, e);
        float ny = (p.y - (c.y - 0.5 * sc * iS.y)) / (sc * iS.y);
        float wf = mix(mix(0.55, 1.0, e), 1.0, clamp(ny, 0.0, 1.0));
        return fen(vec2(0.5 + (p.x - c.x) / (sc * iS.x * wf), ny)) * apparait;
    }
    if (mode == 10) {
        // Vantaux (dracula) : deux battants pivotent sur les bords extérieurs, une ombre marque la fente.
        float c = sin(e * PI * 0.5);
        if (c < 1e-3)
            return vec4(0.0);
        bool  gauche = q.x < 0.5;
        float x      = gauche ? q.x : 1.0 - q.x;
        if (x > 0.5 * c)
            return vec4(0.0);
        float src   = x / c;
        float d     = clamp(src / 0.5, 0.0, 1.0);
        float hs    = 1.0 - 0.14 * (1.0 - c) * d;
        float fente = exp(-(0.5 * c - x) * iS.x / (8.0 * s));
        vec4  col   = fen(vec2(gauche ? src : 1.0 - src, 0.5 + (q.y - 0.5) / hs));
        return teinte(col, (1.0 - 0.4 * (1.0 - c) * d) * (1.0 - 0.45 * (1.0 - c) * fente));
    }
    if (mode == 11) {
        // Balayage (matrice) : un front tramé (Bayer 4 × 4) révèle la fenêtre de gauche à droite.
        float bande = 64.0 * s / iS.x;
        float front = smoothstep(0.0, 1.0, t) * (1.0 + 2.0 * bande) - bande;
        float u     = (front - q.x) / bande;
        float seuil = (bayer4(floor(p / (4.0 * s))) + 0.5) / 16.0;
        return fen(q) * (u >= 1.0 ? 1.0 : (u <= 0.0 ? 0.0 : step(seuil, u)));
    }
    if (mode == 12) {
        // Averse (pluie-verte) : lignes de 18 px révélées de haut en bas, colonnes légèrement décalées.
        float ligne = 18.0 * s;
        float r     = floor((p.y - u_inner.y) / ligne);
        float n     = max(ceil(iS.y / ligne), 1.0);
        float pc    = clamp((t - hash(floor((p.x - u_inner.x) / (36.0 * s))) * 0.15) / 0.85, 0.0, 1.0);
        float front = pc * (n + 1.0);
        float m     = step(r + 1.0, front);
        float tete  = m * step(front, r + 2.0);
        return teinte(fen(q) * m, 1.0 + 0.18 * tete * (1.0 - t));
    }
    if (mode == 13) {
        // Deux paliers (retro) : une bande s'élargit, puis s'étend en hauteur, par crans.
        float w = floor(eo(t / 0.42) * 6.0) / 6.0;
        float h = mix(0.12, 1.0, floor(eo((t - 0.45) / 0.55) * 6.0) / 6.0);
        vec2  d = abs(q - 0.5);
        bool  dedans = (w >= 1.0 || d.x <= w * 0.5) && (h >= 1.0 || d.y <= h * 0.5);
        return dedans ? fen(q) : vec4(0.0);
    }
    if (mode == 14) {
        // Contour (oled) : le filet du contour se trace depuis le haut, puis le contenu apparaît dedans.
        float d     = sdBox(p - winC, iS * 0.5, u_radius);
        float trait = 1.0 - smoothstep(0.75 * s - 0.5, 0.75 * s + 0.5, abs(d));
        float a     = abs(atan(p.x - winC.x, -(p.y - winC.y))) / PI;
        trait *= step(a, eo(t / 0.48)) * (1.0 - smoothstep(0.75, 1.0, t));
        return accent() * trait + fen(q) * smoothstep(0.35, 1.0, t) * (1.0 - trait);
    }
    return fen(q);
}

void main() {
    vec2  p = u_canvas + gl_FragCoord.xy;
    float t = clamp(u_t, 0.0, 1.0);
    fragColor = u_mode == 1 ? goutte(p, t) : geste(u_mode, p, t);
}
)GLSL";

    std::optional<NcGestes::SGesteShader> g_geste;
    bool                                  g_failed = false;
}

NcGestes::SGesteShader* NcGestes::gesteShader() {
    if (g_geste)
        return &*g_geste;
    if (g_failed)
        return nullptr;

    SGesteShader s;
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
    s.mode          = glGetUniformLocation(PROG, "u_mode");
    g_geste         = std::move(s);
    return &*g_geste;
}

bool NcGestes::gesteShaderFailed() {
    return g_failed;
}

void NcGestes::destroyShaders() {
    g_geste.reset();
    g_failed = false;
}
