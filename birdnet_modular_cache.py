"""
pipeline_gui.py
===============
A desktop interface wrapper for running:
  - 01_create_npz.py  (Create Cache / Feature Extraction)
  - 02_combine_npz.py (Combine Caches)
  - 03_split_npz.py   (Split Cache)

Provides native Windows folder/file selection dialogs, input validation,
and a non-blocking background runner with real-time log coloring.
"""

import os
import sys
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import datetime

# --- Active background process reference ---
active_process = None


# =============================================================================
# Styling
# =============================================================================

def setup_styles():
    """Configure modern dark theme styles for the Tkinter application."""
    style = ttk.Style()
    style.theme_use('clam')

    # Custom color palette
    bg_color = "#1e1e1e"
    fg_color = "#e5e5e5"
    accent_color = "#007acc"
    field_bg = "#2d2d2d"

    # Global styles
    style.configure(".", background=bg_color, foreground=fg_color, font=("Segoe UI", 10))
    style.configure("TLabel", background=bg_color, foreground=fg_color)
    style.configure("TFrame", background=bg_color)
    style.configure("TLabelframe", background=bg_color, foreground=fg_color)
    style.configure("TLabelframe.Label", background=bg_color, foreground=accent_color,
                    font=("Segoe UI", 10, "bold"))

    # Buttons
    style.configure("TButton", background="#3c3c3c", foreground=fg_color, borderwidth=1,
                    focuscolor=accent_color)
    style.map("TButton",
              background=[('disabled', '#2a2a2a'), ('active', '#505050'), ('pressed', accent_color)],
              foreground=[('disabled', '#666666'), ('active', '#ffffff')])

    style.configure("Run.TButton", background=accent_color, foreground="#ffffff",
                    font=("Segoe UI", 10, "bold"))
    style.map("Run.TButton",
              background=[('disabled', '#2a2a2a'), ('active', '#005999'), ('pressed', '#004070')],
              foreground=[('disabled', '#666666')])

    style.configure("Cancel.TButton", background="#d32f2f", foreground="#ffffff",
                    font=("Segoe UI", 10, "bold"))
    style.map("Cancel.TButton",
              background=[('disabled', '#2a2a2a'), ('active', '#b71c1c'), ('pressed', '#8e0000')],
              foreground=[('disabled', '#666666')])

    # Inputs & Dropdowns
    style.configure("TEntry", fieldbackground=field_bg, foreground=fg_color, borderwidth=1)
    style.configure("TCombobox", fieldbackground=field_bg, background="#3c3c3c", foreground=fg_color)
    style.map("TCombobox",
              fieldbackground=[('readonly', field_bg)],
              foreground=[('readonly', fg_color)])

    # Radiobuttons
    style.configure("TRadiobutton", background=bg_color, foreground=fg_color)

    # Notebook Tabs
    style.configure("TNotebook", background="#121212", borderwidth=0)
    style.configure("TNotebook.Tab", background="#2d2d2d", foreground="#888888",
                    padding=[16, 8], font=("Segoe UI", 10, "bold"))
    style.map("TNotebook.Tab",
              background=[('selected', bg_color)],
              foreground=[('selected', "#ffffff")])


# =============================================================================
# Helpers
# =============================================================================

def append_text(widget, text, tag=None):
    """Append text to a scrolledtext widget and scroll to end."""
    widget.config(state=tk.NORMAL)
    widget.insert(tk.END, text, tag)
    widget.see(tk.END)
    widget.config(state=tk.DISABLED)


def safe_append(root, widget, text, tag=None):
    """Thread-safe call to append text to the log console."""
    root.after(0, lambda: append_text(widget, text, tag))


def validate_float(value_str, field_name, allow_negative=False):
    """Validate that a string can be converted to a float.
    Returns (True, float_val) on success, (False, error_msg) on failure."""
    value_str = value_str.strip()
    if not value_str:
        return False, f"{field_name} cannot be empty."
    try:
        val = float(value_str)
    except ValueError:
        return False, f"{field_name} must be a number. Got: '{value_str}'"
    if not allow_negative and val < 0:
        return False, f"{field_name} cannot be negative. Got: {val}"
    return True, val


