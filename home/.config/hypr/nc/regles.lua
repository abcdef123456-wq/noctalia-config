-- Règles de fenêtres, de bureaux et de surfaces (barre, panneaux).

-- Chat de l'assistant distant : suit les couleurs et le flou de kitty.
hl.window_rule({
    name = "assistant-chat", match = { class = "^(nc-assistant-chat)$" },
    float = true, center = true, size = { "monitor_w*0.52", "monitor_h*0.62" },
})

-- Cockpit JARVIS (Super + Alt + Maj + A) : une fenêtre classique (bordure, arrondi et marges de Hyprland), flottante ;
-- nc/automatismes.lua la met à l'ouverture à la place et à la taille d'une fenêtre rangée seule sous la barre (une
-- fenêtre maximisée par Hyprland n'aurait pas les marges). Super + F la passe en plein écran et la rend, comme toute fenêtre.
hl.window_rule({ name = "jarvis-cockpit", match = { title = "^(JARVIS)$" }, float = true })

-- Fenêtre des réglages (Super + Alt + , ; nc-reglages fenetre) : flottante, centrée, aux deux tiers de l'écran
hl.window_rule({ name = "nc-reglages-fenetre", match = { title = "^(Réglages du bureau)$" }, float = true, center = true, size = { "monitor_w*0.66", "monitor_h*0.78" } })

-- Petite fenêtre de chat JARVIS (Super + Alt + A) : flottante, centrée, 420 x 560. Pas d'épinglage forcé : Super + Ctrl + P
-- l'épingle sur tous les bureaux comme n'importe quelle fenêtre.
hl.window_rule({ name = "jarvis-chat", match = { title = "^(JARVIS Chat)$" }, float = true, center = true, size = { "420", "560" } })

-- Les applis ne se maximisent pas toutes seules
hl.window_rule({ name = "pas-de-maximisation", match = { class = ".*" }, suppress_event = "maximize" })
-- Fenêtres sans nom ni classe (glisser-déposer XWayland, menus fantômes) : ne prennent pas le focus en apparaissant
hl.window_rule({ name = "sans-nom", match = { class = "^$", title = "^$" }, no_initial_focus = true })
-- Mode souris (nc-reglages → Clavier et souris, SAISIE=souris) : fenêtres libres et centrées, comme sur Windows
-- (automatismes.lua les rouvre ensuite à la place et à la taille où tu les as laissées)
if nc.reglage("SAISIE", "clavier") == "souris" then
    hl.window_rule({ name = "souris-libres", match = { class = ".*", title = "negative:^(JARVIS)$" }, float = true, center = true })   -- sauf le cockpit, placé par nc/automatismes.lua
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
-- Dock en verre dépoli : flouté même là où il est très transparent
hl.layer_rule({ name = "noctalia-dock-verre", match = { namespace = "^noctalia-dock$" }, ignore_alpha = 0.2 })
