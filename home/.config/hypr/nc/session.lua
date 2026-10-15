-- Session : variables propres à Hyprland et démarrage.
-- Les variables de toute la session graphique (Qt, etc.) sont dans ~/.config/uwsm/env.
-- Noctalia v5 démarre via noctalia.service (systemd --user), comme les autres services de la session.

hl.env("XCURSOR_SIZE", "24")
hl.env("HYPRCURSOR_SIZE", "24")

hl.on("hyprland.start", function()
    -- Fond d'écran affiché tout de suite, en attendant Noctalia (évite l'écran noir)
    hl.exec_cmd("~/.local/bin/nc-boot-wallpaper")
end)
