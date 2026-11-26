.pragma library
.import "ScenesIle.js" as S

function gruvbox() {
    const wood = '#352b24', brass = '#d9b078', tape = '#514738';
    const cassette = S.box(10,11,204,152,7,'#211e1a') + S.box(14,14,196,144,6,'#a98b59')
        + S.box(22,22,180,86,5,'#e7cc92') + S.box(24,78,176,28,5,'#c5754e')
        + S.box(31,30,54,54,2,tape) + S.box(94,35,95,4,0,'#554332')
        + S.path('M94 51h95m-95 12h68',null,'#987646',2)
        + S.box(41,87,141,30,15,tape) + S.box(82,97,58,10,2,'#201e1b')
        + [59,164].map(x => S.dot(x,102,11,'#d3c5a2') + S.dot(x,102,5,tape)
            + S.repeat(6,i => S.ray(x,102,10,60*i,3,tape,2))).join('')
        + S.path('M45 155l11-25h111l12 25z','#c1a16a','#796445')
        + [68,154].map(x => S.dot(x,146,5,tape)).join('')
        + [[21,20],[203,20],[21,151],[203,151]].map(p => S.dot(p[0],p[1],2.5,tape)).join('');
    const meter = S.box(231,97,232,22,3,'#201e1a') + S.repeat(24,i =>
        S.box(239+9*i,104,6,8,0,i<15?'#bda15f':i<20?'#d48a51':'#8a5142'));
    const sheet = S.sheet('Bande magnétique · A','Magnetic tape · A',wood,'#fae4b8',brass,'monospace',
        [233,14,230,12],[231,35,235,27],[233,72,228,14],
        [[232,130,48,33],[287,130,119,33],[413,130,48,33]],3,cassette+meter);
    sheet.cover = [33,32,50,1];
    return sheet;
}

function matrice() {
    const black = '#07120d', green = '#7cda93', wire = '#365c43';
    const window = S.path('M12 10h456v112H12z',null,wire)
        + S.box(13,11,454,22,0,'#183826') + S.path('M331 33v88',null,wire)
        + S.repeat(3,i => S.box(447-9*i,19,5,5,0,i===2?green:'#476451'))
        + S.path('M24 50l7 6-7 6 M24 87h8m-8 5h8',null,green,2)
        + S.path('M379 40h-7v8m72-8h7v8m-79 56v8h7m72-8v8h-7',null,green)
        + S.repeat(5,i => S.box(340,49+i*12,5+(i%3)*4,2,0,wire));
    // Les touches de fonction partent toutes de la même ligne de commande.
    const prompt = S.path('M15 139l9 9-9 9m13 0h9',null,green,2)
        + S.path('M45 128h422',null,wire);
    const sheet = S.sheet('mpd / console audio','mpd / audio console',black,'#c4ffc9',green,'monospace',
        [22,13,360,11],[43,42,280,27],[44,79,277,15],
        [[46,135,115,30],[171,135,162,30],[343,135,124,30]],0,window+prompt);
    sheet.cover = [378,42,68,0];
    return sheet;
}

function brutaliste() {
    const stock = '#f2e9c7', black = '#181916', orange = '#d95432';
    // Billet de concert : le visuel est imprimé sur la souche détachable.
    const ticket = S.box(6,6,468,164,0,black) + S.box(10,10,322,156,0,stock)
        + S.box(335,10,135,156,0,orange) + S.box(10,10,322,28,0,'#e9a83e')
        + S.box(10,38,322,4,0,black) + S.box(10,113,322,5,0,black)
        + S.repeat(12,i => S.box(331,11+i*14,5,6,0,stock))
        + S.box(349,18,108,108,0,black)
        + S.repeat(21,i => S.box(350+5*i,137, i%4===0?4:i%2?1:3,18,0,black));
    const sheet = S.sheet('BILLET SONORE / 01','SOUND TICKET / 01',stock,black,black,'sans-serif',
        [19,11,301,16],[18,46,306,31],[20,88,302,15],
        [[15,123,77,37],[96,123,146,37],[246,123,80,37]],0,ticket);
    sheet.cover = [353,22,100,0];
    return sheet;
}

function cyberjaune() {
    const base = '#20231e', warning = '#ffde36', metal = '#717967';
    const platter = S.dot(86,85,74,'#0e1714') + S.ring(86,85,71,metal,2)
        + S.repeat(48,i => S.ray(86,85,67,i*7.5,i%4===0?7:3, i%4===0?warning:metal,2))
        + S.ring(86,85,53,'#5d6452',1) + S.ring(86,85,43,'#a29441',1)
        + S.path('M85 11h15l-7 8z',warning);
    const chassis = S.path('M168 12h272l22 20v67l-14 14H178l-12-12z','#2b332c',metal)
        + S.path('M168 11h135l-7 5H168z',warning)
        + S.repeat(6,i => S.path('M'+(424+i*6)+' 6h4l-4 6h-4z',warning))
        + S.path('M176 121h267l17-12m-293 57h224',null,metal)
        + S.path('M13 166h89l9-6h27',null,warning,2);
    const sheet = S.sheet('PLATINE / CUE A','DECK / CUE A',base,'#fff4b4',warning,'monospace',
        [182,21,242,12],[180,41,266,28],[182,83,252,14],
        [[169,129,57,32],[232,126,155,38],[393,129,66,32]],1,chassis+platter);
    sheet.cover = [48,47,76,38];
    return sheet;
}

