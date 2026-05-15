"""Red HSV calibration tool — captures frames at multiple printer positions,
lets the user click on the red object, and reports the HSV range needed.

Also runs the current detection pipeline and shows what it sees vs the raw
red mask, so you can diagnose why detection fails.

Usage:
    python scripts/calibrate_red.py [--positions 5] [--camera-url http://127.0.0.1:8766]
                                     [--printer-url http://127.0.0.1:8765]

Press 'q' to quit any preview window.
"""

from __future__ import annotations

import argparse
import sys
import time

import cv2
import numpy as np
import requests

# Current thresholds (mirrored from visual_servo.py)
RED_LOW1 = np.array([0, 50, 50])
RED_HIGH1 = np.array([10, 255, 255])
RED_LOW2 = np.array([165, 50, 50])
RED_HIGH2 = np.array([180, 255, 255])

BLUE_LOW = np.array([95, 80, 50])
BLUE_HIGH = np.array([130, 255, 255])


def grab_frame(cam_url: str) -> np.ndarray | None:
    try:
        r = requests.get(f"{cam_url}/frame", timeout=3)
        if r.status_code != 200:
            return None
        arr = np.frombuffer(r.content, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"[!] Camera error: {e}")
        return None


def jog_printer(printer_url: str, x: float = 0, y: float = 0, feed: int = 3000):
    try:
        requests.post(f"{printer_url}/gcode",
                       json={"command": f"G91\nG1 X{x} Y{y} F{feed}\nG90"},
                       timeout=3)
    except Exception as e:
        print(f"[!] Printer jog error: {e}")


def get_position(printer_url: str) -> tuple[float, float, float]:
    try:
        r = requests.get(f"{printer_url}/state", timeout=3)
        d = r.json()
        return d.get("x", 0), d.get("y", 0), d.get("z", 0)
    except Exception:
        return 0, 0, 0


