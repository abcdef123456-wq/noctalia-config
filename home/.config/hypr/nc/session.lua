-- Session : variables propres à Hyprland et démarrage.
-- Les variables de toute la session graphique (Qt, etc.) sont dans ~/.config/uwsm/env.
-- Noctalia v5 démarre via noctalia.service (systemd --user), comme les autres services de la session.

-- Taille du curseur : nc-reglages (CURSEUR_TAILLE)
local curseur = tostring(math.floor(nc.reglage("CURSEUR_TAILLE", 24)))
hl.env("XCURSOR_SIZE", curseur)
hl.env("HYPRCURSOR_SIZE", curseur)

hl.on("hyprland.start", function()
    -- Fond d'écran affiché tout de suite, en attendant Noctalia (évite l'écran noir)
    hl.exec_cmd("~/.local/bin/nc-boot-wallpaper")
    -- Suit le dernier lecteur de musique actif : les touches de musique le visent (pas un onglet en pause depuis des heures)
    hl.exec_cmd("playerctld daemon")
    -- Ancienne barre (Waybar, HyprPanel, ancienne Noctalia…) qui démarrerait encore : arrêtée et désactivée
    hl.exec_cmd("~/.local/bin/nc-session-propre")
end)
