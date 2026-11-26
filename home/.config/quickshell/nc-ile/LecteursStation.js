.pragma library
.import "ScenesIle.js" as S

// Platine à entraînement direct : la pochette devient le macaron du disque.
function noctalia() {
    const metal = '#a49abc', light = '#e4d8f1';
    const platter = S.dot(91,87,79,'#272336') + S.ring(91,87,76,metal,2)
        + S.repeat(50,i => S.ray(91,87,73,i*7.2,2.5,metal,1))
        + S.dot(91,87,68,'#161520') + S.repeat(7,i => S.ring(91,87,36+i*4.4,'#453b52',1))
        + S.path('M34 74Q37 55 54 42M123 133q15 -10 21 -26',null,'#76687f',2);
    const arm = S.dot(174,31,13,'#756e81') + S.dot(174,31,8,'#373044')
        + S.path('M174 31L176 78Q177 89 166 101L148 117',null,light,3)
        + S.path('M141 115l8 -8 8 7 -9 9Z','#c8afca');
    const art = S.box(5,4,187,168,13,'#514957') + platter + arm
        + S.dot(176,152,3,'#ead0a5') + S.path('M202 118H466',null,'#71647c')
        + S.path('M449 13l2 6 6 2 -6 2 -2 6 -2 -6 -6 -2 6 -2Z',metal);
    const s = S.sheet('Platine lunaire','Lunar turntable','#2d283a',light,'#c6b3d1','serif',
        [204,17,226,12],[202,42,265,30],[205,86,258,15],[[203,129,48,34],[259,125,146,42],[413,129,50,34]],18,art);
    s.cover = [59,55,64,32];
    return s;
}

// Un banc de mesure avec vumètre à aiguille et réglette de calibration.
function solarizedClair() {
    const ink = '#2f5153', rule = '#8f9c89';
    const meter = S.box(11,114,144,53,3,'#bfbba6') + S.box(15,118,136,45,2,'#fff9e5')
        + S.path('M27 145Q80 114 138 144',null,ink,1.5)
        + S.repeat(13,i => S.ray(82,225,95,237+i*5.5, i%3 ? 4 : 7,i>9?'#a44e3a':ink,1.5))
        + S.path('M81 159l24 -25',null,'#a84c35',2) + S.dot(81,159,3,ink);
    const art = S.path('M13 29H345V103H13M13 106H467',null,rule)
        + S.repeat(32,i => S.box(14+i*10.5,96,1,i%5?3:7,0,rule))
        + S.box(369,7,96,96,1,'#d5d2bd') + S.path('M365 22V5h17m71 0h15v16m0 65v17h-16',null,ink)
        + meter + S.box(165,114,303,53,3,'#dbd9c5')
        + S.repeat(3,i => S.box(173+i*100,120,90,40,2,'#a8ac99'));
    const s = S.sheet('Banc de modulation','Modulation bench','#f8f1db',ink,'#527a70','monospace',
        [15,9,328,12],[15,34,323,28],[17,73,316,14],[[176,123,84,34],[276,123,84,34],[376,123,84,34]],2,art);
    s.cover = [374,12,85,1];
    return s;
}

// Enregistreur de terrain, micros stéréo à grille et touches en colonne.
function nord() {
    const chassis = '#3d4c59', ink = '#e3eef1', frost = '#a1bec8';
    const mic = x => S.box(x,8,107,23,11,'#1e2e3a')
        + S.repeat(16,i => S.path('M'+(x+7+i*6)+' 24l5 -10',null,'#778b98',2));
    const art = S.box(6,4,468,168,15,chassis) + mic(14) + mic(235)
        + S.path('M125 20h103',null,'#8a9da6') + S.dot(177,20,4,'#cedde0')
        + S.box(13,39,334,121,7,'#243641') + S.box(21,60,90,90,4,'#64808d')
        + S.path('M118 146h218',null,'#758c98')
        + S.repeat(21,i => S.box(120+i*10.5,139,2,i%5===0?7:3,0,'#94aeb8'))
        + S.box(354,9,111,155,11,'#1d2b35') + S.dot(362,16,2,'#b8c6ca') + S.dot(456,157,2,'#b8c6ca');
    const s = S.sheet('Prise de son polaire','Polar field recording','#293a47',ink,frost,'sans-serif',
        [21,42,315,11],[120,63,217,25],[121,104,214,14],[[363,21,93,33],[359,64,101,44],[363,119,93,32]],7,art);
    s.cover = [25,64,82,2];
    return s;
}

// Synthétiseur de scène : le transport est un jeu de pads au-dessus du clavier.
function synthwave() {
    const hot = '#ff96c4';
    const keyboard = S.box(7,125,321,46,3,'#29203e')
        + S.repeat(21,i => S.box(10+i*15,128,14,40,2,'#e9cbdc'))
        + S.repeat(21,i => (i%7===2 || i%7===6) ? '' : S.box(20+i*15,127,9,25,2,'#343050'));
    const art = S.path('M0 0H338L311 119H0Z','#2d2041') + S.path('M365 0h8l-41 176h-8Z','#ed7ba9')
        + S.path('M379 0h4l-41 176h-4Z','#9c80cf') + S.box(337,15,134,128,5,'#202336')
        + S.path('M343 35V21h17m104 100v15h-17',null,'#a0e3df',2)
        + S.repeat(4,i => S.path('M'+(355+i*27)+' 151l-3 9h14l3 -9z',i===1?hot:'#826f9b')) + keyboard;
    const s = S.sheet('Clavier de minuit','Midnight keyboard','#452b52','#ffe7f1',hot,'sans-serif',
        [15,8,307,11],[13,24,305,27],[15,62,300,13],[[12,88,63,29],[82,85,142,33],[232,88,65,29]],4,art);
    s.cover = [351,25,107,4];
    return s;
}

