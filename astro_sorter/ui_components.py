"""
AstroSorter - Modern UI Components
AAA-level UI with cosmic theme
"""

import customtkinter as ctk
from tkinter import ttk
from typing import Optional, Callable
import os

from .classifier import ImageMetadata, ImageType


# Color Theme - Cosmic Dark
class Theme:
    """Application theme colors and constants"""
    
    # Primary colors
    BG_PRIMARY = "#0d0d1a"        # Deepest space
    BG_SECONDARY = "#1a1a2e"      # Dark navy
    BG_TERTIARY = "#16213e"       # Medium navy
    BG_CARD = "#1f1f3d"           # Card background
    
    # Accent colors
    ACCENT_PRIMARY = "#e94560"    # Cosmic red/pink
    ACCENT_SECONDARY = "#0f3460"  # Medium blue
    ACCENT_HIGHLIGHT = "#00d9ff"  # Cyan glow
    ACCENT_SUCCESS = "#00ff88"    # Green success
    ACCENT_WARNING = "#ffa500"    # Orange warning
    
    # Text colors
    TEXT_PRIMARY = "#ffffff"      # White
    TEXT_SECONDARY = "#a0a0a0"    # Gray
    TEXT_MUTED = "#606080"        # Muted
    
    # Gradient colors for cards
    GRADIENT_START = "#1a1a2e"
    GRADIENT_END = "#0f3460"
    
    # Border
    BORDER_COLOR = "#2a2a4a"
    BORDER_LIGHT = "#3a3a5a"
    
    # Spacing
    PAD_SMALL = 8
    PAD_MEDIUM = 16
    PAD_LARGE = 24
    PAD_XLARGE = 32
    
    # Border radius
    RADIUS_SMALL = 6
    RADIUS_MEDIUM = 10
    RADIUS_LARGE = 16
    RADIUS_XLARGE = 24
    
    # Font sizes
    FONT_TITLE = 28
    FONT_HEADING = 20
    FONT_SUBHEADING = 16
    FONT_BODY = 14
    FONT_SMALL = 12
    FONT_TINY = 10


# Set appearance mode
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class AstroButton(ctk.CTkButton):
    """Custom styled button with glow effect"""
    
    def __init__(self, *args, **kwargs):
        # Set custom colors
        fg_color = kwargs.pop('fg_color', Theme.ACCENT_PRIMARY)
        hover_color = kwargs.pop('hover_color', '#ff6b8a')
        border_color = kwargs.pop('border_color', Theme.ACCENT_HIGHLIGHT)
        
        super().__init__(
            *args,
            fg_color=fg_color,
            hover_color=hover_color,
            border_color=border_color,
            border_width=2,
            corner_radius=Theme.RADIUS_MEDIUM,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=44,
            **kwargs
        )


class AstroCard(ctk.CTkFrame):
    """Custom card with gradient background and glow"""
    
    def __init__(self, *args, **kwargs):
        fg_color = kwargs.pop('fg_color', Theme.BG_CARD)
        
        super().__init__(
            *args,
            fg_color=fg_color,
            border_color=Theme.BORDER_COLOR,
            border_width=1,
            corner_radius=Theme.RADIUS_LARGE,
            **kwargs
        )