function retro() {
    const cabinet = '#45352e', cream = '#ffefc9', amber = '#d9ac72';
    // Le catalogue des disques se glisse sous le fronton du juke-box.
    const grille = S.path('M10 165V74a65 65 0 0 1 130 0v91z','#ca795b','#e6c09a',2)
        + S.path('M18 164V74a57 57 0 0 1 114 0v90z','#42655c','#f8cf99',3)
        + S.path('M26 164V74a49 49 0 0 1 98 0v90z','#302e28','#8ca79a',3)
        + S.box(39,41,72,72,8,'#dab589') + S.repeat(6,i => S.box(34,121+i*6,82,2,1,'#baaa80'))
        + S.box(11,158,128,8,3,'#deba91');
    const cards = S.box(150,13,316,103,8,'#d2ac80') + S.box(154,17,308,95,6,'#32473f')
        + S.path('M163 44h290M163 81h290',null,'#60746a')
        + S.box(151,123,314,43,7,'#806353') + S.path('M155 161h306',null,'#bca17a',2);
    const sheet = S.sheet('Sélecteur de disques','Record selector',cabinet,cream,amber,'serif',
        [165,20,282,15],[165,46,287,26],[167,85,278,15],
        [[157,129,94,28],[256,127,105,32],[366,129,94,28]],6,grille+cards);
    sheet.cover = [43,45,64,5];
    return sheet;
}

function oled() {
    const night = '#000000', ice = '#ecf5f4', line = '#9ab2af';
    const points = [3,8,3,15,9,5,21,11,7,14,3,8,18,9,4,12,6,2];
    // Les deux oscillogrammes encadrent les commandes, sans simuler une progression.
    const scope = S.repeat(points.length,i => S.path('M'+(15+i*4)+' '+(146-points[i]/2)+'v'+points[i],null,line,1.5))
        + S.repeat(points.length,i => S.path('M'+(397+i*4)+' '+(146-points[17-i]/2)+'v'+points[17-i],null,line,1.5));
    const sheet = S.sheet('Écoute binaurale','Binaural monitor',night,ice,line,'sans-serif',
        [18,20,291,12],[16,43,336,31],[19,87,327,15],
        [[99,129,58,34],[168,125,144,42],[323,129,58,34]],21,
        S.dot(370,22,2,ice)+S.path('M18 116h444',null,'#344340')+scope);
    sheet.cover = [382,17,81,4];
    return sheet;
}

function clairNeutre() {
    const ivory = '#f8f7f2', black = '#262725', grey = '#747772';
    // Une fiche de discothèque : pochette sous passe-partout et onglets latéraux.
    const mount = S.box(16,44,115,115,0,'#e6e4db') + S.path('M16 57V44h13m102 102v13h-13',null,grey)
        + S.box(15,17,9,9,0,'#315d8c') + S.path('M16 34h448M143 44v115M365 44v115',null,'#b7b8af')
        + S.path('M155 98h198',null,'#c7c8c0') + S.box(155,145,37,3,0,'#315d8c');
    const sheet = S.sheet('Phonothèque / fiche d’écoute','Sound library / listening card',ivory,black,'#65726e','serif',
        [33,9,417,16],[154,57,203,29],[155,109,200,15],
        [[378,44,84,32],[378,85,84,32],[378,126,84,32]],1,mount);
    sheet.cover = [23,51,101,0];
    return sheet;
}

function apple() {
    const shell = '#e9e8e3', ink = '#25332e', rim = '#87968e';
    const lcd = S.box(11,14,280,147,9,'#adafa5') + S.box(13,16,276,143,8,'#414943')
        + S.box(17,20,268,135,5,'#ced7bb') + S.box(17,20,268,26,5,'#bac6a9')
        + S.path('M17 46h268',null,'#88957d') + S.box(26,59,79,79,2,'#a7b29c')
        + S.path('M255 28h16v8h-16z m18 2v4',null,ink) + S.box(257,30,12,4,0,ink);
    const wheel = S.dot(386,88,77,'#c5c5bd') + S.dot(386,87,75,'#fbfaf4')
        + S.ring(386,87,28,'#d4d5cc',1) + S.path('M378 35h16m-16 4h16',null,rim,1.6)
        + S.repeat(4,i => S.dot(380+i*4,142,1.25,rim));
    const sheet = S.sheet('Baladeur de poche','Pocket player',shell,ink,rim,'sans-serif',
        [25,23,213,13],[114,62,165,24],[115,104,163,14],
        [[317,70,34,34],[362,63,48,48],[421,70,34,34]],24,lcd+wheel);
    sheet.cover = [29,62,73,0];
    return sheet;
}

const catalogue = { gruvbox, matrice, brutaliste, cyberjaune, retro, oled, 'clair-neutre': clairNeutre, apple };
function pour(nom) {
    return Object.prototype.hasOwnProperty.call(catalogue,nom) ? catalogue[nom]() : null;
}
