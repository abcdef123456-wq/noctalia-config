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

uniform float u_pret;       // goutte : fondu du vrai contenu de la fenêtre, 0..1
uniform vec3  u_surface;    // goutte : surface de la pilule (Émail du thème)
uniform vec3  u_bord;       // goutte : accent du thème, pour le filet

out vec4 fragColor;

const float PI        = 3.14159265;
const float T_RUPTURE = 0.56; // la goutte se détache (maquette email-goutte.html : 0,54)

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

vec4 echantillon(vec2 px) {
    return texture(tex, (px - u_texOrigin) / u_texSize);
}

vec4 fenPx(vec2 px);

// Profil de goutte (capsule inégale) : cercle r1 à l'origine, cercle r2 à (0, h), y vers le haut. Exacte, donc un
// contour net à un pixel près quelle que soit la taille.
float sdGoutte(vec2 q, float r1, float r2, float h) {
    q.x     = abs(q.x);
    float b = (r1 - r2) / h;
    float a = sqrt(max(1.0 - b * b, 0.0));
    float k = dot(q, vec2(-b, a));
    if (k < 0.0)
        return length(q) - r1;
    if (k > a * h)
        return length(q - vec2(0.0, h)) - r2;
    return dot(q, vec2(a, b)) - r1;
}

// Col en sablier, vertical de y0 à y1 : demi-largeur a en haut, b en bas, w au pincement (à la fraction uw).
float sdCou(vec2 p, float x, float y0, float y1, float a, float b, float w, float uw) {
    float len = y1 - y0;
    if (len < 0.5)
        return 1e5;
    float u    = clamp((p.y - y0) / len, 0.0, 1.0);
    float demi = u < uw ? mix(a, w, smoothstep(0.0, 1.0, u / uw)) : mix(w, b, smoothstep(0.0, 1.0, (u - uw) / (1.0 - uw)));
    vec2  d    = vec2(abs(p.x - x) - demi, max(y0 - p.y, p.y - y1));
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}

// Ressort amorti (dépassement d'environ 2,5 %, posé à x = 1).
float ressort(float x) {
    return 1.0 - exp(-7.0 * x) * (cos(6.0 * x) + 1.1667 * sin(6.0 * x));
}

// Corps de la goutte, posé par goutte() et relu pour l'ombre. Repère local : x de l'écran, y compté depuis le bord de
// l'île vers la fenêtre (la goutte pend toujours « vers le bas », même sous une pilule en bas d'écran).
vec2  gC;    // centre du grand cercle, puis de la fenêtre qui s'ouvre
float gR1;   // rayon du bulbe
float gRH;   // rayon du haut, côté col
float gH;    // écart des deux centres
vec2  gEt;   // étirement de la chute
vec2  gDemi; // demi-taille de la fenêtre qui s'ouvre
float gRR;   // son arrondi
float gM;    // 0 goutte -> 1 fenêtre

float corps(vec2 L) {
    vec2  q  = (L - gC) / gEt;
    float dG = sdGoutte(vec2(q.x, -q.y), gR1, gRH, gH) * min(gEt.x, gEt.y);
    if (gM <= 0.0)
        return dG;
    return mix(dG, sdBox(L - gC, gDemi, gRR), gM);
}