def run_script(root, script_name, args, console, run_btn, cancel_btn, on_success=None):
    """Run a python script in a background thread and pipe stdout/stderr to the console."""
    global active_process

    # UI updates - Disable Start, Enable Stop
    run_btn.config(state=tk.DISABLED)
    cancel_btn.config(state=tk.NORMAL)

    # Clear console
    console.config(state=tk.NORMAL)
    console.delete("1.0", tk.END)
    console.config(state=tk.DISABLED)

    # Get local script path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, script_name)

    # Construct display command string
    full_cmd = [script_path] + args
    cmd_str = "py -3.11 " + " ".join(
        f'"{a}"' if " " in a or "\\" in a else a for a in full_cmd
    )

    safe_append(root, console, f"Launching process:\n{cmd_str}\n\n", "info")

    def worker():
        global active_process
        try:
            # On Windows, hide command window popups
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW

            active_process = subprocess.Popen(
                ["py", "-3.11", script_path] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creation_flags
            )

            # Read stdout line by line
            for line in active_process.stdout:
                # Classify line for coloring
                tag = None
                if "[WARN]" in line:
                    tag = "warning"
                elif "ERROR:" in line or "failed" in line.lower():
                    tag = "error"
                elif "Saved ->" in line or "Successfully" in line or "Split complete" in line:
                    tag = "success"

                safe_append(root, console, line, tag)

            active_process.wait()
            exit_code = active_process.returncode

            if exit_code == 0:
                safe_append(root, console, "\nProcess finished successfully!\n", "success")
                if on_success:
                    root.after(0, on_success)
            elif exit_code in (-15, 1, 3221225786):
                safe_append(root, console, "\nProcess stopped by user.\n", "warning")
            else:
                safe_append(root, console, f"\nProcess failed (Exit code: {exit_code})\n", "error")

        except Exception as e:
            safe_append(root, console, f"\nError running script: {e}\n", "error")

        finally:
            active_process = None
            root.after(0, lambda: run_btn.config(state=tk.NORMAL))
            root.after(0, lambda: cancel_btn.config(state=tk.DISABLED))

    t = threading.Thread(target=worker, daemon=True)
    t.start()


def kill_active_process():
    """Terminate the active background subprocess."""
    global active_process
    if active_process:
        if messagebox.askyesno("Confirm Stop", "Are you sure you want to stop the running task?"):
            try:
                active_process.terminate()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to stop process: {e}")


def setup_log_tags(log_widget):
    """Configure colored tags for a log console widget."""
    log_widget.tag_config("info",    foreground="#569cd6")
    log_widget.tag_config("warning", foreground="#ffb300")
    log_widget.tag_config("error",   foreground="#f44336")
    log_widget.tag_config("success", foreground="#4caf50")


# =============================================================================
# Main Application
# =============================================================================

