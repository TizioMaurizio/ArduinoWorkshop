import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import os
import threading
from PIL import Image, ImageTk


class FrameExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MP4 Frame Extractor")
        self.root.geometry("900x650")
        self.root.minsize(700, 500)

        self.video_path = None
        self.total_frames = 0
        self.fps = 0
        self.duration_sec = 0
        self.preview_images = []

        self._build_ui()

    def _build_ui(self):
        # --- Top: file selection ---
        file_frame = ttk.LabelFrame(self.root, text="Video", padding=8)
        file_frame.pack(fill="x", padx=10, pady=(10, 4))

        self.path_var = tk.StringVar(value="No file selected")
        ttk.Label(file_frame, textvariable=self.path_var, anchor="w").pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(file_frame, text="Browse…", command=self._browse).pack(side="right")

        # --- Info row ---
        info_frame = ttk.LabelFrame(self.root, text="Video Info", padding=8)
        info_frame.pack(fill="x", padx=10, pady=4)

        self.info_var = tk.StringVar(value="—")
        ttk.Label(info_frame, textvariable=self.info_var, anchor="w").pack(
            fill="x"
        )

        # --- Parameters ---
        param_frame = ttk.LabelFrame(self.root, text="Parameters", padding=8)
        param_frame.pack(fill="x", padx=10, pady=4)

        ttk.Label(param_frame, text="Number of frames to extract:").grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        self.num_frames_var = tk.IntVar(value=10)
        self.num_spin = ttk.Spinbox(
            param_frame, from_=1, to=200, textvariable=self.num_frames_var, width=8
        )
        self.num_spin.grid(row=0, column=1, sticky="w")

        ttk.Label(param_frame, text="Label font scale:").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=(6, 0)
        )
        self.font_scale_var = tk.DoubleVar(value=1.5)
        ttk.Spinbox(
            param_frame,
            from_=0.5,
            to=5.0,
            increment=0.25,
            textvariable=self.font_scale_var,
            width=8,
        ).grid(row=1, column=1, sticky="w", pady=(6, 0))

        ttk.Label(param_frame, text="Label bg color:").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=(6, 0)
        )
        self.bg_color_var = tk.StringVar(value="red")
        color_combo = ttk.Combobox(
            param_frame,
            textvariable=self.bg_color_var,
            values=["red", "green", "blue", "yellow", "black", "white", "orange", "magenta"],
            state="readonly",
            width=10,
        )
        color_combo.grid(row=2, column=1, sticky="w", pady=(6, 0))

        # --- Buttons ---
        btn_frame = ttk.Frame(self.root, padding=4)
        btn_frame.pack(fill="x", padx=10)

        self.extract_btn = ttk.Button(
            btn_frame, text="Extract & Label Frames", command=self._start_extraction
        )
        self.extract_btn.pack(side="left")

        self.progress = ttk.Progressbar(btn_frame, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(10, 0))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(btn_frame, textvariable=self.status_var).pack(side="right", padx=(10, 0))

        # --- Preview area ---
        preview_frame = ttk.LabelFrame(self.root, text="Preview", padding=4)
        preview_frame.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        self.canvas = tk.Canvas(preview_frame, bg="#2b2b2b")
        v_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.canvas.yview)
        h_scroll = ttk.Scrollbar(preview_frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        h_scroll.pack(side="bottom", fill="x")
        v_scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
        self.inner_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select MP4 video",
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")],
            initialdir=os.path.join(os.path.dirname(__file__), "input"),
        )
        if not path:
            return
        self.video_path = path
        self.path_var.set(os.path.basename(path))
        self._load_video_info()

    def _load_video_info(self):
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            messagebox.showerror("Error", f"Cannot open video:\n{self.video_path}")
            return
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.duration_sec = self.total_frames / self.fps
        cap.release()

        minutes = int(self.duration_sec // 60)
        seconds = self.duration_sec % 60
        self.info_var.set(
            f"Duration: {minutes}m {seconds:.1f}s  |  "
            f"Frames: {self.total_frames}  |  "
            f"FPS: {self.fps:.2f}  |  "
            f"Resolution: {width}x{height}"
        )

    def _start_extraction(self):
        if not self.video_path:
            messagebox.showwarning("No video", "Please select a video file first.")
            return
        self.extract_btn.configure(state="disabled")
        self.status_var.set("Extracting…")
        self.progress["value"] = 0
        threading.Thread(target=self._extract_frames, daemon=True).start()

    def _extract_frames(self):
        n = self.num_frames_var.get()
        font_scale = self.font_scale_var.get()
        bg_name = self.bg_color_var.get()

        color_map = {
            "red": (0, 0, 255),
            "green": (0, 200, 0),
            "blue": (255, 100, 0),
            "yellow": (0, 230, 230),
            "black": (0, 0, 0),
            "white": (255, 255, 255),
            "orange": (0, 140, 255),
            "magenta": (255, 0, 200),
        }
        bg_bgr = color_map.get(bg_name, (0, 0, 255))

        # Choose text color for contrast
        brightness = 0.299 * bg_bgr[2] + 0.587 * bg_bgr[1] + 0.114 * bg_bgr[0]
        text_bgr = (0, 0, 0) if brightness > 128 else (255, 255, 255)

        output_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(output_dir, exist_ok=True)

        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            self.root.after(0, lambda: messagebox.showerror("Error", "Cannot open video."))
            return

        # Evenly-spaced frame indices across the video
        if n >= self.total_frames:
            indices = list(range(self.total_frames))
        else:
            indices = [
                int(round(i * (self.total_frames - 1) / (n - 1))) if n > 1 else 0
                for i in range(n)
            ]

        saved_paths = []
        for count, idx in enumerate(indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue

            label = str(count + 1)
            thickness = max(2, int(font_scale * 2))
            (tw, th), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
            )
            pad = int(font_scale * 8)
            # Draw background rectangle
            cv2.rectangle(
                frame,
                (0, 0),
                (tw + pad * 2, th + pad * 2 + baseline),
                bg_bgr,
                cv2.FILLED,
            )
            # Draw label number
            cv2.putText(
                frame,
                label,
                (pad, th + pad),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                text_bgr,
                thickness,
                cv2.LINE_AA,
            )

            out_name = f"frame_{count + 1:04d}.png"
            out_path = os.path.join(output_dir, out_name)
            cv2.imwrite(out_path, frame)
            saved_paths.append(out_path)

            pct = int((count + 1) / len(indices) * 100)
            self.root.after(0, self._update_progress, pct)

        cap.release()
        self.root.after(0, self._extraction_done, saved_paths)

    def _update_progress(self, pct):
        self.progress["value"] = pct
        self.status_var.set(f"{pct}%")

    def _extraction_done(self, paths):
        self.extract_btn.configure(state="normal")
        self.progress["value"] = 100
        self.status_var.set(f"Done — {len(paths)} frames saved")

        # Show thumbnails in preview
        for widget in self.inner_frame.winfo_children():
            widget.destroy()
        self.preview_images.clear()

        cols = 5
        thumb_w = 160
        for i, path in enumerate(paths):
            img = Image.open(path)
            ratio = thumb_w / img.width
            img_thumb = img.resize(
                (thumb_w, int(img.height * ratio)), Image.LANCZOS
            )
            tk_img = ImageTk.PhotoImage(img_thumb)
            self.preview_images.append(tk_img)

            lbl = ttk.Label(self.inner_frame, image=tk_img)
            lbl.grid(row=i // cols, column=i % cols, padx=3, pady=3)


def main():
    root = tk.Tk()
    FrameExtractorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