// 1 · Goutte (rose-aube) : une goutte de l'émail de l'île gonfle sous la pilule, pend à un col qui s'amincit en
// sablier, se pince et se détache (une gouttelette suit), tombe en s'étirant un peu, puis s'ouvre en fenêtre à sa place
// sur un ressort amorti. Le vrai contenu entre en fondu dès que l'appli l'a dessiné.
vec4 goutte(vec2 p, float t) {
    float s    = u_scale;
    vec2  iS   = max(u_inner.zw, vec2(1.0));
    float ww   = iS.x, wh = iS.y;
    vec2  winC = u_inner.xy + iS * 0.5;
    vec2  aC   = u_anchor.xy + u_anchor.zw * 0.5;

    // La goutte pend sous l'île, ou monte au-dessus si la pilule est en bas.
    float dir     = winC.y >= aC.y ? 1.0 : -1.0;
    float bordIle = dir > 0.0 ? u_anchor.y + u_anchor.w : u_anchor.y;
    vec2  L       = vec2(p.x, (p.y - bordIle) * dir);
    vec2  wC      = vec2(winC.x, (winC.y - bordIle) * dir);

    // Bulbe à la rupture : un tiers de la largeur, rond, jamais plus grand que la fenêtre.
    float R  = 0.5 * min(clamp(0.34 * ww, 80.0 * s, 320.0 * s), 0.6 * min(ww, wh));
    float Lc = clamp(0.55 * R, 22.0 * s, 80.0 * s); // col au plus long (maquette : un quart du bulbe)

    float g       = clamp(t / T_RUPTURE, 0.0, 1.0);
    float gonfle  = smoothstep(0.0, 0.85, g);
    float poids   = smoothstep(0.55, 1.0, g);
    float tension = pow(smoothstep(0.4, 1.0, g), 1.3);
    bool  casse   = t > T_RUPTURE;
    float f       = clamp((t - T_RUPTURE) / (1.0 - T_RUPTURE), 0.0, 1.0);
    float recul   = smoothstep(0.0, 0.22, f);   // la queue rentre dans la goutte, qui s'arrondit
    float xc      = clamp(f / 0.72, 0.0, 1.0);
    float chute   = xc * xc * (3.0 - 2.0 * xc);
    float xo      = clamp((f - 0.16) / 0.84, 0.0, 1.0);
    float ouvre   = ressort(xo);
    // La goutte, déjà ronde après le recul, devient une boîte arrondie (un disque) qui s'ouvre en fenêtre.
    gM            = casse ? smoothstep(0.0, 0.18, f) : 0.0;

    // Goutte suspendue : elle gonfle, puis s'alourdit (le haut s'affine, le col s'allonge). Après la rupture, valeurs
    // de la rupture (g = 1).
    float r1   = mix(4.0 * s, R, gonfle) * (1.0 + 0.04 * poids);
    float rH   = r1 * mix(0.6, 0.38, poids);
    float h    = r1 * mix(0.2, 0.55, poids);
    float col  = mix(4.0 * s, Lc, gonfle) * (1.0 + 0.35 * poids);
    float cBas = col + rH + h;
    if (casse) {
        rH = mix(rH, r1 * 0.9, recul);
        h  = mix(h, r1 * 0.12, recul);
    }
    gR1 = r1;
    gRH = rH;
    gH  = max(h, abs(r1 - rH) + 0.5);
    gC  = casse ? mix(vec2(aC.x, cBas), wC, chute) : vec2(aC.x, cBas);
    float et = 4.0 * xc * (1.0 - xc) * (1.0 - clamp(ouvre, 0.0, 1.0));
    gEt      = vec2(1.0 - 0.08 * et, 1.0 + 0.16 * et);
    gDemi    = mix(vec2(r1), iS * 0.5, ouvre) * gEt;
    gRR      = mix(min(gDemi.x, gDemi.y), u_radius, smoothstep(0.0, 0.7, clamp(ouvre, 0.0, 1.0)));

    float dCorps = corps(L);

    // Collerette sous la pilule (cachée par l'île, l'île est au-dessus des fenêtres), col, restes de la rupture.
    float capDemi = clamp(u_anchor.z * 0.5 - u_anchor.w * 0.5, 2.0 * s, 30.0 * s) * (0.7 + 0.3 * gonfle);
    float d, dEclats = 1e5;
    if (!casse) {
        // Col en sablier : large contre la pilule, il s'évase dans l'épaule du bulbe et se pince entre les deux.
        float a      = min(u_anchor.z * 0.2, 26.0 * s) * mix(1.0, 0.55, tension);
        float b      = rH * mix(0.9, 0.7, tension);
        float taille = mix(min(a, b) * 0.6, 0.35, tension); // jusqu'à un fil d'un demi-pixel avant de céder
        float dCou   = sdCou(L, aC.x, -6.0 * s, col + rH * 0.6, a, b, taille, 0.6);
        float dCap   = sdBox(L - vec2(aC.x, -8.0 * s), vec2(capDemi, 6.0 * s), 6.0 * s);
        d            = smin(smin(dCorps, dCou, mix(28.0, 8.0, tension) * s), dCap, 12.0 * s);
    } else {
        float reste = 1.0 - smoothstep(0.0, 0.15, f);
        float dCap  = sdBox(L - vec2(aC.x, -8.0 * s), vec2(capDemi * mix(1.0, 0.6, recul), 6.0 * s), 6.0 * s);
        float bout  = col * 0.2 * reste; // ménisque qui remonte dans la pilule
        float dBout = reste > 0.01 ? length(L - vec2(aC.x, clamp(L.y, -6.0 * s, bout))) - 5.0 * s * reste : 1e5;
        // Gouttelette née au pincement, qui suit plus lentement et se résorbe.
        float rs   = max(r1 * 0.035, 2.5 * s) * (1.0 - smoothstep(0.25, 0.6, f));
        vec2  cs   = vec2(mix(aC.x, gC.x, 0.5 * chute), -6.0 * s + 0.6 * (col + 0.23 * r1 + 6.0 * s) + (gC.y - cBas) * 0.5);
        float dSat = rs > 0.2 ? length(L - cs) - rs : 1e5;
        dEclats    = min(dSat, smin(dCap, dBout, 6.0 * s));
        d          = min(dCorps, dEclats);
    }

    float M  = 1.0 - smoothstep(-0.5, 0.5, d);      // anticrénelage sur un pixel physique
    float Mc = 1.0 - smoothstep(-0.5, 0.5, dCorps);

    // Émail : la surface de la pilule, teintée de l'accent (un peu plus sur un thème sombre, où elle se fondrait dans le
    // fond), une lumière douce en haut (comme l'île fermée).
    bool  sombre = dot(u_surface, vec3(0.299, 0.587, 0.114)) < 0.5;
    vec3  S      = mix(u_surface, u_bord, sombre ? 0.14 : 0.08);
    float haut   = gC.y - mix(gH + gRH, gDemi.y, gM);
    float rel    = clamp((L.y - haut) / max(mix(gH + gRH + gR1, 2.0 * gDemi.y, gM), 1.0), 0.0, 1.0);
    vec3  c      = mix(S, vec3(1.0), (sombre ? 0.12 : 0.3) * (1.0 - smoothstep(0.0, 0.6, rel)));
    // Ménisque et gouttelette, trop petits pour un filet : plus soutenus pour rester visibles.
    c            = mix(c, mix(S, u_bord, 0.5), (1.0 - smoothstep(-0.5, 0.5, dEclats)) * (1.0 - Mc));

    // Vrai contenu, une fois dessiné par l'appli : dans la goutte qui tombe, sans déformation (il la couvre, sans
    // bordure), puis exact quand la fenêtre se pose.
    float cyL  = mix(gC.y + 0.5 * (gR1 - gH - gRH) * gEt.y, gC.y, gM);
    vec2  ech  = mix(vec2(gR1, 0.5 * (gH + gRH + gR1)) * gEt, gDemi, gM) / (iS * 0.5);
    vec2  cR   = vec2(gC.x, bordIle + dir * cyL);
    vec2  q    = (p - cR) / mix(vec2(max(ech.x, ech.y)), ech, smoothstep(0.5, 1.0, clamp(ouvre, 0.0, 1.0))) + winC;
    vec4  cw   = fenPx(clamp(q, u_inner.xy + 1.0, u_inner.xy + iS - 1.0));
    float cA   = u_pret * smoothstep(T_RUPTURE - 0.1, T_RUPTURE + 0.12, t) * Mc;
    c          = c * (1.0 - cA * cw.a) + cA * cw.rgb;

    // Filet fin de l'accent et reflet en haut : la goutte se lit sur un thème clair comme sur un sombre. Ils s'effacent
    // quand la fenêtre se pose.
    float arete  = 1.0 - smoothstep(0.8, 0.95, t);
    float filet  = 1.0 - smoothstep(0.6 * s, 1.4 * s, -(casse ? dCorps : d));
    c            = mix(c, mix(S, u_bord, sombre ? 0.8 : 0.7), filet * (sombre ? 0.85 : 0.6) * arete);
    float bande  = smoothstep(1.0 * s, 1.8 * s, -dCorps) * (1.0 - smoothstep(2.0 * s, 3.0 * s, -dCorps));
    c            = mix(c, mix(S, vec3(1.0), sombre ? 0.4 : 0.85), bande * (1.0 - smoothstep(0.0, 0.3, rel)) * 0.8 * arete);

    // Ombre douce du corps, vers le bas de l'écran.
    vec2  pO    = p - vec2(0.0, 8.0 * s);
    float dO    = corps(vec2(pO.x, (pO.y - bordIle) * dir));
    float ombre = (sombre ? 0.32 : 0.22) * (1.0 - smoothstep(-6.0 * s, 20.0 * s, dO)) * clamp(r1 / (20.0 * s), 0.0, 1.0) * arete;

    vec4 res = vec4(c, 1.0) * M + vec4(0.0, 0.0, 0.0, ombre) * (1.0 - M); // alpha prémultiplié
    // Fin : la vraie fenêtre (bordure et ombre comprises), au pixel près.
    return mix(res, fenPx(p), smoothstep(0.86, 1.0, t));
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
    s.pret          = glGetUniformLocation(PROG, "u_pret");
    s.surface       = glGetUniformLocation(PROG, "u_surface");
    s.bord          = glGetUniformLocation(PROG, "u_bord");
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
