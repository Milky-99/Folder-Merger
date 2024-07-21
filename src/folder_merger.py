import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import logging
from datetime import datetime

# Try to import tkinterdnd2, but don't fail if it's not available
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TKDND_AVAILABLE = True
except ImportError:
    TKDND_AVAILABLE = False

class FolderMerger:
    def __init__(self, root):
        self.root = root
        self.root.title("Premium Folder Merger")
        self.root.geometry("600x500")

        self.folders = []
        self.rename_conflict = tk.BooleanVar(value=True)
        self.delete_empty = tk.BooleanVar(value=False)
        self.target_folder = tk.StringVar()
        self.preserve_structure = tk.BooleanVar(value=False)
        self.create_log = tk.BooleanVar(value=True)

        self.setup_logging()
        self.setup_ui()

    def setup_ui(self):
        self.set_theme()

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        ttk.Label(left_frame, text="Source Folders", font=("Helvetica", 12, "bold")).pack(pady=5)
        self.listbox = tk.Listbox(left_frame, selectmode=tk.MULTIPLE, height=15, width=40)
        self.listbox.pack(pady=5, fill=tk.BOTH, expand=True)

        button_frame = ttk.Frame(left_frame)
        button_frame.pack(pady=5)

        ttk.Button(button_frame, text="Add Folders", command=self.select_folders).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Remove Selected", command=self.remove_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear All", command=self.clear_source_folders).pack(side=tk.LEFT, padx=5)

        ttk.Label(right_frame, text="Settings", font=("Helvetica", 12, "bold")).pack(pady=5)
        
        ttk.Label(right_frame, text="Target Folder:").pack(anchor=tk.W, pady=2)
        self.target_entry = ttk.Entry(right_frame, textvariable=self.target_folder, width=30)
        self.target_entry.pack(fill=tk.X, padx=(0, 5), pady=2)
        ttk.Button(right_frame, text="Browse", command=self.change_target_folder).pack(pady=2)

        ttk.Checkbutton(right_frame, text="Rename files on conflict", variable=self.rename_conflict).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(right_frame, text="Delete source folders if empty", variable=self.delete_empty).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(right_frame, text="Preserve folder structure", variable=self.preserve_structure).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(right_frame, text="Create log file", variable=self.create_log).pack(anchor=tk.W, pady=2)

        self.progress = ttk.Progressbar(right_frame, length=200, mode='determinate')
        self.progress.pack(pady=10)

        ttk.Button(right_frame, text="Merge Folders", command=self.start_merge).pack(pady=10)

        self.status_var = tk.StringVar()
        ttk.Label(right_frame, textvariable=self.status_var).pack(pady=5)

        # Configure drag-and-drop if available
        if TKDND_AVAILABLE:
            self.listbox.drop_target_register(DND_FILES)
            self.listbox.dnd_bind('<<Drop>>', self.on_drop_source)
            self.target_entry.drop_target_register(DND_FILES)
            self.target_entry.dnd_bind('<<Drop>>', self.on_drop_target)
        else:
            ttk.Label(left_frame, text="Drag and drop not available", foreground="red").pack(pady=5)

    def set_theme(self):
        style = ttk.Style()
        available_themes = style.theme_names()
        preferred_themes = ['clam', 'alt', 'default']
        
        for theme in preferred_themes:
            if theme in available_themes:
                try:
                    style.theme_use(theme)
                    self.logger.info(f"Using '{theme}' theme")
                    return
                except tk.TclError:
                    continue
        
        self.logger.warning("Could not set a preferred theme. Using default theme.")

    def setup_logging(self):
        self.logger = logging.getLogger('FolderMerger')
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def on_drop_source(self, event):
        paths = self.listbox.tk.splitlist(event.data)
        new_folders = [path for path in paths if os.path.isdir(path)]
        self.folders.extend(new_folders)
        self.update_folder_list()
        self.logger.info(f"{len(new_folders)} folders dropped to source.")

    def on_drop_target(self, event):
        paths = self.target_entry.tk.splitlist(event.data)
        if paths:
            self.target_folder.set(paths[0])
            self.logger.info(f"Target folder set to: {paths[0]}")

    def select_folders(self):
        new_folders = list(filedialog.askdirectory(multiple=True))
        if new_folders:
            self.folders.extend(new_folders)
            self.update_folder_list()
            self.logger.info(f"{len(new_folders)} folders selected.")

    def remove_selected(self):
        selected_indices = self.listbox.curselection()
        for index in reversed(selected_indices):
            del self.folders[index]
        self.update_folder_list()

    def clear_source_folders(self):
        self.folders.clear()
        self.update_folder_list()
        self.logger.info("Source folders cleared.")

    def update_folder_list(self):
        self.listbox.delete(0, tk.END)
        for folder in self.folders:
            self.listbox.insert(tk.END, folder)

    def change_target_folder(self):
        target = filedialog.askdirectory(title="Select Target Folder")
        if target:
            self.target_folder.set(target)

    def start_merge(self):
        if not self.folders:
            messagebox.showwarning("Warning", "No folders to merge.")
            return

        target_folder = self.target_folder.get()
        if not target_folder:
            messagebox.showwarning("Warning", "No target folder selected.")
            return

        threading.Thread(target=self.merge_folders, daemon=True).start()

    def merge_folders(self):
        total_files = sum(len(files) for folder in self.folders for _, _, files in os.walk(folder))
        processed_files = 0

        log_file = None
        if self.create_log.get():
            log_filename = f"merge_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            log_file = open(log_filename, 'w', encoding='utf-8')

        try:
            for folder in self.folders:
                for root, _, files in os.walk(folder):
                    for filename in files:
                        src = os.path.join(root, filename)
                        if self.preserve_structure.get():
                            rel_path = os.path.relpath(root, folder)
                            dst_dir = os.path.join(self.target_folder.get(), rel_path)
                            os.makedirs(dst_dir, exist_ok=True)
                            dst = os.path.join(dst_dir, filename)
                        else:
                            dst = os.path.join(self.target_folder.get(), filename)

                        if os.path.exists(dst) and self.rename_conflict.get():
                            base, ext = os.path.splitext(filename)
                            counter = 1
                            while os.path.exists(dst):
                                dst = os.path.join(os.path.dirname(dst), f"{base}_{counter}{ext}")
                                counter += 1

                        shutil.move(src, dst)
                        processed_files += 1
                        self.update_progress(processed_files, total_files)

                        if log_file:
                            log_file.write(f"Moved: {src} -> {dst}\n")

                if self.delete_empty.get() and not os.listdir(folder):
                    os.rmdir(folder)
                    if log_file:
                        log_file.write(f"Deleted empty folder: {folder}\n")

            self.logger.info("Folders merged successfully.")
            messagebox.showinfo("Info", "Folders merged successfully.")
            self.status_var.set("Merge completed")
        except Exception as e:
            self.logger.error(f"Error during merge: {str(e)}")
            messagebox.showerror("Error", f"An error occurred during the merge: {str(e)}")
            self.status_var.set("Merge failed")
        finally:
            if log_file:
                log_file.close()

    def update_progress(self, current, total):
        progress = int((current / total) * 100)
        self.progress['value'] = progress
        self.status_var.set(f"Processing: {current}/{total} files")
        self.root.update_idletasks()

if __name__ == "__main__":
    if TKDND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = FolderMerger(root)
    root.mainloop()
