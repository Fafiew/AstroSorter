"""
AstroSorter - Main Application v1.0.4
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

from AstroSorter.classifier import ImageMetadata, ImageType, classify_directory, get_summary


VERSION = "1.0.4"


class AstroSorterApp(ctk.CTk):
    
    def __init__(self):
        super().__init__()
        
        self.title(f"AstroSorter v{VERSION}")
        self.geometry("1400x800")
        self.minsize(1000, 600)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.configure(fg_color="#0d0d1a")
        
        self.results: List[ImageMetadata] = []
        self.current_view = "home"
        self.sort_col = "filename"
        self.sort_asc = True
        
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
        
        self.title_label = ctk.CTkLabel(header, text="Welcome", font=("Segoe UI", 24, "bold"), text_color="white")
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
        
        titles = {"home": "Welcome to AstroSorter", "files": "Source Files", "settings": "Settings"}
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
        card = ctk.CTkFrame(self.view_container, fg_color="#1f1f3d", corner_radius=20)
        card.pack(fill="both", expand=True, padx=50, pady=30)
        
        ctk.CTkLabel(card, text="📂", font=("Segoe UI", 64), text_color="#00d9ff").pack(pady=(50, 20))
        ctk.CTkLabel(card, text="Select Image Folder", font=("Segoe UI", 24, "bold"), text_color="white").pack()
        ctk.CTkLabel(card, text="Browse a folder to automatically classify your astrophotography images",
                    text_color="#a0a0a0").pack(pady=10)
        ctk.CTkButton(card, text="Browse Folder", fg_color="#e94560", hover_color="#ff6b8a",
                     height=45, font=("Segoe UI", 14, "bold"), command=self.browse_folder).pack(pady=30)
        ctk.CTkLabel(card, text="Supports: CR2, CR3, NEF, ARW, RAF, DNG, FITS, TIFF, JPG",
                    text_color="#606080", font=("Segoe UI", 10)).pack(pady=(0, 40))
    
    def _show_files(self):
        if not self.results:
            card = ctk.CTkFrame(self.view_container, fg_color="#1f1f3d", corner_radius=20)
            card.pack(fill="both", expand=True)
            ctk.CTkLabel(card, text="📁", font=("Segoe UI", 48), text_color="#606080").pack(pady=(80, 20))
            ctk.CTkLabel(card, text="No images loaded", font=("Segoe UI", 18, "bold"), text_color="white").pack()
            ctk.CTkButton(card, text="Browse Folder", fg_color="#e94560", command=self.browse_folder).pack(pady=20)
            return
        
        # Summary cards
        cards = ctk.CTkFrame(self.view_container, fg_color="transparent")
        cards.pack(fill="x", pady=(0, 15))
        
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
        table = ctk.CTkFrame(self.view_container, fg_color="#1f1f3d", corner_radius=12)
        table.pack(fill="both", expand=True)
        
        headers = ctk.CTkFrame(table, fg_color="#16213e", corner_radius=8)
        headers.pack(fill="x", padx=10, pady=10)
        
        cols = [("filename", "File", 200), ("type", "Type", 120), ("exposure", "Exp", 80), 
                ("iso", "ISO", 60), ("camera", "Camera", 120), ("mean", "Mean", 80)]
        
        for col_id, col_name, width in cols:
            ctk.CTkButton(headers, text=col_name, fg_color="transparent", hover_color="#1f1f3d",
                         text_color="white", width=width, height=30, corner_radius=5, border_width=0,
                         font=("Segoe UI", 11, "bold"),
                         command=partial(self.sort_files, col_id)).pack(side="left", padx=5)
        
        scroll = ctk.CTkScrollableFrame(table, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self._populate_file_list(scroll)
    
    def _populate_file_list(self, parent):
        for w in parent.winfo_children():
            w.destroy()
        
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
            sorted_results = sorted(self.results, key=lambda r: r.camera_model or "", reverse=reverse)
        elif self.sort_col == "mean":
            sorted_results = sorted(self.results, key=lambda r: r.mean or 0, reverse=reverse)
        else:
            sorted_results = self.results
        
        # Type values for dropdown
        type_values = ["Lights", "Darks", "Flats", "Biases", "Unknown"]
        
        for idx, m in enumerate(sorted_results):
            row = ctk.CTkFrame(parent, fg_color="#1a1a2e" if idx % 2 == 0 else "#1f1f3d", corner_radius=6)
            row.pack(fill="x", pady=2)
            
            # Filename
            fname = m.filename[:35] + ("..." if len(m.filename) > 35 else "")
            ctk.CTkLabel(row, text=fname, text_color="white", width=200, anchor="w", 
                        font=("Segoe UI", 10)).pack(side="left", padx=10, pady=8)
            
            # Type dropdown - show current value immediately
            current_type = m.classified_type.value if m.classified_type else "Unknown"
            
            var = ctk.StringVar(value=current_type)
            dropdown = ctk.CTkOptionMenu(row, values=type_values, variable=var,
                            fg_color="#0f3460", button_color="#e94560",
                            dropdown_fg_color="#1f1f3d", width=120, height=28, font=("Segoe UI", 10),
                            command=lambda v, mm=m: self.change_type(mm, v))
            dropdown.pack(side="left", padx=5)
            
            # Other columns
            exp_text = f"{m.exposure_time:.3f}s" if m.exposure_time else "-"
            ctk.CTkLabel(row, text=exp_text, text_color="#a0a0a0", width=80).pack(side="left")
            
            ctk.CTkLabel(row, text=str(m.iso) if m.iso else "-",
                        text_color="#a0a0a0", width=60).pack(side="left")
            
            cam_text = (m.camera_model[:15] + "..") if m.camera_model and len(m.camera_model) > 15 else (m.camera_model or "-")
            ctk.CTkLabel(row, text=cam_text, text_color="#a0a0a0", width=120).pack(side="left")
            
            mean_text = f"{m.mean:.0f}" if m.mean else "-"
            ctk.CTkLabel(row, text=mean_text, text_color="#a0a0a0", width=80).pack(side="left")
        
        # Update counts
        for t, card in self.type_cards.items():
            count = sum(1 for r in self.results if r.classified_type == t)
            card.winfo_children()[1].configure(text=str(count))
    
    def change_type(self, metadata: ImageMetadata, new_type: str):
        metadata.selected_type = new_type
        type_map = {"Lights": ImageType.LIGHT, "Darks": ImageType.DARK, 
                   "Flats": ImageType.FLAT, "Biases": ImageType.BIAS, "Unknown": ImageType.UNKNOWN}
        metadata.classified_type = type_map.get(new_type, ImageType.UNKNOWN)
        self._refresh_counts()
    
    def _refresh_counts(self):
        for t, card in self.type_cards.items():
            count = sum(1 for r in self.results if r.classified_type == t)
            card.winfo_children()[1].configure(text=str(count))
    
    def sort_files(self, col: str):
        if self.sort_col == col:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = col
            self.sort_asc = True
        
        # Find scrollable frame and repopulate
        for w in self.view_container.winfo_children():
            if hasattr(w, 'winfo_children'):
                for c in w.winfo_children():
                    if isinstance(c, ctk.CTkFrame):
                        for sc in c.winfo_children():
                            if isinstance(sc, ctk.CTkScrollableFrame):
                                self._populate_file_list(sc)
    
    def _show_settings(self):
        card = ctk.CTkFrame(self.view_container, fg_color="#1f1f3d", corner_radius=20)
        card.pack(fill="both", expand=True, padx=100, pady=30)
        
        ctk.CTkLabel(card, text="⚙️ Settings", font=("Segoe UI", 20, "bold"), text_color="white").pack(anchor="w", padx=30, pady=(25, 20))
        
        ctk.CTkLabel(card, text="Scanning", font=("Segoe UI", 14, "bold"), text_color="#00d9ff").pack(anchor="w", padx=30, pady=(15, 10))
        
        self.recursive_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(card, text="Scan subfolders", variable=self.recursive_var,
                       text_color="white", font=("Segoe UI", 12)).pack(anchor="w", padx=30)
        
        ctk.CTkLabel(card, text="Export", font=("Segoe UI", 14, "bold"), text_color="#00d9ff").pack(anchor="w", padx=30, pady=(20, 10))
        
        self.method_var = ctk.StringVar(value="copy")
        ctk.CTkRadioButton(card, text="Copy files (keep originals)", variable=self.method_var, value="copy",
                          text_color="white").pack(anchor="w", padx=30)
        ctk.CTkRadioButton(card, text="Move files (remove originals)", variable=self.method_var, value="move",
                          text_color="white").pack(anchor="w", padx=30)
        
        self.json_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(card, text="Export JSON report", variable=self.json_var,
                       text_color="white").pack(anchor="w", padx=30, pady=15)
        
        ctk.CTkButton(card, text="Save Settings", fg_color="#e94560", height=40,
                     command=lambda: messagebox.showinfo("Settings", "Settings saved!")).pack(pady=30)
    
    def _center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"{self.winfo_width()}x{self.winfo_height()}+{x}+{y}")
    
    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select folder with images")
        if folder:
            self.process_folder(folder)
    
    def process_folder(self, folder: str):
        self.status_label.configure(text=f"Processing {Path(folder).name}...")
        self.browse_btn.configure(state="disabled")
        
        thread = threading.Thread(target=self._process, args=(folder,))
        thread.daemon = True
        thread.start()
    
    def _process(self, folder: str):
        try:
            self.results = classify_directory(folder, recursive=self.recursive_var.get(),
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
        
        # Create folders - include Unknown
        folders = {}
        for t in ImageType:
            folders[t] = os.path.join(dest, t.value)
            os.makedirs(folders[t], exist_ok=True)
        
        # Export
        for m in self.results:
            dst = folders[m.classified_type]
            dst_path = os.path.join(dst, m.filename)
            
            counter = 1
            while os.path.exists(dst_path):
                dst_path = os.path.join(dst, f"{Path(m.filename).stem}_{counter}{Path(m.filename).suffix}")
                counter += 1
            
            try:
                if self.method_var.get() == "move":
                    shutil.move(m.filepath, dst_path)
                else:
                    shutil.copy2(m.filepath, dst_path)
            except:
                pass
        
        # JSON
        if self.json_var.get():
            data = {
                'generated': datetime.now().isoformat(),
                'version': VERSION,
                'total': len(self.results),
                'files': [{
                    'filename': m.filename,
                    'type': m.classified_type.value,
                    'exposure': m.exposure_time,
                    'iso': m.iso,
                    'camera': m.camera_model,
                    'mean': m.mean
                } for m in self.results]
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
