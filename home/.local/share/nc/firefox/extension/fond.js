// Couleurs de l'île : l'hôte natif nc_firefox (le script nc-firefox lancé par Firefox) envoie la palette du fond
// d'écran (~/.config/nc/palette-ile.json) au démarrage et à chaque changement ; le thème de Firefox est mis à jour
// aussitôt (browser.theme.update), sans relancer. Si l'hôte manque, nouvel essai toutes les 15 s ; l'extension
// désactivée ou retirée, Firefox revient au thème d'avant tout seul.
// Les thèmes choisis dans Firefox restent prioritaires : les couleurs ne s'appliquent que sur le thème « Système »
// et sur Sombre ou Clair quand il est du même côté que le fond d'écran ; tout autre thème (Alpenglow, un thème
// installé) est laissé tel quel, et l'extension revient dès qu'un thème de base est repris.
"use strict";

const HOTE = "nc_firefox";
const SYSTEME = "default-theme@mozilla.org";
const SOMBRE = "firefox-compact-dark@mozilla.org";
const CLAIR = "firefox-compact-light@mozilla.org";
let port = null;
let palette = null;
let applique = false;    // notre thème est posé : à retirer seulement dans ce cas
let reprise = false;     // thème choisi en train d'être repris : les événements qu'on provoque sont ignorés

async function themeActif() {
  const tous = await browser.management.getAll();
  const t = tous.find((e) => e.type === "theme" && e.enabled);
  return t ? t.id : SYSTEME;
}

async function appliquer() {
  if (!palette || reprise) return;
  const actif = await themeActif();
  const sombre = palette.sombre !== false;
  if (actif === SYSTEME || actif === (sombre ? SOMBRE : CLAIR)) {
    browser.theme.update(theme(palette));
    applique = true;
  } else if (applique) {
    applique = false;
    browser.theme.reset();
    // Après reset(), Firefox (Developer Edition 159) retombait sur son repli clair au lieu du thème choisi (revue
    // EXT-02) : ce thème est repris (désactivé puis réactivé)
    if (actif !== SYSTEME) {
      reprise = true;
      try {
        await browser.management.setEnabled(actif, false);
        await browser.management.setEnabled(actif, true);
      } catch (e) {
        // thème introuvable entre-temps : rien à reprendre
      }
      setTimeout(() => { reprise = false; }, 1000);
    }
  }
}

browser.management.onEnabled.addListener((e) => { if (e.type === "theme") appliquer(); });
browser.management.onDisabled.addListener((e) => { if (e.type === "theme") appliquer(); });

// Au démarrage, Firefox pose son propre thème après nous et la palette était perdue jusqu'au fond d'écran suivant
// (revue EXT-01) : quand un thème qui n'est pas le nôtre arrive sur un thème de base, on réapplique. Pas de boucle :
// le nôtre est reconnu, reset() n'arrive que hors des thèmes de base, et au plus 5 reprises par 10 s.
let reprises = [];
browser.theme.onUpdated.addListener(async ({ theme: t }) => {
  if (!palette || reprise) return;
  const actif = await themeActif();
  const eligible = actif === SYSTEME || actif === (palette.sombre !== false ? SOMBRE : CLAIR);
  const nous = t && t.colors && t.colors.frame === couleur(palette, "fond", "#1c1b22");
  const maintenant = Date.now();
  reprises = reprises.filter((x) => maintenant - x < 10000);
  if (eligible && !nous && reprises.length < 5) {
    reprises.push(maintenant);
    setTimeout(appliquer, 300);
  }
});

function couleur(p, cle, sinon) {
  const v = p[cle];
  return typeof v === "string" && /^#[0-9a-fA-F]{6}$/.test(v) ? v : sinon;
}

// Mélange de deux couleurs #rrggbb : t = part de b (0 à 1)
function melange(a, b, t) {
  const h = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
  const [x, y] = [h(a), h(b)];
  return "#" + x.map((v, i) => Math.round(v + (y[i] - v) * t).toString(16).padStart(2, "0")).join("");
}

function theme(p) {
  const fond = couleur(p, "fond", "#1c1b22");
  const texte = couleur(p, "texte", "#fbfbfe");
  const texteSec = couleur(p, "texteSec", texte);
  const carte = couleur(p, "carte", fond);
  const carteSurvol = couleur(p, "carteSurvol", carte);
  const accent = couleur(p, "accent", "#8a8a8a");
  const surAccent = couleur(p, "surAccent", fond);
  const sombre = p.sombre !== false;
  return {
    colors: {
      frame: fond, frame_inactive: fond, toolbar: fond, toolbar_text: texte,
      tab_selected: melange(fond, texte, 0.16), tab_text: texte, tab_background_text: texteSec, tab_line: accent,
      toolbar_field: carte, toolbar_field_text: texte, toolbar_field_focus: carte, toolbar_field_text_focus: texte,
      toolbar_field_border: fond, toolbar_field_border_focus: accent,
      toolbar_field_highlight: accent, toolbar_field_highlight_text: surAccent,
      popup: fond, popup_text: texte, popup_border: carteSurvol, popup_highlight: melange(fond, texte, 0.18), popup_highlight_text: texte,
      sidebar: fond, sidebar_text: texte, sidebar_border: carte, sidebar_highlight: carteSurvol, sidebar_highlight_text: texte,
      ntp_background: fond, ntp_text: texte, icons: texte, icons_attention: accent,
      button_background_hover: carte, button_background_active: carteSurvol,
      toolbar_bottom_separator: fond, toolbar_top_separator: fond, toolbar_vertical_separator: fond,
    },
    // Pages internes (réglages, modules…) du même côté que la palette : avec "auto", elles suivaient le système et
    // une palette sombre sur un système clair donnait des réglages clairs. Les sites web aussi, avec « Apparence des
    // sites : automatique » (le réglage par défaut) : ils suivent alors le fond d'écran, comme les thèmes Sombre et
    // Clair de Firefox
    properties: { color_scheme: sombre ? "dark" : "light", content_color_scheme: sombre ? "dark" : "light" },
  };
}

function connecter() {
  try {
    port = browser.runtime.connectNative(HOTE);
  } catch (e) {
    setTimeout(connecter, 15000);
    return;
  }
  port.onMessage.addListener((m) => {
    if (m && typeof m === "object" && m.palette) {
      palette = m.palette;
      appliquer();
    }
  });
  port.onDisconnect.addListener(() => {
    port = null;
    setTimeout(connecter, 15000);
  });
  port.postMessage({ demande: "couleurs" });
}

connecter();
