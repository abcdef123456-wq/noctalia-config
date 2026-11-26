.pragma library
.import "ScenesIle.js" as S

// La commande appartient à l'objet illustré. Un seul dessin au repos ; le survol et
// le focus restent des états natifs du bouton, indépendants de la géométrie peinte.
function dessin(theme, p, index, w, h) {
    const a = p.accent, i = p.ink, b = p.paper, mid = h / 2
    const trait = d => S.path(d, null, a, 1.3)
    const plaque = d => S.path(d, b, a, 1.4)
    const cadre = r => `<rect x="1" y="1" width="${w-2}" height="${h-2}" rx="${r}" fill="${b}" stroke="${a}"/>`
    const bas = y => trait(`M3 ${y}H${w-3}`)
    const rive = (x, y, n) => S.repeat(n, k => S.dot(x, y + k * 4, .9, a))
    let art
    switch (theme) {
    case 'papier': art = plaque(`M3 2H${w-12}l9 9v${h-13}H3Z`) + trait(`M${w-12} 2v9h9`) + rive(8,8,4); break
    case 'sakura': art = bas(h-4) + S.repeat(3,k=>S.dot(w-8+k*2, h-6-(k%2)*3, 1.8, a)); break
    case 'kanagawa': art = cadre(1) + trait(`M4 5h8M5 4v8M${w-4} ${h-5}h-8`); break
    case 'rose-aube': art = plaque(`M2 ${h-2}V${mid}Q2 3 ${mid} 3H${w-mid}Q${w-2} 3 ${w-2} ${mid}V${h-2}Z`) + bas(h-5); break
    case 'gruvbox': art = cadre(3) + S.box(3,h-6,w-6,4,1,a) + rive(8,8,3); break
    case 'brutaliste': art = S.box(4,4,w-4,h-4,0,i) + plaque(`M1 1H${w-5}V${h-5}H1Z`); break
    case 'matrice': art = trait(`M11 3H3V${h-3}h8M${w-11} 3h8v${h-6}h-8`) + S.box(8,h-8,5,2,0,a); break
    case 'cyberjaune': art = plaque(`M2 10l8 -8h${w-12}v${h-12}l-8 8H2Z`) + trait(`M${w-18} ${h-5}l5 -5m0 5l5 -5`); break
    case 'oled': art = bas(h-2) + S.dot(6,5,2,index===1?i:a); break
    case 'clair-neutre': art = bas(h-2) + S.box(2,3,index===0?4:2,h-8,0,index===0?a:i); break
    case 'apple': art = cadre(9) + S.box(5,mid-5,2,10,1,a); break
    case 'retro': art = cadre(6) + bas(h-5) + trait(`M5 8V5h${w-10}`); break
    case 'pluie-verte': art = plaque(`M2 2H${w-2}l-5 ${h-4}H7Z`) + trait(`M6 8h7m-6 5h4`); break
    case 'solarized-clair': art = cadre(0) + S.repeat(5,k=>trait(`M${4+k*4} ${h-2}v-${k%2?3:5}`)); break
    case 'everforest': art = plaque(`M1 2h${w-11}l9 ${mid-2}-${9} ${mid-2}H1Z`) + S.dot(7,mid,2,a); break
    case 'nord': art = trait(`M2 ${h-3}H${w-8}l6 -6M2 9V3h12`) + S.path('M4 12l4 -6 4 6Z',a); break
    case 'synthwave': art = plaque(`M9 2h${w-11}l-7 ${h-4}H2Z`) + bas(h-5); break
    case 'vaporwave': art = cadre(0) + trait(`M3 ${h-3}V3h${w-6}`) + S.path(`M3 ${h-3}h${w-6}V3`,null,i,2); break
    case 'tokyo': art = trait(`M2 ${h-5}H${w-2}`) + S.dot(8,h-5,3,b) + S.ring(8,h-5,3,a,1.4); break
    case 'ocean': art = cadre(mid) + S.repeat(3,k=>S.dot(8+k*3,mid+(k%2?2:-2),1,a)); break
    case 'catppuccin': art = bas(h-3) + S.repeat(4,k=>S.box(2,4+k*5,2,2,0,a)); break
    case 'penombre': art = plaque(`M1 7l10 -5h${w-12}v${h-9}l-10 5H1Z`) + trait('M2 7l10 3 -1 -8'); break
    default: art = trait(`M2 ${mid}Q2 3 16 3H${w-16}Q${w-2} 3 ${w-2} ${mid}Q${w-2} ${h-3} ${w-16} ${h-3}H16Q2 ${h-3} 2 ${mid}Z`) + S.dot(7,mid,1.7,a)
    }
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}">${art}</svg>`)
}
