"""
AstroSorter - Main Application
Complete rewrite with sortable columns and proper preview
"""

import os
import shutil
import threading
import json
from pathlib import Path
from tkinter import filedialog, messagebox
from datetime import datetime
from typing import Optional, List
from functools import partial

import customtkinter as ctk
from customtkinter import CTkImage

from AstroSorter.classifier import (
    ImageMetadata, ImageType, classify_directory, get_summary
)
from AstroSorter.ui_components import Theme


VERSION = "1.0.2"


class AstroSorterApp(ctk.CTk):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Window config
        self.title(f"AstroSorter v{VERSION}")
        self.geometry("1600x900")
        self.minsize(1400, 800)
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.configure(fg_color=Theme.BG_PRIMARY)
        
        # State
        self.results: List[ImageMetadata] = []
        self.current_directory: Optional[str] = None
        self.is_processing = False
        self.sort_column = "filename"
        self.sort_reverse = False
        self.selected_file: Optional[ImageMetadata] = None
        
        # Settings
        self.settings = {
            'recursive': True,
            'export_method': 'copy',
            'export_json_report': True
        }
        
        self._setup_ui()
        self._center_window()
    
    def _setup_ui(self):
        # Sidebar
        self._setup_sidebar()
        
        # Main content
        self.main_frame = ctk.CTkFrame(self, fg_color=Theme.BG_PRIMARY, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_rowconfigure(1, weight=1)
        
        # Header
        self._setup_header()
        
        # Content container
        self.content_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        
        # Show home view
        self._show_home_view()
        
        # Status bar
        self._setup_status_bar()
    
    def _setup_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, fg_color=Theme.BG_SECONDARY, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        # Logo
        logo = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo.pack(fill="x", padx=20, pady=(25, 15))
        
        ctk.CTkLabel(logo, text="🔭", font=ctk.CTkFont(size=36)).pack(side="left")
        ctk.CTkLabel(logo, text="AstroSorter", font=ctk.CTkFont(size=20, weight="bold"), 
                     text_color=Theme.ACCENT_HIGHLIGHT).pack(side="left", padx=(10, 0))
        ctk.CTkLabel(logo, text=f"v{VERSION}", font=ctk.CTkFont(size=11),
                     text_color=Theme.TEXT_MUTED).pack(side="right")
        
        # Nav
        nav = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav.pack(fill="x", padx=10, pady=10)
        
        self.nav_buttons = []
        for i, (icon, text) in enumerate([("🏠", "Home"), ("📁", "Source Files"), ("⚙️", "Settings")]):
            btn = ctk.CTkButton(nav, text=f"  {icon}  {text}",
                fg_color="transparent", hover_color=Theme.BG_TERTIARY,
                text_color=Theme.TEXT_SECONDARY, font=ctk.CTkFont(size=14),
                height=40, corner_radius=8, anchor="w", border_width=0,
                command=lambda idx=i: self.switch_view(idx))
            btn.pack(fill="x", pady=3)
            self.nav_buttons.append(btn)
        
        self.nav_buttons[0].configure(fg_color=Theme.ACCENT_PRIMARY, text_color=Theme.TEXT_PRIMARY)
    
    def _setup_header(self):
        header = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=25, pady=(20, 15))
        
        self.header_title = ctk.CTkLabel(header, text="Welcome to AstroSorter",
            font=ctk.CTkFont(size=24, weight="bold"), text_color=Theme.TEXT_PRIMARY)
        self.header_title.pack(side="left")
        
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")
        
        self.browse_btn = ctk.CTkButton(btn_frame, text="📂 Browse", fg_color=Theme.ACCENT_SECONDARY,
            hover_color=Theme.ACCENT_PRIMARY, height=38, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"), command=self.browse_folder)
        self.browse_btn.pack(side="right", padx=8)
        
        self.export_btn = ctk.CTkButton(btn_frame, text="💾 Export", fg_color=Theme.ACCENT_SUCCESS,
            hover_color="#00cc6a", height=38, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"), command=self.export_results, state="disabled")
        self.export_btn.pack(side="right")
    
    def _setup_status_bar(self):
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
        for i, btn in enumerate(self.nav_buttons):
            btn.configure(fg_color=Theme.ACCENT_PRIMARY if i == index else "transparent",
                         text_color=Theme.TEXT_PRIMARY if i == index else Theme.TEXT_SECONDARY)
        
        for widget in self.content_container.winfo_children():
            widget.grid_forget()
        
        views = [self._show_home_view, self._show_files_view, self._show_settings_view]
        titles = ["Welcome to AstroSorter", "Source Files", "Settings"]
        
        self.header_title.configure(text=titles[index])
        views[index]()
    
    def _show_home_view(self):
        card = ctk.CTkFrame(self.content_container, fg_color=Theme.BG_CARD, 
                            border_color=Theme.BORDER_COLOR, border_width=1, corner_radius=20)
        card.pack(fill="both", expand=True, pady=10)
        
        ctk.CTkLabel(card, text="📂", font=ctk.CTkFont(size=72),
                     text_color=Theme.ACCENT_HIGHLIGHT).pack(pady=(50, 20))
        
        ctk.CTkLabel(card, text="Select Image Folder",
                     font=ctk.CTkFont(size=24, weight="bold"), text_color=Theme.TEXT_PRIMARY).pack()
        
        ctk.CTkLabel(card, text="Browse a folder to automatically classify your astrophotography images",
                     font=ctk.CTkFont(size=13), text_color=Theme.TEXT_SECONDARY).pack(pady=10)
        
        ctk.CTkButton(card, text="Browse Folder", fg_color=Theme.ACCENT_PRIMARY,
                      hover_color="#ff6b8a", height=45, corner_radius=10,
                      font=ctk.CTkFont(size=15, weight="bold"), command=self.browse_folder).pack(pady=30)
        
        ctk.CTkLabel(card, text="Supports: CR2, NEF, ARW, RAF, DNG, FITS, TIFF, JPG, PNG",
                     font=ctk.CTkFont(size=11), text_color=Theme.TEXT_MUTED).pack(pady=(0, 40))
    
    def _show_files_view(self):
        if not self.results:
            card = ctk.CTkFrame(self.content_container, fg_color=Theme.BG_CARD, corner_radius=20)
            card.pack(fill="both", expand=True)
            
            ctk.CTkLabel(card, text="📁", font=ctk.CTkFont(size=64),
                         text_color=Theme.TEXT_MUTED).pack(pady=(80, 20))
            ctk.CTkLabel(card, text="No images loaded",
                         font=ctk.CTkFont(size=18, weight="bold"), text_color=Theme.TEXT_PRIMARY).pack()
            ctk.CTkButton(card, text="Browse Folder", fg_color=Theme.ACCENT_PRIMARY,
                          height=40, command=self.browse_folder).pack(pady=20)
            return
        
        self._setup_files_view()
    
    def _setup_files_view(self):
        # Clear
        for widget in self.content_container.winfo_children():
            widget.destroy()
        
        # Main container with preview
        main = ctk.CTkFrame(self.content_container, fg_color="transparent")
        main.pack(fill="both", expand=True)
        main.grid_rowconfigure(2, weight=1)
        main.grid_columnconfigure(0, weight=1)
        
        # Summary cards
        cards_frame = ctk.CTkFrame(main, fg_color="transparent")
        cards_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        
        self.type_cards = {}
        types = [(ImageType.LIGHT, "🌟", "Lights"), (ImageType.DARK, "🌙", "Darks"),
                 (ImageType.FLAT, "☀️", "Flats"), (ImageType.BIAS, "📊", "Biases"),
                 (ImageType.FLAT_DARK, "🔲", "Flat-Darks"), (ImageType.UNKNOWN, "❓", "Unknown")]
        
        for i, (img_type, icon, label) in enumerate(types):
            card = self._create_card(cards_frame, img_type, icon, label)
            card.grid(row=0, column=i, sticky="ew", padx=6)
            self.type_cards[img_type] = card
        
        for i in range(len(types)):
            cards_frame.grid_columnconfigure(i, weight=1)
        
        # Instructions
        ctk.CTkLabel(main, text="💡 Click column headers to sort • Click filename to preview • Change type via dropdown",
                     font=ctk.CTkFont(size=12), text_color=Theme.TEXT_SECONDARY
                     ).grid(row=1, column=0, sticky="w", pady=(0, 10))
        
        # Split: table (left) + preview (right)
        table_frame = ctk.CTkFrame(main, fg_color=Theme.BG_CARD, corner_radius=12)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 15))
        table_frame.grid_rowconfigure(1, weight=1)
        
        # Table with headers
        header_frame = ctk.CTkFrame(table_frame, fg_color=Theme.BG_TERTIARY, corner_radius=8)
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        
        # Sortable headers
        columns = [
            ("filename", "File", 200),
            ("type", "Type", 130),
            ("exposure", "Exposure", 80),
            ("iso", "ISO", 60),
            ("camera", "Camera", 120),
            ("mean", "Mean", 80)
        ]
        
        for col_id, col_name, width in columns:
            btn = ctk.CTkButton(header_frame, text=col_name,
                fg_color="transparent", hover_color=Theme.BG_SECONDARY,
                text_color=Theme.TEXT_PRIMARY, font=ctk.CTkFont(size=12, weight="bold"),
                width=width, height=30, corner_radius=5, border_width=0,
                command=partial(self.sort_by, col_id))
            btn.pack(side="left", padx=5)
        
        # Scrollable file list
        self.file_scroll = ctk.CTkScrollableFrame(table_frame, fg_color="transparent")
        self.file_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Preview panel
        preview_frame = ctk.CTkFrame(main, fg_color=Theme.BG_CARD, corner_radius=12, width=280)
        preview_frame.grid(row=2, column=1, sticky="nsew")
        preview_frame.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(preview_frame, text="Preview", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=Theme.TEXT_PRIMARY).grid(row=0, column=0, padx=15, pady=(15, 10))
        
        self.preview_label = ctk.CTkLabel(preview_frame, text="Click a file to preview",
                                           font=ctk.CTkFont(size=13), text_color=Theme.TEXT_MUTED)
        self.preview_label.grid(row=1, column=0, padx=15, pady=15, sticky="nsew")
        
        # File details
        self.file_details = ctk.CTkLabel(preview_frame, text="", font=ctk.CTkFont(size=11),
                                          text_color=Theme.TEXT_SECONDARY, justify="left")
        self.file_details.grid(row=2, column=0, padx=15, pady=(0, 15), sticky="w")
        
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=1)
        
        # Populate
        self._populate_files()
    
    def _create_card(self, parent, img_type, icon, label):
        card = ctk.CTkFrame(parent, fg_color=Theme.BG_CARD, corner_radius=12)
        
        count = sum(1 for r in self.results if r.classified_type == img_type)
        
        ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=28)).pack(pady=(15, 5))
        ctk.CTkLabel(card, text=str(count), font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=Theme.TEXT_PRIMARY).pack()
        ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=12),
                     text_color=Theme.TEXT_SECONDARY).pack(pady=(0, 15))
        
        return card
    
    def sort_by(self, column: str):
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        
        self._populate_files()
    
    def _populate_files(self):
        # Clear
        for widget in self.file_scroll.winfo_children():
            widget.destroy()
        
        # Sort results
        sorted_results = sorted(self.results, key=lambda r: self._get_sort_key(r), reverse=self.sort_reverse)
        
        for idx, metadata in enumerate(sorted_results):
            self._create_file_row(metadata, idx % 2 == 0)
        
        # Update counts
        self._update_counts()
    
    def _get_sort_key(self, r: ImageMetadata):
        key = getattr(r, self.sort_column)
        if key is None:
            return ""
        if isinstance(key, float):
            return key
        if isinstance(key, int):
            return key
        return str(key).lower()
    
    def _create_file_row(self, metadata: ImageMetadata, alternate: bool):
        row = ctk.CTkFrame(self.file_scroll, fg_color=Theme.BG_SECONDARY if alternate else "transparent", corner_radius=6)
        row.pack(fill="x", pady=2)
        
        # Filename (clickable)
        fname = metadata.filename[:30] + ("..." if len(metadata.filename) > 30 else "")
        name_btn = ctk.CTkLabel(row, text=fname, font=ctk.CTkFont(size=11),
                               text_color=Theme.ACCENT_HIGHLIGHT, width=200, anchor="w", cursor="hand2")
        name_btn.pack(side="left", padx=12, pady=8)
        name_btn.bind("<Button-1>", lambda e, m=metadata: self._show_preview(m))
        
        # Type dropdown
        if not hasattr(metadata, 'selected_type'):
            metadata.selected_type = metadata.classified_type.value
        
        type_var = ctk.StringVar(value=metadata.selected_type)
        type_menu = ctk.CTkOptionMenu(row, values=["Lights", "Darks", "Flats", "Biases", "Flat-Darks", "Unknown"],
                                     variable=type_var, fg_color=Theme.ACCENT_SECONDARY,
                                     button_color=Theme.ACCENT_PRIMARY, button_hover_color="#ff6b8a",
                                     dropdown_fg_color=Theme.BG_CARD, width=130, height=30, font=ctk.CTkFont(size=11))
        type_menu.pack(side="left", padx=5)
        type_var.trace_add("write", lambda *args, m=metadata, v=type_var: self._on_type_change(m, v))
        
        # Exposure
        exp_str = f"{metadata.exposure_time:.3f}s" if metadata.exposure_time else "-"
        ctk.CTkLabel(row, text=exp_str, font=ctk.CTkFont(size=11), text_color=Theme.TEXT_SECONDARY, width=80).pack(side="left", padx=5)
        
        # ISO
        ctk.CTkLabel(row, text=str(metadata.iso) if metadata.iso else "-", font=ctk.CTkFont(size=11),
                     text_color=Theme.TEXT_SECONDARY, width=60).pack(side="left", padx=5)
        
        # Camera
        cam = (metadata.camera_model[:15] + "..") if metadata.camera_model and len(metadata.camera_model) > 17 else (metadata.camera_model or "-")
        ctk.CTkLabel(row, text=cam, font=ctk.CTkFont(size=11), text_color=Theme.TEXT_SECONDARY, width=120).pack(side="left", padx=5)
        
        # Mean
        mean_str = f"{metadata.mean:.1f}" if metadata.mean else "-"
        ctk.CTkLabel(row, text=mean_str, font=ctk.CTkFont(size=11), text_color=Theme.TEXT_SECONDARY, width=80).pack(side="left", padx=5)
    
    def _on_type_change(self, metadata: ImageMetadata, type_var):
        new_type = type_var.get()
        metadata.selected_type = new_type
        
        type_map = {"Lights": ImageType.LIGHT, "Darks": ImageType.DARK, 
                   "Flats": ImageType.FLAT, "Biases": ImageType.BIAS,
                   "Flat-Darks": ImageType.FLAT_DARK, "Unknown": ImageType.UNKNOWN}
        
        metadata.classified_type = type_map.get(new_type, ImageType.UNKNOWN)
        metadata.confidence = 1.0
        
        self._update_counts()
    
    def _update_counts(self):
        for img_type, card in self.type_cards.items():
            count = sum(1 for r in self.results if r.classified_type == img_type)
            card.winfo_children()[1].configure(text=str(count))
    
    def _show_preview(self, metadata: ImageMetadata):
        self.selected_file = metadata
        
        # Update details
        details = f"""File: {metadata.filename}
Type: {metadata.classified_type.value}
Exposure: {metadata.exposure_time if metadata.exposure_time else '-'}
ISO: {metadata.iso if metadata.iso else '-'}
Camera: {metadata.camera_model if metadata.camera_model else '-'}
Object: {metadata.object_name if metadata.object_name else '-'}
Filter: {metadata.filter_name if metadata.filter_name else '-'}
Mean: {metadata.mean:.2f}" if metadata.mean else '-'"""
        
        self.file_details.configure(text=details)
        
        # Try to load image
        try:
            from PIL import Image
            import io
            
            # Try different methods to load
            img = None
            
            # Method 1: Direct open
            try:
                img = Image.open(metadata.filepath)
            except:
                pass
            
            # Method 2: Try with rawpy if it's a RAW file
            if img is None:
                try:
                    import rawpy
                    with rawpy.imread(metadata.filepath) as raw:
                        rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True)
                        img = Image.fromarray(rgb)
                except:
                    pass
            
            if img:
                # Resize for preview
                img.thumbnail((250, 250), Image.Resizing.LANCZOS)
                
                # Use CTkImage
                ctk_img = CTkImage(img, size=img.size)
                self.preview_label.configure(image=ctk_img, text="")
                self.preview_label.image = ctk_img
            else:
                self.preview_label.configure(text="Cannot load preview", image=None)
                
        except Exception as e:
            self.preview_label.configure(text=f"Preview: {str(e)[:40]}", image=None)
    
    def _show_settings_view(self):
        card = ctk.CTkFrame(self.content_container, fg_color=Theme.BG_CARD, corner_radius=20)
        card.pack(fill="both", expand=True, padx=50, pady=30)
        
        ctk.CTkLabel(card, text="⚙️ Settings", font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=Theme.TEXT_PRIMARY).pack(anchor="w", padx=30, pady=(25, 20))
        
        ctk.CTkLabel(card, text="Scanning", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=Theme.ACCENT_HIGHLIGHT).pack(anchor="w", padx=30, pady=(15, 10))
        
        self.recursive_var = ctk.BooleanVar(value=self.settings['recursive'])
        ctk.CTkCheckBox(card, text="Scan subfolders recursively", variable=self.recursive_var,
                        font=ctk.CTkFont(size=13), text_color=Theme.TEXT_PRIMARY).pack(anchor="w", padx=30)
        
        ctk.CTkLabel(card, text="Export", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=Theme.ACCENT_HIGHLIGHT).pack(anchor="w", padx=30, pady=(20, 10))
        
        self.export_method_var = ctk.StringVar(value=self.settings['export_method'])
        ctk.CTkRadioButton(card, text="Copy files (keep originals)", variable=self.export_method_var,
                           value="copy", font=ctk.CTkFont(size=13), text_color=Theme.TEXT_PRIMARY).pack(anchor="w", padx=30)
        ctk.CTkRadioButton(card, text="Move files (remove originals)", variable=self.export_method_var,
                           value="move", font=ctk.CTkFont(size=13), text_color=Theme.TEXT_PRIMARY).pack(anchor="w", padx=30)
        
        self.json_var = ctk.BooleanVar(value=self.settings['export_json_report'])
        ctk.CTkCheckBox(card, text="Export JSON report", variable=self.json_var,
                        font=ctk.CTkFont(size=13), text_color=Theme.TEXT_PRIMARY).pack(anchor="w", padx=30, pady=(15, 0))
        
        ctk.CTkButton(card, text="Save", fg_color=Theme.ACCENT_PRIMARY, height=40,
                      command=self._save_settings).pack(pady=30)
    
    def _save_settings(self):
        self.settings['recursive'] = self.recursive_var.get()
        self.settings['export_method'] = self.export_method_var.get()
        self.settings['export_json_report'] = self.json_var.get()
        messagebox.showinfo("Settings", "Settings saved!")
    
    def _center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"{self.winfo_width()}x{self.winfo_height()}+{x}+{y}")
    
    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select folder with astrophotography images")
        if folder:
            self.process_directory(folder)
    
    def process_directory(self, directory: str):
        if self.is_processing:
            return
        
        self.current_directory = directory
        self.is_processing = True
        
        self.status_label.configure(text=f"Scanning {Path(directory).name}...")
        self.progress.pack(side="right", fill="x", expand=True, padx=20, pady=8)
        self.progress.set(0)
        self.browse_btn.configure(state="disabled")
        
        thread = threading.Thread(target=self._process_thread, args=(directory,))
        thread.daemon = True
        thread.start()
    
    def _process_thread(self, directory: str):
        try:
            self.results = classify_directory(directory, recursive=self.settings['recursive'],
                                             progress_callback=self._update_progress)
            self.after(0, self._processing_complete)
        except Exception as e:
            self.after(0, lambda err=str(e): self._processing_error(err))
    
    def _update_progress(self, current: int, total: int, filepath: str):
        def update():
            self.status_label.configure(text=f"Processing: {Path(filepath).name[:25]}")
            self.progress.set(current / total)
        self.after(0, update)
    
    def _processing_complete(self):
        self.is_processing = False
        self.status_label.configure(text=f"Classified {len(self.results)} images!")
        
        try:
            self.progress.pack_forget()
        except:
            pass
        
        self.browse_btn.configure(state="normal")
        self.export_btn.configure(state="normal")
        
        self.switch_view(1)
        
        summary = get_summary(self.results)
        msg = f"Classified {len(self.results)} images:\n\n"
        for t, c in summary['by_type'].items():
            msg += f"  {t}: {c}\n"
        messagebox.showinfo("Complete", msg)
    
    def _processing_error(self, error: str):
        self.is_processing = False
        self.status_label.configure(text="Error")
        
        try:
            self.progress.pack_forget()
        except:
            pass
        
        self.browse_btn.configure(state="normal")
        messagebox.showerror("Error", error)
    
    def export_results(self):
        if not self.results:
            return
        
        destination = filedialog.askdirectory(title="Select output folder")
        if not destination:
            return
        
        move = self.settings['export_method'] == 'move'
        
        if not messagebox.askyesno("Confirm", f"{'Move' if move else 'Copy'} {len(self.results)} files?"):
            return
        
        self._export_files(destination, move)
    
    def _export_files(self, destination: str, move: bool):
        self.status_label.configure(text="Exporting...")
        self.progress.pack(side="right", fill="x", expand=True, padx=20, pady=8)
        self.progress.set(0)
        
        # Create folders
        folders = {}
        for t in ImageType:
            if t != ImageType.UNKNOWN:
                folders[t] = os.path.join(destination, t.value)
                os.makedirs(folders[t], exist_ok=True)
        
        exported = 0
        total = len(self.results)
        
        for i, m in enumerate(self.results):
            if m.classified_type == ImageType.UNKNOWN:
                continue
            
            dest_folder = folders.get(m.classified_type)
            if not dest_folder:
                continue
            
            dest_path = os.path.join(dest_folder, m.filename)
            
            # Handle duplicates
            counter = 1
            base = Path(m.filename).stem
            ext = Path(m.filename).suffix
            while os.path.exists(dest_path):
                dest_path = os.path.join(dest_folder, f"{base}_{counter}{ext}")
                counter += 1
            
            try:
                if move:
                    shutil.move(m.filepath, dest_path)
                else:
                    shutil.copy2(m.filepath, dest_path)
                exported += 1
            except Exception as e:
                print(f"Error: {m.filename}: {e}")
            
            self.after(0, lambda p=(i+1)/total: self.progress.set(p))
        
        # JSON report
        if self.settings['export_json_report']:
            self._export_json(destination)
        
        self.status_label.configure(text=f"Exported {exported} files!")
        
        try:
            self.progress.pack_forget()
        except:
            pass
        
        try:
            os.startfile(destination)
        except:
            pass
        
        messagebox.showinfo("Complete", f"Exported to:\n{destination}")
    
    def _export_json(self, destination: str):
        data = {
            'generated': datetime.now().isoformat(),
            'version': VERSION,
            'source_directory': self.current_directory,
            'total_files': len(self.results),
            'summary': get_summary(self.results),
            'files': [{
                'filename': m.filename,
                'classified_type': getattr(m, 'selected_type', m.classified_type.value),
                'exposure_time': m.exposure_time,
                'iso': m.iso,
                'camera_model': m.camera_model,
                'object_name': m.object_name,
                'filter_name': m.filter_name,
                'mean': m.mean,
                'std': m.std
            } for m in self.results]
        }
        
        with open(os.path.join(destination, 'classification_report.json'), 'w') as f:
            json.dump(data, f, indent=2)


def main():
    app = AstroSorterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
