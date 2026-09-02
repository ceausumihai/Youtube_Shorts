#!/usr/bin/env python3
"""Auto Shorts 9:16 macOS GUI.

Drag a 16:9 source video into the app, choose Start Time and Duration,
and use the existing auto_shorts.py pipeline to create a 9:16 MP4 beside it.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import threading
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tkinter import messagebox, ttk

from tkinterdnd2 import DND_FILES, TkinterDnD
import tkinter as tk

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}
ASPECT_TOLERANCE = 0.02

# Make the bundled/source copy of auto_shorts.py importable.
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import auto_shorts  # noqa: E402


class AutoShortsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Auto Shorts 9:16")
        self.root.geometry("920x820")
        self.root.minsize(820, 720)
        self.root.resizable(True, True)

        self.files = []
        self.processing = False
        self.successful_outputs = []
        self._current_process_label = ""

        self.start_var = tk.StringVar(value="0")
        self.duration_var = tk.StringVar(value="45")
        self.status_var = tk.StringVar(value="Drop a 16:9 video above to begin.")
        self.log_path = None

        self._configure_theme()
        self._build_ui()
        self._bind_window_drop()

    def _configure_theme(self):
        try:
            self.root.tk.call("tk", "scaling", 1.2)
        except Exception:
            pass

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Helvetica", 26, "bold"))
        style.configure("Subtitle.TLabel", font=("Helvetica", 12))
        style.configure("Section.TLabel", font=("Helvetica", 12, "bold"))

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=(28, 22))
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(4, weight=1)
        main.rowconfigure(7, weight=2)

        ttk.Label(main, text="🎬 Auto Shorts 9:16", style="Title.TLabel").grid(
            row=0, column=0, pady=(0, 4)
        )
        ttk.Label(
            main,
            text="Extract a segment from a 16:9 video and convert it to 9:16",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, pady=(0, 18))

        # Drop zone
        drop = tk.Frame(main, height=145, relief="groove", borderwidth=2, bg="#f3f3f3")
        drop.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        drop.grid_propagate(False)
        self.drop_label = tk.Label(
            drop,
            text="DROP 16:9 VIDEO FILES HERE\n\nMP4 • MOV • M4V • MKV • WEBM",
            font=("Helvetica", 16),
            bg="#f3f3f3",
            justify="center",
        )
        self.drop_label.pack(fill="both", expand=True)
        for w in (drop, self.drop_label):
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>", self.handle_drop)
            w.dnd_bind("<<DragEnter>>", self._drag_enter)
            w.dnd_bind("<<DragLeave>>", self._drag_leave)

        # Settings card
        settings = ttk.LabelFrame(main, text="Short settings", padding=(14, 10))
        settings.grid(row=3, column=0, sticky="ew", pady=(0, 14))
        settings.columnconfigure(4, weight=1)

        ttk.Label(settings, text="Start time", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(settings, textvariable=self.start_var, width=12).grid(row=1, column=0, sticky="w", pady=(5, 0))
        ttk.Label(settings, text="seconds", foreground="#666").grid(row=2, column=0, sticky="w")

        ttk.Label(settings, text="Short duration", style="Section.TLabel").grid(row=0, column=1, sticky="w", padx=(22, 0))
        ttk.Entry(settings, textvariable=self.duration_var, width=12).grid(row=1, column=1, sticky="w", padx=(22, 0), pady=(5, 0))
        ttk.Label(settings, text="seconds", foreground="#666").grid(row=2, column=1, sticky="w", padx=(22, 0))

        ttk.Label(settings, text="Output", style="Section.TLabel").grid(row=0, column=2, sticky="w", padx=(35, 0))
        ttk.Label(settings, text="OriginalName_9_16.mp4").grid(row=1, column=2, sticky="w", padx=(35, 0), pady=(5, 0))
        ttk.Label(settings, text="Saved next to the source video", foreground="#666").grid(row=2, column=2, sticky="w", padx=(35, 0))

        self.duration_hint = ttk.Label(settings, text="", foreground="#666")
        self.duration_hint.grid(row=1, column=4, sticky="e")

        # Files
        files_frame = ttk.LabelFrame(main, text="Videos", padding=8)
        files_frame.grid(row=4, column=0, sticky="nsew")
        files_frame.columnconfigure(0, weight=1)
        files_frame.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(files_frame, font=("Helvetica", 11), selectmode=tk.EXTENDED)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(files_frame, orient="vertical", command=self.listbox.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.listbox.config(yscrollcommand=sb.set)

        # Log panel
        log_frame = ttk.LabelFrame(main, text="Conversion log", padding=8)
        log_frame.grid(row=5, column=0, sticky="ew", pady=(14, 0))
        log_frame.columnconfigure(0, weight=1)
        self.log_text = tk.Text(
            log_frame,
            height=11,
            wrap="word",
            font=("Menlo", 10),
            state="disabled",
        )
        self.log_text.grid(row=0, column=0, sticky="ew")
        log_sb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_sb.grid(row=0, column=1, sticky="ns")
        self.log_text.config(yscrollcommand=log_sb.set)

        log_buttons = ttk.Frame(log_frame)
        log_buttons.grid(row=1, column=0, sticky="w", pady=(7, 0))
        self.open_log_btn = ttk.Button(log_buttons, text="Open log file", command=self.open_log_file, state="disabled")
        self.open_log_btn.grid(row=0, column=0, padx=(0, 8))
        ttk.Button(log_buttons, text="Clear log", command=self.clear_log).grid(row=0, column=1)

        # Progress + status
        self.progress = ttk.Progressbar(main, mode="determinate", maximum=100)
        self.progress.grid(row=6, column=0, sticky="ew", pady=(14, 5))
        ttk.Label(main, textvariable=self.status_var).grid(row=6, column=0, sticky="w", pady=(14, 5))

        # Bottom buttons
        buttons = ttk.Frame(main)
        buttons.grid(row=8, column=0, pady=(13, 0))
        self.convert_btn = tk.Button(
            buttons,
            text="Create 9:16",
            width=18,
            height=2,
            font=("Helvetica", 12, "bold"),
            command=self.start_conversion,
        )
        self.convert_btn.grid(row=0, column=0, padx=8)
        self.clear_btn = tk.Button(
            buttons,
            text="Clear",
            width=18,
            height=2,
            font=("Helvetica", 12),
            command=self.clear_files,
        )
        self.clear_btn.grid(row=0, column=1, padx=8)
        self.open_output_btn = tk.Button(
            buttons,
            text="Open Output Folder",
            width=18,
            height=2,
            font=("Helvetica", 12),
            command=self.open_output_folder,
            state=tk.DISABLED,
        )
        self.open_output_btn.grid(row=0, column=2, padx=8)

    def _bind_window_drop(self):
        # Register the root too, so dropping anywhere in the app works.
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind("<<Drop>>", self.handle_drop)
        self.root.dnd_bind("<<DragEnter>>", self._drag_enter)
        self.root.dnd_bind("<<DragLeave>>", self._drag_leave)

    def _drag_enter(self, _event):
        try:
            self.drop_label.config(bg="#e8f1ff")
        except tk.TclError:
            pass

    def _drag_leave(self, _event):
        try:
            self.drop_label.config(bg="#f3f3f3")
        except tk.TclError:
            pass

    def handle_drop(self, event):
        self._drag_leave(event)
        self.add_files(self.root.tk.splitlist(event.data))

    def add_files(self, files):
        added = 0
        skipped = []
        for value in files:
            p = Path(value)
            if not p.is_file() or p.suffix.lower() not in SUPPORTED_EXTENSIONS:
                skipped.append(p.name)
                continue
            if str(p) in self.files:
                continue
            self.files.append(str(p))
            self.listbox.insert(tk.END, p.name)
            added += 1

        if added:
            self.status_var.set(f"{len(self.files)} video(s) ready.")
            self._append_log(f"Added {added} video(s).")
        elif skipped:
            self.status_var.set("No supported video files were added.")
            self._append_log("Skipped unsupported items: " + ", ".join(skipped))

    def clear_files(self):
        if self.processing:
            return
        self.files.clear()
        self.listbox.delete(0, tk.END)
        self.progress["value"] = 0
        self.successful_outputs.clear()
        self.open_output_btn.config(state=tk.DISABLED)
        self.status_var.set("Drop a 16:9 video above to begin.")

    @staticmethod
    def _parse_number(value, field):
        try:
            n = float(value)
        except ValueError as exc:
            raise ValueError(f"{field} must be a number.") from exc
        if n < 0:
            raise ValueError(f"{field} must be 0 or greater.")
        return n

    def validate_settings(self):
        start = self._parse_number(self.start_var.get().strip(), "Start time")
        duration = self._parse_number(self.duration_var.get().strip(), "Short duration")
        if duration <= 0:
            raise ValueError("Short duration must be greater than 0 seconds.")
        return start, duration

    @staticmethod
    def _tool_path(name):
        found = shutil.which(name)
        if found:
            return found
        candidates = [f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}"]
        for candidate in candidates:
            if Path(candidate).is_file():
                return candidate
        return None

    def _ffmpeg_path(self):
        return self._tool_path("ffmpeg")

    def _ffprobe_path(self):
        return self._tool_path("ffprobe")

    def start_conversion(self):
        if self.processing:
            return
        if not self.files:
            messagebox.showwarning("Auto Shorts 9:16", "Please add at least one video file.")
            return
        try:
            start, duration = self.validate_settings()
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return
        if not self._ffmpeg_path() or not self._ffprobe_path():
            messagebox.showerror(
                "FFmpeg not found",
                "FFmpeg and ffprobe are required.\n\nInstall them with:\n\nbrew install ffmpeg",
            )
            return

        self.processing = True
        self.successful_outputs.clear()
        self.progress["value"] = 0
        self.convert_btn.config(state=tk.DISABLED)
        self.clear_btn.config(state=tk.DISABLED)
        self.open_output_btn.config(state=tk.DISABLED)
        self._append_log("\n=== New conversion job ===")
        self._append_log(f"Start time: {start:g}s | Duration: {duration:g}s")
        threading.Thread(target=self._worker, args=(start, duration), daemon=True).start()

    def _probe_video(self, video_path):
        probe = self._ffprobe_path()
        cmd = [
            probe,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration:format=duration",
            "-of", "json",
            str(video_path),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            detail = r.stderr.strip() or "Unable to read video information."
            raise RuntimeError(detail)
        data = json.loads(r.stdout)
        if not data.get("streams"):
            raise ValueError("No video stream was found.")
        stream = data["streams"][0]
        width = int(stream["width"])
        height = int(stream["height"])
        duration_raw = stream.get("duration") or data.get("format", {}).get("duration")
        duration = float(duration_raw) if duration_raw else None
        return width, height, duration

    def _output_path(self, input_path):
        output = input_path.with_name(f"{input_path.stem}_9_16.mp4")
        counter = 1
        while output.exists():
            output = input_path.with_name(f"{input_path.stem}_9_16_{counter}.mp4")
            counter += 1
        return output

    def _worker(self, start, duration):
        total = len(self.files)
        success = 0
        failed = 0
        ffmpeg = self._ffmpeg_path()
        old_ffmpeg_path = os.environ.get("FFMPEG_PATH")
        os.environ["FFMPEG_PATH"] = ffmpeg
        auto_shorts.FFMPEG_BIN = ffmpeg

        try:
            for idx, input_value in enumerate(self.files, 1):
                input_path = Path(input_value)
                self._ui_log(f"\n[{idx}/{total}] {input_path.name}")
                try:
                    width, height, source_duration = self._probe_video(input_path)
                    ratio = width / height
                    self._ui_log(f"Source: {width}x{height} ({ratio:.4f}:1)")
                    if abs(ratio - (16 / 9)) > ASPECT_TOLERANCE:
                        raise ValueError(
                            f"Source is {width}×{height} ({ratio:.4f}:1), not approximately 16:9."
                        )
                    if source_duration is not None:
                        self._ui_log(f"Source duration: {source_duration:.2f}s")
                        if start >= source_duration:
                            raise ValueError(
                                f"Start time {start:g}s is beyond the video duration ({source_duration:.2f}s)."
                            )
                        if start + duration > source_duration + 0.05:
                            raise ValueError(
                                f"Requested end time {start + duration:g}s exceeds the video duration ({source_duration:.2f}s)."
                            )

                    clip_data = [{
                        "start": start,
                        "end": start + duration,
                        "title": input_path.stem,
                        "reason": "Selected in GUI",
                    }]

                    # Keep the clips.json idea from auto_shorts.py while avoiding a
                    # sidecar file next to the user's video.
                    temp_dir = Path(os.path.expanduser("~/Library/Caches/AutoShorts9x16"))
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    clips_json = temp_dir / f"clips_{threading.get_ident()}_{idx}.json"
                    clips_json.write_text(json.dumps(clip_data, indent=2), encoding="utf-8")
                    self._ui_log(f"Generated clips.json: {clips_json}")

                    clips = auto_shorts.load_clips_from_json(clips_json)
                    output_path = self._output_path(input_path)
                    output_dir = input_path.parent
                    self._ui_log(f"Output: {output_path}")

                    buffer = io.StringIO()
                    with redirect_stdout(buffer), redirect_stderr(buffer):
                        final_path = auto_shorts.cut_and_format_clip(
                            input_path,
                            clips[0],
                            output_dir,
                            output_filename=output_path.name,
                        )
                    captured = buffer.getvalue().strip()
                    if captured:
                        self._ui_log(captured)
                    clips_json.unlink(missing_ok=True)

                    success += 1
                    self.successful_outputs.append(Path(final_path))
                    self._ui_log(f"✓ Created: {final_path}")
                    self._ui_status(f"Created {idx}/{total}: {Path(final_path).name}")
                except Exception as exc:
                    failed += 1
                    self._ui_log(f"✗ ERROR: {exc}")
                    self._ui_log(traceback.format_exc())
                    self._ui_status(f"Failed {idx}/{total}: {input_path.name}")
                finally:
                    self.root.after(0, self._set_progress, idx / total * 100)
        finally:
            if old_ffmpeg_path is None:
                os.environ.pop("FFMPEG_PATH", None)
            else:
                os.environ["FFMPEG_PATH"] = old_ffmpeg_path
            self.root.after(0, self._finished, success, failed)

    def _set_progress(self, value):
        self.progress["value"] = value

    def _ui_log(self, text):
        self.root.after(0, self._append_log, text)

    def _ui_status(self, text):
        self.root.after(0, self.status_var.set, text)

    def _append_log(self, text):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, text.rstrip() + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")
        self.log_path = None
        self.open_log_btn.config(state="disabled")

    def _finished(self, success, failed):
        self.processing = False
        self.convert_btn.config(state=tk.NORMAL)
        self.clear_btn.config(state=tk.NORMAL)
        self.progress["value"] = 100 if success else 0
        self.open_output_btn.config(state=tk.NORMAL if success else tk.DISABLED)
        self.status_var.set(f"Finished — {success} succeeded, {failed} failed.")

        # Persist the visible log so the user can inspect it without Terminal.
        try:
            if self.files:
                log_dir = Path(self.files[0]).parent
                self.log_path = log_dir / ".auto_shorts_9_16.log"
                content = self.log_text.get("1.0", tk.END)
                self.log_path.write_text(content, encoding="utf-8")
                self.open_log_btn.config(state=tk.NORMAL)
        except Exception:
            pass

        if success and failed == 0:
            messagebox.showinfo(
                "Conversion complete",
                f"Created {success} 9:16 video(s).\n\nOutput files are beside the source videos with _9_16 in the name.",
            )
        elif success:
            messagebox.showwarning(
                "Conversion completed with errors",
                f"Created {success} video(s).\nFailed: {failed}.\n\nSee the Conversion log in the app for details.",
            )
        else:
            messagebox.showerror(
                "Conversion failed",
                "No videos were converted.\n\nSee the Conversion log in this window for the exact error.",
            )

    def open_log_file(self):
        if not self.log_path:
            return
        try:
            subprocess.run(["open", str(self.log_path)], check=False)
        except Exception as exc:
            messagebox.showerror("Unable to open log", str(exc))

    def open_output_folder(self):
        outputs = self.successful_outputs
        if not outputs:
            return
        folder = outputs[0].parent
        try:
            subprocess.run(["open", str(folder)], check=False)
        except Exception as exc:
            messagebox.showerror("Unable to open folder", str(exc))


def main():
    root = TkinterDnD.Tk()
    AutoShortsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
