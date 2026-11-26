.pragma library

// Les découpes de repos occupent 30 px, les cartouches 32 px. La page garde une marge sûre pour les commandes.
// Chaque thème dessine sa propre silhouette et les aplats/traits de son cartouche. L'heure et la date ont leurs
// propres positions : t, d et s sont les largeurs mesurées de l'heure, de la date (0 si masquée) et du signe.
function composition(largeur, tx, ty, dx, dy, sx, sy, blocs = []) {
    return { largeur, temps: [tx, ty], date: [dx, dy], signe: [sx, sy], blocs }
}
function bloc(x, y, largeur, hauteur, rayon, ton) {
    return { x, y, largeur, hauteur, rayon, ton }
}
function cartouche(aplat, traits = "") { return { aplat, traits } }
function disque(x, y, r) {
    return `M${x-r},${y} a${r},${r} 0 1,0 ${2*r},0 a${r},${r} 0 1,0 ${-2*r},0 Z`
}
function matrice(w) {
    let points = ""
    for (let x = 10; x < w - 6; x += 7) {
        const col = (x - 10) / 7
        for (let ligne = 0; ligne < 4; ligne++) {
            if (Math.abs(x - w/2) < 48 && ligne > 0) continue
            if ((col + ligne * 3) % 7 !== 2)
                points += disque(x, 5 + ligne * 7, (col + ligne) % 4 === 0 ? 2.6 : 1.65)
        }
    }
    return points
}