def main():
    root = tk.Tk()
    root.title("BirdNET NPZ Pipeline")
    root.geometry("920x820")
    root.configure(bg="#1e1e1e")

    setup_styles()

    # --- Top Banner ---
    top_bar = tk.Frame(root, bg="#121212", height=40)
    top_bar.pack(fill=tk.X, side=tk.TOP)
    top_bar.pack_propagate(False)
    tk.Label(top_bar, text="BirdNET NPZ Pipeline Management Console",
             bg="#121212", fg="#007acc", font=("Segoe UI", 11, "bold")
             ).pack(pady=8, padx=15, side=tk.LEFT)

    # --- Tab Control ---
    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    tab_create  = ttk.Frame(notebook)
    tab_combine = ttk.Frame(notebook)
    tab_split   = ttk.Frame(notebook)

    notebook.add(tab_create,  text="Create cache (NPZ)")
    notebook.add(tab_combine, text="Combine caches (NPZs)")
    notebook.add(tab_split,   text="Split cache (NPZ)")

    # =========================================================================
    # TAB 1: CREATE CACHE (01_create_npz.py)
    # =========================================================================

    # Scrollable container
    t1_canvas = tk.Canvas(tab_create, bg="#1e1e1e", highlightthickness=0)
    t1_scrollbar = ttk.Scrollbar(tab_create, orient="vertical", command=t1_canvas.yview)
    t1_scrollable = ttk.Frame(t1_canvas)

    t1_scrollable.bind(
        "<Configure>",
        lambda e: t1_canvas.configure(scrollregion=t1_canvas.bbox("all"))
    )
    t1_canvas.create_window((0, 0), window=t1_scrollable, anchor="nw")
    t1_canvas.configure(yscrollcommand=t1_scrollbar.set)

    t1_canvas.pack(side="left", fill="both", expand=True)
    t1_scrollbar.pack(side="right", fill="y")

    # ------------------------------------------------------------------
    # Card 1: Settings & Extraction Parameters  (FIRST)
    # ------------------------------------------------------------------
    card_settings = ttk.LabelFrame(t1_scrollable, text=" Settings & Extraction Parameters ",
                                   padding=12)
    card_settings.pack(fill=tk.X, expand=True, padx=15, pady=10)

    cur_row = 0

    # -- Save Mode --
    ttk.Label(card_settings, text="Save Mode:").grid(row=cur_row, column=0, sticky=tk.W, pady=5)
    t1_save_mode_var = tk.StringVar(value="separate")

    t1_save_radio_frame = ttk.Frame(card_settings)
    t1_save_radio_frame.grid(row=cur_row, column=1, padx=8, sticky=tk.W)
    ttk.Radiobutton(t1_save_radio_frame, text="Separate NPZ per class (Default)",
                    variable=t1_save_mode_var, value="separate").pack(side=tk.LEFT, padx=5)
    ttk.Radiobutton(t1_save_radio_frame, text="Single combined NPZ file",
                    variable=t1_save_mode_var, value="combined").pack(side=tk.LEFT, padx=5)

    cur_row += 1

    # -- Crop Mode (radio buttons) --
    ttk.Label(card_settings, text="Crop Mode:").grid(row=cur_row, column=0, sticky=tk.W, pady=5)
    t1_crop_var = tk.StringVar(value="center")

    t1_crop_radio_frame = ttk.Frame(card_settings)
    t1_crop_radio_frame.grid(row=cur_row, column=1, padx=8, sticky=tk.W)
    for mode_text, mode_val in [("Center (Default)", "center"), ("First", "first"),
                                ("Segments", "segments"), ("Smart", "smart")]:
        ttk.Radiobutton(t1_crop_radio_frame, text=mode_text,
                        variable=t1_crop_var, value=mode_val).pack(side=tk.LEFT, padx=5)

    cur_row += 1

    # -- Overlap (only enabled for segments/smart) --
    t1_overlap_lbl = ttk.Label(card_settings, text="Segment Overlap (secs):")
    t1_overlap_lbl.grid(row=cur_row, column=0, sticky=tk.W, pady=5)
    t1_overlap_var = tk.StringVar(value="0.0")
    t1_overlap_ent = ttk.Entry(card_settings, textvariable=t1_overlap_var, width=28)
    t1_overlap_ent.grid(row=cur_row, column=1, padx=8, sticky=tk.W)

    def on_crop_mode_change(*_args):
        mode = t1_crop_var.get()
        if mode in ("segments", "smart"):
            t1_overlap_ent.config(state=tk.NORMAL)
            t1_overlap_lbl.config(foreground="#e5e5e5")
        else:
            t1_overlap_ent.config(state=tk.DISABLED)
            t1_overlap_lbl.config(foreground="#666666")

    t1_crop_var.trace_add("write", on_crop_mode_change)

    cur_row += 1

    # -- Bandpass Fmin --
    ttk.Label(card_settings, text="Bandpass Fmin (Hz):").grid(
        row=cur_row, column=0, sticky=tk.W, pady=5)
    t1_fmin_var = tk.StringVar(value="0.0")
    ttk.Entry(card_settings, textvariable=t1_fmin_var, width=28).grid(
        row=cur_row, column=1, padx=8, sticky=tk.W)

    cur_row += 1

    # -- Bandpass Fmax --
    ttk.Label(card_settings, text="Bandpass Fmax (Hz):").grid(
        row=cur_row, column=0, sticky=tk.W, pady=5)
    t1_fmax_var = tk.StringVar(value="15000.0")
    ttk.Entry(card_settings, textvariable=t1_fmax_var, width=28).grid(
        row=cur_row, column=1, padx=8, sticky=tk.W)

    cur_row += 1

    # -- Audio Speed --
    ttk.Label(card_settings, text="Audio Speed Factor:").grid(
        row=cur_row, column=0, sticky=tk.W, pady=5)
    t1_speed_var = tk.StringVar(value="1.0")
    ttk.Entry(card_settings, textvariable=t1_speed_var, width=28).grid(
        row=cur_row, column=1, padx=8, sticky=tk.W)

    cur_row += 1

    # -- Reset Defaults Button --
    def reset_t1_defaults():
        t1_save_mode_var.set("separate")
        t1_crop_var.set("center")
        t1_overlap_var.set("0.0")
        t1_fmin_var.set("0.0")
        t1_fmax_var.set("15000.0")
        t1_speed_var.set("1.0")

    ttk.Button(card_settings, text="Reset Settings to Defaults", command=reset_t1_defaults).grid(
        row=cur_row, column=1, sticky=tk.W, padx=8, pady=10)

    # ------------------------------------------------------------------
    # Card 2: Paths & Directories  (SECOND)
    # ------------------------------------------------------------------
    card_paths = ttk.LabelFrame(t1_scrollable, text=" Paths & Directories ", padding=12)
    card_paths.pack(fill=tk.X, expand=True, padx=15, pady=10)

    # -- Model Path --
    ttk.Label(card_paths, text="BirdNET Model Path:").grid(row=0, column=0, sticky=tk.W, pady=5)
    t1_model_var = tk.StringVar(value="")
    ttk.Entry(card_paths, textvariable=t1_model_var, width=65).grid(
        row=0, column=1, padx=8, sticky=tk.EW)

    def browse_model():
        d = filedialog.askdirectory(
            title="Select BirdNET Model Directory",
            initialdir=r"D:\BirdNET-Analyzer\_internal\NB_NPZ\model")
        if d:
            t1_model_var.set(d.replace("/", "\\"))
    ttk.Button(card_paths, text="Browse...", command=browse_model).grid(
        row=0, column=2, sticky=tk.E)

    # -- Input Audio Directory --
    ttk.Label(card_paths, text="Input Audio Directory:").grid(row=1, column=0, sticky=tk.W, pady=5)
    t1_audio_var = tk.StringVar()
    ttk.Entry(card_paths, textvariable=t1_audio_var, width=65).grid(
        row=1, column=1, padx=8, sticky=tk.EW)

    def browse_audio():
        d = filedialog.askdirectory(
            title="Select Input Audio Directory", initialdir=r"D:\ebird")
        if d:
            t1_audio_var.set(d.replace("/", "\\"))
    ttk.Button(card_paths, text="Browse...", command=browse_audio).grid(
        row=1, column=2, sticky=tk.E)

    # -- Output Location --
    t1_out_lbl = ttk.Label(card_paths, text="Output Directory:")
    t1_out_lbl.grid(row=2, column=0, sticky=tk.W, pady=5)
    t1_out_var = tk.StringVar()
    ttk.Entry(card_paths, textvariable=t1_out_var, width=65).grid(
        row=2, column=1, padx=8, sticky=tk.EW)

    def browse_t1_out():
        mode = t1_save_mode_var.get()
        if mode == "separate":
            d = filedialog.askdirectory(
                title="Select Parent Output Folder",
                initialdir=r"D:\BirdNET-Analyzer\_internal\NB_NPZ\npzs")
            if d:
                t1_out_var.set(d.replace("/", "\\"))
        else:
            f = filedialog.asksaveasfilename(
                title="Select Output .npz File Path",
                initialdir=r"D:\BirdNET-Analyzer\_internal\NB_NPZ\npzs",
                filetypes=[("NPZ Files", "*.npz"), ("All Files", "*.*")],
                defaultextension=".npz")
            if f:
                t1_out_var.set(f.replace("/", "\\"))
    ttk.Button(card_paths, text="Browse...", command=browse_t1_out).grid(
        row=2, column=2, sticky=tk.E)

    card_paths.columnconfigure(1, weight=1)

    # Update output label text when save mode changes
    def on_save_mode_change(*_args):
        mode = t1_save_mode_var.get()
        if mode == "separate":
            t1_out_lbl.config(text="Output Directory:")
        else:
            t1_out_lbl.config(text="Output NPZ File:")
    t1_save_mode_var.trace_add("write", on_save_mode_change)

    # ------------------------------------------------------------------
    # Buttons & Log for Tab 1
    # ------------------------------------------------------------------
    t1_controls = ttk.Frame(t1_scrollable)
    t1_controls.pack(fill=tk.X, padx=15, pady=10)

    t1_log = scrolledtext.ScrolledText(
        t1_scrollable, bg="#0c0c0c", fg="#d4d4d4", font=("Consolas", 10),
        height=14, state=tk.DISABLED)
    t1_log.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
    setup_log_tags(t1_log)

    def start_t1():
        # --- Validate all numeric inputs ---
        validations = [
            (t1_fmin_var.get(),    "Bandpass Fmin"),
            (t1_fmax_var.get(),    "Bandpass Fmax"),
            (t1_speed_var.get(),   "Audio Speed Factor"),
        ]
        # Only validate overlap if it is enabled
        crop = t1_crop_var.get()
        if crop in ("segments", "smart"):
            validations.append((t1_overlap_var.get(), "Segment Overlap"))

        for val_str, name in validations:
            ok, result = validate_float(val_str, name)
            if not ok:
                messagebox.showerror("Validation Error", result)
                return

        # --- Validate required paths ---
        if not t1_audio_var.get().strip():
            messagebox.showerror("Error", "Please specify the input audio directory!")
            return

        # --- Build CLI arguments ---
        args = ["--audio_dir", t1_audio_var.get().strip()]

        if t1_out_var.get().strip():
            args += ["--output_npz", t1_out_var.get().strip()]

        if t1_model_var.get().strip():
            args += ["--model_path", t1_model_var.get().strip()]

        args += ["--crop_mode", crop]

        sm = t1_save_mode_var.get()
        if sm == "separate":
            args += ["--separate_files"]
        elif sm == "combined":
            args += ["--combined_file"]

        args += [
            "--fmin", t1_fmin_var.get().strip(),
            "--fmax", t1_fmax_var.get().strip(),
            "--audio_speed", t1_speed_var.get().strip(),
            "--overlap", t1_overlap_var.get().strip() if crop in ("segments", "smart") else "0.0",
        ]
        
        def on_success():
            now = datetime.datetime.now()
            now_str = now.strftime("%Y%m%d_%H%M%S")
            log_filename = f"CreateCache_Log_{now_str}.txt"
            
            # Determine output directory
            out_loc = t1_out_var.get().strip()
            if not out_loc:
                out_loc = t1_audio_var.get().strip()
            
            # If combined mode, out_loc is a file, so get its directory
            if sm == "combined":
                out_dir = os.path.dirname(out_loc) if os.path.dirname(out_loc) else out_loc
            else:
                out_dir = out_loc
                
            log_path = os.path.join(out_dir, log_filename)
            try:
                # Ensure directory exists just in case
                if out_dir and not os.path.exists(out_dir):
                    os.makedirs(out_dir, exist_ok=True)
                
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write(f"BirdNET NPZ Create Cache Log\n")
                    f.write(f"Completed: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"{'-'*50}\n")
                    f.write(f"Audio Directory : {t1_audio_var.get()}\n")
                    f.write(f"Output Location : {t1_out_var.get()}\n")
                    f.write(f"BirdNET Model   : {t1_model_var.get()}\n")
                    f.write(f"Save Mode       : {sm}\n")
                    f.write(f"Crop Mode       : {crop}\n")
                    f.write(f"Overlap (s)     : {t1_overlap_var.get() if crop in ('segments', 'smart') else 'N/A'}\n")
                    f.write(f"Fmin (Hz)       : {t1_fmin_var.get()}\n")
                    f.write(f"Fmax (Hz)       : {t1_fmax_var.get()}\n")
                    f.write(f"Audio Speed     : {t1_speed_var.get()}\n")
                safe_append(root, t1_log, f"\nSaved run log to: {log_path}\n", "info")
            except Exception as e:
                safe_append(root, t1_log, f"\nFailed to write run log: {e}\n", "error")

        run_script(root, "01_create_npz.py", args, t1_log, t1_start_btn, t1_stop_btn, on_success)

    t1_start_btn = ttk.Button(t1_controls, text="  Start  ", style="Run.TButton",
                              command=start_t1)
    t1_start_btn.pack(side=tk.LEFT, padx=5)

    t1_stop_btn = ttk.Button(t1_controls, text="  Stop  ", style="Cancel.TButton",
                             state=tk.DISABLED, command=kill_active_process)
    t1_stop_btn.pack(side=tk.LEFT, padx=5)

    # Fire initial state for overlap enable/disable and output label
    on_crop_mode_change()
    on_save_mode_change()

    # =========================================================================
    # TAB 2: COMBINE CACHES (02_combine_npz.py)
    # =========================================================================
    card_t2 = ttk.LabelFrame(tab_combine, text=" Combine Parameters ", padding=15)
    card_t2.pack(fill=tk.X, padx=15, pady=15)

    # -- Input NPZ Directory --
    ttk.Label(card_t2, text="Input NPZ Directory:").grid(row=0, column=0, sticky=tk.W, pady=5)
    t2_dir_var = tk.StringVar()
    ttk.Entry(card_t2, textvariable=t2_dir_var, width=65).grid(
        row=0, column=1, padx=8, sticky=tk.EW)

    def browse_t2_dir():
        d = filedialog.askdirectory(
            title="Select Folder containing NPZs",
            initialdir=r"D:\BirdNET-Analyzer\_internal\NB_NPZ\npzs")
        if d:
            t2_dir_var.set(d.replace("/", "\\"))
    ttk.Button(card_t2, text="Browse...", command=browse_t2_dir).grid(
        row=0, column=2, sticky=tk.E)

    # -- Output Combined file --
    ttk.Label(card_t2, text="Output Combined NPZ File:").grid(row=1, column=0, sticky=tk.W, pady=5)
    t2_out_var = tk.StringVar()
    ttk.Entry(card_t2, textvariable=t2_out_var, width=65).grid(
        row=1, column=1, padx=8, sticky=tk.EW)

    def browse_t2_out():
        f = filedialog.asksaveasfilename(
            title="Choose Location for Master NPZ",
            initialdir=r"D:\BirdNET-Analyzer\_internal\NB_NPZ\npzs",
            filetypes=[("NPZ Files", "*.npz"), ("All Files", "*.*")],
            defaultextension=".npz")
        if f:
            t2_out_var.set(f.replace("/", "\\"))
    ttk.Button(card_t2, text="Browse...", command=browse_t2_out).grid(
        row=1, column=2, sticky=tk.E)

    card_t2.columnconfigure(1, weight=1)

    # Buttons & Log for Tab 2
    t2_controls = ttk.Frame(tab_combine)
    t2_controls.pack(fill=tk.X, padx=15, pady=5)

    t2_log = scrolledtext.ScrolledText(
        tab_combine, bg="#0c0c0c", fg="#d4d4d4", font=("Consolas", 10),
        height=20, state=tk.DISABLED)
    t2_log.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
    setup_log_tags(t2_log)

    def start_t2():
        if not t2_dir_var.get().strip() or not t2_out_var.get().strip():
            messagebox.showerror("Error", "Please fill in all inputs before starting!")
            return
        args = ["--npz_dir", t2_dir_var.get().strip(),
                "--output_npz", t2_out_var.get().strip()]
        run_script(root, "02_combine_npz.py", args, t2_log, t2_start_btn, t2_stop_btn)

    t2_start_btn = ttk.Button(t2_controls, text="  Start  ", style="Run.TButton",
                              command=start_t2)
    t2_start_btn.pack(side=tk.LEFT, padx=5)

    t2_stop_btn = ttk.Button(t2_controls, text="  Stop  ", style="Cancel.TButton",
                             state=tk.DISABLED, command=kill_active_process)
    t2_stop_btn.pack(side=tk.LEFT, padx=5)

    # =========================================================================
    # TAB 3: SPLIT CACHE (03_split_npz.py)
    # =========================================================================
    card_t3 = ttk.LabelFrame(tab_split, text=" Split Parameters ", padding=15)
    card_t3.pack(fill=tk.X, padx=15, pady=15)

    # -- Input Combined NPZ file --
    ttk.Label(card_t3, text="Combined NPZ File:").grid(row=0, column=0, sticky=tk.W, pady=5)
    t3_file_var = tk.StringVar()
    ttk.Entry(card_t3, textvariable=t3_file_var, width=65).grid(
        row=0, column=1, padx=8, sticky=tk.EW)

    def browse_t3_file():
        f = filedialog.askopenfilename(
            title="Select Combined Master NPZ",
            initialdir=r"D:\BirdNET-Analyzer\_internal\NB_NPZ\npzs",
            filetypes=[("NPZ Files", "*.npz"), ("All Files", "*.*")])
        if f:
            t3_file_var.set(f.replace("/", "\\"))
    ttk.Button(card_t3, text="Browse...", command=browse_t3_file).grid(
        row=0, column=2, sticky=tk.E)

    # -- Destination Directory --
    ttk.Label(card_t3, text="Destination Directory:").grid(row=1, column=0, sticky=tk.W, pady=5)
    t3_dir_var = tk.StringVar()
    ttk.Entry(card_t3, textvariable=t3_dir_var, width=65).grid(
        row=1, column=1, padx=8, sticky=tk.EW)

    def browse_t3_dir():
        d = filedialog.askdirectory(
            title="Select Folder to Save Split NPZs",
            initialdir=r"D:\BirdNET-Analyzer\_internal\NB_NPZ\npzs")
        if d:
            t3_dir_var.set(d.replace("/", "\\"))
    ttk.Button(card_t3, text="Browse...", command=browse_t3_dir).grid(
        row=1, column=2, sticky=tk.E)

    card_t3.columnconfigure(1, weight=1)

    # Buttons & Log for Tab 3
    t3_controls = ttk.Frame(tab_split)
    t3_controls.pack(fill=tk.X, padx=15, pady=5)

    t3_log = scrolledtext.ScrolledText(
        tab_split, bg="#0c0c0c", fg="#d4d4d4", font=("Consolas", 10),
        height=20, state=tk.DISABLED)
    t3_log.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
    setup_log_tags(t3_log)

    def start_t3():
        if not t3_file_var.get().strip() or not t3_dir_var.get().strip():
            messagebox.showerror("Error", "Please fill in all inputs before starting!")
            return
        args = ["--input_npz", t3_file_var.get().strip(),
                "--output_dir", t3_dir_var.get().strip()]
        run_script(root, "03_split_npz.py", args, t3_log, t3_start_btn, t3_stop_btn)

    t3_start_btn = ttk.Button(t3_controls, text="  Start  ", style="Run.TButton",
                              command=start_t3)
    t3_start_btn.pack(side=tk.LEFT, padx=5)

    t3_stop_btn = ttk.Button(t3_controls, text="  Stop  ", style="Cancel.TButton",
                             state=tk.DISABLED, command=kill_active_process)
    t3_stop_btn.pack(side=tk.LEFT, padx=5)

    # Explicitly set variables one time after startup
    t1_save_mode_var.set("separate")
    t1_crop_var.set("center")

    # =========================================================================
    root.mainloop()


if __name__ == "__main__":
    main()