// MiniDisc translucide. La cartouche se glisse derrière le panneau de lecture.
function vaporwave() {
    const ink = '#453455', edge = '#866e99';
    const cartridge = S.path('M16 17H158L176 35V142H12V24Z','#87b5bd','#617b92',2)
        + S.ring(84,79,52,'#d9e3db',5) + S.ring(84,79,44,'#b4d8cf',2)
        + S.box(111,18,42,54,2,'#bfc6d4') + S.path('M119 24v40m24 -40v40',null,'#8d98b0',2)
        + S.box(19,41,83,83,1,'#6c8e9f') + S.path('M20 133h45m80 0h19',null,'#dceedf',2);
    const art = cartridge + S.box(147,12,317,114,0,'#9988aa') + S.box(141,7,317,114,0,'#f8e8e5')
        + S.box(144,10,311,22,0,'#d1b2cf') + S.path('M145 33h309',null,edge)
        + S.repeat(3,i => S.box(415+i*12,16,8,8,0,i===2?edge:'#f7ddea'))
        + S.box(141,115,317,5,0,'#c2acc3') + S.path('M20 155h98l9 -9h17',null,edge,2)
        + S.dot(20,155,3,edge) + S.box(154,133,298,39,0,'#9f8aab') + S.box(150,129,298,39,0,'#e4d3dd');
    const s = S.sheet('Minidisque nacré','Pearl minidisc','#dfcfdf',ink,edge,'serif',
        [151,12,257,13],[151,42,294,28],[153,86,289,15],[[155,133,71,30],[232,133,131,30],[369,133,73,30]],0,art);
    s.cover = [22,44,77,1];
    return s;
}

// Le morceau et l’artiste forment les deux lignes d’un afficheur de quai.
function tokyo() {
    const orange = '#ffbb85', ivory = '#f2eee1';
    const ticket = S.path('M10 17h81l8 8v87l-8 8H10Z','#dad3b9')
        + S.repeat(11,i => S.box(15+i*7,101,(i%3)+1,11,0,'#414c52'));
    const art = ticket + S.box(107,14,360,108,3,'#151d25') + S.box(116,22,4,90,1,'#e29966')
        + S.path('M129 83h323',null,'#49565d') + S.repeat(6,i => S.dot(410+i*8,27,2,i<4?orange:'#485660'))
        + S.path('M17 149h440l9 -7m-9 7 9 7',null,'#e29b6e',4)
        + S.dot(35,149,7,ivory) + S.dot(35,149,3,'#29333d') + S.dot(445,149,7,ivory) + S.dot(445,149,3,'#29333d');
    const s = S.sheet('Diffusion de quai','Platform broadcast','#29333d',ivory,orange,'monospace',
        [130,21,271,12],[128,42,323,28],[130,92,320,15],[[62,133,94,32],[172,129,135,40],[325,133,91,32]],2,art);
    s.cover = [18,22,74,1];
    return s;
}

// Récepteur d’hydrophone, hublot boulonné et trois commandes étanches.
function ocean() {
    const sea = '#163d48', brass = '#d3bd8d', foam = '#e3f3ec';
    const port = S.dot(390,86,76,'#142e39') + S.ring(390,86,70,'#88a4a1',7)
        + S.ring(390,86,59,brass,3) + S.repeat(8,i => {
            const angle = i*Math.PI/4, x = 390+69*Math.cos(angle), y = 86+69*Math.sin(angle);
            return S.dot(x,y,3.3,'#374f53') + S.path('M'+(x-1)+' '+(y+1)+'l2 -2',null,'#d2c6a9');
        });
    const art = port + S.path('M13 18h9l7 -7h267v91H13Z','#0f313e','#50757a',1.5)
        + S.path('M15 113h29l4 -4 3 8 4 -11 4 13 4 -7h22l3 -4 3 6 3 -3h201',null,'#7aa5a4',1.5)
        + S.box(12,125,287,41,14,'#416169') + S.dot(304,114,2.5,brass);
    const s = S.sheet('Écoute sous-marine','Hydrophone receiver',sea,foam,brass,'monospace',
        [27,18,257,11],[24,37,260,26],[27,77,257,14],[[19,130,56,31],[82,128,148,35],[237,130,55,31]],15,art);
    s.cover = [336,32,108,54];
    return s;
}

const lecteurs = {noctalia, 'solarized-clair': solarizedClair, nord, synthwave, vaporwave, tokyo, ocean};
function pour(nom) {
    return Object.prototype.hasOwnProperty.call(lecteurs,nom) ? lecteurs[nom]() : null;
}