const plans = {
    "penombre": {
        dessin: "pliage", tailles: [16, 10, 12], signe: "◇", titre: "droite",
        repos: (w,h) => `M0,0 H${w} L${w-5},${h-7} L${w-23},${h} H19 L5,${h-5} Z`,
        page: (w,h) => `M0,0 H${w} V${h-24} L${w-23},${h} H17 L0,${h-16} Z`,
        carte: w => cartouche(`M0,3 L${w*.28},7 L${w*.38},23 L${w*.49},8 L${w*.58},4 L${w*.4},31 L${w*.21},18 Z`, `M4,4 L${w*.38},23 L${w*.4},31 M${w*.58},25 H${w-13}`),
        cadre: (t,d,s) => composition(t+s+14+(d ? d+16 : 0), 3,15, t+s+24,17, t+11,10,
            [bloc(t+7,20,s+6,2,0,"encre")])
    },
    "noctalia": {
        dessin: "halo", tailles: [16, 11, 13], signe: "◉", titre: "centre",
        repos: (w,h) => `M23,1 H${w-22} C${w-2},1 ${w-1},7 ${w-2},15 Q${w-4},${h-1} ${w-24},${h-1} H20 Q1,${h-1} 1,16 Q1,1 23,1 Z`,
        page: (w,h) => `M44,0 H${w-44} C${w-10},0 ${w},11 ${w},37 V${h-32} Q${w},${h} ${w-33},${h} H33 Q0,${h} 0,${h-33} V37 C0,11 10,0 44,0 Z`,
        carte: w => cartouche(`M14,19 Q${w*.23},-9 ${w*.42},6 Q${w/2},8 ${w*.58},6 Q${w*.77},-9 ${w-14},19 Q${w*.72},34 ${w/2},29 Q${w*.28},34 14,19 Z`, `M24,19 Q${w*.26},5 ${w*.37},11 M${w*.63},11 Q${w*.74},5 ${w-24},19`),
        cadre: (t,d,s) => composition(s+8+t+(d ? d+12 : 0), s+8,15, s+20+t,15, 0,15)
    },
    "apple": {
        dessin: "verre", tailles: [16, 11, 0], signe: "", titre: "centre",
        repos: (w,h) => `M0,0 H${w} V5 C${w},${h-5} ${w-11},${h} ${w-29},${h} H29 C11,${h} 0,${h-5} 0,5 Z`,
        page: (w,h) => `M0,0 H${w} V${h-49} C${w},${h-12} ${w-20},${h} ${w-51},${h} H51 C20,${h} 0,${h-12} 0,${h-49} Z`,
        carte: w => cartouche(`M0,0 H${w} V7 Q${w},27 ${w-26},27 H26 Q0,27 0,7 Z M16,10 Q11,15 16,20 H50 Q55,15 50,10 Z M${w-16},10 Q${w-11},15 ${w-16},20 H${w-50} Q${w-55},15 ${w-50},10 Z`, `M68,6 Q${w/2},2 ${w-68},6 M80,24 Q${w/2},29 ${w-80},24`),
        cadre: (t,d) => composition(t+(d ? d+21 : 0), 0,15, t+16,15, 0,15, d ? [bloc(t+11,5,d+10,20,10,"verre")] : [])
    },
    "oled": {
        dessin: "obturateur", tailles: [17, 10, 12], signe: "◧", titre: "droite",
        repos: (w,h) => `M13,1 H${w-20} V${h-1} H13 Q1,${h-1} 1,${h-13} V13 Q1,1 13,1 Z M${w-14},4 H${w-11} Q${w-1},4 ${w-1},14 V16 Q${w-1},${h-4} ${w-11},${h-4} H${w-14} Z`,
        page: (w,h) => `M20,1 H${w-9} V${h-1} H20 Q1,${h-1} 1,${h-20} V20 Q1,1 20,1 Z M${w-5},18 Q${w},28 ${w},38 V${h-38} Q${w},${h-28} ${w-5},${h-18} Z`,
        carte: w => cartouche(`M12,6 H${w*.55} V27 H12 Z M${w*.55+6},9 H${w-25} V24 H${w*.55+6} Z`, `M16,12 H${w*.48} M16,20 H${w*.34} M${w-6},26 V60`),
        cadre: (t,d,s) => composition(s+10+t+(d ? d+6 : 0), s+9,14, s+t+14,20, 0,14, [bloc(s+5,3,1,23,0,"encre")])
    },
    "clair-neutre": {
        dessin: "index", tailles: [14, 9, 13], signe: "№", titre: "droite",
        repos: (w,h) => `M25,1 H${w-3} V${h-1} H1 V18 C1,8 12,1 25,1 Z`,
        page: (w,h) => `M60,0 H${w} V${h-12} L${w-12},${h} H0 V43 Q5,0 60,0 Z`,
        carte: w => cartouche(`M7,25 Q11,4 53,4 H${w*.46} V32 H7 Z M${w*.46+9},6 H${w-9} V31 H${w*.46+9} Z`, `M19,25 H${w*.46-10} M30,12 H${w*.42} M${w*.46+4},4 V32`),
        cadre: (t,d,s) => composition(s+18+Math.max(d,t), s+18,d ? 21 : 15, s+18,7, 2,15, [bloc(0,2,s+7,26,2,"verre")])
    },
    "brutaliste": {
        dessin: "monolithe", tailles: [19, 10, 11], signe: "01", titre: "droite",
        repos: (w,h) => `M1,1 H${w-22} V6 H${w-1} V${h-1} H16 V${h-5} H1 Z`,
        page: (w,h) => `M0,0 H${w-44} V9 H${w} V${h-18} H${w-14} V${h} H32 V${h-7} H0 Z`,
        carte: w => cartouche(`M0,0 H${w*.44} V12 H${w*.55} V31 H0 Z M${w*.60},13 H${w-5} V31 H${w*.60} Z`, `M8,8 H${w*.43} M8,15 H${w*.29} M8,24 H${w*.49} M${w-10},${32} V54`),
        cadre: (t,d,s) => composition(s+13+t+(d ? d+8 : 0), s+12,14, s+t+20,18, 3,14, [bloc(0,1,s+7,26,0,"plein")])
    },
    "cyberjaune": {
        dessin: "balisage", tailles: [19, 9, 10], signe: "//", titre: "gauche",
        repos: (w,h) => `M14,1 H${w-14} L${w-1},14 V${h-8} L${w-8},${h-1} H2 V12 Z`,
        page: (w,h) => `M24,0 H${w-42} L${w},33 V${h-15} L${w-15},${h} H7 L0,${h-7} V26 Z`,
        carte: w => cartouche(`M20,5 H${w*.49} L${w*.41},29 H4 Z M${w*.60},5 H${w*.68} L${w*.58},30 H${w*.50} Z M${w*.75},5 H${w*.83} L${w*.73},30 H${w*.65} Z M${w*.90},9 L${w-5},29 H${w*.81} Z`, `M18,28 H${w*.42} M${w*.55},4 H${w*.60} M${w*.70},4 H${w*.75}`),
        cadre: (t,d,s) => composition(t+s+16+(d ? d+13 : 0), 0,14, t+s+27,17, t+7,15, [bloc(t+3,3,s+10,24,0,"plein")])
    },
    "gruvbox": {
        dessin: "cassette", tailles: [15, 10, 11], signe: "● ●", titre: "centre",
        repos: (w,h) => `M1,1 H${w-1} V${h-6} H${w-17} L${w-22},${h-1} H22 L17,${h-6} H1 Z`,
        page: (w,h) => `M0,0 H${w} V${h-8} H${w-35} L${w-45},${h} H45 L35,${h-8} H0 Z`,
        carte: w => cartouche(`M0,4 H${w} V27 H0 Z M${w*.26},11 H${w*.74} V23 H${w*.26} Z`, `M9,28 H${w-9} M${w*.27},8 H${w*.73} `+disque(w*.17,16,8)+disque(w*.83,16,8)+disque(w*.17,16,3)+disque(w*.83,16,3)),
        cadre: (t,d,s) => composition(t+s+14+(d ? d+11 : 0), 3,14, t+s+25,13, t+11,14, [bloc(0,4,t+6,20,2,"verre"), bloc(t+8,7,s+6,14,7,"contour")])
    },
    "matrice": {
        dessin: "afficheur", tailles: [14, 9, 11], signe: "⠿", titre: "centre",
        repos: (w,h) => `M10,3 H${w-10} Q${w-4},3 ${w-4},9 V${h-9} Q${w-4},${h-3} ${w-10},${h-3} H10 Q4,${h-3} 4,${h-9} V9 Q4,3 10,3 Z `+disque(2,15,1.5)+disque(w-2,15,1.5),
        page: (w,h) => `M6,0 H${w-6} L${w},6 V${h-6} L${w-6},${h} H6 L0,${h-6} V6 Z`,
        carte: w => cartouche(`M${w/2-45},10 H${w/2+45} V29 H${w/2-45} Z`, matrice(w)),
        cadre: (t,d,s) => composition(s+13+Math.max(t,d), s+13,d ? 9 : 15, s+13,23, 1,15, [bloc(0,5,s+8,20,2,"plein")])
    },
    "retro": {
        dessin: "crt", tailles: [15, 9, 10], signe: "C:\\>", titre: "gauche",
        repos: (w,h) => `M15,1 Q${w/2},-1 ${w-15},1 Q${w-1},1 ${w-1},14 Q${w-1},${h-3} ${w-15},${h-3} H${w-28} V${h-1} H${w-40} V${h-3} H40 V${h-1} H28 V${h-3} H15 Q1,${h-3} 1,14 Q1,1 15,1 Z`,
        page: (w,h) => `M18,2 Q${w/2},-2 ${w-18},2 Q${w},2 ${w},20 V${h-24} Q${w},${h-8} ${w-18},${h-8} H${w-47} V${h} H${w-78} V${h-8} H78 V${h} H47 V${h-8} H18 Q0,${h-8} 0,${h-24} V20 Q0,2 18,2 Z`,
        carte: w => cartouche(`M12,8 Q${w/2},3 ${w-12},8 Q${w-5},19 ${w-12},28 Q${w/2},31 12,28 Q5,19 12,8 Z`, `M13,12 H${w-13} M10,17 H${w-10} M10,22 H${w-10} M13,27 H${w-13} `+disque(w-24,20,5)),
        cadre: (t,d,s) => composition(s+t+9+(d ? d+12 : 0), s+7,14, s+t+19,16, 0,14, [bloc(0,25,s+t+7,1,0,"encre")])
    },
    "pluie-verte": {
        dessin: "averse", tailles: [15, 10, 15], signe: "⫶", titre: "droite",
        repos: (w,h) => `M1,1 H${w-1} V${h-6} H${w-17} V${h-1} H${w-24} V${h-6} H34 V${h-2} H25 V${h-6} H11 V${h-1} H5 V${h-6} H1 Z`,
        page: (w,h) => `M0,0 H${w} V${h-8} H${w-24} V${h} H${w-33} V${h-8} H${w-52} V${h-4} H${w-66} V${h-8} H51 V${h-3} H37 V${h-8} H14 V${h} H5 V${h-8} H0 Z`,
        carte: w => {
            let pluie = ""
            for (let x = 5; x < w*.61; x += 11) {
                const n = (x-5)/11, a = 9+(n*7)%21
                pluie += `M${x},0 h5 v${a} h-5 Z`
            }
            return cartouche(pluie+`M${w*.62},3 H${w-4} V25 H${w*.62} Z`, `M${w*.62},27 H${w-4} M17,22 V36 M50,23 V34`)
        },
        cadre: (t,d,s) => {
            const x = s+10+(d ? d+10 : 0)
            return composition(x+t+2, x,13, s+9,18, 1,13, [bloc(0,1,s+4,23,0,"verre"), bloc(x,22,t,3,0,"encre")])
        }
    },
    "papier": {
        dessin: "feuillet", tailles: [17, 10, 12], signe: "¶", titre: "gauche",
        repos: (w,h) => `M1,1 H${w-15} L${w-1},14 V${h-1} H1 V21 Q12,15 1,9 Z`,
        page: (w,h) => `M0,0 H${w-43} L${w},37 V${h} H0 V${h*.48+7} Q13,${h*.48} 0,${h*.48-7} Z`,
        carte: w => cartouche(`M0,2 H${w*.72} V27 H0 Z M${w-45},0 L${w},37 H${w-45} Z`, `M${w*.74},3 v5 m0,3 v5 m0,3 v5 m0,3 v5 M15,25 H${w*.69} M${w-43},30 L${w-32},19`),
        cadre: (t,d,s) => composition(s+10+t+(d ? d+23 : 0), s+9,15, s+t+26,15, 0,15, d ? [bloc(s+t+18,3,d+15,24,0,"contour"), bloc(s+t+20,5,1,19,0,"encre")] : [])
    },
    "solarized-clair": {
        dessin: "quadrillage", tailles: [15, 10, 14], signe: "⊕", titre: "centre",
        repos: (w,h) => `M7,1 H${w-7} V7 H${w-1} V${h-7} H${w-7} V${h-1} H7 V${h-7} H1 V7 H7 Z`,
        page: (w,h) => `M10,0 H${w-10} V10 H${w} V${h-10} H${w-10} V${h} H10 V${h-10} H0 V10 H10 Z`,
        carte: w => cartouche(`M12,4 H${w-12} V27 H12 Z M${w/2-56},8 H${w/2+56} V24 H${w/2-56} Z`, `M12,11 H${w/2-56} M12,20 H${w/2-56} M${w/2+56},11 H${w-12} M${w/2+56},20 H${w-12} M31,4 V28 M48,4 V28 M${w-31},4 V28 M${w-48},4 V28`),
        cadre: (t,d,s) => composition(t+d+s+20, 4,15, t+s+20,15, t+12,15, [bloc(0,3,t+8,24,0,"plein"), bloc(t+8,3,s+8,24,0,"contour")])
    },
    "sakura": {
        dessin: "floraison", tailles: [14, 9, 19], signe: "✿", titre: "droite",
        repos: (w,h) => `M7,15 Q-2,3 17,4 Q25,-3 38,3 H${w-25} Q${w-7},0 ${w-1},12 Q${w-2},21 ${w-10},21 Q${w-12},${h+2} ${w-31},${h-2} H35 Q19,${h+2} 17,${h-4} Q-3,${h-4} 7,15 Z`,
        page: (w,h) => `M10,23 Q19,0 49,8 Q72,-4 106,0 H${w-57} Q${w-21},0 ${w},25 V${h-32} Q${w},${h-13} ${w-22},${h-11} Q${w-29},${h} ${w-56},${h} H55 Q27,${h} 15,${h-10} Q0,${h-14} 0,${h-33} V35 Q0,24 10,23 Z`,
        carte: w => cartouche(`M12,23 Q23,5 46,11 Q54,-1 71,5 Q87,-3 103,8 Q132,2 145,15 Q${w*.61},36 ${w*.68},14 Q${w*.83},0 ${w-12},14 Q${w*.81},36 ${w*.64},27 Q${w*.37},41 90,24 Q53,42 12,23 Z`, `M29,22 Q45,12 67,20 Q86,6 108,17 M${w*.71},21 Q${w*.81},11 ${w-26},15`),
        cadre: (t,d,s) => composition(s+8+Math.max(t, d+8), s+7,d ? 9 : 15, s+15,23, 0,15)
    },
    "kanagawa": {
        dessin: "estampe", tailles: [16, 11, 14], signe: "≋", titre: "droite",
        repos: (w,h) => `M1,11 Q19,-4 46,5 Q54,7 63,1 H${w-21} Q${w-1},1 ${w-1},16 Q${w-1},${h-2} ${w-20},${h-2} H32 Q17,${h+4} 1,${h-4} Z`,
        page: (w,h) => `M0,22 Q37,-10 89,10 Q112,19 145,0 H${w-25} Q${w},0 ${w},28 V${h-18} Q${w},${h} ${w-30},${h} H37 Q18,${h+2} 0,${h-9} Z`,
        carte: w => cartouche(`M0,26 Q58,-6 83,6 Q105,14 88,21 Q111,22 144,13 Q${w*.55},-5 ${w-8},21 Q${w*.76},31 ${w*.62},25 Q${w*.5},18 ${w*.41},27 Q97,36 0,30 Z`, `M6,25 Q48,3 77,11 Q88,14 77,19 M111,26 Q152,16 174,16 M${w*.73},16 Q${w*.82},12 ${w-17},21`),
        cadre: (t,d,s) => composition(s+t+8+(d ? d+15 : 0), s+8,14, s+t+23,16, 0,16, d ? [bloc(s+t+20,23,d+3,2,0,"encre")] : [])
    },
    "rose-aube": {
        dessin: "aube", tailles: [14, 9, 0], signe: "", titre: "centre",
        repos: (w,h) => `M1,${h-4} Q${w*.13},1 ${w/2},1 Q${w*.87},1 ${w-1},${h-4} Q${w-1},${h-1} ${w-12},${h-1} H12 Q1,${h-1} 1,${h-4} Z`,
        page: (w,h) => `M0,39 Q${w*.05},0 ${w/2},0 Q${w*.95},0 ${w},39 V${h-23} Q${w},${h} ${w-27},${h} H27 Q0,${h} 0,${h-23} Z`,
        carte: w => cartouche(`M15,31 Q${w*.19},3 ${w/2},3 Q${w*.81},3 ${w-15},31 Z`, `M36,31 Q${w*.25},10 ${w*.39},11 M${w*.61},11 Q${w*.75},10 ${w-36},31 M67,31 H${w-67}`),
        cadre: (t,d) => {
            const w = Math.max(t,d)+16
            return composition(w, (w-t)/2,d ? 10 : 16, (w-d)/2,24, 0,0)
        }
    },
    "everforest": {
        dessin: "lisiere", tailles: [14, 9, 13], signe: "▲", titre: "droite",
        repos: (w,h) => `M1,21 L12,7 L19,11 L27,1 L37,8 L45,2 L59,5 H${w-14} Q${w-1},5 ${w-1},16 Q${w-1},${h-1} ${w-17},${h-1} H9 Q1,${h-1} 1,21 Z`,
        page: (w,h) => `M0,31 L24,10 L40,18 L60,0 L76,11 L97,3 L130,12 H${w-23} Q${w},12 ${w},34 V${h-20} Q${w},${h} ${w-23},${h} H23 Q0,${h} 0,${h-20} Z`,
        carte: w => cartouche(`M0,31 L24,13 L40,24 L61,4 L90,21 L107,11 L130,25 H${w-7} V32 H0 Z M${w*.58},12 H${w-9} V26 H${w*.58} Z`, `M5,31 L24,18 L40,29 L61,11 L90,27 L107,17 L130,31`),
        cadre: (t,d,s) => composition(s+15+Math.max(t,d+6), s+14,d ? 21 : 16, s+20,7, 0,18, [bloc(s+5,13,4,14,0,"encre")])
    },
    "synthwave": {
        dessin: "horizon", tailles: [16, 10, 13], signe: "◒", titre: "droite",
        repos: (w,h) => `M16,1 H${w-16} L${w-1},${h-1} H1 Z`,
        page: (w,h) => `M21,0 H${w-21} L${w},35 V${h-13} L${w-10},${h} H10 L0,${h-13} V35 Z`,
        carte: w => cartouche(`M22,22 Q38,-13 54,22 Z M25,25 H51 V27 H25 Z M29,29 H47 V31 H29 Z M${w*.58},8 H${w-26} L${w-10},30 H${w*.55} Z`, `M12,31 H${w-12} M62,25 H${w*.54} M66,19 H${w*.56} M75,14 L61,31 M103,14 L95,31 M133,14 V31 M161,14 L170,31`),
        cadre: (t,d,s) => composition(s+7+t+(d ? d+14 : 0), s+6,12, s+t+20,16, 0,14, [bloc(0,23,s+t+5,2,0,"encre")])
    },
    "vaporwave": {
        dessin: "video", tailles: [16, 9, 11], signe: "▶", titre: "gauche",
        repos: (w,h) => `M1,8 H${w*.56} L${w*.63},1 H${w-1} V${h-10} H${w*.53} L${w*.48},${h-1} H1 Z`,
        page: (w,h) => `M0,13 H${w*.56} L${w*.62},0 H${w} V${h-16} H${w*.44} L${w*.38},${h} H0 Z`,
        carte: w => cartouche(`M0,14 H${w*.52} L${w*.59},3 H${w-5} V19 H${w*.55} L${w*.5},31 H0 Z`, `M${w*.60},8 H${w-12} M${w*.57},13 H${w-12} M${w*.57},22 H${w-8} M${w*.54},28 H${w-24}`),
        cadre: (t,d,s) => composition(s+8+t+(d ? d+16 : 0), s+7,17, s+t+20,11, 0,17, d ? [bloc(s+t+16,4,d+8,14,0,"plein")] : [])
    },
    "tokyo": {
        dessin: "quai", tailles: [17, 10, 11], signe: "↗", titre: "droite",
        repos: (w,h) => `M1,7 H10 V2 H21 V7 H27 V1 H41 V5 H48 V8 H${w-15} V4 H${w-4} V10 H${w-1} V${h-1} H1 Z`,
        page: (w,h) => `M0,14 H19 V6 H36 V14 H51 V0 H80 V8 H96 V15 H${w-34} V5 H${w-14} V14 H${w} V${h-14} L${w-14},${h} H11 L0,${h-11} Z`,
        carte: w => cartouche(`M0,19 H13 V12 H27 V19 H44 V8 H63 V17 H78 V5 H91 V13 H105 V19 H127 V11 H147 V19 H${w*.47} V32 H0 Z M${w*.52},13 H${w-5} V31 H${w*.52} Z`, `M7,26 H${w*.45} M20,15 h4 M51,12 h5 M82,9 h5 M133,15 h4 M${w-15},18 v8`),
        cadre: (t,d,s) => composition(t+s+13+(d ? d+9 : 0), 0,18, t+s+21,18, t+8,18, [bloc(t+3,10,s+10,17,2,"plein")])
    },
    "dracula": {
        dessin: "ailes", tailles: [14, 9, 0], signe: "", titre: "droite",
        repos: (w,h) => `M1,2 Q${w*.27},0 ${w/2-10},6 L${w/2-5},1 L${w/2},5 L${w/2+5},1 L${w/2+10},6 Q${w*.73},0 ${w-1},2 L${w-10},${h-7} Q${w*.75},${h-14} ${w*.64},${h-3} Q${w*.55},${h-8} ${w/2},${h-1} Q${w*.45},${h-8} ${w*.36},${h-3} Q${w*.25},${h-14} 10,${h-7} Z`,
        page: (w,h) => `M0,8 Q${w*.25},-5 ${w/2-19},9 L${w/2-10},0 L${w/2},7 L${w/2+10},0 L${w/2+19},9 Q${w*.75},-5 ${w},8 V${h-19} Q${w*.74},${h-24} ${w*.64},${h-5} Q${w*.55},${h-11} ${w/2},${h} Q${w*.45},${h-11} ${w*.36},${h-5} Q${w*.26},${h-24} 0,${h-19} Z`,
        carte: w => cartouche(`M8,12 Q30,5 65,16 L74,9 L80,16 L86,9 L95,16 Q130,5 154,12 L143,29 Q121,20 103,29 Q92,23 80,32 Q68,23 57,29 Q39,20 19,29 Z M${w*.58},11 H${w-9} L${w-18},29 H${w*.54} Z`, `M29,17 Q49,15 65,22 M95,22 Q111,15 131,17`),
        cadre: (t,d) => {
            const w = Math.max(t,d) + 19
            return composition(w, (w-t)/2,d ? 10 : 15, (w-d)/2,24, 0,0, [bloc(2,9,3,10,0,"encre"), bloc(w-5,9,3,10,0,"encre")])
        }
    },
    "ocean": {
        dessin: "maree", tailles: [16, 10, 15], signe: "○", titre: "centre",
        repos: (w,h) => `M1,17 C15,4 22,9 38,5 Q51,0 70,3 H${w-17} Q${w-1},3 ${w-1},14 Q${w-1},${h-1} ${w-19},${h-1} H23 Q1,${h-1} 1,17 Z`,
        page: (w,h) => `M0,36 C34,-5 79,24 127,11 Q176,-2 218,2 H${w-35} Q${w},2 ${w},34 V${h-33} Q${w},${h-9} ${w-30},${h-9} Q${w-60},${h-8} ${w-99},${h} H34 Q0,${h} 0,${h-30} Z`,
        carte: w => cartouche(`M2,27 C${w*.17},-5 ${w*.24},31 ${w*.39},13 S${w*.66},-1 ${w*.75},11 S${w*.88},29 ${w-4},11 V29 C${w*.88},39 ${w*.75},22 ${w*.64},24 S${w*.43},39 ${w*.33},26 S${w*.13},35 2,30 Z`, disque(22,13,4)+disque(w-28,9,5)+disque(w-15,4,2)+`M12,28 Q${w*.1},18 ${w*.26},25 M${w*.72},15 Q${w*.85},34 ${w-12},24`),
        cadre: (t,d,s) => composition(t+s+9+(d ? d+19 : 0), 0,15, t+s+22,15, t+7,15, d ? [bloc(t+s+18,4,d+10,22,11,"verre")] : [])
    },
    "catppuccin": {
        dessin: "mousse", tailles: [15, 9, 14], signe: "•ᴗ•", titre: "gauche",
        repos: (w,h) => `M1,18 Q1,7 12,6 Q24,-4 38,4 H${w-30} Q${w-16},-1 ${w-10},7 Q${w-1},9 ${w-1},17 Q${w-1},${h-1} ${w-21},${h-1} H19 Q1,${h-1} 1,18 Z`,
        page: (w,h) => `M0,39 Q0,16 23,13 Q42,-8 68,4 H${w-61} Q${w-38},-4 ${w-20},13 Q${w},19 ${w},44 V${h-32} Q${w},${h} ${w-31},${h} H34 Q0,${h} 0,${h-35} Z`,
        carte: w => cartouche(`M5,27 Q6,1 37,5 Q62,11 82,7 Q${w*.39},1 ${w*.49},19 Q${w*.44},30 ${w*.26},30 Q25,31 5,27 Z M${w*.55},24 Q${w*.65},4 ${w*.75},16 Q${w*.83},22 ${w*.89},10 Q${w-13},2 ${w-6},17 Q${w-9},36 ${w*.83},28 Q${w*.73},24 ${w*.66},31 Q${w*.58},34 ${w*.55},24 Z`, disque(w*.53,10,4)+disque(w*.68,7,3)+disque(w*.78,12,2)),
        cadre: (t,d,s) => composition(s+9+Math.max(t,d+11), s+8,d ? 9 : 15, s+17,24, 0,15, [bloc(0,5,s+5,20,10,"verre")])
    },
    "nord": {
        dessin: "glacier", tailles: [17, 10, 13], signe: "◈", titre: "droite",
        repos: (w,h) => `M1,15 L16,1 L27,4 L38,1 H${w-13} L${w-1},12 V${h-7} L${w-11},${h-1} H15 L1,${h-6} Z`,
        page: (w,h) => `M0,30 L29,0 L60,8 L88,0 H${w-28} L${w},22 V${h-21} L${w-14},${h} H26 L0,${h-18} Z`,
        carte: w => cartouche(`M0,31 L29,2 L63,11 L90,4 L136,27 L${w*.59},9 H${w-29} L${w-4},31 Z`, `M30,4 L43,23 L63,11 L79,28 L90,6 M43,23 L19,31 M105,14 L119,29 M${w*.6},10 L${w*.57},31 M${w-28},10 L${w-37},31`),
        cadre: (t,d,s) => composition(s+11+t+(d ? d+15 : 0), s+11,16, s+t+22,11, 0,15,
            d ? [bloc(s+5,4,1,22,0,"encre"), bloc(s+t+18,4,d+8,15,2,"contour")] : [bloc(s+5,4,1,22,0,"encre")])
    }
}

function pour(theme) { return Object.prototype.hasOwnProperty.call(plans, theme) ? plans[theme] : plans.noctalia }
