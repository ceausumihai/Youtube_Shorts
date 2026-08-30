#!/usr/bin/env python3

import os
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from tkinterdnd2 import DND_FILES, TkinterDnD


SUPPORTED_EXTENSIONS = {
    ".mp4", ".m4a", ".mov", ".aac",
    ".mp3", ".wav", ".mkv", ".flac", ".ogg"
}

OUTPUT_SAMPLE_RATE = "48000"
OUTPUT_CHANNELS = "1"
OUTPUT_CODEC = "pcm_s16le"


class YouCutConverter:

    def __init__(self, root):
        self.root = root
        self.files = []
        self.processing = False

        self.setup_window()
        self.create_ui()

    # ========================================================
    # WINDOW
    # ========================================================

    def setup_window(self):

        self.root.title("Audio Converter")

        # Larger initial window
        self.root.geometry("760x700")

        # Prevent window becoming too small
        self.root.minsize(700, 620)

        # Allow resizing
        self.root.resizable(True, True)

        # macOS friendly Tk scaling
        try:
            self.root.tk.call("tk", "scaling", 1.25)
        except Exception:
            pass

    # ========================================================
    # UI
    # ========================================================

    def create_ui(self):

        # Main container
        main = tk.Frame(self.root)
        main.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=25
        )

        # Allow vertical expansion
        main.columnconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        title = tk.Label(
            main,
            text="🎵 Audio Converter",
            font=("Helvetica", 25, "bold")
        )

        title.grid(
            row=0,
            column=0,
            pady=(0, 5)
        )

        subtitle = tk.Label(
            main,
            text="Convert audio to YouCut-compatible WAV",
            font=("Helvetica", 12)
        )

        subtitle.grid(
            row=1,
            column=0,
            pady=(0, 20)
        )

        # ----------------------------------------------------
        # DROP AREA
        # ----------------------------------------------------

        self.drop_area = tk.Frame(
            main,
            height=170,
            relief="groove",
            borderwidth=2,
            bg="#f5f5f5"
        )

        self.drop_area.grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(0, 15)
        )

        self.drop_area.grid_propagate(False)

        drop_label = tk.Label(
            self.drop_area,
            text=(
                "DROP FILES HERE\n\n"
                "MP4 • M4A • MOV • AAC • MP3 • WAV\n\n"
                "Output: WAV PCM 16-bit • 48 kHz • Mono"
            ),
            font=("Helvetica", 15),
            justify="center",
            bg="#f5f5f5"
        )

        drop_label.pack(
            fill="both",
            expand=True
        )

        # Register both widgets
        for widget in (self.drop_area, drop_label):

            widget.drop_target_register(DND_FILES)

            widget.dnd_bind(
                "<<Drop>>",
                self.handle_drop
            )

        # ----------------------------------------------------
        # FILE LIST AREA
        # ----------------------------------------------------

        list_container = tk.Frame(main)

        list_container.grid(
            row=3,
            column=0,
            sticky="nsew"
        )

        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(
            list_container,
            selectmode=tk.EXTENDED,
            font=("Helvetica", 11)
        )

        self.listbox.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        scrollbar = tk.Scrollbar(
            list_container,
            orient="vertical",
            command=self.listbox.yview
        )

        scrollbar.grid(
            row=0,
            column=1,
            sticky="ns"
        )

        self.listbox.config(
            yscrollcommand=scrollbar.set
        )

        # ----------------------------------------------------
        # PROGRESS
        # ----------------------------------------------------

        self.progress = ttk.Progressbar(
            main,
            length=600,
            mode="determinate"
        )

        self.progress.grid(
            row=4,
            column=0,
            sticky="ew",
            pady=(15, 5)
        )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self.status = tk.Label(
            main,
            text="Drop files into the area above.",
            font=("Helvetica", 11)
        )

        self.status.grid(
            row=5,
            column=0,
            pady=(0, 10)
        )

        # ----------------------------------------------------
        # BUTTONS
        # ----------------------------------------------------

        button_frame = tk.Frame(main)

        button_frame.grid(
            row=6,
            column=0,
            pady=(5, 0)
        )

        self.convert_button = tk.Button(
            button_frame,
            text="Convert",
            width=18,
            height=2,
            font=("Helvetica", 12, "bold"),
            command=self.start_conversion
        )

        self.convert_button.grid(
            row=0,
            column=0,
            padx=10
        )

        self.clear_button = tk.Button(
            button_frame,
            text="Clear",
            width=18,
            height=2,
            font=("Helvetica", 12),
            command=self.clear_files
        )

        self.clear_button.grid(
            row=0,
            column=1,
            padx=10
        )

    # ========================================================
    # DRAG & DROP
    # ========================================================

    def handle_drop(self, event):

        try:
            files = self.root.tk.splitlist(event.data)
            self.add_files(files)

        except Exception as error:
            print(f"Drop error: {error}")

    # ========================================================
    # ADD FILES
    # ========================================================

    def add_files(self, files):

        added = 0

        for file in files:

            path = Path(file)

            if not path.exists():
                continue

            if not path.is_file():
                continue

            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            path_string = str(path)

            if path_string in self.files:
                continue

            self.files.append(path_string)

            self.listbox.insert(
                tk.END,
                path.name
            )

            added += 1

        if added:

            self.status.config(
                text=f"{len(self.files)} file(s) ready for conversion."
            )

        elif files:

            self.status.config(
                text="No supported files were added."
            )

    # ========================================================
    # CLEAR
    # ========================================================

    def clear_files(self):

        if self.processing:
            return

        self.files.clear()

        self.listbox.delete(
            0,
            tk.END
        )

        self.progress["value"] = 0

        self.status.config(
            text="Drop files into the area above."
        )

    # ========================================================
    # FIND FFMPEG
    # ========================================================

    def find_ffmpeg(self):

        ffmpeg = shutil.which("ffmpeg")

        if ffmpeg:
            return ffmpeg

        paths = [
            "/opt/homebrew/bin/ffmpeg",
            "/usr/local/bin/ffmpeg"
        ]

        for path in paths:

            if os.path.isfile(path):
                return path

        return None

    # ========================================================
    # START CONVERSION
    # ========================================================

    def start_conversion(self):

        if self.processing:
            return

        if not self.files:

            messagebox.showwarning(
                "Audio Converter",
                "Please add at least one file."
            )

            return

        ffmpeg = self.find_ffmpeg()

        if not ffmpeg:

            messagebox.showerror(
                "FFmpeg not found",
                (
                    "FFmpeg is not installed.\n\n"
                    "Install it with:\n\n"
                    "brew install ffmpeg"
                )
            )

            return

        self.processing = True

        self.convert_button.config(
            state=tk.DISABLED
        )

        self.clear_button.config(
            state=tk.DISABLED
        )

        thread = threading.Thread(
            target=self.convert_files,
            args=(ffmpeg,),
            daemon=True
        )

        thread.start()

    # ========================================================
    # CONVERSION
    # ========================================================

    def convert_files(self, ffmpeg):

        total = len(self.files)

        success = 0
        failed = 0

        for index, input_path in enumerate(self.files):

            input_file = Path(input_path)

            self.root.after(
                0,
                self.update_status,
                f"Converting {index + 1}/{total}: {input_file.name}"
            )

            output_file = self.create_output_name(
                input_file
            )

            command = [
                ffmpeg,
                "-hide_banner",
                "-loglevel", "error",
                "-i", str(input_file),
                "-vn",
                "-map", "0:a:0",
                "-c:a", OUTPUT_CODEC,
                "-ar", OUTPUT_SAMPLE_RATE,
                "-ac", OUTPUT_CHANNELS,
                str(output_file)
            ]

            try:

                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                if result.returncode == 0:
                    success += 1
                else:
                    failed += 1
                    print(result.stderr)

            except Exception as error:

                failed += 1
                print(error)

            progress = (
                (index + 1) /
                total *
                100
            )

            self.root.after(
                0,
                self.update_progress,
                progress
            )

        self.root.after(
            0,
            self.conversion_finished,
            success,
            failed
        )

    # ========================================================
    # OUTPUT NAME
    # ========================================================

    def create_output_name(self, input_file):

        output = input_file.with_name(
            f"{input_file.stem}_YouCut.wav"
        )

        counter = 1

        while output.exists():

            output = input_file.with_name(
                f"{input_file.stem}_YouCut_{counter}.wav"
            )

            counter += 1

        return output

    # ========================================================
    # UI UPDATES
    # ========================================================

    def update_status(self, text):

        self.status.config(
            text=text
        )

    def update_progress(self, value):

        self.progress["value"] = value

    # ========================================================
    # FINISHED
    # ========================================================

    def conversion_finished(
        self,
        success,
        failed
    ):

        self.processing = False

        self.convert_button.config(
            state=tk.NORMAL
        )

        self.clear_button.config(
            state=tk.NORMAL
        )

        self.progress["value"] = 100

        self.status.config(
            text=f"Finished — {success} succeeded, {failed} failed."
        )

        if success:

            messagebox.showinfo(
                "Conversion complete",
                (
                    "Conversion completed!\n\n"
                    f"Successful: {success}\n"
                    f"Failed: {failed}\n\n"
                    "The _YouCut.wav files were created "
                    "beside the original files."
                )
            )

        else:

            messagebox.showerror(
                "Conversion failed",
                "None of the files could be converted."
            )


# ============================================================
# MAIN
# ============================================================

def main():

    root = TkinterDnD.Tk()

    YouCutConverter(root)

    root.mainloop()


if __name__ == "__main__":
    main()