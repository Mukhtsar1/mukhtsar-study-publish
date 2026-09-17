"""
Mukhtsar brand themes.

Option A = primary dark theme (navy bg, gold accents, red offset shadows)
Option B = light theme (cream bg, navy text, teal accents, gold offset)

Both themes share the same layout code; only these tokens differ.
Colours are locked to the six official brand colours plus the arcade red.
"""

BRAND = {
    "navy_deep":  "#000B58",
    "navy":       "#003161",
    "teal_deep":  "#006A67",
    "teal":       "#048480",
    "gold":       "#F5A800",
    "cream":      "#FDEB9E",
    # supporting tones used in the evolved (pixel/blueprint) look
    "bg_dark":    "#0D1B3E",
    "red":        "#79002B",
    "cyan":       "#00AADD",
    "card_dark":  "#14264E",
    "body_dark":  "#D5DEF2",
    "muted_dark": "#B9C6E4",
    "muted_lite": "#7E8CA8",
}

THEMES = {
    "A": {
        "name": "Option A",
        "logo":          "logo_big.png",
        "bg":            BRAND["bg_dark"],
        "grid":          "grid_dark.png",
        "checker":       "checker_dark.png",
        "text":          "#FFFFFF",
        "text_body":     BRAND["body_dark"],
        "text_muted":    BRAND["muted_dark"],
        "accent":        BRAND["gold"],        # headline keyword, icons, rules
        "accent_2":      BRAND["cyan"],        # eyebrow, inline emphasis, tips
        "shadow":        BRAND["red"],         # hard offset behind gold
        "pixel_fill":    BRAND["gold"],
        "pixel_shadow":  BRAND["red"],
        "tag_bg":        BRAND["gold"],
        "tag_text":      BRAND["bg_dark"],
        "tag_shadow":    BRAND["red"],
        "card_bg":       BRAND["card_dark"],
        "card_border":   "rgba(245,168,0,0.55)",
        "frame_border":  BRAND["gold"],        # photo window border
        "cta_bg":        BRAND["gold"],
        "cta_text":      BRAND["bg_dark"],
        "cta_sub":       BRAND["navy"],
        "cta_shadow":    BRAND["red"],
        "footer":        BRAND["cream"],
        "source_note":   "#7B8CB5",
        "dot":           BRAND["gold"],
        "icon":          BRAND["gold"],
        "icon_alt":      BRAND["cyan"],
    },
    "B": {
        "name": "Option B",
        "logo":          "logo_big_light.png",
        "bg":            BRAND["cream"],
        "grid":          "grid_light.png",
        "checker":       "checker_light.png",
        "text":          BRAND["navy_deep"],
        "text_body":     BRAND["navy"],
        "text_muted":    BRAND["navy"],
        "accent":        BRAND["teal"],
        "accent_2":      BRAND["teal_deep"],
        "shadow":        BRAND["gold"],
        "pixel_fill":    BRAND["navy_deep"],
        "pixel_shadow":  BRAND["gold"],
        "tag_bg":        BRAND["navy_deep"],
        "tag_text":      BRAND["cream"],
        "tag_shadow":    BRAND["teal"],
        "card_bg":       "#F3DE8A",
        "card_border":   "rgba(4,132,128,0.55)",
        "frame_border":  BRAND["navy_deep"],
        "cta_bg":        BRAND["navy_deep"],
        "cta_text":      BRAND["gold"],
        "cta_sub":       BRAND["cream"],
        "cta_shadow":    BRAND["teal"],
        "footer":        BRAND["teal_deep"],
        "source_note":   BRAND["muted_lite"],
        "dot":           BRAND["teal"],
        "icon":          BRAND["teal"],
        "icon_alt":      BRAND["teal_deep"],
    },
}

# Canvas + safe zones (Instagram portrait carousel)
CANVAS = {
    "w": 1080,
    "h": 1350,
    "footer_band": (1275, 1310),   # footer text sits here; content must clear it
    "min_clearance": 40,           # px between last content and footer band
    "window": (64, 154, 1016, 666),  # transparent photo window bbox
    "window_size": (952, 512),
}

PATHS = {
    "A":     {"theme": "A", "images": False},
    "A-img": {"theme": "A", "images": True},
    "B":     {"theme": "B", "images": False},
    "B-img": {"theme": "B", "images": True},
}


def theme(path_key: str) -> dict:
    """Return the token dict for a path key like 'A-img'."""
    if path_key not in PATHS:
        raise ValueError(f"Unknown path '{path_key}'. Valid: {list(PATHS)}")
    return THEMES[PATHS[path_key]["theme"]]


def uses_images(path_key: str) -> bool:
    return PATHS[path_key]["images"]
