"""
AstroSorter - Main Application
AAA-level astrophotography image sorting application
"""

import os
import shutil
import threading
import json
from pathlib import Path
from tkinter import filedialog, messagebox
from datetime import datetime
from typing import Optional

import customtkinter as ctk

from AstroSorter.classifier import (
    AstroClassifier, BatchClassifier, ImageMetadata, ImageType
)
from AstroSorter.ui_components import Theme


class AstroSorterApp(ctk.CTk):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Window configuration
        self.title("AstroSorter - Astrophotography Image Classifier")
        self.geometry("1400x850")
        self.minsize(1200, 700)
        
        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Set theme colors
        self.configure(fg_color=Theme.BG_PRIMARY)
        
        # Initialize classifier
        self.classifier = AstroClassifier()
        self.batch_classifier = BatchClassifier(self.classifier)
        
        # State
        self.current_directory: Optional[str] = None
        self.results: list[ImageMetadata] = []
        self.is_processing = False
        self.current_view = "home"
        
        # Settings
        self.settings = {
            'recursive': True,
            'compute_stats': True,
            'export_method': 'copy',
            'create_subfolders': True,
            'export_json_report': True
        }
        
        # Setup UI
        self._setup_ui()
        
        # Center window
        self._center_window()
    
    def _setup_ui(self):
        """Setup the main UI"""
        
        # Sidebar
        self._setup_sidebar()
        
        # Main content area
        self.main_frame = ctk.CTkFrame(self, fg_color=Theme.BG_PRIMARY, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # Header
        self._setup_header()
        
        # Content container
        self.content_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.content_container.grid_rowconfigure(0, weight=1)
        self.content_container.grid_columnconfigure(0, weight=1)
        
        # Show home view
        self._show_home_view()
        
        # Status bar
        self._setup_status_bar()
    
    def _setup_sidebar(self):
        """Setup sidebar"""
        self.sidebar = ctk.CTkFrame(self, fg_color=Theme.BG_SECONDARY, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        # Logo area
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=20, pady=(25, 15))
        
        ctk.CTkLabel(logo_frame, text="🔭", font=ctk.CTkFont(size=36)).pack(side="left")
        ctk.CTkLabel(logo_frame, text="AstroSorter", font=ctk.CTkFont(size=20, weight="bold"), 
                     text_color=Theme.ACCENT_HIGHLIGHT).pack(side="left", padx=(10, 0))
        
        # Navigation
        nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_frame.pack(fill="x", padx=10, pady=10)
        
        self.nav_buttons = []
        nav_items = [("🏠", "Home", 0), ("📁", "Source Files", 1), ("⚙️", "Settings", 2)]
        
        for icon, text, idx in nav_items:
            btn = ctk.CTkButton(
                nav_frame, text=f"  {icon}  {text}",
                fg_color="transparent", hover_color=Theme.BG_TERTIARY,
                text_color=Theme.TEXT_SECONDARY, font=ctk.CTkFont(size=14),
                height=40, corner_radius=8, anchor="w", border_width=0,
                command=lambda i=idx: self.switch_view(i)
            )
            btn.pack(fill="x", pady=3)
            self.nav_buttons.append(btn)
        
        self.nav_buttons[0].configure(fg_color=Theme.ACCENT_PRIMARY, text_color=Theme.TEXT_PRIMARY)
        
        # Version
        ctk.CTkLabel(self.sidebar, text="v1.0.0", font=ctk.CTkFont(size=11),
                     text_color=Theme.TEXT_MUTED).pack(side="bottom", pady=15)
    
    def _setup_header(self):
        """Setup header"""
        header = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=25, pady=(20, 15))
        
        self.header_title = ctk.CTkLabel(header, text="Welcome to AstroSorter",
            font=ctk.CTkFont(size=24, weight="bold"), text_color=Theme.TEXT_PRIMARY)
        self.header_title.pack(side="left")
        
        # Action buttons
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")
        
        self.browse_btn = ctk.CTkButton(
            btn_frame, text="📂 Browse Folder", fg_color=Theme.ACCENT_SECONDARY,
            hover_color=Theme.ACCENT_PRIMARY, height=38, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"), command=self.browse_folder
        )
        self.browse_btn.pack(side="right", padx=8)
        
        self.export_btn = ctk.CTkButton(
            btn_frame, text="💾 Apply & Export", fg_color=Theme.ACCENT_SUCCESS,
            hover_color="#00cc6a", height=38, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"), command=self.export_results,
            state="disabled"
        )
        self.export_btn.pack(side="right")
    
    def _setup_status_bar(self):
        """Setup status bar"""
        self.status_bar = ctk.CTkFrame(self.main_frame, fg_color=Theme.BG_SECONDARY, height=36, corner_radius=0)
        self.status_bar.grid(row=2, column=0, sticky="ew")
        
        self.status_label = ctk.CTkLabel(self.status_bar, text="Ready", font=ctk.CTkFont(size=12),
                                         text_color=Theme.TEXT_SECONDARY)
        self.status_label.pack(side="left", padx=20)
        
        self.progress = ctk.CTkProgressBar(self.status_bar, fg_color=Theme.BG_TERTIARY,
                                           progress_color=Theme.ACCENT_HIGHLIGHT, height=4)
        self.progress.set(0)
        self.progress.pack(side="right", fill="x", expand=True, padx=20, pady=8)
        self.progress.pack_forget()
    
    def switch_view(self, index: int):
        """Switch between views"""
        # Update nav buttons
        for i, btn in enumerate(self.nav_buttons):
            if i == index:
                btn.configure(fg_color=Theme.ACCENT_PRIMARY, text_color=Theme.TEXT_PRIMARY)
            else:
                btn.configure(fg_color="transparent", text_color=Theme.TEXT_SECONDARY)
        
        # Hide all views
        for widget in self.content_container.winfo_children():
            widget.grid_forget()
        
        if index == 0:
            self.current_view = "home"
            self.header_title.configure(text="Welcome to AstroSorter")
            self._show_home_view()
        elif index == 1:
            self.current_view = "files"
            self.header_title.configure(text="Source Files")
            self._show_files_view()
        elif index == 2:
            self.current_view = "settings"
            self.header_title.configure(text="Settings")
            self._show_settings_view()
    
    def _show_home_view(self):
        """Show home/drop zone view"""
        # Drop zone card
        drop_card = ctk.CTkFrame(self.content_container, fg_color=Theme.BG_CARD, 
                                  border_color=Theme.BORDER_COLOR, border_width=1, corner_radius=20)
        drop_card.grid(row=0, column=0, sticky="nsew", pady=10)
        
        drop_card.grid_rowconfigure(2, weight=1)
        drop_card.grid_columnconfigure(0, weight=1)
        
        # Icon
        ctk.CTkLabel(drop_card, text="📂", font=ctk.CTkFont(size=72),
                     text_color=Theme.ACCENT_HIGHLIGHT).grid(row=0, column=0, pady=(50, 20))
        
        # Title
        ctk.CTkLabel(drop_card, text="Select Image Folder",
                     font=ctk.CTkFont(size=24, weight="bold"), text_color=Theme.TEXT_PRIMARY
                     ).grid(row=1, column=0)
        
        ctk.CTkLabel(drop_card, text="Choose a folder containing your astrophotography images\nto automatically classify them into Lights, Darks, Flats, and Biases",
                     font=ctk.CTkFont(size=13), text_color=Theme.TEXT_SECONDARY
                     ).grid(row=2, column=0, pady=10)
        
        # Browse button
        ctk.CTkButton(drop_card, text="Browse Folder", fg_color=Theme.ACCENT_PRIMARY,
                      hover_color="#ff6b8a", height=45, corner_radius=10,
                      font=ctk.CTkFont(size=15, weight="bold"), command=self.browse_folder
                      ).grid(row=3, column=0, pady=30)
        
        # Supported formats
        ctk.CTkLabel(drop_card, text="Supports: CR2, NEF, ARW, RAF, DNG, FITS, TIFF, JPG • All major camera brands",
                     font=ctk.CTkFont(size=11), text_color=Theme.TEXT_MUTED
                     ).grid(row=4, column=0, pady=(0, 40))
        
        # Results summary (initially hidden)
        self.summary_frame = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self.summary_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.summary_frame.grid_forget()
    
    def _show_files_view(self):
        """Show files view with classification results"""
        if not self.results:
            # No results yet
            empty_frame = ctk.CTkFrame(self.content_container, fg_color=Theme.BG_CARD, 
                                       corner_radius=20)
            empty_frame.grid(row=0, column=0, sticky="nsew")
            
            ctk.CTkLabel(empty_frame, text="📁", font=ctk.CTkFont(size=64),
                         text_color=Theme.TEXT_MUTED).pack(pady=(80, 20))
            ctk.CTkLabel(empty_frame, text="No images loaded",
                         font=ctk.CTkFont(size=18, weight="bold"), text_color=Theme.TEXT_PRIMARY).pack()
            ctk.CTkLabel(empty_frame, text="Browse a folder to classify images",
                         font=ctk.CTkFont(size=13), text_color=Theme.TEXT_SECONDARY).pack(pady=10)
            ctk.CTkButton(empty_frame, text="Browse Folder", fg_color=Theme.ACCENT_PRIMARY,
                          hover_color="#ff6b8a", height=40, corner_radius=8,
                          command=self.browse_folder).pack(pady=20)
            return
        
        # Files view with table and type controls
        self._setup_files_view()
    
    def _setup_files_view(self):
        """Setup the files view with table"""
        # Clear content
        for widget in self.content_container.winfo_children():
            widget.grid_forget()
        
        # Main container
        main_container = ctk.CTkFrame(self.content_container, fg_color="transparent")
        main_container.grid(row=0, column=0, sticky="nsew")
        main_container.grid_rowconfigure(2, weight=1)
        main_container.grid_columnconfigure(0, weight=1)
        
        # Type summary cards
        cards_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        cards_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        
        # Create type cards
        self.type_cards = {}
        types = [(ImageType.LIGHT, "🌟", "Lights"), (ImageType.DARK, "🌙", "Darks"),
                 (ImageType.FLAT, "☀️", "Flats"), (ImageType.BIAS, "📊", "Biases"),
                 (ImageType.FLAT_DARK, "🔲", "Flat-Darks"), (ImageType.UNKNOWN, "❓", "Unknown")]
        
        for i, (img_type, icon, label) in enumerate(types):
            card = self._create_type_card(cards_frame, img_type, icon, label)
            card.grid(row=0, column=i, sticky="ew", padx=6)
            self.type_cards[img_type] = card
        
        cards_frame.grid_columnconfigure(tuple(range(len(types))), weight=1)
        
        # Info label
        info_label = ctk.CTkLabel(main_container, 
            text="💡 Click on a type dropdown in the table below to change it, then click 'Apply & Export' to organize files",
            font=ctk.CTkFont(size=12), text_color=Theme.TEXT_SECONDARY)
        info_label.grid(row=1, column=0, sticky="w", pady=(0, 10))
        
        # Table frame
        table_frame = ctk.CTkFrame(main_container, fg_color=Theme.BG_CARD, corner_radius=12)
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.grid_rowconfigure(1, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Table title
        ctk.CTkLabel(table_frame, text="Classified Files", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=Theme.TEXT_PRIMARY).grid(row=0, column=0, sticky="w", padx=20, pady=(15, 10))
        
        # Scrollable table
        self.table_scroll = ctk.CTkScrollableFrame(table_frame, fg_color="transparent")
        self.table_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # Populate table
        self._populate_file_table()
    
    def _create_type_card(self, parent, img_type, icon, label):
        """Create a type summary card"""
        card = ctk.CTkFrame(parent, fg_color=Theme.BG_CARD, corner_radius=12)
        
        count = sum(1 for r in self.results if r.classified_type == img_type)
        
        icon_label = ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=28))
        icon_label.pack(pady=(15, 5))
        
        count_label = ctk.CTkLabel(card, text=str(count), font=ctk.CTkFont(size=24, weight="bold"),
                                    text_color=Theme.TEXT_PRIMARY)
        count_label.pack()
        
        type_label = ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=12),
                                   text_color=Theme.TEXT_SECONDARY)
        type_label.pack(pady=(0, 15))
        
        return card
    
    def _populate_file_table(self):
        """Populate the file table"""
        # Clear existing
        for widget in self.table_scroll.winfo_children():
            widget.destroy()
        
        # Header
        header_frame = ctk.CTkFrame(self.table_scroll, fg_color=Theme.BG_TERTIARY, corner_radius=8)
        header_frame.pack(fill="x", pady=(0, 5))
        
        headers = [("File", 250), ("Detected Type", 140), ("Exposure", 90), ("ISO", 70), ("Camera", 120)]
        for i, (text, width) in enumerate(headers):
            ctk.CTkLabel(header_frame, text=text, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=Theme.TEXT_PRIMARY, width=width).pack(side="left", padx=12, pady=10)
        
        # Sort results by type
        sorted_results = sorted(self.results, key=lambda x: x.classified_type.value)
        
        # File rows
        self.file_rows = []
        for idx, metadata in enumerate(sorted_results):
            row_frame = ctk.CTkFrame(self.table_scroll, fg_color=Theme.BG_SECONDARY if idx % 2 == 0 else "transparent", corner_radius=6)
            row_frame.pack(fill="x", pady=2)
            
            # Filename
            fname = metadata.filename[:35] + ("..." if len(metadata.filename) > 35 else "")
            ctk.CTkLabel(row_frame, text=fname,
                         font=ctk.CTkFont(size=11), text_color=Theme.TEXT_PRIMARY, width=250, anchor="w"
                         ).pack(side="left", padx=12, pady=8)
            
            # Type selector (dropdown)
            type_var = ctk.StringVar(value=metadata.classified_type.value)
            type_menu = ctk.CTkOptionMenu(row_frame, values=["Lights", "Darks", "Flats", "Biases", "Flat-Darks", "Unknown"],
                                          variable=type_var, fg_color=Theme.ACCENT_SECONDARY,
                                          button_color=Theme.ACCENT_PRIMARY, button_hover_color="#ff6b8a",
                                          dropdown_fg_color=Theme.BG_CARD, width=140, height=30,
                                          font=ctk.CTkFont(size=11))
            type_menu.pack(side="left", padx=5)
            type_menu.configure(command=lambda m=metadata, v=type_var: self._on_type_change(m, v))
            
            # Exposure
            exp_str = f"{metadata.exposure_time:.2f}s" if metadata.exposure_time else "-"
            ctk.CTkLabel(row_frame, text=exp_str, font=ctk.CTkFont(size=11), 
                         text_color=Theme.TEXT_SECONDARY, width=90).pack(side="left", padx=5)
            
            # ISO
            ctk.CTkLabel(row_frame, text=str(metadata.iso) if metadata.iso else "-", 
                         font=ctk.CTkFont(size=11), text_color=Theme.TEXT_SECONDARY, width=70).pack(side="left", padx=5)
            
            # Camera
            cam_str = (metadata.camera[:15] + "..") if metadata.camera and len(metadata.camera) > 17 else (metadata.camera or "-")
            ctk.CTkLabel(row_frame, text=cam_str, font=ctk.CTkFont(size=11), 
                         text_color=Theme.TEXT_SECONDARY, width=120).pack(side="left", padx=5)
            
            self.file_rows.append((metadata, type_var, row_frame))
    
    def _on_type_change(self, metadata: ImageMetadata, type_var: ctk.StringVar):
        """Handle type change"""
        new_type = type_var.get()
        
        # Update metadata
        type_map = {
            "Lights": ImageType.LIGHT, "Darks": ImageType.DARK, 
            "Flats": ImageType.FLAT, "Biases": ImageType.BIAS,
            "Flat-Darks": ImageType.FLAT_DARK, "Unknown": ImageType.UNKNOWN
        }
        
        metadata.classified_type = type_map.get(new_type, ImageType.UNKNOWN)
        metadata.confidence = 1.0
        
        # Refresh the summary
        self._refresh_summary()
    
    def _refresh_summary(self):
        """Refresh the type summary counts"""
        for img_type, card in self.type_cards.items():
            count = sum(1 for r in self.results if r.classified_type == img_type)
            # Update the count label (second child)
            children = card.winfo_children()
            if len(children) > 1:
                children[1].configure(text=str(count))
    
    def _show_settings_view(self):
        """Show settings view"""
        # Clear content
        for widget in self.content_container.winfo_children():
            widget.grid_forget()
        
        settings_card = ctk.CTkFrame(self.content_container, fg_color=Theme.BG_CARD, corner_radius=20)
        settings_card.grid(row=0, column=0, sticky="nsew", padx=50, pady=30)
        
        # Title
        ctk.CTkLabel(settings_card, text="⚙️ Settings", font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=Theme.TEXT_PRIMARY).pack(anchor="w", padx=30, pady=(25, 20))
        
        # Scanning options
        ctk.CTkLabel(settings_card, text="Scanning Options", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=Theme.ACCENT_HIGHLIGHT).pack(anchor="w", padx=30, pady=(15, 10))
        
        self.recursive_var = ctk.BooleanVar(value=self.settings['recursive'])
        ctk.CTkCheckBox(settings_card, text="Scan subfolders recursively", variable=self.recursive_var,
                        font=ctk.CTkFont(size=13), text_color=Theme.TEXT_PRIMARY).pack(anchor="w", padx=30, pady=5)
        
        self.stats_var = ctk.BooleanVar(value=self.settings['compute_stats'])
        ctk.CTkCheckBox(settings_card, text="Compute image statistics (slower but more accurate)", 
                        variable=self.stats_var, font=ctk.CTkFont(size=13), 
                        text_color=Theme.TEXT_PRIMARY).pack(anchor="w", padx=30, pady=5)
        
        # Export options
        ctk.CTkLabel(settings_card, text="Export Options", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=Theme.ACCENT_HIGHLIGHT).pack(anchor="w", padx=30, pady=(25, 10))
        
        self.export_method_var = ctk.StringVar(value=self.settings['export_method'])
        ctk.CTkRadioButton(settings_card, text="Copy files (keep originals)", variable=self.export_method_var,
                           value="copy", font=ctk.CTkFont(size=13), text_color=Theme.TEXT_PRIMARY,
                           fg_color=Theme.ACCENT_PRIMARY).pack(anchor="w", padx=30, pady=5)
        ctk.CTkRadioButton(settings_card, text="Move files (remove originals)", variable=self.export_method_var,
                           value="move", font=ctk.CTkFont(size=13), text_color=Theme.TEXT_PRIMARY,
                           fg_color=Theme.ACCENT_PRIMARY).pack(anchor="w", padx=30, pady=5)
        
        self.json_var = ctk.BooleanVar(value=self.settings['export_json_report'])
        ctk.CTkCheckBox(settings_card, text="Export JSON classification report", variable=self.json_var,
                        font=ctk.CTkFont(size=13), text_color=Theme.TEXT_PRIMARY).pack(anchor="w", padx=30, pady=(15, 5))
        
        # Save button
        ctk.CTkButton(settings_card, text="Save Settings", fg_color=Theme.ACCENT_PRIMARY,
                      hover_color="#ff6b8a", height=40, corner_radius=8,
                      font=ctk.CTkFont(size=14, weight="bold"), command=self._save_settings
                      ).pack(pady=30)
    
    def _save_settings(self):
        """Save settings"""
        self.settings['recursive'] = self.recursive_var.get()
        self.settings['compute_stats'] = self.stats_var.get()
        self.settings['export_method'] = self.export_method_var.get()
        self.settings['export_json_report'] = self.json_var.get()
        
        messagebox.showinfo("Settings", "Settings saved successfully!")
    
    def _center_window(self):
        """Center the window"""
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = self.winfo_width()
        window_height = self.winfo_height()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    def browse_folder(self):
        """Browse for folder"""
        folder = filedialog.askdirectory(title="Select folder containing astrophotography images")
        if folder:
            self.process_directory(folder)
    
    def process_directory(self, directory: str):
        """Process all images in directory"""
        if self.is_processing:
            return
        
        self.current_directory = directory
        self.is_processing = True
        
        self.status_bar.grid()
        self.status_label.configure(text=f"Scanning {Path(directory).name}...")
        self.progress.pack(side="right", fill="x", expand=True, padx=20, pady=8)
        self.progress.set(0)
        self.browse_btn.configure(state="disabled")
        
        thread = threading.Thread(target=self._process_thread, args=(directory,))
        thread.daemon = True
        thread.start()
    
    def _process_thread(self, directory: str):
        """Processing thread"""
        try:
            self.batch_classifier.set_progress_callback(self._update_progress)
            
            self.results = self.batch_classifier.classify_directory(
                directory,
                recursive=self.settings['recursive'],
                compute_stats=self.settings['compute_stats']
            )
            
            self.after(0, self._processing_complete)
        except Exception as e:
            self.after(0, lambda: self._processing_error(str(e)))
    
    def _update_progress(self, current: int, total: int, filepath: str):
        """Update progress"""
        progress = current / total
        def update():
            self.status_label.configure(text=f"Processing: {Path(filepath).name[:30]}")
            self.progress.set(progress)
        self.after(0, update)
    
    def _processing_complete(self):
        """Handle processing complete"""
        self.is_processing = False
        
        self.status_label.configure(text=f"Classified {len(self.results)} images!")
        
        try:
            self.progress.pack_forget()
        except:
            pass
        
        self.browse_btn.configure(state="normal")
        
        # Enable export
        self.export_btn.configure(state="normal")
        
        # Switch to files view
        self.switch_view(1)
        
        # Show results
        summary = self.batch_classifier.get_summary()
        result_msg = f"Classified {len(self.results)} images:\n\n"
        for img_type, count in summary['by_type'].items():
            result_msg += f"  {img_type}: {count}\n"
        
        messagebox.showinfo("Classification Complete", result_msg)
    
    def _processing_error(self, error: str):
        """Handle processing error"""
        self.is_processing = False
        self.status_label.configure(text="Error occurred")
        
        try:
            self.progress.pack_forget()
        except:
            pass
        
        self.browse_btn.configure(state="normal")
        messagebox.showerror("Error", f"Error processing files: {error}")
    
    def export_results(self):
        """Export classified results"""
        if not self.results:
            return
        
        # Ask for destination
        destination = filedialog.askdirectory(title="Select output directory")
        
        if not destination:
            return
        
        # Confirm
        move_files = self.settings['export_method'] == 'move'
        
        confirm_msg = f"{'Move' if move_files else 'Copy'} {len(self.results)} files to:\n{destination}?"
        
        if not messagebox.askyesno("Confirm Export", confirm_msg):
            return
        
        self._export_files(destination, move_files)
    
    def _export_files(self, destination: str, move: bool = False):
        """Export files"""
        self.status_bar.grid()
        self.status_label.configure(text="Exporting files...")
        self.progress.pack(side="right", fill="x", expand=True, padx=20, pady=8)
        self.progress.set(0)
        
        # Create folders
        folders = {}
        for img_type in ImageType:
            if img_type != ImageType.UNKNOWN:
                folder_path = os.path.join(destination, img_type.value)
                os.makedirs(folder_path, exist_ok=True)
                folders[img_type] = folder_path
        
        # Process each file
        total = len(self.results)
        exported = 0
        
        for i, metadata in enumerate(self.results):
            if metadata.classified_type == ImageType.UNKNOWN:
                continue
            
            dest_folder = folders.get(metadata.classified_type)
            if not dest_folder:
                continue
            
            dest_path = os.path.join(dest_folder, metadata.filename)
            
            # Handle duplicate names
            counter = 1
            base_name = Path(metadata.filename).stem
            ext = Path(metadata.filename).suffix
            while os.path.exists(dest_path):
                dest_path = os.path.join(dest_folder, f"{base_name}_{counter}{ext}")
                counter += 1
            
            try:
                if move:
                    shutil.move(metadata.filepath, dest_path)
                else:
                    shutil.copy2(metadata.filepath, dest_path)
                exported += 1
            except Exception as e:
                print(f"Error exporting {metadata.filename}: {e}")
            
            self.after(0, lambda p=(i+1)/total: self.progress.set(p))
        
        # Export JSON report
        if self.settings['export_json_report']:
            self._export_metadata_json(destination)
        
        self.status_label.configure(text=f"Exported {exported} files!")
        
        try:
            self.progress.pack_forget()
        except:
            pass
        
        # Open destination
        os.startfile(destination)
        
        messagebox.showinfo("Export Complete", f"Files exported to:\n{destination}")
    
    def _export_metadata_json(self, destination: str):
        """Export metadata to JSON"""
        metadata_list = []
        
        for metadata in self.results:
            metadata_list.append({
                'filename': metadata.filename,
                'original_path': metadata.filepath,
                'classified_type': metadata.classified_type.value,
                'confidence': metadata.confidence,
                'exposure_time': metadata.exposure_time,
                'iso': metadata.iso,
                'filter': metadata.filter_name,
                'camera': metadata.camera,
                'object_name': metadata.object_name
            })
        
        output_data = {
            'generated': datetime.now().isoformat(),
            'source_directory': self.current_directory,
            'total_files': len(self.results),
            'summary': self.batch_classifier.get_summary(),
            'files': metadata_list
        }
        
        output_path = os.path.join(destination, 'classification_report.json')
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)


def main():
    """Main entry point"""
    app = AstroSorterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
