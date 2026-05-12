"""
PC detector — adds a cv2.imshow() live preview window to the headless runner.
Use detector.py (parking-vision) for Pi / headless / systemd deployment.

Install:
    uv sync --extra pc        # installs opencv-python (replaces headless)

Run:
    uv run parking-vision-pc                  # interactive lot selection
    uv run parking-vision-pc --lot <uuid>     # non-interactive
    uv run parking-vision-pc --no-display     # headless mode (same as Pi version)
"""
import argparse
import getpass
import os
import sys
import time

import cv2

from gateway.vision.detector import (
    AppConfig,
    HeadlessRunner,
    SupabaseClient,
    load_config,
)


class DisplayRunner(HeadlessRunner):
    """HeadlessRunner + live cv2.imshow() preview for each camera."""

    def __init__(self, *args, display: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.display = display

    def _annotate(self, cam_idx: int, frame, boxes):
        super()._annotate(cam_idx, frame, boxes)
        if self.display:
            cv2.imshow(f"Camera {cam_idx + 1}", frame)

    def run(self):
        self.api.start()
        self._log("Started" + (f" · lot {self.lot_id}" if self.lot_id else " · local config"))
        self._log(f"Dashboard : http://localhost:{self.config.api_port}/")
        self._log(f"Status    : http://localhost:{self.config.api_port}/status")
        if self.display:
            self._log("Press Q or Esc in the preview window to stop")
        else:
            self._log("Press Ctrl+C to stop")
        try:
            while self.running:
                self._tick()
                if self.display:
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord("q"), 27):  # q or Esc
                        break
                else:
                    time.sleep(0.03)
        except KeyboardInterrupt:
            pass
        finally:
            if self.display:
                cv2.destroyAllWindows()
            self._log("Shutting down...")
            self.worker.stop()
            self.api.stop()
            for s in self.streams:
                s.release()


def main():
    parser = argparse.ArgumentParser(description="Smart Parking vision detector (PC)")
    parser.add_argument("--lot",        required=False, help="Lot UUID (prompted if omitted)")
    parser.add_argument("--model",      default="yolov8s.pt",
                        help="YOLO model file (default: yolov8s.pt)")
    parser.add_argument("--no-display", action="store_true",
                        help="Disable cv2 preview window (stream via HTTP only)")
    args = parser.parse_args()

    email    = os.environ.get("GATEWAY_EMAIL")    or input("Gateway email: ").strip()
    password = os.environ.get("GATEWAY_PASSWORD") or getpass.getpass("Gateway password: ")

    db = SupabaseClient(email=email, password=password)

    lot_id       = args.lot
    camera_meta  = []
    slot_regions = []

    if db.available:
        if not lot_id:
            lots = db.list_lots()
            if not lots:
                sys.exit("No parking lots found in database.")
            print("\nAvailable lots:")
            for i, lot in enumerate(lots, 1):
                print(f"  {i}. {lot.get('name', '(unnamed)'):<30}  {lot['id']}")
            while True:
                raw = input("\nSelect lot (number or UUID): ").strip()
                if not raw:
                    continue
                if raw.isdigit():
                    idx = int(raw) - 1
                    if 0 <= idx < len(lots):
                        lot_id = lots[idx]["id"]
                        break
                    print(f"  Enter a number between 1 and {len(lots)}.")
                else:
                    if any(lot["id"] == raw for lot in lots):
                        lot_id = raw
                        break
                    print("  UUID not found in the list above.")

        camera_meta  = db.load_cameras(lot_id)
        slot_regions = db.load_slot_regions(lot_id)
        cfg          = db.load_settings(lot_id) or load_config()
        camera_urls  = [c["url"] for c in camera_meta]
        if not camera_urls:
            sys.exit(f"No cameras found for lot {lot_id} in Supabase.")
        print(f"[Supabase] Lot {lot_id}: "
              f"{len(camera_urls)} camera(s), {len(slot_regions)} slot region(s)")
    else:
        camera_url = os.environ.get("CAMERA_URL")
        if not camera_url:
            sys.exit(
                "Supabase not configured and CAMERA_URL not set.\n"
                "Set SUPABASE_URL + SUPABASE_KEY in .env, or set CAMERA_URL."
            )
        print("[Warning] Supabase not configured — using CAMERA_URL env var.")
        camera_urls = [camera_url]
        cfg         = load_config()

    DisplayRunner(
        camera_urls, cfg, args.model,
        lot_id=lot_id,
        db=db if db.available else None,
        camera_meta=camera_meta,
        slot_regions=slot_regions,
        display=not args.no_display,
    ).run()


if __name__ == "__main__":
    main()
