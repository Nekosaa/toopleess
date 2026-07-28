"""CustomTkinter theme configuration – Bold Purple-Cyan gradient style."""
from __future__ import annotations

# ============================================================================
# COLOR PALETTE – Bold Purple-Cyan Theme
# ============================================================================

# Background gradient (dark indigo → purple)
BG_GRADIENT_START = "#1e1b4b"  # Deep indigo
BG_GRADIENT_END = "#312e81"    # Rich purple
BG_DARK = "#0f0e1a"            # Very dark for contrast
BG_CARD = "#2d2a4d"            # Card background

# Accent colors
ACCENT_CYAN = "#06b6d4"        # Primary cyan accent
ACCENT_PURPLE = "#a855f7"      # Secondary purple accent
NEON_GLOW = "#c084fc"          # Neon glow effect
ACCENT_PINK = "#ec4899"        # Tertiary pink accent

# Text colors
TEXT_PRIMARY = "#f0f0f0"       # Main text
TEXT_SECONDARY = "#a0a0b0"     # Secondary text
TEXT_MUTED = "#6b6b80"         # Muted text

# UI elements
BUTTON_GRADIENT_START = "#8b5cf6"  # Violet
BUTTON_GRADIENT_END = "#06b6d4"    # Cyan
BUTTON_HOVER = "#9333ea"           # Hover state
BORDER_GLOW = "#c084fc"            # Border with glow

# Status colors
SUCCESS = "#10b981"
WARNING = "#f59e0b"
ERROR = "#ef4444"
INFO = "#3b82f6"


# ============================================================================
# CustomTkinter Theme Settings
# ============================================================================

def get_ctk_theme_colors() -> dict:
    """Returns CustomTkinter color configuration."""
    return {
        # Base colors
        "CTk": {
            "fg_color": [BG_GRADIENT_START, BG_GRADIENT_START]
        },
        "CTkToplevel": {
            "fg_color": [BG_GRADIENT_START, BG_GRADIENT_START]
        },
        
        # Frame
        "CTkFrame": {
            "fg_color": [BG_CARD, BG_CARD],
            "border_color": [BORDER_GLOW, BORDER_GLOW],
            "border_width": 1
        },
        
        # Button
        "CTkButton": {
            "fg_color": [ACCENT_PURPLE, ACCENT_PURPLE],
            "hover_color": [BUTTON_HOVER, BUTTON_HOVER],
            "border_color": [BORDER_GLOW, BORDER_GLOW],
            "text_color": [TEXT_PRIMARY, TEXT_PRIMARY],
            "corner_radius": 12
        },
        
        # Label
        "CTkLabel": {
            "fg_color": "transparent",
            "text_color": [TEXT_PRIMARY, TEXT_PRIMARY]
        },
        
        # Entry
        "CTkEntry": {
            "fg_color": [BG_DARK, BG_DARK],
            "border_color": [ACCENT_CYAN, ACCENT_CYAN],
            "text_color": [TEXT_PRIMARY, TEXT_PRIMARY],
            "placeholder_text_color": [TEXT_MUTED, TEXT_MUTED],
            "corner_radius": 8
        },
        
        # Textbox
        "CTkTextbox": {
            "fg_color": [BG_DARK, BG_DARK],
            "border_color": [ACCENT_CYAN, ACCENT_CYAN],
            "text_color": [TEXT_PRIMARY, TEXT_PRIMARY],
            "corner_radius": 8
        },
        
        # Scrollbar
        "CTkScrollbar": {
            "fg_color": [BG_CARD, BG_CARD],
            "button_color": [ACCENT_PURPLE, ACCENT_PURPLE],
            "button_hover_color": [BUTTON_HOVER, BUTTON_HOVER]
        },
        
        # Checkbox & Radio
        "CTkCheckBox": {
            "fg_color": [ACCENT_CYAN, ACCENT_CYAN],
            "hover_color": [BUTTON_HOVER, BUTTON_HOVER],
            "border_color": [BORDER_GLOW, BORDER_GLOW],
            "text_color": [TEXT_PRIMARY, TEXT_PRIMARY],
            "corner_radius": 6
        },
        
        "CTkRadioButton": {
            "fg_color": [ACCENT_PURPLE, ACCENT_PURPLE],
            "hover_color": [BUTTON_HOVER, BUTTON_HOVER],
            "border_color": [BORDER_GLOW, BORDER_GLOW],
            "text_color": [TEXT_PRIMARY, TEXT_PRIMARY]
        },
        
        # Combobox
        "CTkComboBox": {
            "fg_color": [BG_DARK, BG_DARK],
            "border_color": [ACCENT_CYAN, ACCENT_CYAN],
            "button_color": [ACCENT_PURPLE, ACCENT_PURPLE],
            "button_hover_color": [BUTTON_HOVER, BUTTON_HOVER],
            "text_color": [TEXT_PRIMARY, TEXT_PRIMARY],
            "corner_radius": 8
        },
        
        # Tabview
        "CTkTabview": {
            "fg_color": [BG_CARD, BG_CARD],
            "border_color": [BORDER_GLOW, BORDER_GLOW],
            "segmented_button_fg_color": [BG_DARK, BG_DARK],
            "segmented_button_selected_color": [ACCENT_CYAN, ACCENT_CYAN],
            "segmented_button_selected_hover_color": [BUTTON_HOVER, BUTTON_HOVER],
            "segmented_button_unselected_color": [BG_CARD, BG_CARD],
            "segmented_button_unselected_hover_color": [ACCENT_PURPLE, ACCENT_PURPLE],
            "text_color": [TEXT_PRIMARY, TEXT_PRIMARY],
            "corner_radius": 12
        }
    }


def apply_ctk_theme():
    """Apply the custom theme to CustomTkinter."""
    import customtkinter as ctk
    
    # Set appearance mode to dark
    ctk.set_appearance_mode("dark")
    
    # Use built-in dark-blue theme as base, will override with custom colors
    ctk.set_default_color_theme("dark-blue")