class GlassCard(ctk.CTkFrame):
    """Glass morphism style card"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            fg_color=(Theme.BG_CARD, Theme.BG_CARD),
            border_color=Theme.BORDER_LIGHT,
            border_width=1,
            corner_radius=Theme.RADIUS_LARGE,
            **kwargs
        )


class DropZone(ctk.CTkFrame):
    """Drag and drop zone for files"""
    
    def __init__(self, *args, on_drop: Callable = None, **kwargs):
        self.on_drop = on_drop
        
        super().__init__(
            *args,
            fg_color=Theme.BG_SECONDARY,
            border_color=Theme.ACCENT_HIGHLIGHT,
            border_width=2,
            corner_radius=Theme.RADIUS_XLARGE,
            **kwargs
        )
        
        self._setup_ui()
        self._bind_events()
    
    def _setup_ui(self):
        """Setup the drop zone UI"""
        # Icon
        self.icon_label = ctk.CTkLabel(
            self,
            text="📁",
            font=ctk.CTkFont(size=64),
            text_color=Theme.ACCENT_HIGHLIGHT
        )
        self.icon_label.pack(pady=(40, 20))
        
        # Title
        self.title_label = ctk.CTkLabel(
            self,
            text="Drop Images Here",
            font=ctk.CTkFont(size=Theme.FONT_HEADING, weight="bold"),
            text_color=Theme.TEXT_PRIMARY
        )
        self.title_label.pack()
        
        # Subtitle
        self.subtitle_label = ctk.CTkLabel(
            self,
            text="or click to browse",
            font=ctk.CTkFont(size=Theme.FONT_BODY),
            text_color=Theme.TEXT_SECONDARY
        )
        self.subtitle_label.pack(pady=(8, 0))
        
        # Supported formats
        self.formats_label = ctk.CTkLabel(
            self,
            text="Supports: CR2, NEF, ARW, RAF, DNG, FITS, TIFF, JPG",
            font=ctk.CTkFont(size=Theme.FONT_SMALL),
            text_color=Theme.TEXT_MUTED
        )
        self.formats_label.pack(pady=(20, 40))
    
    def _bind_events(self):
        """Bind drag and drop events"""
        # Enable drag and drop
        self.drop_target_register('DND_Files')
        self.dnd_bind('<<Drop>>', self._on_drop)
        
        # Click to browse
        self.bind('<Button-1>', self._on_click)
        self.icon_label.bind('<Button-1>', self._on_click)
        self.title_label.bind('<Button-1>', self._on_click)
        self.subtitle_label.bind('<Button-1>', self._on_click)
    
    def _on_drop(self, event):
        """Handle file drop"""
        if self.on_drop:
            self.on_drop(event.data)
    
    def _on_click(self, event):
        """Handle click to browse"""
        # This will be connected to the main app's browse function
        pass
    
    def set_browse_command(self, command: Callable):
        """Set the browse command"""
        self._browse_command = command


class TypeCard(AstroCard):
    """Card displaying image type count"""
    
    def __init__(self, *args, image_type: ImageType = None, **kwargs):
        self.image_type = image_type
        super().__init__(*args, **kwargs)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the type card UI"""
        # Icon based on type
        icons = {
            ImageType.LIGHT: "🌟",
            ImageType.DARK: "🌙",
            ImageType.FLAT: "☀️",
            ImageType.BIAS: "📊",
            ImageType.FLAT_DARK: "🔲",
            ImageType.UNKNOWN: "❓"
        }
        
        # Title
        title = self.image_type.value if self.image_type else "Unknown"
        
        # Container for icon and count
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Icon
        self.icon = ctk.CTkLabel(
            self.container,
            text=icons.get(self.image_type, "❓"),
            font=ctk.CTkFont(size=40),
            text_color=Theme.ACCENT_HIGHLIGHT
        )
        self.icon.pack()
        
        # Count
        self.count_label = ctk.CTkLabel(
            self.container,
            text="0",
            font=ctk.CTkFont(size=Theme.FONT_TITLE, weight="bold"),
            text_color=Theme.TEXT_PRIMARY
        )
        self.count_label.pack(pady=(10, 0))
        
        # Title
        self.title_label = ctk.CTkLabel(
            self.container,
            text=title,
            font=ctk.CTkFont(size=Theme.FONT_BODY),
            text_color=Theme.TEXT_SECONDARY
        )
        self.title_label.pack(pady=(5, 0))
    
    def update_count(self, count: int):
        """Update the count display"""
        self.count_label.configure(text=str(count))


class ProgressRing(ctk.CTkCanvas):
    """Custom progress ring widget"""
    
    def __init__(self, *args, **kwargs):
        size = kwargs.pop('size', 120)
        super().__init__(*args, width=size, height=size, **kwargs)
        
        self.size = size
        self.progress = 0
        self._ring_id = None
        self._text_id = None
        
        self._draw()
    
    def _draw(self):
        """Draw the progress ring"""
        center = self.size // 2
        radius = self.size // 2 - 10
        thickness = 8
        
        # Background ring
        self.create_oval(
            center - radius, center - radius,
            center + radius, center + radius,
            outline=Theme.BG_TERTIARY,
            width=thickness
        )
        
        # Progress arc
        if self.progress > 0:
            # Calculate arc
            angle = 360 * (self.progress / 100)
            self._ring_id = self.create_arc(
                center - radius, center - radius,
                center + radius, center + radius,
                start=90, extent=-angle,
                outline=Theme.ACCENT_HIGHLIGHT,
                width=thickness,
                style="arc"
            )
        
        # Percentage text
        self._text_id = self.create_text(
            center, center,
            text=f"{self.progress}%",
            font=ctk.CTkFont(size=18, weight="bold"),
            fill=Theme.TEXT_PRIMARY
        )
    
    def set_progress(self, value: float):
        """Set progress value (0-100)"""
        self.progress = max(0, min(100, value))
        self._draw()


