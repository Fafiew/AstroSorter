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
from AstroSorter.ui_components import (
    Theme, AstroButton, AstroCard, DropZone, TypeCard, FileTable,
    Sidebar, StatusBar, MetadataPanel, GlassCard
)


class AstroSorterApp(ctk.CTk):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Window configuration
        self.title("AstroSorter - Astrophotography Image Classifier")
        self.geometry("1400x900")
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
        
        # Setup UI
        self._setup_ui()
        
        # Center window
        self._center_window()
    
    def _setup_ui(self):
        """Setup the main UI"""
        
        # Sidebar
        self.sidebar = Sidebar(self)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        # Main content area
        self.main_frame = ctk.CTkFrame(self, fg_color=Theme.BG_PRIMARY, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_rowconfigure(2, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # Header
        self._setup_header()
        
        # Content based on current view
        self._setup_home_view()
        
        # Status bar
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=1, column=1, sticky="ew")
        
        # Connect navigation
        self._connect_navigation()
    
    def _setup_header(self):
        """Setup header area"""
        header = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=30, pady=(30, 20))
        
        # Title
        ctk.CTkLabel(
            header,
            text="AstroSorter",
            font=ctk.CTkFont(size=Theme.FONT_TITLE, weight="bold"),
            text_color=Theme.TEXT_PRIMARY
        ).pack(side="left")
        
        # Subtitle
        ctk.CTkLabel(
            header,
            text="Automatic Astrophotography Image Classifier",
            font=ctk.CTkFont(size=Theme.FONT_BODY),
            text_color=Theme.TEXT_SECONDARY
        ).pack(side="left", padx=(15, 0))
        
        # Action buttons
        button_frame = ctk.CTkFrame(header, fg_color="transparent")
        button_frame.pack(side="right")
        
        self.browse_btn = AstroButton(
            button_frame,
            text="📂 Browse Folder",
            fg_color=Theme.ACCENT_SECONDARY,
            hover_color=Theme.ACCENT_PRIMARY,
            command=self.browse_folder
        )
        self.browse_btn.pack(side="right", padx=10)
        
        self.export_btn = AstroButton(
            button_frame,
            text="💾 Export Results",
            fg_color=Theme.ACCENT_SUCCESS,
            hover_color="#00cc6a",
            command=self.export_results,
            state="disabled"
        )
        self.export_btn.pack(side="right")
    
    def _setup_home_view(self):
        """Setup the home/drop zone view"""
        self.content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content_frame.grid(row=2, column=0, sticky="nsew", padx=30, pady=(0, 30))
        self.content_frame.grid_rowconfigure(1, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)
        
        # Drop zone
        self.drop_zone = DropZone(
            self.content_frame,
            height=300
        )
        self.drop_zone.set_browse_command(self.browse_folder)
        self.drop_zone.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        
        # Results container
        self.results_container = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.results_container.grid(row=1, column=0, sticky="nsew")
        self.results_container.grid_rowconfigure(0, weight=1)
        self.results_container.grid_columnconfigure(0, weight=1)
        
        # Type cards (hidden initially)
        self._setup_type_cards()
        
        # File table (hidden initially)
        self._setup_file_table()
        
        # Metadata panel (hidden initially)
        self._setup_metadata_panel()
        
        # Initially hide results area
        self.results_container.grid_remove()
    
    def _setup_type_cards(self):
        """Setup type cards for results"""
        cards_frame = ctk.CTkFrame(self.results_container, fg_color="transparent")
        cards_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        
        # Create cards for each type
        self.type_cards = {}
        
        types = [
            ImageType.LIGHT,
            ImageType.DARK,
            ImageType.FLAT,
            ImageType.BIAS,
            ImageType.FLAT_DARK
        ]
        
        for i, img_type in enumerate(types):
            card = TypeCard(cards_frame, image_type=img_type)
            card.grid(row=0, column=i, sticky="ew", padx=8)
            self.type_cards[img_type] = card
        
        # Configure grid weights
        cards_frame.grid_columnconfigure(tuple(range(len(types))), weight=1)
    
    def _setup_file_table(self):
        """Setup file table"""
        table_frame = ctk.CTkFrame(self.results_container, fg_color="transparent")
        table_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 20))
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Label
        ctk.CTkLabel(
            table_frame,
            text="Classified Files",
            font=ctk.CTkFont(size=Theme.FONT_SUBHEADING, weight="bold"),
            text_color=Theme.TEXT_PRIMARY
        ).grid(row=0, column=0, sticky="nw", pady=(0, 10))
        
        # Table
        self.file_table = FileTable(table_frame)
        self.file_table.grid(row=1, column=0, sticky="nsew")
        
        # Selection binding
        self.file_table.tree.bind('<<TreeviewSelect>>', self.on_file_select)
    
    def _setup_metadata_panel(self):
        """Setup metadata panel"""
        self.metadata_panel = MetadataPanel(self.results_container)
        self.metadata_panel.grid(row=1, column=1, sticky="nsew", padx=(20, 0))
        self.metadata_panel.grid_remove()
    
    def _connect_navigation(self):
        """Connect sidebar navigation"""
        # Get nav buttons and bind to view switching
        for i, btn in enumerate(self.sidebar.nav_buttons):
            btn.configure(command=lambda idx=i: self.switch_view(idx))
    
    def switch_view(self, index: int):
        """Switch between views"""
        self.sidebar.set_active(index)
        
        if index == 0:
            # Home view
            self._show_home_view()
        elif index == 1:
            # Source files view
            self._show_files_view()
        elif index == 2:
            # Classification view
            self._show_classification_view()
        elif index == 3:
            # Settings view
            self._show_settings_view()
    
    def _show_home_view(self):
        """Show home view"""
        self.drop_zone.grid()
        self.results_container.grid_remove()
    
    def _show_files_view(self):
        """Show files view"""
        if not self.results:
            messagebox.showinfo("No Data", "Please load and classify images first.")
            return
        
        self.drop_zone.grid_remove()
        self.results_container.grid()
        self.metadata_panel.grid()
    
    def _show_classification_view(self):
        """Show classification view"""
        self._show_files_view()
    
    def _show_settings_view(self):
        """Show settings view"""
        # For now, just show message
        messagebox.showinfo("Settings", "Settings panel coming soon!")
        self.switch_view(0)
    
    def _center_window(self):
        """Center the window on screen"""
        self.update_idletasks()
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        window_width = self.winfo_width()
        window_height = self.winfo_height()
        
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    def browse_folder(self):
        """Browse for folder to process"""
        folder = filedialog.askdirectory(
            title="Select folder containing astrophotography images",
            mustexist=True
        )
        
        if folder:
            self.process_directory(folder)
    
    def handle_drop(self, data: str):
        """Handle dropped files/folders"""
        # Parse dropped data
        paths = data.strip().split()
        
        if not paths:
            return
        
        # Check if it's a directory
        path = paths[0].strip('{}')  # Handle { } wrapping
        
        if os.path.isdir(path):
            self.process_directory(path)
        else:
            # It's a file, get its directory
            directory = os.path.dirname(path)
            if directory:
                self.process_directory(directory)
    
    def process_directory(self, directory: str):
        """Process all images in a directory"""
        if self.is_processing:
            return
        
        self.current_directory = directory
        self.is_processing = True
        
        # Update UI
        self.status_bar.set_status(f"Scanning {directory}...")
        self.status_bar.show_progress()
        self.browse_btn.configure(state="disabled")
        
        # Run processing in thread
        thread = threading.Thread(target=self._process_thread, args=(directory,))
        thread.daemon = True
        thread.start()
    
    def _process_thread(self, directory: str):
        """Processing thread"""
        try:
            # Set progress callback
            self.batch_classifier.set_progress_callback(self._update_progress)
            
            # Classify all files
            self.results = self.batch_classifier.classify_directory(
                directory,
                recursive=True,
                compute_stats=True
            )
            
            # Update UI on main thread
            self.after(0, self._processing_complete)
            
        except Exception as e:
            self.after(0, lambda: self._processing_error(str(e)))
    
    def _update_progress(self, current: int, total: int, filepath: str):
        """Update progress during processing"""
        progress = current / total
        
        def update():
            self.status_bar.set_status(f"Processing: {Path(filepath).name}")
            self.status_bar.set_progress(progress)
        
        self.after(0, update)
    
    def _processing_complete(self):
        """Handle processing completion"""
        self.is_processing = False
        
        # Update status
        self.status_bar.set_status("Processing complete!")
        self.status_bar.hide_progress()
        self.browse_btn.configure(state="normal")
        
        # Update type cards
        summary = self.batch_classifier.get_summary()
        
        for img_type, card in self.type_cards.items():
            count = summary['by_type'].get(img_type.value, 0)
            card.update_count(count)
        
        # Populate file table
        self.file_table.clear()
        
        # Sort by type for better display
        sorted_results = sorted(self.results, key=lambda x: x.classified_type.value)
        
        for metadata in sorted_results:
            self.file_table.add_file(metadata)
        
        # Show results
        self.results_container.grid()
        self.export_btn.configure(state="normal")
        
        # Show message
        messagebox.showinfo(
            "Classification Complete",
            f"Successfully classified {len(self.results)} images!\n\n"
            f"Lights: {summary['by_type'].get('Lights', 0)}\n"
            f"Darks: {summary['by_type'].get('Darks', 0)}\n"
            f"Flats: {summary['by_type'].get('Flats', 0)}\n"
            f"Biases: {summary['by_type'].get('Biases', 0)}\n"
            f"Flat-Darks: {summary['by_type'].get('Flat-Darks', 0)}"
        )
    
    def _processing_error(self, error: str):
        """Handle processing error"""
        self.is_processing = False
        
        self.status_bar.set_status("Error occurred")
        self.status_bar.hide_progress()
        self.browse_btn.configure(state="normal")
        
        messagebox.showerror("Error", f"Error processing files: {error}")
    
    def on_file_select(self, event):
        """Handle file selection in table"""
        selection = self.file_table.tree.selection()
        
        if not selection:
            return
        
        # Get selected item
        item = selection[0]
        values = self.file_table.tree.item(item, 'values')
        
        if not values:
            return
        
        filename = values[0]
        
        # Find corresponding metadata
        for metadata in self.results:
            if metadata.filename == filename:
                self.metadata_panel.display_metadata(metadata)
                break
    
    def export_results(self):
        """Export classified results"""
        if not self.results:
            return
        
        # Ask for destination
        destination = filedialog.askdirectory(
            title="Select output directory",
            mustexist=True
        )
        
        if not destination:
            return
        
        # Ask for export method
        method = messagebox.askyesnocancel(
            "Export Method",
            "Move files (instead of copying)?\n\n"
            "Yes = Move (removes from original location)\n"
            "No = Copy (keeps original files)"
        )
        
        if method is None:
            return
        
        move_files = method
        
        # Create folders and copy/move files
        self._export_files(destination, move_files)
    
    def _export_files(self, destination: str, move: bool = False):
        """Export files to destination"""
        self.status_bar.set_status("Exporting files...")
        self.status_bar.show_progress()
        
        # Create type folders
        folders = {}
        for img_type in ImageType:
            if img_type != ImageType.UNKNOWN:
                folder_path = os.path.join(destination, img_type.value)
                os.makedirs(folder_path, exist_ok=True)
                folders[img_type] = folder_path
        
        # Process each file
        total = len(self.results)
        
        for i, metadata in enumerate(self.results):
            if metadata.classified_type == ImageType.UNKNOWN:
                continue
            
            dest_folder = folders.get(metadata.classified_type)
            if not dest_folder:
                continue
            
            dest_path = os.path.join(dest_folder, metadata.filename)
            
            try:
                if move:
                    shutil.move(metadata.filepath, dest_path)
                else:
                    shutil.copy2(metadata.filepath, dest_path)
            except Exception as e:
                print(f"Error exporting {metadata.filename}: {e}")
            
            # Update progress
            self.after(0, lambda p=(i+1)/total: self.status_bar.set_progress(p))
        
        # Export metadata to JSON
        self._export_metadata_json(destination)
        
        self.status_bar.set_status("Export complete!")
        self.status_bar.hide_progress()
        
        # Open destination folder
        os.startfile(destination)
        
        messagebox.showinfo(
            "Export Complete",
            f"Files have been exported to:\n{destination}"
        )
    
    def _export_metadata_json(self, destination: str):
        """Export classification metadata to JSON"""
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
                'object_name': metadata.object_name,
                'mean': metadata.mean,
                'std': metadata.std,
                'error': metadata.error
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
