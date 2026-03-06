"""
AstroSorter - Main Application v1.0.7
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
from PIL import Image as PILImage

from AstroSorter.classifier import ImageMetadata, ImageType, classify_directory, get_summary


VERSION = "1.0.7"


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
        
        self.settings = {'recursive': True, 'export_method': 'copy', 'export_json': True}
        
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
        
        # Top bar
        top = ctk.CTkFrame(main, fg_color="#1f1f3d", corner_radius=10)
        top.pack(fill="x", pady=(0, 10))
        
        ctk.CTkButton(top, text="⬆️ Up", fg_color="transparent", hover_color="#16213e",
                      width=50, command=self.go_up).pack(side="left", padx=10, pady=10)
        
        path = self.current_directory if self.current_directory else "Select a folder"
        ctk.CTkLabel(top, text=path[:70] + "..." if len(path) > 70 else path,
                    text_color="#00d9ff", font=("Segoe UI", 12)).pack(side="left", pady=10)
        
        ctk.CTkButton(top, text="📂 Browse", fg_color="#e94560", hover_color="#ff6b8a",
                      command=self.browse_folder).pack(side="right", padx=10, pady=10)
        
        # File list
        list_frame = ctk.CTkFrame(main, fg_color="#1f1f3d", corner_radius=10)
        list_frame.pack(fill="both", expand=True)
        
        scroll = ctk.CTkScrollableFrame(list_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        self._populate_file_explorer(scroll)
    
    def _populate_file_explorer(self, parent):
        for w in parent.winfo_children():
            w.destroy()
        
        base_path = self.current_directory if self.current_directory else os.getcwd()
        
        if not os.path.exists(base_path):
            ctk.CTkLabel(parent, text="Folder not found", text_color="#ff6666").pack()
            return
        
        items = []
        try:
            for item in os.listdir(base_path):
                full_path = os.path.join(base_path, item)
                is_dir = os.path.isdir(full_path)
                items.append((item, is_dir, full_path))
        except:
            pass
        
        items.sort(key=lambda x: (not x[1], x[0].lower()))
        
        if not items:
            ctk.CTkLabel(parent, text="Empty folder", text_color="#606080").pack(pady=20)
            return
        
        for name, is_dir, full_path in items:
            row = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=6)
            row.pack(fill="x", pady=2)
            
            icon = "📁" if is_dir else "📄"
            color = "#00d9ff" if is_dir else "#a0a0a0"
            
            label = ctk.CTkLabel(row, text=f"  {icon} {name}", text_color=color, 
                                font=("Segoe UI", 11), anchor="w", cursor="hand2")
            label.pack(side="left", fill="x", expand=True, padx=10, pady=8)
            
            if is_dir:
                label.bind("<Button-1>", lambda e, p=full_path: self.open_folder(p))
            else:
                ext = Path(name).suffix.lower()
                if ext in {'.cr2', '.cr3', '.nef', '.arw', '.raf', '.dng', '.tif', '.tiff', '.jpg', '.jpeg', '.png', '.fits', '.fit', '.fts'}:
                    label.bind("<Button-1>", lambda e, p=full_path: self._preview_image(p))
    
    def go_up(self):
        if self.current_directory:
            parent = os.path.dirname(self.current_directory)
            if parent and parent != self.current_directory:
                self.current_directory = parent
                self._show_home()
    
    def open_folder(self, path: str):
        self.current_directory = path
        self._show_home()
    
    def _preview_image(self, filepath: str):
        """Load image for preview - supports RAW formats"""
        img = None
        ext = Path(filepath).suffix.lower()
        
        try:
            # Try RAW formats first with rawpy
            if ext in {'.cr2', '.cr3', '.nef', '.arw', '.raf', '.dng', '.orf', '.rw2', '.pef'}:
                try:
                    import rawpy
                    with rawpy.imread(filepath) as raw:
                        rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True)
                        img = PILImage.fromarray(rgb)
                except:
                    pass
            
            # Fallback to PIL
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
        
        # Split view: table (left) + preview (right)
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
                     (ImageType.FLAT, "☀️", "Flats"), (ImageType.BIAS, "📊", "Biases"),
                     (ImageType.UNKNOWN, "❓", "Unknown")]
        
        for i, (t, icon, label) in enumerate(types_list):
            card = ctk.CTkFrame(cards, fg_color="#1f1f3d", corner_radius=12)
            card.pack(side="left", expand=True, padx=5, fill="both")
            ctk.CTkLabel(card, text=icon, font=("Segoe UI", 24)).pack(pady=(15, 5))
            count = sum(1 for r in self.results if r.classified_type == t)
            ctk.CTkLabel(card, text=str(count), font=("Segoe UI", 20, "bold"), text_color="white").pack()
            ctk.CTkLabel(card, text=label, text_color="#a0a0a0", font=("Segoe UI", 10)).pack(pady=(0, 15))
            self.type_cards[t] = card
            cards.grid_columnconfigure(i, weight=1)
        
        # Table
        table = ctk.CTkFrame(main, fg_color="#1f1f3d", corner_radius=12)
        table.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        
        # Headers
        headers = ctk.CTkFrame(table, fg_color="#16213e", corner_radius=8)
        headers.pack(fill="x", padx=10, pady=10)
        
        cols = [("filename", "File", 180), ("type", "Type", 110), ("exposure", "Exp", 70), 
                ("iso", "ISO", 50), ("camera", "Camera", 100), ("mean", "Mean", 70)]
        
        for col_id, col_name, width in cols:
            arrow = " ▼" if self.sort_col == col_id else ""
            ctk.CTkButton(headers, text=col_name + arrow, fg_color="transparent", hover_color="#1f1f3d",
                         text_color="#00d9ff" if self.sort_col == col_id else "white", 
                         width=width, height=30, corner_radius=5, border_width=0,
                         font=("Segoe UI", 11, "bold"),
                         command=partial(self.sort_files, col_id)).pack(side="left", padx=3)
        
        scroll = ctk.CTkScrollableFrame(table, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Preview panel
        preview = ctk.CTkFrame(main, fg_color="#1f1f3d", corner_radius=12)
        preview.grid(row=1, column=1, sticky="nsew")
        
        ctk.CTkLabel(preview, text="Preview", font=("Segoe UI", 14, "bold"), text_color="white").pack(pady=(15, 5))
        
        self.preview_label = ctk.CTkLabel(preview, text="Click image to preview", text_color="#606080", font=("Segoe UI", 11))
        self.preview_label.pack(pady=20)
        
        self.preview_info = ctk.CTkLabel(preview, text="", text_color="#a0a0a0", font=("Segoe UI", 10), justify="left")
        self.preview_info.pack(pady=10)
        
        self._populate_file_list(scroll)
    
    def _populate_file_list(self, parent):
        for w in parent.winfo_children():
            w.destroy()
        
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
        
        type_values = ["Lights", "Darks", "Flats", "Biases", "Unknown"]
        
        for idx, m in enumerate(sorted_results):
            row = ctk.CTkFrame(parent, fg_color="#1a1a2e" if idx % 2 == 0 else "#1f1f3d", corner_radius=6)
            row.pack(fill="x", pady=2)
            
            # Thumbnail click
            thumb = ctk.CTkLabel(row, text="🖼", font=("Segoe UI", 14), cursor="hand2", text_color="#00d9ff")
            thumb.pack(side="left", padx=(8, 0))
            thumb.bind("<Button-1>", lambda e, mm=m: self._show_preview(mm))
            
            # Filename
            fname = m.filename[:25] + ("..." if len(m.filename) > 25 else "")
            ctk.CTkLabel(row, text=fname, text_color="white", width=150, anchor="w", 
                        font=("Segoe UI", 10)).pack(side="left", padx=5)
            
            # Type dropdown
            current_type = m.classified_type.value if m.classified_type else "Unknown"
            var = ctk.StringVar(value=current_type)
            
            dropdown = ctk.CTkOptionMenu(row, values=type_values, variable=var,
                            fg_color="#0f3460", button_color="#e94560",
                            dropdown_fg_color="#1f1f3d", width=110, height=28, font=("Segoe UI", 9),
                            command=lambda v, mm=m: self.change_type(mm, v))
            dropdown.pack(side="left", padx=3)
            
            # Columns
            exp_text = f"{m.exposure_time:.3f}s" if m.exposure_time else "-"
            ctk.CTkLabel(row, text=exp_text, text_color="#a0a0a0", width=70).pack(side="left")
            ctk.CTkLabel(row, text=str(m.iso) if m.iso else "-", text_color="#a0a0a0", width=50).pack(side="left")
            cam = (m.camera_model[:12] + "..") if m.camera_model and len(m.camera_model) > 12 else (m.camera_model or "-")
            ctk.CTkLabel(row, text=cam, text_color="#a0a0a0", width=100).pack(side="left")
            mean_text = f"{m.mean:.0f}" if m.mean else "-"
            ctk.CTkLabel(row, text=mean_text, text_color="#a0a0a0", width=70).pack(side="left")
        
        # Update counts
        for t, card in self.type_cards.items():
            count = sum(1 for r in self.results if r.classified_type == t)
            card.winfo_children()[1].configure(text=str(count))
    
    def _show_preview(self, metadata: ImageMetadata):
        """Show image preview in the panel"""
        self.selected_image = metadata
        
        try:
            img = self._preview_image(metadata.filepath)
            
            if img:
                img.thumbnail((350, 280))
                ctk_img = CTkImage(img, size=img.size)
                self.preview_label.configure(image=ctk_img, text="")
                self.preview_label.image = ctk_img
                
                # Update info
                info = f"File: {metadata.filename}\n"
                info += f"Type: {metadata.classified_type.value}\n"
                info += f"Exp: {metadata.exposure_time if metadata.exposure_time else '-'}s\n"
                info += f"ISO: {metadata.iso if metadata.iso else '-'}\n"
                info += f"Mean: {metadata.mean:.0f if metadata.mean else '-'}"
                self.preview_info.configure(text=info)
        except Exception as e:
            self.preview_label.configure(text=f"Cannot load:\n{str(e)[:50]}", image=None)
    
    def sort_files(self, col: str):
        if self.sort_col == col:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = col
            self.sort_asc = True
        
        # Find the scrollable frame and refresh
        for w in self.view_container.winfo_children():
            if isinstance(w, ctk.CTkFrame):
                for c in w.winfo_children():
                    if isinstance(c, ctk.CTkFrame):
                        for sc in c.winfo_children():
                            if isinstance(sc, ctk.CTkScrollableFrame):
                                self._populate_file_list(sc)
                                return
    
    def change_type(self, metadata: ImageMetadata, new_type: str):
        type_map = {"Lights": ImageType.LIGHT, "Darks": ImageType.DARK, 
                   "Flats": ImageType.FLAT, "Biases": ImageType.BIAS, "Unknown": ImageType.UNKNOWN}
        metadata.classified_type = type_map.get(new_type, ImageType.UNKNOWN)
        self._refresh_counts()
    
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
        
        ctk.CTkButton(card, text="Save", fg_color="#e94560", height=40,
                     command=self._save_settings).pack(pady=30)
    
    def _save_settings(self):
        self.settings['recursive'] = self.recursive_var.get()
        self.settings['export_method'] = self.method_var.get()
        self.settings['export_json'] = self.json_var.get()
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
        try:
            self.results = classify_directory(folder, recursive=self.settings['recursive'],
                                             progress_callback=self._progress)
            self.after(0, self._done)
        except Exception as e:
            self.after(0, lambda err=str(e): self._error(err))
    
    def _progress(self, cur, total, path):
        self.after(0, lambda: self.status_label.configure(text=f"Processing: {Path(path).name[:30]}"))
    
    def _done(self):
        self.browse_btn.configure(state="normal")
        self.export_btn.configure(state="normal")
        
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
        
        for m in self.results:
            dst = folders[m.classified_type]
            dst_path = os.path.join(dst, m.filename)
            
            counter = 1
            while os.path.exists(dst_path):
                dst_path = os.path.join(dst, f"{Path(m.filename).stem}_{counter}{Path(m.filename).suffix}")
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