class FileTable(ctk.CTkFrame):
    """Table widget for displaying files"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, fg_color="transparent", **kwargs)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup table UI"""
        # Style configuration
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Treeview",
            background=Theme.BG_SECONDARY,
            foreground=Theme.TEXT_PRIMARY,
            fieldbackground=Theme.BG_SECONDARY,
            rowheight=32,
            font=("Segoe UI", 11)
        )
        style.configure(
            "Treeview.Heading",
            background=Theme.BG_TERTIARY,
            foreground=Theme.TEXT_PRIMARY,
            font=("Segoe UI", 12, "bold")
        )
        style.map(
            "Treeview",
            background=[("selected", Theme.ACCENT_PRIMARY)],
            foreground=[("selected", Theme.TEXT_PRIMARY)]
        )
        
        # Scrollbar
        scrollbar = ctk.CTkScrollbar(self, orientation="vertical")
        scrollbar.pack(side="right", fill="y")
        
        # Treeview
        self.tree = ttk.Treeview(
            self,
            columns=("filename", "type", "confidence", "exposure", "iso"),
            show="headings",
            yscrollcommand=scrollbar.set,
            style="Treeview"
        )
        self.tree.pack(side="left", fill="both", expand=True)
        
        scrollbar.configure(command=self.tree.yview)
        
        # Columns
        self.tree.heading("filename", text="Filename")
        self.tree.heading("type", text="Type")
        self.tree.heading("confidence", text="Confidence")
        self.tree.heading("exposure", text="Exposure")
        self.tree.heading("iso", text="ISO")
        
        self.tree.column("filename", width=250)
        self.tree.column("type", width=100)
        self.tree.column("confidence", width=100)
        self.tree.column("exposure", width=100)
        self.tree.column("iso", width=80)
    
    def add_file(self, metadata: ImageMetadata):
        """Add a file to the table"""
        confidence_str = f"{metadata.confidence:.0%}" if metadata.confidence > 0 else "-"
        exposure_str = f"{metadata.exposure_time:.2f}s" if metadata.exposure_time else "-"
        iso_str = str(metadata.iso) if metadata.iso else "-"
        
        self.tree.insert("", "end", values=(
            metadata.filename,
            metadata.classified_type.value,
            confidence_str,
            exposure_str,
            iso_str
        ))
    
    def clear(self):
        """Clear all items"""
        for item in self.tree.get_children():
            self.tree.delete(item)


class Sidebar(ctk.CTkFrame):
    """Application sidebar navigation"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            fg_color=Theme.BG_SECONDARY,
            width=220,
            corner_radius=0,
            **kwargs
        )
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup sidebar UI"""
        # Logo/Brand area
        brand_frame = ctk.CTkFrame(self, fg_color="transparent")
        brand_frame.pack(fill="x", padx=20, pady=(30, 20))
        
        # App icon
        ctk.CTkLabel(
            brand_frame,
            text="🔭",
            font=ctk.CTkFont(size=40)
        ).pack(side="left")
        
        # App name
        ctk.CTkLabel(
            brand_frame,
            text="AstroSorter",
            font=ctk.CTkFont(size=Theme.FONT_HEADING, weight="bold"),
            text_color=Theme.ACCENT_HIGHLIGHT
        ).pack(side="left", padx=(10, 0))
        
        # Navigation items
        self.nav_buttons = []
        
        nav_items = [
            ("🏠", "Home"),
            ("📁", "Source Files"),
            ("🔍", "Classification"),
            ("⚙️", "Settings")
        ]
        
        for icon, text in nav_items:
            btn = self._create_nav_button(icon, text)
            btn.pack(fill="x", padx=16, pady=4)
            self.nav_buttons.append(btn)
        
        # Version info at bottom
        ctk.CTkLabel(
            self,
            text="v1.0.0",
            font=ctk.CTkFont(size=Theme.FONT_TINY),
            text_color=Theme.TEXT_MUTED
        ).pack(side="bottom", pady=20)
    
    def _create_nav_button(self, icon: str, text: str) -> ctk.CTkButton:
        """Create a navigation button"""
        btn = ctk.CTkButton(
            self,
            text=f"  {icon}  {text}",
            fg_color="transparent",
            hover_color=Theme.BG_TERTIARY,
            text_color=Theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=Theme.FONT_BODY),
            height=44,
            corner_radius=Theme.RADIUS_MEDIUM,
            anchor="w",
            border_width=0
        )
        return btn
    
    def set_active(self, index: int):
        """Set active navigation item"""
        for i, btn in enumerate(self.nav_buttons):
            if i == index:
                btn.configure(
                    fg_color=Theme.ACCENT_PRIMARY,
                    text_color=Theme.TEXT_PRIMARY
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=Theme.TEXT_SECONDARY
                )


