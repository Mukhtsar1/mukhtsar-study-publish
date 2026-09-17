"""
Mukhtsar brand icon set — SVG paths only, recoloured at render time.
No emoji anywhere in the brand; these replace them.
"""

_PATHS = {
    # education
    "university": '<path d="M3 21h18M5 21V10M19 21V10M12 3L2 9h20L12 3zM9 21v-6h6v6" fill="none" stroke="C" stroke-width="1.8" stroke-linejoin="round"/>',
    "graduation": '<path d="M12 4L2 9l10 5 10-5-10-5zM6 11.5V16c0 1.7 2.7 3 6 3s6-1.3 6-3v-4.5M22 9v5" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "book":       '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5v14zM4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "language":   '<path d="M4 5h9M8.5 3v2M6 8c1.5 4 5 7 8 8M11 8c-1 3.5-4 6.5-7 8M13 21l4-9 4 9M14.5 18h5" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "document":   '<path d="M7 3h7l4 4v14H7V3zM14 3v4h4" fill="none" stroke="C" stroke-width="1.8" stroke-linejoin="round"/><path d="M10 12h5M10 16h5" stroke="C" stroke-width="1.8" stroke-linecap="round"/>',
    "certificate":'<circle cx="12" cy="9" r="5" fill="none" stroke="C" stroke-width="1.8"/><path d="M9 13.5L8 21l4-2 4 2-1-7.5" fill="none" stroke="C" stroke-width="1.8" stroke-linejoin="round"/>',
    # trust / status
    "shield":     '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z" fill="none" stroke="C" stroke-width="1.8" stroke-linejoin="round"/><path d="M9 12l2 2 4-4" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "check":      '<path d="M20 6L9 17l-5-5" fill="none" stroke="C" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>',
    "alert":      '<path d="M12 3L2 20h20L12 3z" fill="none" stroke="C" stroke-width="1.8" stroke-linejoin="round"/><path d="M12 9v5" stroke="C" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="17" r="1.2" fill="C"/>',
    "star":       '<path d="M12 3l2.7 5.6 6.1.8-4.5 4.3 1.1 6-5.4-2.9-5.4 2.9 1.1-6L3.2 9.4l6.1-.8L12 3z" fill="none" stroke="C" stroke-width="1.8" stroke-linejoin="round"/>',
    "trophy":     '<path d="M7 4h10v5a5 5 0 0 1-10 0V4zM7 6H4v2a3 3 0 0 0 3 3M17 6h3v2a3 3 0 0 1-3 3M9 19h6M12 14v5M8 21h8" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    # money
    "money":      '<circle cx="12" cy="12" r="9" fill="none" stroke="C" stroke-width="1.8"/><path d="M12 7v10M15 9.5c0-1.4-1.3-2.2-3-2.2s-3 .8-3 2.2 1.3 1.9 3 2.3 3 .9 3 2.3-1.3 2.2-3 2.2-3-.8-3-2.2" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round"/>',
    "discount":   '<circle cx="7.5" cy="7.5" r="2" fill="none" stroke="C" stroke-width="1.8"/><circle cx="16.5" cy="16.5" r="2" fill="none" stroke="C" stroke-width="1.8"/><path d="M19 5L5 19" stroke="C" stroke-width="1.8" stroke-linecap="round"/>',
    "card":       '<rect x="2.5" y="5" width="19" height="14" rx="2.5" fill="none" stroke="C" stroke-width="1.8"/><path d="M2.5 10h19M6 15h4" stroke="C" stroke-width="1.8" stroke-linecap="round"/>',
    "bank":       '<path d="M3 10h18M4 10L12 4l8 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 21h18" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    # living
    "home":       '<path d="M3 11l9-8 9 8M5 9.5V21h14V9.5" fill="none" stroke="C" stroke-width="1.8" stroke-linejoin="round"/><path d="M9 21v-7h6v7" fill="none" stroke="C" stroke-width="1.8" stroke-linejoin="round"/>',
    "key":        '<circle cx="8" cy="14" r="4.5" fill="none" stroke="C" stroke-width="1.8"/><path d="M11.2 10.8L20 2M17 5l2.5 2.5M14.5 7.5L17 10" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round"/>',
    "location":   '<path d="M12 21s7-6.1 7-11a7 7 0 1 0-14 0c0 4.9 7 11 7 11z" fill="none" stroke="C" stroke-width="1.8" stroke-linejoin="round"/><circle cx="12" cy="10" r="2.6" fill="none" stroke="C" stroke-width="1.8"/>',
    "mosque":     '<path d="M4 21h16M5 21v-7h14v7M12 3c0 3-4 4-4 7h8c0-3-4-4-4-7zM12 14v7M8.5 17.5v3.5M15.5 17.5v3.5" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "halal":      '<circle cx="12" cy="12" r="9" fill="none" stroke="C" stroke-width="1.8"/><path d="M8 8v8M8 12h4M12 8v8M16 8v5.5a2.5 2.5 0 0 1-2.5 2.5" fill="none" stroke="C" stroke-width="1.6" stroke-linecap="round"/>',
    "food":       '<path d="M4 3v7a2 2 0 0 0 2 2h1v9M7 3v6M10 3v6M17 3c-1.7 1-3 3.2-3 6v4h3v8M17 3v18" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "health":     '<path d="M12 21s-8-5.5-8-11a4.6 4.6 0 0 1 8-3 4.6 4.6 0 0 1 8 3c0 5.5-8 11-8 11z" fill="none" stroke="C" stroke-width="1.8" stroke-linejoin="round"/><path d="M8.5 11h2l1-2 1.5 4 1-2h2" fill="none" stroke="C" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
    # transport
    "metro":      '<rect x="5" y="3" width="14" height="14" rx="3" fill="none" stroke="C" stroke-width="1.8"/><path d="M5 11h14M9 17l-2 4M15 17l2 4M9.5 7h5" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round"/><circle cx="9" cy="14" r="0.9" fill="C"/><circle cx="15" cy="14" r="0.9" fill="C"/>',
    "bus":        '<rect x="4" y="4" width="16" height="13" rx="3" fill="none" stroke="C" stroke-width="1.8"/><path d="M4 11h16M8 17l-1.5 3M16 17l1.5 3" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round"/><circle cx="8" cy="14" r="0.9" fill="C"/><circle cx="16" cy="14" r="0.9" fill="C"/>',
    "car":        '<path d="M4 16v-3l2-5h12l2 5v3M4 16h16M4 16v2.5M20 16v2.5" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="7.5" cy="16" r="1.6" fill="none" stroke="C" stroke-width="1.6"/><circle cx="16.5" cy="16" r="1.6" fill="none" stroke="C" stroke-width="1.6"/>',
    "plane":      '<path d="M2 12l19-8-6 18-3.5-7L2 12z" fill="none" stroke="C" stroke-width="1.8" stroke-linejoin="round"/><path d="M11.5 15L21 4" stroke="C" stroke-width="1.8"/>',
    # nature
    "leaf":       '<path d="M4 20c0-9 6-15 16-16 0 10-5 16-14 16H4z" fill="none" stroke="C" stroke-width="1.8" stroke-linejoin="round"/><path d="M4 20c4-5 8-8 13-10" fill="none" stroke="C" stroke-width="1.7" stroke-linecap="round"/>',
    "wave":       '<path d="M2 9c2.5-2 5-2 7.5 0S15 11 17.5 9 22 7 22 7M2 14c2.5-2 5-2 7.5 0s5.5 2 8-.1 4.5-1.9 4.5-1.9M2 19c2.5-2 5-2 7.5 0s5.5 2 8-.1S22 17 22 17" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round"/>',
    "mountain":   '<path d="M2 20h20L15 6l-4 7-2.5-3L2 20z" fill="none" stroke="C" stroke-width="1.8" stroke-linejoin="round"/>',
    "moon":       '<path d="M20 14.5A8.5 8.5 0 1 1 10.5 4a7 7 0 0 0 9.5 10.5z" fill="none" stroke="C" stroke-width="1.8" stroke-linejoin="round"/>',
    # people / comms
    "users":      '<circle cx="9" cy="8" r="3.4" fill="none" stroke="C" stroke-width="1.8"/><path d="M2.5 20c.6-3.4 3.3-5.2 6.5-5.2s5.9 1.8 6.5 5.2" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round"/><circle cx="17" cy="9" r="2.6" fill="none" stroke="C" stroke-width="1.8"/><path d="M16.5 14.6c2.6.3 4.5 1.9 5 4.4" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round"/>',
    "user":       '<circle cx="12" cy="8" r="3.6" fill="none" stroke="C" stroke-width="1.8"/><path d="M4.5 20c.8-4 3.9-6 7.5-6s6.7 2 7.5 6" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round"/>',
    "chat":       '<path d="M21 12a8 8 0 0 1-8 8H4l1.5-3A8 8 0 1 1 21 12z" fill="none" stroke="C" stroke-width="1.8" stroke-linejoin="round"/><path d="M8.5 12h.01M12 12h.01M15.5 12h.01" stroke="C" stroke-width="2.6" stroke-linecap="round"/>',
    "whatsapp":   '<path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5.1-1.3A10 10 0 1 0 12 2zm0 18.2a8.2 8.2 0 0 1-4.2-1.1l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1-.2.2-.7.8-.8 1-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.2-.4.2-.4.7-1.3.1-.2 0-.4 0-.5l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5c-.2 0-.5.1-.7.3-.9.9-1.1 2.2-.2 3.9a12 12 0 0 0 4.6 4.4c1.7.9 2.6.9 3.4.8.6-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.1-1.2 0-.2-.2-.3-.4-.4z" fill="C"/>',
    "globe":      '<circle cx="12" cy="12" r="9" fill="none" stroke="C" stroke-width="1.8"/><path d="M3 12h18M12 3c3 3 3 15 0 18-3-3-3-15 0-18z" fill="none" stroke="C" stroke-width="1.8"/>',
    # misc
    "clock":      '<circle cx="12" cy="12" r="9" fill="none" stroke="C" stroke-width="1.8"/><path d="M12 7v5l3.5 2" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "calendar":   '<rect x="3.5" y="5" width="17" height="16" rx="2.5" fill="none" stroke="C" stroke-width="1.8"/><path d="M3.5 10h17M8 3v4M16 3v4" stroke="C" stroke-width="1.8" stroke-linecap="round"/>',
    "bulb":       '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 1 4 10.5c-.8.7-1 1.5-1 2.5h-6c0-1-.2-1.8-1-2.5A6 6 0 0 1 12 3z" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "briefcase":  '<rect x="3" y="8" width="18" height="12" rx="2.5" fill="none" stroke="C" stroke-width="1.8"/><path d="M9 8V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 13h18M12 12v3" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round"/>',
    "chart":      '<path d="M4 20V4M4 20h16" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round"/><path d="M8 16v-5M12 16V7M16 16v-8" fill="none" stroke="C" stroke-width="2.4" stroke-linecap="round"/>',
    "ai":         '<rect x="7" y="7" width="10" height="10" rx="2.4" fill="none" stroke="C" stroke-width="1.8"/><path d="M10 10.5h4M10 13.5h4M9.5 3v4M14.5 3v4M9.5 17v4M14.5 17v4M3 9.5h4M3 14.5h4M17 9.5h4M17 14.5h4" fill="none" stroke="C" stroke-width="1.7" stroke-linecap="round"/>',
    "arrow":      '<path d="M20 12H6M11 6l-6 6 6 6" fill="none" stroke="C" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "sim":        '<path d="M6 3h8l4 4v14H6V3z" fill="none" stroke="C" stroke-width="1.8" stroke-linejoin="round"/><rect x="9" y="11" width="6" height="7" rx="1.2" fill="none" stroke="C" stroke-width="1.6"/>',
    "gear":       '<circle cx="12" cy="12" r="3.4" fill="none" stroke="C" stroke-width="1.8"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.2 5.2l2.1 2.1M16.7 16.7l2.1 2.1M18.8 5.2l-2.1 2.1M7.3 16.7l-2.1 2.1" fill="none" stroke="C" stroke-width="1.8" stroke-linecap="round"/>',
}


def icon(name: str, size: int, colour: str) -> str:
    """Return an inline SVG string for the named icon."""
    if name not in _PATHS:
        raise KeyError(f"Unknown icon '{name}'. Available: {sorted(_PATHS)}")
    body = _PATHS[name].replace("C", colour)
    return f'<svg width="{size}" height="{size}" viewBox="0 0 24 24">{body}</svg>'


def available() -> list:
    return sorted(_PATHS)