def analyze_frame(frame: np.ndarray) -> dict:
    """Run red and blue detection, return analysis dict."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Red mask (current thresholds)
    m1 = cv2.inRange(hsv, RED_LOW1, RED_HIGH1)
    m2 = cv2.inRange(hsv, RED_LOW2, RED_HIGH2)
    red_mask = cv2.bitwise_or(m1, m2)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    red_clean = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel)
    red_clean = cv2.morphologyEx(red_clean, cv2.MORPH_CLOSE, kernel)

    # Blue mask
    blue_mask = cv2.inRange(hsv, BLUE_LOW, BLUE_HIGH)
    blue_clean = cv2.morphologyEx(blue_mask, cv2.MORPH_OPEN, kernel)
    blue_clean = cv2.morphologyEx(blue_clean, cv2.MORPH_CLOSE, kernel)

    # Red contours
    red_contours, _ = cv2.findContours(red_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    blue_contours, _ = cv2.findContours(blue_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Sample HSV values from red mask pixels
    red_pixels = hsv[red_clean > 0]

    return {
        "hsv": hsv,
        "red_mask_raw": red_mask,
        "red_mask_clean": red_clean,
        "blue_mask": blue_clean,
        "red_contours": red_contours,
        "blue_contours": blue_contours,
        "red_pixel_count": len(red_pixels),
        "red_hsv_samples": red_pixels,
    }


def click_sample_hsv(frame: np.ndarray, hsv: np.ndarray):
    """Interactive: click on the frame to print HSV values at that pixel."""
    samples = []

    def on_click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            h, s, v = hsv[y, x]
            bgr = frame[y, x]
            print(f"  Click ({x},{y}): HSV=({h},{s},{v})  BGR=({bgr[0]},{bgr[1]},{bgr[2]})")
            samples.append((h, s, v))
            # Draw marker
            cv2.circle(param["display"], (x, y), 5, (0, 255, 0), -1)
            cv2.putText(param["display"], f"H{h} S{s} V{v}", (x + 8, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            cv2.imshow("Click on RED object", param["display"])

    display = frame.copy()
    cv2.namedWindow("Click on RED object", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("Click on RED object", on_click, {"display": display})
    cv2.imshow("Click on RED object", display)

    print("\n  Click on the RED LEGO in the image. Press 'q' when done.")
    while True:
        key = cv2.waitKey(100) & 0xFF
        if key == ord('q'):
            break
    cv2.destroyWindow("Click on RED object")
    return samples


def main():
    parser = argparse.ArgumentParser(description="Red HSV calibration")
    parser.add_argument("--camera-url", default="http://127.0.0.1:8766")
    parser.add_argument("--printer-url", default="http://127.0.0.1:8765")
    parser.add_argument("--positions", type=int, default=5,
                        help="Number of positions to sample (moves printer in a grid)")
    parser.add_argument("--no-move", action="store_true",
                        help="Don't move printer, just analyze current frame")
    args = parser.parse_args()

    all_hsv_samples = []

    if args.no_move:
        positions = [None]
    else:
        # Create a grid of offsets from current position
        offsets = [(0, 0)]
        step = 30  # mm between sample points
        for dx in [-step, 0, step]:
            for dy in [-step, 0, step]:
                if (dx, dy) != (0, 0):
                    offsets.append((dx, dy))
        positions = offsets[:args.positions]

    px, py, pz = get_position(args.printer_url)
    print(f"Current position: X{px} Y{py} Z{pz}")

    for i, pos in enumerate(positions):
        if pos is not None and pos != (0, 0):
            print(f"\n--- Moving to offset ({pos[0]:+.0f}, {pos[1]:+.0f})mm ---")
            jog_printer(args.printer_url, pos[0], pos[1])
            time.sleep(2)  # Wait for move to complete

        frame = grab_frame(args.camera_url)
        if frame is None:
            print("[!] Could not grab frame, skipping")
            continue

        px2, py2, pz2 = get_position(args.printer_url)
        print(f"\nPosition {i + 1}/{len(positions)}: X{px2:.1f} Y{py2:.1f}")

        analysis = analyze_frame(frame)

        # Draw annotations
        annotated = frame.copy()
        for c in analysis["red_contours"]:
            area = cv2.contourArea(c)
            if area > 50:
                cv2.drawContours(annotated, [c], -1, (0, 0, 255), 2)
                M = cv2.moments(c)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    cv2.putText(annotated, f"A={area:.0f}", (cx - 20, cy - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

        for c in analysis["blue_contours"]:
            area = cv2.contourArea(c)
            if area > 50:
                cv2.drawContours(annotated, [c], -1, (255, 100, 0), 2)

        # Show 4-panel view
        h, w = frame.shape[:2]
        red_mask_bgr = cv2.cvtColor(analysis["red_mask_raw"], cv2.COLOR_GRAY2BGR)
        red_clean_bgr = cv2.cvtColor(analysis["red_mask_clean"], cv2.COLOR_GRAY2BGR)
        blue_mask_bgr = cv2.cvtColor(analysis["blue_mask"], cv2.COLOR_GRAY2BGR)

        top = np.hstack([annotated, red_mask_bgr])
        bot = np.hstack([red_clean_bgr, blue_mask_bgr])
        panel = np.vstack([top, bot])

        # Add labels
        cv2.putText(panel, "Annotated", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(panel, "Red Raw Mask", (w + 10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(panel, "Red Clean Mask", (10, h + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(panel, "Blue Mask", (w + 10, h + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Stats
        n_red = analysis["red_pixel_count"]
        n_contours = len([c for c in analysis["red_contours"] if cv2.contourArea(c) > 50])
        print(f"  Red pixels: {n_red}, Red contours (>50px): {n_contours}")

        if n_red > 0:
            samples = analysis["red_hsv_samples"]
            h_vals = samples[:, 0]
            s_vals = samples[:, 1]
            v_vals = samples[:, 2]
            print(f"  HSV ranges in current mask:")
            print(f"    H: {h_vals.min()}-{h_vals.max()}  (mean {h_vals.mean():.1f})")
            print(f"    S: {s_vals.min()}-{s_vals.max()}  (mean {s_vals.mean():.1f})")
            print(f"    V: {v_vals.min()}-{v_vals.max()}  (mean {v_vals.mean():.1f})")
        else:
            print("  *** NO RED DETECTED with current thresholds ***")

        cv2.namedWindow("Calibration", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Calibration", w * 2, h * 2)
        cv2.imshow("Calibration", panel)

        # Interactive HSV sampling
        user_samples = click_sample_hsv(frame, analysis["hsv"])
        all_hsv_samples.extend(user_samples)

        cv2.destroyAllWindows()

    # Return printer to original position
    if not args.no_move and len(positions) > 1:
        print("\nReturning to original position...")
        # Already at offset — go back
        last_off = positions[-1]
        if last_off and last_off != (0, 0):
            jog_printer(args.printer_url, -last_off[0], -last_off[1])

    # Report
    if all_hsv_samples:
        arr = np.array(all_hsv_samples)
        h_min, h_max = arr[:, 0].min(), arr[:, 0].max()
        s_min, s_max = arr[:, 1].min(), arr[:, 1].max()
        v_min, v_max = arr[:, 2].min(), arr[:, 2].max()

        # Add margins
        margin_h = 5
        margin_s = 20
        margin_v = 30

        print(f"\n{'=' * 50}")
        print(f"CLICKED HSV SAMPLES ({len(all_hsv_samples)} points):")
        print(f"  Raw:    H=[{h_min},{h_max}] S=[{s_min},{s_max}] V=[{v_min},{v_max}]")
        print(f"  + margin: H=[{max(0, h_min - margin_h)},{min(180, h_max + margin_h)}]"
              f" S=[{max(0, s_min - margin_s)},{min(255, s_max + margin_s)}]"
              f" V=[{max(0, v_min - margin_v)},{min(255, v_max + margin_v)}]")
        print(f"{'=' * 50}")
    else:
        print("\nNo HSV samples collected (you didn't click anything).")

    print("\nDone.")


if __name__ == "__main__":
    main()
