-- Règles de fenêtres, de bureaux et de surfaces (barre, panneaux).

-- Chat de l'assistant distant : suit les couleurs et le flou de kitty.
hl.window_rule({
    name = "assistant-chat", match = { class = "^(nc-assistant-chat)$" },
    float = true, center = true, size = { "monitor_w*0.52", "monitor_h*0.62" },
})

-- Cockpit JARVIS (Super + Ctrl + A) : une fenêtre classique (bordure, arrondi et marges de Hyprland), flottante ;
-- nc/automatismes.lua la met à l'ouverture à la place et à la taille d'une fenêtre rangée seule sous la barre (une
-- fenêtre maximisée par Hyprland n'aurait pas les marges). Super + F la passe en plein écran et la rend, comme toute fenêtre.
hl.window_rule({ name = "jarvis-cockpit", match = { title = "^(JARVIS)$" }, float = true })

-- Fenêtre « Connexion JARVIS » (nc-assistant configurer) : petite fenêtre flottante, centrée
hl.window_rule({ name = "nc-connexion-jarvis", match = { title = "^(Connexion JARVIS|JARVIS connection)$" }, float = true, center = true, size = { "600", "660" } })
-- Fenêtre « Clés des IA » (nc-ia configurer) : flottante, centrée
hl.window_rule({ name = "nc-cles-ia", match = { title = "^(Clés des IA|AI keys)$" }, float = true, center = true, size = { "640", "720" } })

-- Fenêtre des réglages (Super + Alt + , ; nc-reglages fenetre) : comme le cockpit, une fenêtre classique placée par
-- nc/automatismes.lua à la taille d'une fenêtre rangée seule sous la barre
hl.window_rule({ name = "nc-reglages-fenetre", match = { title = "^(Réglages du bureau|Desktop settings)$" }, float = true })

-- Petite fenêtre de chat JARVIS (Super + Maj + A) : flottante, centrée, 420 x 560. Pas d'épinglage forcé : Super + Ctrl + P
-- l'épingle sur tous les bureaux comme n'importe quelle fenêtre.
hl.window_rule({ name = "jarvis-chat", match = { title = "^(JARVIS Chat)$" }, float = true, center = true, size = { "420", "560" } })

-- Les applis ne se maximisent pas toutes seules
hl.window_rule({ name = "pas-de-maximisation", match = { class = ".*" }, suppress_event = "maximize" })
-- Fenêtres sans nom ni classe (glisser-déposer XWayland, menus fantômes) : ne prennent pas le focus en apparaissant
hl.window_rule({ name = "sans-nom", match = { class = "^$", title = "^$" }, no_initial_focus = true })
-- Mode souris (nc-reglages → Clavier et souris, SAISIE=souris) : fenêtres libres et centrées, comme sur Windows
-- (automatismes.lua les rouvre ensuite à la place et à la taille où tu les as laissées)
if nc.reglage("SAISIE", "clavier") == "souris" then
    hl.window_rule({ name = "souris-libres", match = { class = ".*", title = "negative:^(JARVIS|Réglages du bureau|Desktop settings|VPN)$" }, float = true, center = true })   -- sauf le cockpit, les réglages et la fenêtre VPN, placés par nc/automatismes.lua
    hl.window_rule({ name = "souris-terminal", match = { class = "^(kitty)$" }, size = { "monitor_w*0.5", "monitor_h*0.55" } })
end
hl.window_rule({ name = "hyprland-run",match = { class = "hyprland-run" }, float = true, move = "20 monitor_h-120" })

-- Fenêtres utilitaires en flottant
hl.window_rule({
    name   = "utilitaires",
    match  = { class = "^(org.pulseaudio.pavucontrol|com.saivert.pwvucontrol|nm-connection-editor|blueman-manager)$" },
    float  = true,
    center = true,
    size   = { "monitor_w*0.55", "monitor_h*0.6" },
})
hl.window_rule({
    name   = "polkit",
    match  = { class = "^(org.kde.polkit-kde-authentication-agent-1|polkit-kde-authentication-agent-1)$" },
    float  = true,
    center = true,
})

-- Incrustation vidéo des navigateurs : flottante, sur tous les bureaux, en bas à droite (taille relative à l'écran)
hl.window_rule({
    name              = "incrustation-video",
    match             = { title = "^(Picture-in-Picture|Picture in picture|Incrustation vidéo)$" },
    float             = true,
    pin               = true,
    keep_aspect_ratio = true,
    size              = { "monitor_w*0.28", "monitor_w*0.1575" },
    move              = { "monitor_w-window_w-20", "monitor_h-window_h-20" },
})

-- Terminal déroulant (Super + touche sous Échap) : kitty lancé au premier appel
hl.workspace_rule({ workspace = "special:term", on_created_empty = "kitty --class dropterm" })
hl.window_rule({
    name   = "terminal-deroulant",
    match  = { class = "^(dropterm)$" },
    float  = true,
    size   = { "monitor_w*0.72", "monitor_h*0.62" },
    center = true,
})

-- Sélecteur de projets de l'espace de code (Super + X ; nc-code) sans l'île Quickshell : fenêtre kitty flottante et
-- centrée, façon Spotlight. Exclue de la mémoire des fenêtres flottantes (nc/automatismes.lua) : sa taille est toujours celle-ci.
hl.window_rule({
    name   = "espace-de-code",
    match  = { class = "^(nc-code)$" },
    float  = true,
    size   = { "monitor_w*0.5", "monitor_h*0.6" },
    center = true,
})

-- Fenêtres « Ouvrir » / « Enregistrer » des applis : flottantes, centrées, à une taille confortable
hl.window_rule({
    name   = "dialogues-fichiers",
    match  = { class = "^(xdg-desktop-portal-gtk|org.freedesktop.impl.portal.desktop.kde|org.gnome.FileChooser)$" },
    float  = true,
    center = true,
    size   = { "monitor_w*0.5", "monitor_h*0.62" },
})
hl.window_rule({
    name   = "dialogues-titres",
    match  = { title = "^(Open File|Open Files|Save File|Save As|Open Folder|Select Folder|Ouvrir|Ouvrir un fichier|Ouvrir des fichiers|Enregistrer|Enregistrer sous|Enregistrer le fichier|Choisir un dossier|Sélectionner un dossier)$" },
    float  = true,
    center = true,
})
-- Fenêtres secondaires de Steam (amis, réglages) : flottantes
hl.window_rule({
    name  = "steam-secondaires",
    match = { class = "^(steam)$", title = "^(Friends List|Liste d'amis|Steam Settings|Paramètres de Steam|Paramètres Steam)$" },
    float = true,
})
-- Jeux (Steam, Proton, gamescope) : marqués « jeu » (fréquence variable, affichage direct) ; en mode jeu
-- (Super + Alt + G), image envoyée sans attendre l'écran (latence minimale)
hl.window_rule({
    name      = "jeux",
    match     = { class = "^(steam_app_.*|gamescope|.*\\.exe)$" },
    content   = "game",
    immediate = true,
})

-- Pas de mise en veille pendant une vidéo en plein écran
hl.window_rule({ name = "video-plein-ecran", match = { class = ".*" }, idle_inhibit = "fullscreen" })

-- Bouton d'arrêt (nc-finger) : plein écran
hl.window_rule({ name = "doigts", match = { class = "^(fingerpop)$" }, float = true, fullscreen = true })

-- Noctalia v5 : flou derrière la barre, les panneaux, le dock, l'OSD et le sélecteur de fenêtres ;
-- animations Hyprland coupées sur ces surfaces (Noctalia anime elle-même). Règle de la documentation officielle v5.
hl.layer_rule({
    name         = "noctalia-v5",
    match        = { namespace = "^noctalia-(bar-.+|notification|dock|panel|attached-panel|osd|window-switcher)$" },
    no_anim      = true,
    ignore_alpha = 0.5,
    blur         = true,
    blur_popups  = true,
})
-- Île (nc-ile) : elle anime elle-même ses ressorts. Sans cette règle, Hyprland animait la place et la taille du calque
-- (layersIn) à chaque changement de taille de la surface (Spotlight, ouverture, fermeture) : l'île glissait de côté,
-- étirée, pendant environ 270 ms (vu image par image : à droite puis à gauche, retour lent au centre)
hl.layer_rule({ name = "nc-ile-sans-anim", match = { namespace = "^nc-ile$" }, no_anim = true })
-- Dock en verre dépoli : flouté même là où il est très transparent
hl.layer_rule({ name = "noctalia-dock-verre", match = { namespace = "^noctalia-dock$" }, ignore_alpha = 0.2 })
-- Fiche des raccourcis de l'île (Super + /) : verre, le bureau flouté derrière la carte seulement (le reste est transparent)
hl.layer_rule({ name = "nc-fiche-verre", match = { namespace = "^nc-fiche$" }, blur = true, ignore_alpha = 0.2 })
-- Espace de code de l'île (Super + X) : la même carte de verre, floutée seulement sous la carte
hl.layer_rule({ name = "nc-code-verre", match = { namespace = "^nc-code$" }, blur = true, ignore_alpha = 0.2 })
-- Lanceur qui sort de la pilule (nc-reglages → Île, ILE_LANCEUR_FONDU=oui) : l'île anime elle-même Super + X depuis la
-- pilule ; pas d'animation de Hyprland en plus sur ce calque. Réglage non : rien ici (Super + X garde le fondu de Hyprland).
if nc.reglage("ILE_LANCEUR_FONDU", "non") == "oui" then
    hl.layer_rule({ name = "nc-code-sans-anim", match = { namespace = "^nc-code$" }, no_anim = true })
end
-- Fenêtre VPN de l'île (Super + Alt + V ; Vpn.qml) : une vraie fenêtre, titre exact « VPN » (stable, pas traduit), flottante.
-- Règle limitée à ce titre ET à la classe de Quickshell (« VPN » seul est un titre courant). Sa taille et sa place (centrée sous la barre) sont posées à l'ouverture par nc/automatismes.lua :
-- la mémoire des fenêtres flottantes écraserait une règle size/move, et cette fenêtre en est exclue.
hl.window_rule({ name = "nc-vpn-fenetre", match = { class = "^(org.quickshell)$", title = "^(VPN)$" }, float = true })
