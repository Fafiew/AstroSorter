"""
AstroSorter - Main Application
"""

import os
import shutil
import threading
import json
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from typing import Optional, List
from functools import partial

import customtkinter as ctk
from customtkinter import CTkImage
from PIL import Image as PILImage

from AstroSorter.classifier import ImageMetadata, ImageType, classify_directory, get_summary
from AstroSorter.version import VERSION


class AstroSorterApp(ctk.CTk):
    
    def __init__(self):
        super().__init__()
        
        self.title(f"AstroSorter v{VERSION}")
        self.geometry("1600x900")
        self.minsize(1200, 700)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.configure(fg_color="#0d0d1a")
        
        self.results: List[ImageMetadata] = []
        self.current_directory: str = ""
        self.current_view = "home"
        self.sort_col = "filename"
        self.sort_asc = True
        self.selected_image: Optional[ImageMetadata] = None
        
        # UI references
        self.header_buttons = {}
        self.file_tree = None
        self.type_cards = {}
        
        self.settings = {'recursive': True, 'export_method': 'copy', 'export_json': True,
                        'rename_enabled': False, 'rename_pattern': 'type_#'}
        
        self._setup_ui()
        self._center_window()
    
    def _setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, fg_color="#1a1a2e", width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="🔭 AstroSorter", font=("Segoe UI", 20, "bold"),
                     text_color="#00d9ff").pack(pady=20, padx=20)
        ctk.CTkLabel(self.sidebar, text=f"v{VERSION}", font=("Segoe UI", 10),
                     text_color="#606080").pack(pady=(0, 20))
        
        self.nav_btns = {}
        for name, icon in [("home", "🏠 Home"), ("files", "📁 Files"), ("settings", "⚙️ Settings")]:
            btn = ctk.CTkButton(self.sidebar, text=icon, fg_color="transparent", hover_color="#16213e",
                               text_color="#a0a0a0", height=40, corner_radius=8, anchor="w",
                               command=partial(self.show_view, name))
            btn.pack(padx=15, pady=3, fill="x")
            self.nav_btns[name] = btn
        
        self.nav_btns["home"].configure(fg_color="#e94560", text_color="white")
        
        # Main content
        self.content = ctk.CTkFrame(self, fg_color="#0d0d1a", corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        
        self.title_label = ctk.CTkLabel(header, text="Select Folder", font=("Segoe UI", 24, "bold"), text_color="white")
        self.title_label.pack(side="left")
        
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")
        
        self.browse_btn = ctk.CTkButton(btn_frame, text="📂 Browse", fg_color="#0f3460", hover_color="#e94560",
                                       command=self.browse_folder)
        self.browse_btn.pack(side="left", padx=5)
        
        self.export_btn = ctk.CTkButton(btn_frame, text="💾 Export", fg_color="#00ff88", hover_color="#00cc6a",
                                       command=self.export_results, state="disabled")
        self.export_btn.pack(side="left")
        
        self.view_container = ctk.CTkFrame(self.content, fg_color="transparent")
        self.view_container.pack(fill="both", expand=True)
        
        self.status = ctk.CTkFrame(self, fg_color="#1a1a2e", height=30, corner_radius=0)
        self.status.grid(row=1, column=0, columnspan=2, sticky="ew")
        
        self.status_label = ctk.CTkLabel(self.status, text="Ready", text_color="#a0a0a0", font=("Segoe UI", 11))
        self.status_label.pack(side="left", padx=20)
        
        # Progress bar (hidden by default)
        self.progress_frame = ctk.CTkFrame(self.status, fg_color="transparent")
        self.progress_frame.pack(side="right", padx=20, fill="x", expand=True)
        self.progress_frame.pack_forget()  # Hide initially
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, width=200, height=10)
        self.progress_bar.pack(side="left", padx=(0, 10))
        self.progress_bar.set(0)
        
        self.progress_label = ctk.CTkLabel(self.progress_frame, text="0%", text_color="#a0a0a0", font=("Segoe UI", 10))
        self.progress_label.pack(side="left")
        
        self.progress_time = ctk.CTkLabel(self.progress_frame, text="", text_color="#606080", font=("Segoe UI", 9))
        self.progress_time.pack(side="left", padx=(10, 0))
        
        self.start_time = None
        
        self.show_view("home")
    
    def show_view(self, name: str):
        self.current_view = name
        
        for n, btn in self.nav_btns.items():
            btn.configure(fg_color="#e94560" if n == name else "transparent",
                         text_color="white" if n == name else "#a0a0a0")
        
        titles = {"home": "Select Folder", "files": "Source Files", "settings": "Settings"}
        self.title_label.configure(text=titles[name])
        
        for w in self.view_container.winfo_children():
            w.destroy()
        
        if name == "home":
            self._show_home()
        elif name == "files":
            self._show_files()
        elif name == "settings":
            self._show_settings()
    
    def _show_home(self):
        main = ctk.CTkFrame(self.view_container, fg_color="transparent")
        main.pack(fill="both", expand=True)
        
        # Welcome card
        card = ctk.CTkFrame(main, fg_color="#1f1f3d", corner_radius=20)
        card.pack(fill="both", expand=True, padx=50, pady=30)
        
        # Welcome message
        ctk.CTkLabel(card, text="🔭 Welcome to AstroSorter", font=("Segoe UI", 28, "bold"),
                    text_color="#00d9ff").pack(pady=(40, 10))
        
        ctk.CTkLabel(card, text="Automatically sort your astrophotography images", 
                    text_color="#a0a0a0", font=("Segoe UI", 14)).pack(pady=(0, 30))
        
        # Version info
        version_frame = ctk.CTkFrame(card, fg_color="#16213e", corner_radius=10)
        version_frame.pack(pady=20)
        
        ctk.CTkLabel(version_frame, text=f"Current Version: {VERSION}",
                    text_color="white", font=("Segoe UI", 14)).pack(pady=15, padx=30)
        
        # Latest version (fetched from GitHub)
        self.latest_version_label = ctk.CTkLabel(version_frame, text="Checking for updates...", 
                    text_color="#a0a0a0", font=("Segoe UI", 12))
        self.latest_version_label.pack(pady=(0, 15), padx=30)
        
        # Check for updates in background
        threading.Thread(target=self._check_for_updates, daemon=True).start()
        
        # Current folder
        folder_frame = ctk.CTkFrame(card, fg_color="transparent")
        folder_frame.pack(pady=20)
        
        ctk.CTkLabel(folder_frame, text="📁 Selected Folder:", 
                    text_color="#a0a0a0", font=("Segoe UI", 12)).pack()
        
        folder_path = self.current_directory if self.current_directory else "No folder selected"
        ctk.CTkLabel(folder_frame, text=folder_path, text_color="#00d9ff", 
                    font=("Segoe UI", 11), wraplength=400).pack(pady=5)
        
        # Buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(pady=30)
        
        ctk.CTkButton(btn_frame, text="📂 Select Folder", fg_color="#e94560", hover_color="#ff6b8a",
                     height=45, font=("Segoe UI", 14, "bold"), command=self.browse_folder).pack(side="left", padx=10)
        
        ctk.CTkButton(btn_frame, text="🐙 GitHub", fg_color="#16213e", hover_color="#0f3460",
                     height=45, font=("Segoe UI", 14), 
                     command=lambda: os.system("start https://github.com/Fafiew/AstroSorter")).pack(side="left", padx=10)
        
        # Supported formats
        ctk.CTkLabel(card, text="Supports: CR2, CR3, NEF, ARW, RAF, DNG, FITS, TIFF, JPG, PNG",
                    text_color="#606080", font=("Segoe UI", 10)).pack(pady=(20, 40))
    
    def _preview_image(self, filepath: str):
        """Load and return a PIL Image from filepath"""
        img = None
        ext = Path(filepath).suffix.lower()
        
        try:
            if ext in {'.cr2', '.cr3', '.nef', '.arw', '.raf', '.dng', '.orf', '.rw2', '.pef'}:
                try:
                    import rawpy
                    with rawpy.imread(filepath) as raw:
                        rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True)
                        img = PILImage.fromarray(rgb)
                except:
                    pass
            
            if img is None:
                img = PILImage.open(filepath)
                
        except Exception as e:
            messagebox.showerror("Error", f"Cannot load image: {str(e)}")
            return None
        
        return img
    
    def _show_files(self):
        if not self.results:
            card = ctk.CTkFrame(self.view_container, fg_color="#1f1f3d", corner_radius=20)
            card.pack(fill="both", expand=True)
            ctk.CTkLabel(card, text="📁", font=("Segoe UI", 48), text_color="#606080").pack(pady=(80, 20))
            ctk.CTkLabel(card, text="No images loaded", font=("Segoe UI", 18, "bold"), text_color="white").pack()
            ctk.CTkButton(card, text="Browse Folder", fg_color="#e94560", command=self.browse_folder).pack(pady=20)
            return
        
        # Split view
        main = ctk.CTkFrame(self.view_container, fg_color="transparent")
        main.pack(fill="both", expand=True)
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(1, weight=1)
        
        # Summary cards
        cards = ctk.CTkFrame(main, fg_color="transparent")
        cards.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        
        self.type_cards = {}
        types_list = [(ImageType.LIGHT, "🌟", "Lights"), (ImageType.DARK, "🌙", "Darks"),
                     (ImageType.FLAT, "🔆", "Flats"), (ImageType.BIAS, "📊", "Biases"),
                     (ImageType.UNKNOWN, "❓", "Unknown")]
        
        for i, (t, icon, label) in enumerate(types_list):
            card = ctk.CTkFrame(cards, fg_color="#1f1f3d", corner_radius=12)
            card.pack(side="left", expand=True, padx=5, fill="both")
            
            # Center the icon using anchor in a fixed-width container
            icon_container = ctk.CTkFrame(card, fg_color="transparent")
            icon_container.pack(fill="x", pady=(15, 5))
            ctk.CTkLabel(icon_container, text=icon, font=("Segoe UI", 24)).pack(anchor="center")
            
            count = sum(1 for r in self.results if r.classified_type == t)
            ctk.CTkLabel(card, text=str(count), font=("Segoe UI", 20, "bold"), text_color="white").pack()
            ctk.CTkLabel(card, text=label, text_color="#a0a0a0", font=("Segoe UI", 10)).pack(pady=(0, 15))
            self.type_cards[t] = card
            cards.grid_columnconfigure(i, weight=1)
        
        # Table with ttk.Treeview (resizable columns)
        table = ctk.CTkFrame(main, fg_color="#1f1f3d", corner_radius=12)
        table.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        
        # Style for treeview
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#1a1a2e", foreground="white", fieldbackground="#1a1a2e",
                       rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background="#16213e", foreground="white",
                       font=("Segoe UI", 10, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", "#e94560")], foreground=[("selected", "white")])
        
        # Configure Treeview selection colors
        style.configure("Treeview", selectbackground="#e94560", selectforeground="white")
        
        # Treeview columns
        cols = ("filename", "type", "exposure", "iso", "camera", "mean")
        self.file_tree = ttk.Treeview(table, columns=cols, show="headings", style="Treeview")
        
        # Configure columns with resizable headers
        col_configs = [("filename", "File", 180), ("type", "Type", 100), ("exposure", "Exp", 70),
                       ("iso", "ISO", 60), ("camera", "Camera", 100), ("mean", "Mean", 70)]
        for col_id, col_name, width in col_configs:
            self.file_tree.heading(col_id, text=col_name, command=partial(self.sort_files, col_id))
            self.file_tree.column(col_id, width=width, minwidth=40, anchor="w")
        
        # Scrollbars - always visible for simplicity
        vsb = ttk.Scrollbar(table, orient="vertical", command=self.file_tree.yview)
        hsb = ttk.Scrollbar(table, orient="horizontal", command=self.file_tree.xview)
        self.file_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.file_tree.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        vsb.grid(row=0, column=1, sticky="ns", pady=10)
        hsb.grid(row=1, column=0, sticky="ew", padx=10)
        
        table.grid_rowconfigure(0, weight=1)
        table.grid_columnconfigure(0, weight=1)
        
        # Bind click event
        self.file_tree.bind("<ButtonRelease-1>", self._on_file_select)
        
        # Store column widths for sorting updates
        self._col_widths = {col: w for col, _, w in col_configs}
        
        # Preview panel
        preview = ctk.CTkFrame(main, fg_color="#1f1f3d", corner_radius=12)
        preview.grid(row=1, column=1, sticky="nsew")
        
        ctk.CTkLabel(preview, text="Preview", font=("Segoe UI", 14, "bold"), text_color="white").pack(pady=(15, 5))
        
        self.preview_label = ctk.CTkLabel(preview, text="Click image to preview", text_color="#606080", font=("Segoe UI", 11))
        self.preview_label.pack(pady=20)
        
        self.preview_info = ctk.CTkLabel(preview, text="", text_color="#a0a0a0", font=("Segoe UI", 10), justify="left")
        self.preview_info.pack(pady=10)
        
        # Initial populate
        self._update_headers()
        self._populate_file_list()
    
    def _update_headers(self):
        """Update header colors and arrows for Treeview"""
        cols = [("filename", "File"), ("type", "Type"), ("exposure", "Exp"), 
                ("iso", "ISO"), ("camera", "Camera"), ("mean", "Mean")]
        
        for col_id, col_name in cols:
            # Only show arrow for the sorted column
            if self.sort_col == col_id:
                arrow = " ▲" if self.sort_asc else " ▼"
                foreground = "#00d9ff"
            else:
                arrow = ""
                foreground = "white"
            
            self.file_tree.heading(col_id, text=col_name + arrow, command=partial(self.sort_files, col_id))
    
    def _populate_file_list(self):
        if not self.file_tree:
            return
        
        # Clear existing items
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        
        # Sort
        reverse = not self.sort_asc
        
        if self.sort_col == "filename":
            sorted_results = sorted(self.results, key=lambda r: r.filename.lower(), reverse=reverse)
        elif self.sort_col == "type":
            sorted_results = sorted(self.results, key=lambda r: r.classified_type.value, reverse=reverse)
        elif self.sort_col == "exposure":
            sorted_results = sorted(self.results, key=lambda r: r.exposure_time or 0, reverse=reverse)
        elif self.sort_col == "iso":
            sorted_results = sorted(self.results, key=lambda r: r.iso or 0, reverse=reverse)
        elif self.sort_col == "camera":
            sorted_results = sorted(self.results, key=lambda r: (r.camera_model or "").lower(), reverse=reverse)
        elif self.sort_col == "mean":
            sorted_results = sorted(self.results, key=lambda r: r.mean or 0, reverse=reverse)
        else:
            sorted_results = list(self.results)
        
        # Store sorted results for lookups
        self._sorted_results = sorted_results
        
        for idx, m in enumerate(sorted_results):
            exp_text = f"{m.exposure_time:.1f}s" if m.exposure_time else "-"
            iso_text = str(m.iso) if m.iso else "-"
            cam_text = m.camera_model[:20] if m.camera_model else "-"
            mean_text = f"{m.mean:.1f}" if m.mean else "-"
            
            self.file_tree.insert("", "end", iid=str(idx), values=(
                m.filename,
                m.classified_type.value if m.classified_type else "Unknown",
                exp_text,
                iso_text,
                cam_text,
                mean_text
            ), tags=("clickable",))
        
        # Update header arrows
        self._update_headers()
        
        # Update counts
        self._refresh_counts()
    
    def _on_file_select(self, event):
        """Handle file selection in treeview"""
        selection = self.file_tree.selection()
        if selection and hasattr(self, '_sorted_results'):
            idx = int(selection[0])
            if idx < len(self._sorted_results):
                self._show_preview(self._sorted_results[idx])
    
    def _show_preview(self, metadata: ImageMetadata):
        self.selected_image = metadata
        
        try:
            img = self._preview_image(metadata.filepath)
            
            if img:
                img.thumbnail((350, 280))
                ctk_img = CTkImage(img, size=img.size)
                self.preview_label.configure(image=ctk_img, text="")
                self.preview_label.image = ctk_img
                
                info = f"File: {metadata.filename}\n"
                info += f"Type: {metadata.classified_type.value}\n"
                info += f"Exp: {metadata.exposure_time if metadata.exposure_time else '-'}s\n"
                info += f"ISO: {metadata.iso if metadata.iso else '-'}\n"
                info += f"Mean: {metadata.mean if metadata.mean else '-'}"
                self.preview_info.configure(text=info)
        except Exception as e:
            self.preview_label.configure(text=f"Cannot load:\n{str(e)[:50]}", image=None)
    
    def sort_files(self, col: str):
        if self.sort_col == col:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = col
            self.sort_asc = True
        
        # Update headers and list only
        self._update_headers()
        self._populate_file_list()
    
    def change_type(self, metadata: ImageMetadata, new_type: str):
        type_map = {"Lights": ImageType.LIGHT, "Darks": ImageType.DARK, 
                   "Flats": ImageType.FLAT, "Biases": ImageType.BIAS, "Unknown": ImageType.UNKNOWN}
        metadata.classified_type = type_map.get(new_type, ImageType.UNKNOWN)
        self._refresh_counts()
    
    def _check_for_updates(self):
        """Check for latest version from GitHub version.py"""
        try:
            # Fetch the version.py file from GitHub
            url = "https://raw.githubusercontent.com/Fafiew/AstroSorter/main/AstroSorter/version.py"
            req = urllib.request.Request(url, headers={"Accept": "text/plain"})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode()
                # Extract VERSION = "x.x.x"
                import re
                match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    latest = match.group(1)
                    
                    # Update label in main thread
                    def update_label():
                        if hasattr(self, 'latest_version_label'):
                            if latest == VERSION:
                                self.latest_version_label.configure(
                                    text=f"Latest: {latest} (up to date)",
                                    text_color="#00ff88"
                                )
                            else:
                                self.latest_version_label.configure(
                                    text=f"Latest: {latest} (update available)",
                                    text_color="#ffaa00"
                                )
                    self.after(0, update_label)
                    return
        except Exception:
            pass
        
        # Fallback - show error or use current version
        def update_error():
            if hasattr(self, 'latest_version_label'):
                self.latest_version_label.configure(
                    text=f"Latest: {VERSION}",
                    text_color="#a0a0a0"
                )
        self.after(0, update_error)
    
    def _refresh_counts(self):
        for t, card in self.type_cards.items():
            count = sum(1 for r in self.results if r.classified_type == t)
            card.winfo_children()[1].configure(text=str(count))
    
    def _show_settings(self):
        card = ctk.CTkFrame(self.view_container, fg_color="#1f1f3d", corner_radius=20)
        card.pack(fill="both", expand=True, padx=100, pady=30)
        
        ctk.CTkLabel(card, text="⚙️ Settings", font=("Segoe UI", 20, "bold"), text_color="white").pack(anchor="w", padx=30, pady=(25, 20))
        
        ctk.CTkLabel(card, text="Scanning", font=("Segoe UI", 14, "bold"), text_color="#00d9ff").pack(anchor="w", padx=30, pady=(15, 10))
        
        self.recursive_var = ctk.BooleanVar(value=self.settings['recursive'])
        ctk.CTkCheckBox(card, text="Scan subfolders", variable=self.recursive_var,
                       text_color="white", font=("Segoe UI", 12)).pack(anchor="w", padx=30)
        
        ctk.CTkLabel(card, text="Export", font=("Segoe UI", 14, "bold"), text_color="#00d9ff").pack(anchor="w", padx=30, pady=(20, 10))
        
        self.method_var = ctk.StringVar(value=self.settings['export_method'])
        ctk.CTkRadioButton(card, text="Copy files", variable=self.method_var, value="copy",
                          text_color="white").pack(anchor="w", padx=30)
        ctk.CTkRadioButton(card, text="Move files", variable=self.method_var, value="move",
                          text_color="white").pack(anchor="w", padx=30)
        
        self.json_var = ctk.BooleanVar(value=self.settings['export_json'])
        ctk.CTkCheckBox(card, text="Export JSON", variable=self.json_var,
                       text_color="white").pack(anchor="w", padx=30, pady=15)
        
        # Rename settings
        ctk.CTkLabel(card, text="Rename", font=("Segoe UI", 14, "bold"), text_color="#00d9ff").pack(anchor="w", padx=30, pady=(20, 10))
        
        self.rename_var = ctk.BooleanVar(value=self.settings['rename_enabled'])
        rename_check = ctk.CTkCheckBox(card, text="Enable rename", variable=self.rename_var,
                       text_color="white", font=("Segoe UI", 12))
        rename_check.pack(anchor="w", padx=30)
        
        # Tokens help text
        ctk.CTkLabel(card, text="Available tokens: {type}, {exposure}, {iso}, {mean}, {#}",
                    text_color="#a0a0a0", font=("Segoe UI", 10)).pack(anchor="w", padx=30, pady=(10, 0))
        
        # Example
        ctk.CTkLabel(card, text="Examples: {type}_{#} → lights_1 | {type}_{exposure}s_{#} → lights_300s_1",
                    text_color="#606080", font=("Segoe UI", 9)).pack(anchor="w", padx=30, pady=(2, 5))
        
        self.rename_pattern_var = ctk.StringVar(value=self.settings['rename_pattern'])
        pattern_entry = ctk.CTkEntry(card, textvariable=self.rename_pattern_var, width=250,
                                     placeholder_text="{type}_{#}", fg_color="#16213e", border_color="#0f3460")
        pattern_entry.pack(anchor="w", padx=30, pady=5)
        
        ctk.CTkButton(card, text="Save", fg_color="#e94560", height=40,
                     command=self._save_settings).pack(pady=30)
    
    def _save_settings(self):
        self.settings['recursive'] = self.recursive_var.get()
        self.settings['export_method'] = self.method_var.get()
        self.settings['export_json'] = self.json_var.get()
        self.settings['rename_enabled'] = self.rename_var.get()
        self.settings['rename_pattern'] = self.rename_pattern_var.get()
        messagebox.showinfo("Settings", "Saved!")
    
    def _center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"{self.winfo_width()}x{self.winfo_height()}+{x}+{y}")
    
    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select folder with images")
        if folder:
            self.current_directory = folder
            self.process_folder(folder)
    
    def process_folder(self, folder: str):
        self.status_label.configure(text=f"Processing {Path(folder).name}...")
        self.browse_btn.configure(state="disabled")
        
        thread = threading.Thread(target=self._process, args=(folder,))
        thread.daemon = True
        thread.start()
    
    def _process(self, folder: str):
        # Record start time
        self.start_time = datetime.now()
        
        # Show progress bar
        self.after(0, lambda: self.progress_frame.pack(side="right", padx=20, fill="x", expand=True))
        self.after(0, lambda: self.progress_bar.set(0))
        
        try:
            self.results = classify_directory(folder, recursive=self.settings['recursive'],
                                             progress_callback=self._progress)
            self.after(0, self._done)
        except Exception as e:
            self.after(0, lambda err=str(e): self._error(err))
    
    def _progress(self, cur, total, path):
        # Calculate progress
        pct = cur / total if total > 0 else 0
        
        # Calculate elapsed time
        elapsed = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        # Calculate ETA
        if cur > 0 and elapsed > 0:
            eta = (elapsed / cur) * (total - cur)
            eta_str = f"ETA: {int(eta)}s"
        else:
            eta_str = "ETA: --"
        
        elapsed_str = f"Elapsed: {int(elapsed)}s"
        
        self.after(0, lambda: self.progress_bar.set(pct))
        self.after(0, lambda: self.progress_label.configure(text=f"{int(pct * 100)}%"))
        self.after(0, lambda: self.progress_time.configure(text=f"{elapsed_str} | {eta_str}"))
        self.after(0, lambda: self.status_label.configure(text=f"Processing: {Path(path).name[:30]}"))
    
    def _done(self):
        self.browse_btn.configure(state="normal")
        self.export_btn.configure(state="normal")
        
        # Hide progress bar
        self.progress_frame.pack_forget()
        
        count = len(self.results)
        self.status_label.configure(text=f"Classified {count} images")
        
        self.show_view("files")
        
        msg = f"Classified {count} images:\n"
        for t, c in get_summary(self.results)['by_type'].items():
            msg += f"  {t}: {c}\n"
        messagebox.showinfo("Complete", msg)
    
    def _error(self, err: str):
        self.browse_btn.configure(state="normal")
        self.status_label.configure(text="Error")
        messagebox.showerror("Error", err)
    
    def export_results(self):
        if not self.results:
            return
        
        dest = filedialog.askdirectory(title="Select output folder")
        if not dest:
            return
        
        if not messagebox.askyesno("Confirm", f"Export {len(self.results)} files?"):
            return
        
        self.status_label.configure(text="Exporting...")
        
        folders = {}
        for t in ImageType:
            folders[t] = os.path.join(dest, t.value)
            os.makedirs(folders[t], exist_ok=True)
        
        # Counters for rename
        counters = {t: 1 for t in ImageType}
        
        for m in self.results:
            dst = folders[m.classified_type]
            
            # Generate filename (rename or original)
            if self.settings['rename_enabled']:
                pattern = self.settings['rename_pattern']
                type_name = m.classified_type.value.lower()
                counter = counters[m.classified_type]
                
                # Replace tokens
                new_name = pattern
                new_name = new_name.replace('{type}', type_name)
                new_name = new_name.replace('{exposure}', str(int(m.exposure_time)) if m.exposure_time else '0')
                new_name = new_name.replace('{iso}', str(m.iso) if m.iso else '0')
                new_name = new_name.replace('{mean}', str(int(m.mean)) if m.mean else '0')
                new_name = new_name.replace('{#}', str(counter))
                new_name = new_name.replace('#', str(counter))  # Backward compatibility
                
                ext = Path(m.filename).suffix
                dst_path = os.path.join(dst, new_name + ext)
                counters[m.classified_type] += 1
            else:
                dst_path = os.path.join(dst, m.filename)
            
            # Handle filename conflicts
            counter = 1
            original_dst = dst_path
            while os.path.exists(dst_path):
                if self.settings['rename_enabled']:
                    base = Path(original_dst).stem
                    ext = Path(original_dst).suffix
                    dst_path = os.path.join(dst, f"{base}_{counter}{ext}")
                else:
                    base = Path(m.filename).stem
                    ext = Path(m.filename).suffix
                    dst_path = os.path.join(dst, f"{base}_{counter}{ext}")
                counter += 1
            
            try:
                if self.settings['export_method'] == 'move':
                    shutil.move(m.filepath, dst_path)
                else:
                    shutil.copy2(m.filepath, dst_path)
            except:
                pass
        
        if self.settings['export_json']:
            data = {
                'generated': datetime.now().isoformat(),
                'version': VERSION,
                'total': len(self.results),
                'files': [{'filename': m.filename, 'type': m.classified_type.value,
                          'exposure': m.exposure_time, 'iso': m.iso, 'mean': m.mean} for m in self.results]
            }
            with open(os.path.join(dest, 'report.json'), 'w') as f:
                json.dump(data, f, indent=2)
        
        self.status_label.configure(text="Export complete")
        try:
            os.startfile(dest)
        except:
            pass
        messagebox.showinfo("Done", f"Exported to:\n{dest}")


def main():
    app = AstroSorterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
