#!/usr/bin/env bash


COLORS="$HOME/.config/noctalia/colors.json"
OUTPUT="$HOME/.config/kitty/themes/current.conf"
sleep 0.75

cat > "$OUTPUT" << EOF
background            $(jq -r '.mSurface' "$COLORS")
foreground            $(jq -r '.mOnSurface' "$COLORS")
cursor                $(jq -r '.mOnSurface' "$COLORS")
cursor_text_color     $(jq -r '.mSurface' "$COLORS")
selection_background  $(jq -r '.mSurfaceVariant' "$COLORS")
selection_foreground  $(jq -r '.mOnSurfaceVariant' "$COLORS")
active_border_color   $(jq -r '.mPrimary' "$COLORS")
inactive_border_color $(jq -r '.mSurfaceVariant' "$COLORS")
url_color             $(jq -r '.mPrimary' "$COLORS")
color0                $(jq -r '.mSurface' "$COLORS")
color1                $(jq -r '.mError' "$COLORS")
color2                $(jq -r '.mPrimary' "$COLORS")
color3                $(jq -r '.mSecondary' "$COLORS")
color4                $(jq -r '.mTertiary' "$COLORS")
color5                $(jq -r '.mTertiary' "$COLORS")
color6                $(jq -r '.mSecondary' "$COLORS")
color7                $(jq -r '.mOnSurface' "$COLORS")
color8                $(jq -r '.mOutline' "$COLORS")
color9                $(jq -r '.mError' "$COLORS")
color10               $(jq -r '.mPrimary' "$COLORS")
color11               $(jq -r '.mSecondary' "$COLORS")
color12               $(jq -r '.mTertiary' "$COLORS")
color13               $(jq -r '.mTertiary' "$COLORS")
color14               $(jq -r '.mSecondary' "$COLORS")
color15               $(jq -r '.mOnSurface' "$COLORS")
EOF

kill -SIGUSR1 $(pgrep kitty)
