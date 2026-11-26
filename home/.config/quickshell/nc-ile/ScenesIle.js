.pragma library

// Planches originales, sur une feuille de 480 × 176. Les encres (papier, texte,
// accent, second pigment) restent propres à l’objet, même avec une palette utilisateur.
// Chaque planche place ses légendes et ses trois zones de commande sur le dessin.
function path(d, fill, stroke, w) { return '<path d="'+d+'" fill="'+(fill||'none')+'" stroke="'+(stroke||'none')+'" stroke-width="'+(w||1)+'" stroke-linejoin="round" stroke-linecap="round"/>' }
function box(x,y,w,h,r,c) { return '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="'+r+'" fill="'+c+'"/>' }
function dot(x,y,r,c) { return '<circle cx="'+x+'" cy="'+y+'" r="'+r+'" fill="'+c+'"/>' }
function repeat(n,fn) { let s=''; for(let i=0;i<n;i++) s+=fn(i); return s }
function ring(x,y,r,c,w) { return '<circle cx="'+x+'" cy="'+y+'" r="'+r+'" fill="none" stroke="'+c+'" stroke-width="'+w+'"/>' }
function ray(x,y,r,a,b,c,w) { const t=a*Math.PI/180; return path('M'+(x+(r-b)*Math.cos(t))+','+(y+(r-b)*Math.sin(t))+'l'+(b*Math.cos(t))+','+(b*Math.sin(t)),null,c,w) }
// Zones du titre et de la légende : x, y, largeur, corps. Touches : x, y, largeur, hauteur.
function sheet(name,en,paper,ink,accent,font,caption,title,legend,keys,round,art) {
    return {name,en,paper,ink,accent,font,caption,title,legend,keys,round,
        image:'data:image/svg+xml;charset=utf-8,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 176">'+box(0,0,480,176,0,paper)+art+'</svg>')}
}
function noctalia(){
    const sky='#191b30', star='#e5cfff', brass='#bb98df';
    const chart=ring(112,90,70,brass,1)+ring(112,90,54,brass,1)+repeat(36,i=>ray(112,90,69,i*10,i%3?3:8,star,1))+path('M60 108L85 73 110 84 133 54 154 64',null,brass)+[[60,108],[85,73],[110,84],[133,54],[154,64]].map(p=>dot(...p,3,star)).join('')+dot(112,104,13,brass)+dot(118,99,13,sky);
    return sheet('Atlas des nuits','Night atlas',sky,star,brass,'serif',[208,18,245,12],[208,38,256,48],[210,98,248,15],[[204,134,112,30],[327,134,59,30],[398,134,59,30]],15,chart+path('M194 14V162M209 125H458',null,brass));
}
function apple(){
    return sheet('Porte-cartes','Wallet','#e6e9f1','#1f2840','#596b91','sans-serif',[39,48,227,12],[38,61,268,48],[41,122,245,14],[[309,42,132,32],[309,82,132,32],[309,122,132,32]],16,box(18,7,440,125,18,'#829db5')+box(13,17,444,130,18,'#d2ada8')+box(8,29,454,140,18,'#f8f4eb')+path('M294 40V157',null,'#baaead')+repeat(4,i=>dot(390+13*i,20,3,'#f4e0cf')));
}
function oled(){
    return sheet('Veille / 01','Standby / 01','#030404','#f6f9f8','#98b1a6','monospace',[16,6,350,10],[10,19,455,78],[19,111,315,15],[[17,141,146,30],[176,141,145,30],[334,141,129,30]],0,path('M16 134H464',null,'#59655f')+dot(456,15,4,'#d4ffeb'));
}
function clairNeutre(){
    return sheet('Édition quotidienne','Daily edition','#f6f4ee','#1e2120','#9d382a','sans-serif',[18,12,228,13],[171,29,292,57],[173,101,282,15],[[14,52,136,30],[14,89,136,30],[14,126,136,30]],0,path('M14 37H148M160 11V164M172 122H464',null,'#343c38',2)+dot(438,147,15,'#b84231')+box(173,141,75,9,0,'#212422'));
}
function brutaliste(){
    return sheet('BLOC PUBLIC','PUBLIC BLOCK','#f0dea3','#191917','#613312','sans-serif',[15,7,340,17],[14,39,332,60],[15,117,316,18],[[347,7,125,51],[347,64,125,50],[347,120,125,49]],0,path('M0 34H336V0M0 109H338V176M8 163H331',null,'#171716',6)+repeat(12,i=>box(12+i*27,148,13,6,0,'#241e16')));
}
function cyberjaune(){
    return sheet('ORDRE DE SERVICE','SERVICE ORDER','#23251e','#fbf29f','#e1cd4b','monospace',[45,15,273,12],[44,37,285,52],[46,107,280,14],[[24,139,137,31],[173,139,126,31],[311,139,144,31]],2,path('M17 129V17L32 4H333L351 20H467V129Z',null,'#d7cd45',2)+repeat(6,i=>path('M'+(361+15*i)+' 31l7 -7v65l-7 7z','#726e2b'))+path('M347 110H454m-107 7h62',null,'#eada58',2));
}
function gruvbox(){
    let reels=[90,199].map(x=>dot(x,83,36,'#594e3b')+dot(x,83,25,'#c1a376')+repeat(3,i=>dot(x+14*Math.cos(i*2.094),83+14*Math.sin(i*2.094),6,'#483d30'))+dot(x,83,5,'#453d32')).join('');
    return sheet('Face A · magnétophone','Side A · tape deck','#392f29','#f6ddaa','#d4a762','monospace',[258,17,200,11],[256,40,211,41],[258,94,202,14],[[27,130,197,33],[252,131,97,32],[361,131,97,32]],3,box(16,18,223,101,8,'#bca378')+box(32,36,189,76,23,'#4a4334')+path('M90 50H199M90 116H199',null,'#c28355',3)+reels+repeat(3,i=>box(259,117,197-18*i,2,0,'#976f49')));
}
function matrice(){
    return sheet('tty0 : session locale','tty0 : local session','#080e0a','#b9ffb6','#70c985','monospace',[39,12,390,12],[39,32,390,53],[42,96,398,16],[[41,135,130,32],[183,135,125,32],[320,135,125,32]],0,path('M27 9H10V120H27M17 137l9 14 -9 14M41 122H451',null,'#4a9262',2)+repeat(12,i=>box(456,12+9*i,8,4,0,i%4?'#1c3725':'#72b075')));
}
function retro(){
    return sheet('Canal 03 · télétexte','Channel 03 · teletext','#39352f','#eff8dc','#a7bda4','monospace',
        [40,27,290,12],[37,46,290,52],[40,115,280,14],[[350,17,112,40],[350,68,112,40],[350,118,112,40]],8,
        box(4,3,471,170,16,'#bfa987')+box(12,10,324,155,25,'#554d42')+box(20,18,308,139,24,'#283b34')
        +repeat(8,i=>box(37,143+i,271,.5,0,'#415249'))+repeat(3,i=>box(345,13+51*i,122,48,9,'#594e45')));
}
function pluieVerte(){
    const drops=repeat(7,i=>path('M'+(18+i*19)+' '+(5+i%3*13)+'l-7 19m-2 13l-8 23',null,'#50836a',2));
    return sheet('Collecteur de pluie','Rain collector','#142a24','#d4ecdb','#99c6a6','serif',[169,11,280,13],[170,33,285,53],[172,100,284,15],[[165,134,146,33],[320,134,61,33],[392,134,64,33]],5,drops+path('M43 57H115L102 154Q79 166 58 154Z','#203c33','#b1d2ab',2)+path('M52 108Q68 98 85 106T108 102L101 152Q77 164 59 151Z','#679e84')+repeat(7,i=>path('M104 '+(68+i*11)+'h-11',null,'#d8e5bf')));
}
function papier(){
    return sheet('Carnet de poche','Pocket notebook','#f2e8d2','#392f27','#885841','serif',[57,11,242,15],[54,34,262,52],[58,108,254,16],[[335,16,125,39],[335,69,125,39],[335,122,125,39]],1,repeat(7,i=>path('M40 '+(27+i*23)+'H463',null,'#d8ccb1'))+path('M42 2V174M319 2V174',null,'#bf9284')+repeat(6,i=>dot(18,17+i*28,5,'#aaa18e'))+path('M243 158q22 -28 54 -25q-17 22 -54 25m3 -2l42 -18',null,'#79694e',2));
}
function solarizedClair(){
    return sheet('Planche de mesures','Measurement plate','#fdf6e3','#34545a','#317c76','monospace',[171,13,289,12],[170,33,290,50],[173,101,282,15],[[18,137,134,31],[168,137,140,31],[323,137,139,31]],0,repeat(25,i=>path('M'+i*20+' 1V127',null,'#e1ddcc'))+repeat(7,i=>path('M1 '+i*20+'H479',null,'#e1ddcc'))+path('M17 118L78 12 144 118Z M51 99L79 51 108 99Z','#d8e5d6','#467f7d',2)+repeat(10,i=>ray(78,118,60,182+i*13,6,'#368079',1))+box(163,7,305,117,1,'#f7f0db')+path('M165 123H469V7',null,'#649594'));
}
function sakura(){
    const ink='#60483b',blush='#edc4bb'; const petal=(x,y)=>repeat(5,i=>dot(x+4*Math.cos(i*1.257),y+4*Math.sin(i*1.257),3.2,blush))+dot(x,y,1.8,'#bc8c62');
    const cat=path('M35 104Q37 91 47 84L47 61 62 72Q75 65 89 66L105 53 109 78Q126 91 126 109Q108 120 75 117Q47 115 35 104Z','#fffcf3',ink,2.4)+path('M55 92q4 -5 8 0m22 -2q4 -5 8 -1m-21 5q3 5 7 -1m-30 3l-15 -3m17 9l-14 1m65 -9l13 -5',null,ink,2)+dot(55,100,4,blush)+dot(95,96,4,blush);
    return sheet('Salon des cerisiers','Cherry tea room','#faf1e3',ink,'#aa6656','serif',[169,16,282,15],[167,39,286,49],[170,101,279,15],[[156,137,139,31],[303,137,72,31],[384,137,72,31]],15,path('M12 21Q67 52 144 12M65 36L49 13M99 30L123 48',null,'#957769',2)+petal(34,31)+petal(51,14)+petal(122,46)+petal(136,16)+cat+path('M44 128Q88 136 127 123',null,'#c59b86',2)+path('M149 9V124M159 129H456',null,'#d7b9a9'));
}
function kanagawa(){
    const foam='#efe1c3', sea='#344968';
    return sheet('Estampe de la côte','Coastal woodcut','#e9debf','#302f38','#675445','serif',[16,10,235,14],[15,29,263,55],[18,98,247,16],[[14,136,131,32],[153,136,65,32],[225,136,66,32]],2,dot(398,42,28,'#b96f56')+path('M219 123l67 -63 40 36 29 -14 93 66Z','#858887')+path('M247 176Q320 136 338 80Q355 16 400 38Q424 48 419 76Q403 53 388 69Q398 72 395 89Q379 80 370 109Q355 159 391 176Z',sea)+path('M279 174Q334 137 355 76Q366 42 391 44M309 172Q358 141 369 99M378 67Q386 48 402 57',null,foam,3)+path('M360 176Q392 118 479 97V176Z','#577389')+repeat(4,i=>path('M'+(405+i*15)+' 160q10 -18 25 -21',null,foam,2)));
}
function roseAube(){
    return sheet('Almanach de l’aube','Dawn almanac','#fae5da','#573f48','#a56972','serif',[160,13,298,15],[154,34,299,54],[159,103,299,15],[[28,135,130,33],[175,135,130,33],[322,135,130,33]],18,dot(79,83,44,'#edb4a1')+path('M10 96Q54 83 96 88T150 82V128H10Z','#d09ca1')+path('M12 108Q47 98 87 105T147 96',null,'#f9dbcb',2)+repeat(13,i=>ray(79,84,66,182+i*14,7,'#9d7475',1))+path('M14 127H463',null,'#c99799'));
}
function everforest(){
    let trees=repeat(8,i=>{let x=7+i*15,y=50+(i%3)*15;return path('M'+x+' 117l15 -'+y+' 17 '+y+'Z',i%2?'#5e7860':'#425e52')});
    return sheet('Refuge des conifères','Conifer shelter','#e6e6cd','#354535','#6a7952','serif',[153,13,306,15],[151,32,306,53],[154,97,298,14],[[127,136,142,32],[282,136,81,32],[375,136,82,32]],3,trees+path('M86 176Q127 155 92 145Q70 137 100 128Q142 113 130 102',null,'#a3916a',6)+path('M141 117H452l11 7 -11 7H141Z','#b9bb99')+dot(148,124,2,'#43513c'));
}
function nord(){
    return sheet('Expédition polaire','Polar expedition','#2b3544','#eef3f4','#b2ccda','monospace',[14,11,254,11],[13,29,261,50],[16,95,253,15],[[13,132,131,33],[154,132,61,33],[226,132,62,33]],3,repeat(6,i=>path('M'+(280+i*6)+' 166Q'+(314+i*8)+' 128 '+(297+i*9)+' 91T'+(375+i*12)+' 8',null,'#627586'))+path('M278 130l55 -72 23 17 42 -55 70 112Z','#506577')+path('M302 99l31 -41 23 17 -14 6 -10 -5 -12 16ZM373 54l25 -34 28 41 -22 -13 -12 11 -6 -10Z','#d7e6e8')+path('M300 152l40 -26 31 5 62 -53',null,'#afd3da',2)+dot(433,78,4,'#cc9d7c'));
}
function synthwave(){
    const neon='#fc95bd';return sheet('Route de minuit','Midnight highway','#251e42','#ffe3e7',neon,'sans-serif',[21,12,242,13],[18,33,283,54],[22,100,257,15],[[19,136,127,33],[155,136,62,33],[226,136,61,33]],5,dot(383,58,48,'#e6919a')+repeat(5,i=>box(326,63+i*8,114,2+i,0,'#251e42'))+path('M270 124l46 -45 24 16 28 -25 20 20 28 -46 64 66v23Z','#59406d')+path('M283 176l87 -58h15l94 58Z','#342649')+repeat(8,i=>path('M377 116L'+(260+i*39)+' 176',null,'#b16caa'))+repeat(4,i=>path('M289 '+(121+i*i*4)+'H479',null,'#ab659f')));
}
function vaporwave(){
    return sheet('Bureau des mirages','Mirage desktop','#b3a6cd','#403453','#83658e','serif',[39,30,244,14],[39,48,252,42],[41,105,242,14],[[323,10,138,40],[339,67,125,39],[309,122,152,39]],0,box(8,9,277,119,0,'#8ca7ab')+box(17,17,283,120,0,'#706783')+box(23,23,279,117,0,'#eee0df')+box(23,23,279,5,0,'#dba5be')+path('M9 149h282l-18 16H0Z','#dac3db')+repeat(9,i=>path('M'+(i*30)+' 149l-12 16',null,'#aa91bb'))+path('M302 6v150h164',null,'#ebd4e9',2));
}
function tokyo(){
    return sheet('Quai de correspondance','Interchange platform','#202834','#f2ece0','#f0b789','monospace',[16,10,395,12],[17,34,294,52],[20,100,291,15],[[20,135,135,31],[166,135,124,31],[302,135,154,31]],2,path('M16 29H461M16 126H461',null,'#75838b')+path('M350 38v60q0 14 14 14h91',null,'#df9677',5)+path('M382 38v29q0 14 13 14h60',null,'#8db9bf',5)+[48,75,101].map(y=>dot(350,y,5,'#f3e9cd')).join('')+dot(382,50,5,'#f3e9cd')+dot(435,81,5,'#f3e9cd'));
}
function ocean(){
    let sonar=dot(93,87,75,'#153d47')+repeat(4,i=>ring(93,87,14+18*i,'#5f9f9e',1))+path('M18 87H168M93 13V162',null,'#669f9c')+path('M93 87l34 -57q20 11 30 34Z','#367471')+path('M93 87l64 -23',null,'#a9dcd0',2)+dot(121,48,3,'#b1dcbb');
    return sheet('Station bathymétrique','Bathymetric station','#133039','#dbf2e8','#95c8bf','monospace',[183,15,282,11],[181,35,283,48],[184,96,275,14],[[182,130,132,33],[323,130,60,33],[394,130,63,33]],16,sonar+repeat(6,i=>box(184+i*42,116,25,2,0,'#527d80')));
}
function catppuccin(){
    const line='#946e61';
    return sheet('Commande du café','Coffee order','#e4d7d0','#503f45','#8a6163','serif',[154,15,302,14],[150,37,305,52],[154,102,296,14],[[147,135,142,32],[300,135,71,32],[381,135,74,32]],7,path('M138 4H466V168l-8 6 -8 -6 -8 6 -8 -6 -8 6 -8 -6 -8 6 -8 -6H138Z','#f8eee0')+path('M16 71Q56 54 108 71L102 106Q95 133 62 133Q30 132 22 108Z','#c19c91',line,2)+path('M108 77q31 -8 20 15q-7 16 -23 14',null,line,6)+path('M25 71Q66 59 103 72Q69 83 25 71Z','#79594f')+path('M49 55q-18 -17 0 -34m20 28q18 -18 2 -34m17 42q12 -14 7 -22',null,line,2)+path('M12 139q59 22 113 -3',null,line,3)+repeat(20,i=>box(151+i*15,124,7,1,0,'#b79a8c')));
}
function penombre(){
    // Une grue pliée dans trois papiers, à la lumière d'une lampe rouge.
    const ink='#f3ddd0', ember='#e1977e';
    const crane=path('M19 105L66 92 28 41 105 80 149 30 138 82 169 64 179 68 151 75 128 110 99 124 52 117Z','#c59482')
        +path('M28 41L99 124 105 80Z','#eed0af')+path('M105 80L149 30 128 110Z','#dcab8f')
        +path('M66 92L99 124 19 105Z','#9d695e')+path('M99 124L138 82 128 110Z','#85574e')
        +path('M32 145Q86 132 148 142Q97 151 32 145Z','#281816');
    return sheet('Atelier du pli','Paper atelier','#37211e',ink,ember,'serif',
        [197,18,264,13],[193,39,267,48],[197,102,259,15],[[191,138,128,32],[334,138,57,32],[403,138,57,32]],4,
        dot(78,57,37,'#7f463c')+crane+path('M188 12V120M198 127H459',null,'#94695b')
        +path('M10 26V9H27M454 9h16v17',null,'#b38972'));
}
const catalog={noctalia,apple,oled,'clair-neutre':clairNeutre,brutaliste,cyberjaune,gruvbox,matrice,retro,'pluie-verte':pluieVerte,papier,'solarized-clair':solarizedClair,sakura,kanagawa,'rose-aube':roseAube,everforest,synthwave,vaporwave,tokyo,ocean,catppuccin,nord,penombre}
function pour(nom){return (Object.prototype.hasOwnProperty.call(catalog,nom)?catalog[nom]:noctalia)()}
