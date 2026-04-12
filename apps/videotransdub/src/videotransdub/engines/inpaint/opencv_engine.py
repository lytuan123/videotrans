from __future__ import annotations

import logging
from pathlib import Path

from .base import BaseInpaintEngine

logger = logging.getLogger(__name__)


class OpenCVInpaintEngine(BaseInpaintEngine):
    """Remove hardcoded subtitles using OpenCV text detection + inpainting.

    Strategy:
    1. Scan bottom ~25% of each frame for high-contrast text regions (EAST or morphology).
    2. Build a binary mask of detected text.
    3. Use cv2.inpaint (Telea or Navier-Stokes) to fill masked regions.

    This is a best-effort approach — works well on solid-background subtitles,
    less effective on complex scenes. For production use, consider AI-based
    inpainting (e.g., video-inpainting models).
    """

    def __init__(self, region_ratio: float = 0.25, inpaint_radius: int = 5) -> None:
        self.region_ratio = region_ratio
        self.inpaint_radius = inpaint_radius

    def clean(self, video_path: Path, output_path: Path) -> Path:
        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise RuntimeError(
                "opencv-python is not installed. "
                "Run: pip install opencv-python-headless"
            ) from exc

        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
        if not writer.isOpened():
            raise RuntimeError(f"Cannot create output video: {output_path}")

        sub_top = int(height * (1 - self.region_ratio))
        processed = 0

        logger.info(
            "OpenCV inpaint: %dx%d @ %.1ffps, %d frames, sub region y>%d",
            width, height, fps, total_frames, sub_top,
        )

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                roi = frame[sub_top:height, 0:width]
                mask = self._detect_text_mask(roi, cv2, np)

                if mask.any():
                    full_mask = np.zeros((height, width), dtype=np.uint8)
                    full_mask[sub_top:height, 0:width] = mask
                    frame = cv2.inpaint(
                        frame, full_mask, self.inpaint_radius, cv2.INPAINT_TELEA
                    )

                writer.write(frame)
                processed += 1

                if processed % 500 == 0:
                    logger.info("  Inpaint progress: %d/%d frames", processed, total_frames)
        finally:
            cap.release()
            writer.release()

        logger.info("Inpaint complete: %d frames -> %s", processed, output_path)
        return output_path

    @staticmethod
    def _detect_text_mask(roi, cv2, np) -> "np.ndarray":
        """Detect text-like regions in the subtitle area using morphological ops."""
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # Look for bright text on dark background or dark text on bright background
        _, thresh_light = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        _, thresh_dark = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)
        combined = cv2.bitwise_or(thresh_light, thresh_dark)

        # Morphological operations to connect text characters into blocks
        kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 5))
        closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel_close)

        kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 7))
        dilated = cv2.dilate(closed, kernel_dilate, iterations=1)

        # Filter contours by aspect ratio (text blocks are wide and short)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        mask = np.zeros(roi.shape[:2], dtype=np.uint8)
        roi_h, roi_w = roi.shape[:2]

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            aspect = w / max(h, 1)
            # Text blocks: wide aspect ratio, reasonable area
            if aspect > 2.0 and area > (roi_w * roi_h * 0.005) and w > roi_w * 0.1:
                # Expand the bounding box slightly
                pad_x, pad_y = 5, 3
                x1 = max(0, x - pad_x)
                y1 = max(0, y - pad_y)
                x2 = min(roi_w, x + w + pad_x)
                y2 = min(roi_h, y + h + pad_y)
                mask[y1:y2, x1:x2] = 255

        return mask