class StatusBar(ctk.CTkFrame):
    """Application status bar"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            fg_color=Theme.BG_SECONDARY,
            height=32,
            corner_radius=0,
            **kwargs
        )
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup status bar UI"""
        # Status text
        self.status_label = ctk.CTkLabel(
            self,
            text="Ready",
            font=ctk.CTkFont(size=Theme.FONT_SMALL),
            text_color=Theme.TEXT_SECONDARY
        )
        self.status_label.pack(side="left", padx=16)
        
        # Progress (hidden by default)
        self.progress = ctk.CTkProgressBar(
            self,
            fg_color=Theme.BG_TERTIARY,
            progress_color=Theme.ACCENT_HIGHLIGHT,
            height=4
        )
        self.progress.set(0)
        self.progress.pack(side="right", fill="x", expand=True, padx=16, pady=8)
        self.progress.pack_forget()  # Hide initially
    
    def set_status(self, text: str):
        """Set status text"""
        self.status_label.configure(text=text)
    
    def show_progress(self):
        """Show progress bar"""
        self.progress.pack(side="right", fill="x", expand=True, padx=16, pady=8)
    
    def hide_progress(self):
        """Hide progress bar"""
        self.progress.pack_forgets()
    
    def set_progress(self, value: float):
        """Set progress value (0-1)"""
        self.progress.set(value)


class MetadataPanel(ctk.CTkFrame):
    """Panel displaying image metadata"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            fg_color=Theme.BG_SECONDARY,
            corner_radius=0,
            **kwargs
        )
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup metadata panel UI"""
        # Title
        ctk.CTkLabel(
            self,
            text="Image Details",
            font=ctk.CTkFont(size=Theme.FONT_SUBHEADING, weight="bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=20, pady=(16, 8))
        
        # Scrollable frame for metadata
        self.meta_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent"
        )
        self.meta_frame.pack(fill="both", expand=True, padx=16, pady=8)
        
        # Placeholder
        self.placeholder = ctk.CTkLabel(
            self.meta_frame,
            text="Select an image to view details",
            font=ctk.CTkFont(size=Theme.FONT_BODY),
            text_color=Theme.TEXT_MUTED
        )
        self.placeholder.pack(pady=40)
    
    def display_metadata(self, metadata: ImageMetadata):
        """Display metadata for an image"""
        # Clear existing
        for widget in self.meta_frame.winfo_children():
            widget.destroy()
        
        # Create metadata rows
        fields = [
            ("Filename", metadata.filename),
            ("Type", metadata.classified_type.value),
            ("Confidence", f"{metadata.confidence:.0%}"),
            ("Exposure", f"{metadata.exposure_time:.4f}s" if metadata.exposure_time else "-"),
            ("ISO", str(metadata.iso) if metadata.iso else "-"),
            ("Filter", metadata.filter_name or "-"),
            ("Camera", metadata.camera or "-"),
            ("Object", metadata.object_name or "-"),
            ("CCD Temp", f"{metadata.ccd_temp}°C" if metadata.ccd_temp else "-"),
            ("Date", metadata.date_obs or "-"),
            ("Mean", f"{metadata.mean:.1f}" if metadata.mean else "-"),
            ("Std Dev", f"{metadata.std:.1f}" if metadata.std else "-"),
        ]
        
        for label, value in fields:
            self._create_meta_row(label, value)
    
    def _create_meta_row(self, label: str, value: str):
        """Create a metadata row"""
        row = ctk.CTkFrame(self.meta_frame, fg_color="transparent")
        row.pack(fill="x", pady=4)
        
        ctk.CTkLabel(
            row,
            text=f"{label}:",
            font=ctk.CTkFont(size=Theme.FONT_SMALL),
            text_color=Theme.TEXT_SECONDARY,
            width=100,
            anchor="w"
        ).pack(side="left")
        
        ctk.CTkLabel(
            row,
            text=value,
            font=ctk.CTkFont(size=Theme.FONT_SMALL, weight="bold"),
            text_color=Theme.TEXT_PRIMARY,
            anchor="w"
        ).pack(side="left", fill="x", expand=True)


class AnimationHelper:
    """Helper class for UI animations"""
    
    @staticmethod
    def fade_in(widget, duration: int = 300):
        """Fade in widget"""
        widget.alpha = 0
        # Simple implementation - would need actual animation
        widget.pack()
    
    @staticmethod
    def pulse(widget):
        """Create pulse animation on widget"""
        # Placeholder for pulse animation
        pass
