import argparse
import signal
import sys
import cv2
import threading
import time
import dataclasses
from collections import deque
from collections.abc import Callable
from datetime import datetime
import json
import os
import queue
import numpy as np

from dotenv import load_dotenv
load_dotenv()

# opencv-python-headless removes GUI functions; stub them so ultralytics can import cleanly
if not hasattr(cv2, "imshow"):
    cv2.imshow = lambda *_: None
    cv2.waitKey = lambda *_: -1
    cv2.destroyAllWindows = lambda *_: None

from ultralytics import YOLO


# =========================================================
# CONSTANTS
# =========================================================
VEHICLE_CLASSES = [2, 3, 5, 7]
SLOT_FILE       = "slots.json"
CONFIG_FILE     = "config.json"
INFER_W         = 800
INFER_H         = 450


# =========================================================
# CONFIG
# =========================================================
@dataclasses.dataclass
class AppConfig:
    confidence:           float = 0.50
    debounce_frames:      int   = 4    # votes needed in window to confirm occupied
    debounce_frames_free: int   = 4    # "free" votes needed in window to confirm free
    window_size:          int   = 8    # rolling window length for both transitions
    overlap_threshold:    float = 0.55 # min fraction of slot polygon covered to count as a hit
    min_duration:         int   = 5
    clahe_clip_limit:     float = 2.0  # CLAHE clip limit; raise for heavy shadow, 0.0 to disable
    api_host:             str   = "0.0.0.0"
    api_port:             int   = 8000


def load_config() -> AppConfig:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            data = json.load(f)
        valid = {k: v for k, v in data.items() if k in AppConfig.__dataclass_fields__}
        return AppConfig(**valid)
    return AppConfig()


# =========================================================
# SHARED STATE  (detection loop ↔ REST API)
# =========================================================
class SharedState:
    def __init__(self):
        self._lock          = threading.Lock()
        self._slots: dict   = {}
        self._events: deque = deque(maxlen=200)
        self._frames: dict  = {}

    def update_frame(self, cam_idx: int, jpeg: bytes):
        with self._lock:
            self._frames[cam_idx] = jpeg

    def get_frame(self, cam_idx: int) -> bytes | None:
        with self._lock:
            return self._frames.get(cam_idx)

    def update_slot(self, cam_idx, slot_idx, occupied, enter_time):
        with self._lock:
            self._slots[(cam_idx, slot_idx)] = {
                "cam": cam_idx + 1, "slot": slot_idx + 1,
                "occupied": occupied,
                "since": enter_time.isoformat() if enter_time else None,
            }

    def add_event(self, event_type, cam_i, slot_i, duration=None):
        with self._lock:
            self._events.appendleft({
                "type": event_type, "cam": cam_i + 1, "slot": slot_i + 1,
                "timestamp": datetime.now().isoformat(), "duration": duration,
            })

    def get_status(self):
        with self._lock:
            slots = list(self._slots.values())
        occupied = sum(1 for s in slots if s["occupied"])
        return {"total": len(slots), "occupied": occupied,
                "free": len(slots) - occupied, "slots": slots}

    def get_events(self, limit=50):
        with self._lock:
            return list(self._events)[:limit]


# =========================================================
# SUPABASE CLIENT
# =========================================================
class SupabaseClient:
    """Thin wrapper around supabase-py.

    State writes always go through report_slot_state() RPC, never direct
    UPDATE, to keep slot_events + parking_sessions in sync atomically.
    """

    def __init__(self, email: str | None = None, password: str | None = None):
        url           = os.environ.get("SUPABASE_URL", "").strip()
        key           = os.environ.get("SUPABASE_KEY", "").strip()
        self._email    = email or os.environ.get("GATEWAY_EMAIL", "").strip()
        self._password = password or os.environ.get("GATEWAY_PASSWORD", "").strip()
        self._c       = None
        if url and key:
            try:
                from supabase import create_client
                self._c = create_client(url, key)
                if self._email and self._password:
                    self._c.auth.sign_in_with_password(
                        {"email": self._email, "password": self._password}
                    )
                    print("[Supabase] Authenticated as gateway user", flush=True)
            except ImportError:
                print("[Supabase] supabase-py not installed — run: pip install supabase", flush=True)
            except Exception as e:
                print(f"[Supabase] Connection failed: {e}", flush=True)

    def reauthenticate(self) -> None:
        if not self._c:
            return
        try:
            self._c.auth.refresh_session()
            print("[Supabase] Session refreshed", flush=True)
        except Exception:
            if self._email and self._password:
                try:
                    self._c.auth.sign_in_with_password(
                        {"email": self._email, "password": self._password}
                    )
                    print("[Supabase] Re-authenticated", flush=True)
                except Exception as e:
                    print(f"[Supabase] Re-auth failed: {e}", flush=True)

    @property
    def available(self) -> bool:
        return self._c is not None

    def _q(self, table: str, *, select: str = "*",
           filters: dict | None = None, null_cols: list[str] | None = None) -> list:
        try:
            req = self._c.table(table).select(select)
            for col, val in (filters or {}).items():
                req = req.eq(col, val)
            for col in (null_cols or []):
                req = req.is_(col, "null")
            return req.execute().data or []
        except Exception as e:
            print(f"[Supabase] SELECT {table} failed: {e}", flush=True)
            return []

    def list_lots(self) -> list[dict]:
        return self._q("lots", select="id,name,address", null_cols=["deleted_at"])

    def load_cameras(self, lot_id: str) -> list[dict]:
        rows = self._q("devices", filters={"lot_id": lot_id, "kind": "camera"})
        for r in rows:
            meta = r.get("metadata") or {}
            r["url"]  = meta.get("url", "")
            r["name"] = meta.get("name", r.get("mac_or_serial", ""))
        return sorted(rows, key=lambda r: (r.get("metadata") or {}).get("position", 0))

    def list_slots(self, lot_id: str) -> list[dict]:
        return self._q("slots", select="id,label,current_state",
                       filters={"lot_id": lot_id}, null_cols=["deleted_at"])

    def load_slot_regions_for_camera(self, lot_id: str, device_id: str) -> list[dict]:
        regions = self._q("camera_slot_regions",
                          filters={"lot_id": lot_id, "device_id": device_id})
        if not regions:
            return []
        slot_ids = [r["slot_id"] for r in regions]
        try:
            slot_rows = (
                self._c.table("slots").select("id,label")
                .in_("id", slot_ids).execute().data or []
            )
        except Exception as e:
            print(f"[Supabase] SELECT slots for camera regions failed: {e}", flush=True)
            slot_rows = []
        label_map = {s["id"]: s["label"] for s in slot_rows}
        for r in regions:
            r["slot_label"] = label_map.get(r["slot_id"], r["slot_id"][:8])
        return regions

    def save_slot_region(self, lot_id: str, device_id: str,
                         slot_id: str, polygon: list) -> None:
        try:
            self._c.table("camera_slot_regions").delete() \
                .eq("device_id", device_id).eq("slot_id", slot_id).execute()
            self._c.table("camera_slot_regions").insert({
                "lot_id": lot_id, "device_id": device_id,
                "slot_id": slot_id, "polygon": polygon,
            }).execute()
        except Exception as e:
            print(f"[Supabase] save_slot_region failed: {e}", flush=True)

    def delete_slot_region(self, lot_id: str, device_id: str, slot_id: str) -> None:
        try:
            self._c.table("camera_slot_regions").delete() \
                .eq("device_id", device_id).eq("slot_id", slot_id).execute()
        except Exception as e:
            print(f"[Supabase] delete_slot_region failed: {e}", flush=True)

    def load_slot_regions(self, lot_id: str) -> list[dict]:
        regions = self._q("camera_slot_regions", filters={"lot_id": lot_id})
        if not regions:
            return []
        slot_ids = list({r["slot_id"] for r in regions})
        try:
            slot_rows = (
                self._c.table("slots")
                .select("id,label")
                .in_("id", slot_ids)
                .is_("deleted_at", "null")
                .execute()
                .data or []
            )
        except Exception as e:
            print(f"[Supabase] SELECT slots for regions failed: {e}", flush=True)
            slot_rows = []
        label_map = {s["id"]: s["label"] for s in slot_rows}
        for r in regions:
            r["slot_label"] = label_map.get(r["slot_id"], r["slot_id"][:8])
        return regions

    def load_settings(self, lot_id: str) -> "AppConfig | None":
        rows = self._q("lot_settings", filters={"lot_id": lot_id})
        if not rows:
            return None
        r = rows[0]
        return AppConfig(
            confidence=float(r.get("confidence", 0.50)),
            debounce_frames=int(r.get("debounce_frames", 4)),
            debounce_frames_free=int(r.get("debounce_frames_free", 4)),
            window_size=int(r.get("window_size", 8)),
            overlap_threshold=float(r.get("overlap_threshold", 0.55)),
            min_duration=int(r.get("min_duration", 5)),
            clahe_clip_limit=float(r.get("clahe_clip_limit", 2.0)),
            api_host=r.get("api_host", "0.0.0.0"),
            api_port=int(r.get("api_port", 8000)),
        )

    def report_slot_state(self, slot_id: str, new_state: str,
                          confidence: float | None = None,
                          metadata: dict | None = None):
        try:
            self._c.rpc("report_slot_state", {
                "p_slot_id":      slot_id,
                "p_new_state":    new_state,
                "p_source":       "camera",
                "p_confidence":   confidence,
                "p_plate_number": None,
                "p_metadata":     metadata or {},
            }).execute()
        except Exception as e:
            print(f"[Supabase] report_slot_state failed: {e}", flush=True)


# =========================================================
# SUPABASE LOGGER  (fire-and-forget background thread)
# =========================================================
class SupabaseLogger:
    """Queues report_slot_state RPC calls so the detection loop never blocks."""

    def __init__(self, client: SupabaseClient):
        self._db = client
        self._q  = queue.SimpleQueue()
        t = threading.Thread(target=self._run, daemon=True, name="SupabaseLogger")
        t.start()

    def report_state(self, slot_id: str, new_state: str,
                     confidence: float | None = None, metadata: dict | None = None):
        self._q.put((slot_id, new_state, confidence, metadata))

    def _run(self):
        while True:
            slot_id, new_state, confidence, metadata = self._q.get()
            if not self._db.available:
                continue
            try:
                self._db.report_slot_state(slot_id, new_state, confidence, metadata)
            except Exception as e:
                err = str(e).lower()
                if "jwt" in err or "expired" in err or "401" in err or "invalid claim" in err:
                    print("[SupabaseLogger] JWT expired — refreshing session", flush=True)
                    self._db.reauthenticate()
                    try:
                        self._db.report_slot_state(slot_id, new_state, confidence, metadata)
                    except Exception as e2:
                        print(f"[SupabaseLogger] Retry failed: {e2}", flush=True)
                else:
                    print(f"[SupabaseLogger] {e}", flush=True)


# =========================================================
# REST API
# =========================================================
class ParkingAPI:
    def __init__(self, state: SharedState, host: str, port: int, num_cameras: int = 1,
                 db: "SupabaseClient | None" = None, lot_id: str | None = None,
                 camera_meta: "list[dict] | None" = None,
                 on_regions_changed: "Callable[[], None] | None" = None):
        self.state               = state
        self.host                = host
        self.port                = port
        self.num_cameras         = num_cameras
        self.db                  = db
        self.lot_id              = lot_id
        self.camera_meta         = camera_meta or []
        self.on_regions_changed  = on_regions_changed
        self._server             = None
        self._thread             = None

    def start(self):
        import asyncio
        import uvicorn
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, StreamingResponse
        from fastapi.middleware.cors import CORSMiddleware

        from pydantic import BaseModel as _BaseModel

        class RegionIn(_BaseModel):
            slot_id: str
            polygon: list[list[int]]

        app         = FastAPI(title="Smart Parking API", version="1.0")
        state       = self.state
        num_cameras = self.num_cameras
        db          = self.db
        lot_id      = self.lot_id
        camera_meta = self.camera_meta
        app.add_middleware(CORSMiddleware, allow_origins=["*"],
                           allow_methods=["*"], allow_headers=["*"])

        @app.get("/health")
        def health():
            return {"status": "ok", "timestamp": datetime.now().isoformat()}

        @app.get("/status")
        def status():
            return state.get_status()

        @app.get("/events")
        def events(limit: int = 50):
            return state.get_events(limit)

        @app.get("/stream/{cam_idx}")
        async def stream(cam_idx: int):
            async def generate():
                try:
                    while True:
                        jpeg = state.get_frame(cam_idx)
                        if jpeg:
                            yield (
                                b"--frame\r\n"
                                b"Content-Type: image/jpeg\r\n\r\n"
                                + jpeg + b"\r\n"
                            )
                        await asyncio.sleep(0.033)
                except asyncio.CancelledError:
                    pass
            return StreamingResponse(generate(),
                                     media_type="multipart/x-mixed-replace; boundary=frame")

        @app.get("/cameras")
        def list_cameras():
            return [
                {
                    "device_id": c["id"],
                    "name": c.get("name", f"Camera {i + 1}"),
                    "index": i,
                    "frame_width": INFER_W,
                    "frame_height": INFER_H,
                }
                for i, c in enumerate(camera_meta)
            ]

        @app.get("/cameras/{device_id}/stream")
        async def stream_by_device(device_id: str):
            from fastapi import HTTPException
            idx = next((i for i, c in enumerate(camera_meta) if c["id"] == device_id), None)
            if idx is None:
                raise HTTPException(status_code=404, detail="Camera not found")
            async def _gen():
                try:
                    while True:
                        jpeg = state.get_frame(idx)
                        if jpeg:
                            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                        await asyncio.sleep(0.033)
                except asyncio.CancelledError:
                    pass
            return StreamingResponse(_gen(),
                                     media_type="multipart/x-mixed-replace; boundary=frame")

        @app.get("/slots")
        def list_slots():
            if not db or not db.available or not lot_id:
                return []
            return db.list_slots(lot_id)

        @app.get("/cameras/{device_id}/regions")
        def get_regions(device_id: str):
            if not db or not db.available or not lot_id:
                return []
            return db.load_slot_regions_for_camera(lot_id, device_id)

        on_regions_changed = self.on_regions_changed

        @app.post("/cameras/{device_id}/regions", status_code=201)
        def save_region(device_id: str, body: RegionIn):
            if not db or not db.available or not lot_id:
                return {"ok": False, "error": "Supabase not configured"}
            db.save_slot_region(lot_id, device_id, body.slot_id, body.polygon)
            if on_regions_changed:
                on_regions_changed()
            return {"ok": True}

        @app.delete("/cameras/{device_id}/regions/{slot_id}")
        def delete_region(device_id: str, slot_id: str):
            if not db or not db.available or not lot_id:
                return {"ok": False}
            db.delete_slot_region(lot_id, device_id, slot_id)
            if on_regions_changed:
                on_regions_changed()
            return {"ok": True}

        @app.get("/", response_class=HTMLResponse)
        def dashboard():
            feeds = "".join(
                f'<div class="cam"><p>Camera {i + 1}</p><img src="/stream/{i}"></div>'
                for i in range(num_cameras)
            )
            return f"""<!DOCTYPE html>
<html><head><title>Smart Parking</title><meta charset="utf-8">
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#09090b;color:#fafafa;font-family:monospace;padding:24px}}
  h1{{color:#4ade80;font-size:16px;margin-bottom:4px}}
  .sub{{color:#71717a;font-size:12px;margin-bottom:20px}}
  .grid{{display:flex;gap:16px;flex-wrap:wrap}}
  .cam{{flex:1;min-width:320px}}
  .cam p{{color:#71717a;font-size:11px;margin-bottom:6px}}
  .cam img{{width:100%;border-radius:8px;border:1px solid #27272a}}
</style></head><body>
<h1>Smart Parking</h1>
<p class="sub">Live feeds
  · <a href="/status" style="color:#4ade80">/status</a>
  · <a href="/events" style="color:#4ade80">/events</a>
</p>
<div class="grid">{feeds}</div>
</body></html>"""

        cfg          = uvicorn.Config(app, host=self.host, port=self.port, log_level="error")
        self._server = uvicorn.Server(cfg)
        self._thread = threading.Thread(target=self._server.run, daemon=True, name="ParkingAPI")
        self._thread.start()

    def stop(self):
        if self._server:
            self._server.should_exit = True


# =========================================================
# CAMERA THREAD
# =========================================================
class CameraStream(threading.Thread):
    _BACKOFF_INITIAL    = 2.0
    _BACKOFF_MAX        = 30.0
    _DROP_THRESHOLD     = 10   # consecutive read failures before reconnect

    def __init__(self, url: str):
        super().__init__(daemon=True)
        self.url     = url
        self.cap     = None
        self.frame   = None
        self.lock    = threading.Lock()
        self.running = True
        self.start()

    def _open(self) -> bool:
        if self.cap:
            self.cap.release()
        self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        if not self.cap.isOpened():
            # FFMPEG not available (common on Pi OS) — try default backend
            self.cap = cv2.VideoCapture(self.url)
        return self.cap.isOpened()

    def run(self):
        backoff = self._BACKOFF_INITIAL
        while self.running:
            if not self._open():
                print(f"[CameraStream] Cannot open {self.url} — retrying in {backoff:.0f}s",
                      flush=True)
                time.sleep(backoff)
                backoff = min(backoff * 2, self._BACKOFF_MAX)
                continue

            print(f"[CameraStream] Connected to {self.url}", flush=True)
            backoff = self._BACKOFF_INITIAL
            failures = 0

            while self.running:
                ret, frame = self.cap.read()
                if ret:
                    failures = 0
                    with self.lock:
                        self.frame = frame
                else:
                    failures += 1
                    if failures >= self._DROP_THRESHOLD:
                        print(f"[CameraStream] Stream lost on {self.url} — reconnecting",
                              flush=True)
                        break
                    time.sleep(0.05)

    def read(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def release(self):
        self.running = False
        if self.cap:
            self.cap.release()


# =========================================================
# INFERENCE THREAD
# =========================================================
class InferenceWorker(threading.Thread):
    def __init__(self, streams: list[CameraStream], model, config: AppConfig):
        super().__init__(daemon=True)
        self.streams    = streams
        self.model      = model
        self.config     = config
        self._frames    = [None] * len(streams)
        self._boxes     = [[] for _ in streams]
        self._frame_ids = [0] * len(streams)
        self._lock      = threading.Lock()
        self.running    = True
        clip = config.clahe_clip_limit
        self._clahe     = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8)) if clip > 0 else None
        self.start()

    def _enhance(self, frame: np.ndarray) -> np.ndarray:
        if self._clahe is None:
            return frame
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self._clahe.apply(l)
        return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)

    def run(self):
        while self.running:
            processed_any = False
            for cam_idx, stream in enumerate(self.streams):
                frame = stream.read()
                if frame is None:
                    continue
                processed_any = True
                resized  = cv2.resize(frame, (INFER_W, INFER_H))
                enhanced = self._enhance(resized)
                preds    = self.model.predict(enhanced, conf=self.config.confidence,
                                              classes=VEHICLE_CLASSES, verbose=False)
                boxes = [
                    (int(x1), int(y1), int(x2), int(y2), float(conf))
                    for r in preds
                    for (x1, y1, x2, y2), conf in zip(
                        r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy()
                    )
                ]
                with self._lock:
                    self._frames[cam_idx]    = resized   # natural image for display
                    self._boxes[cam_idx]     = boxes
                    self._frame_ids[cam_idx] += 1
            if not processed_any:
                time.sleep(0.05)

    def get(self, cam_idx: int):
        with self._lock:
            f = self._frames[cam_idx]
            return (f.copy() if f is not None else None,
                    list(self._boxes[cam_idx]),
                    self._frame_ids[cam_idx])

    def stop(self):
        self.running = False


# =========================================================
# HEADLESS RUNNER
# =========================================================
class HeadlessRunner:
    def __init__(self, camera_urls: list[str], config: AppConfig,
                 model_path: str = "yolov8s.pt",
                 lot_id: str | None = None,
                 db: SupabaseClient | None = None,
                 camera_meta: list[dict] | None = None,
                 slot_regions: list[dict] | None = None):
        self.config      = config
        self.lot_id      = lot_id
        self.db          = db
        self.camera_meta = camera_meta or []
        self.state       = SharedState()
        self._reload_flag = threading.Event()
        self.api         = ParkingAPI(
            self.state, config.api_host, config.api_port, len(camera_urls),
            db=db if db and db.available else None,
            lot_id=lot_id,
            camera_meta=camera_meta,
            on_regions_changed=self._reload_slots,
        )
        self.streams     = [CameraStream(u) for u in camera_urls]
        self.model       = YOLO(model_path)
        self.worker      = InferenceWorker(self.streams, self.model, config)

        self.camera_ids  = [c["id"] for c in self.camera_meta] if self.camera_meta \
                           else [None] * len(camera_urls)
        self.db_logger   = SupabaseLogger(db) if db and db.available else None

        self.slot_rois:        list = [[] for _ in camera_urls]
        self.slot_state:       dict = {}
        self.slot_window:      dict = {}  # deque[bool] per slot — rolling detection window
        self.slot_consec_free: dict = {}  # consecutive frames with zero hits per slot
        self.slot_enter_time:  dict = {}
        self.slot_confidence:  dict = {}  # latest per-frame confidence per slot
        self.slot_ids:         dict = {}  # (cam_idx, slot_idx) → slots.id UUID
        self.last_frame_ids:   list = [0] * len(camera_urls)
        self.running = True

        self._load_slots(slot_regions or [])

    def _load_slots(self, slot_regions: list[dict]):
        if slot_regions:
            db_state: dict[str, bool] = {}
            if self.db and self.db.available and self.lot_id:
                db_state = {
                    s["id"]: s["current_state"] == "occupied"
                    for s in self.db.list_slots(self.lot_id)
                }

            cam_id_to_idx = {cid: i for i, cid in enumerate(self.camera_ids) if cid}
            for region in slot_regions:
                cam_id  = region.get("device_id")
                cam_idx = cam_id_to_idx.get(cam_id)
                if cam_idx is None:
                    continue
                slot_idx = len(self.slot_rois[cam_idx])
                self.slot_rois[cam_idx].append(region["polygon"])
                slot_id  = region["slot_id"]
                self.slot_ids[(cam_idx, slot_idx)] = slot_id
                key           = (cam_idx, slot_idx)
                initial_state = db_state.get(slot_id, False)
                self.slot_state[key]       = initial_state
                self.slot_window[key]      = deque(maxlen=self.config.window_size)
                self.slot_consec_free[key] = 0
                self.slot_enter_time[key]  = None
                self.slot_confidence[key]  = 0.0
                self.state.update_slot(cam_idx, slot_idx, initial_state, None)
            self._log(f"Loaded {sum(len(p) for p in self.slot_rois)} slot(s) from Supabase")
            return

        if not os.path.exists(SLOT_FILE):
            self._log("No slot file found — detection disabled until slots are defined via admin UI")
            return
        with open(SLOT_FILE) as f:
            loaded = json.load(f)
        for cam_idx, polygons in enumerate(loaded):
            if cam_idx >= len(self.slot_rois):
                self.slot_rois.append([])
            self.slot_rois[cam_idx] = polygons
            for slot_idx in range(len(polygons)):
                key = (cam_idx, slot_idx)
                self.slot_state[key]       = False
                self.slot_window[key]      = deque(maxlen=self.config.window_size)
                self.slot_consec_free[key] = 0
                self.slot_enter_time[key]  = None
                self.state.update_slot(cam_idx, slot_idx, False, None)
        self._log(f"Loaded {sum(len(p) for p in loaded)} slot(s) from {SLOT_FILE}")

    def _log(self, msg: str):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

    def _reload_slots(self) -> None:
        """Called from the API thread — just sets a flag; actual reload is in main thread."""
        self._reload_flag.set()

    def _do_reload(self) -> None:
        """Rebuild slot ROIs from Supabase. Always called from the main thread."""
        if not self.db or not self.db.available or not self.lot_id:
            return
        new_regions = self.db.load_slot_regions(self.lot_id)
        db_state: dict[str, bool] = {
            s["id"]: s["current_state"] == "occupied"
            for s in self.db.list_slots(self.lot_id)
        }
        self.slot_rois        = [[] for _ in self.streams]
        self.slot_state       = {}
        self.slot_window      = {}
        self.slot_consec_free = {}
        self.slot_enter_time  = {}
        self.slot_confidence  = {}
        self.slot_ids         = {}
        if new_regions:
            cam_id_to_idx = {cid: i for i, cid in enumerate(self.camera_ids) if cid}
            for region in new_regions:
                cam_id  = region.get("device_id")
                cam_idx = cam_id_to_idx.get(cam_id)
                if cam_idx is None:
                    continue
                slot_idx      = len(self.slot_rois[cam_idx])
                self.slot_rois[cam_idx].append(region["polygon"])
                slot_id       = region["slot_id"]
                self.slot_ids[(cam_idx, slot_idx)] = slot_id
                key           = (cam_idx, slot_idx)
                initial_state = db_state.get(slot_id, False)
                self.slot_state[key]       = initial_state
                self.slot_window[key]      = deque(maxlen=self.config.window_size)
                self.slot_consec_free[key] = 0
                self.slot_enter_time[key]  = None
                self.slot_confidence[key]  = 0.0
                self.state.update_slot(cam_idx, slot_idx, initial_state, None)
        total = sum(len(r) for r in self.slot_rois)
        self._log(f"Regions reloaded — {total} slot(s) active")

    @staticmethod
    def _poly_array(polygon) -> "np.ndarray | None":
        try:
            arr = np.array(polygon, dtype=np.int32)
            if arr.ndim != 2 or arr.shape[0] < 3 or arr.shape[1] != 2:
                return None
            return arr
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _box_poly_overlap_ratio(pts: np.ndarray,
                                 x1: int, y1: int, x2: int, y2: int) -> float:
        """Fraction of the slot polygon area covered by the bounding box."""
        poly_area = cv2.contourArea(pts)
        if poly_area < 1:
            return 0.0
        px_min, py_min = int(pts[:, 0].min()), int(pts[:, 1].min())
        px_max, py_max = int(pts[:, 0].max()), int(pts[:, 1].max())
        ix1 = max(x1, px_min)
        iy1 = max(y1, py_min)
        ix2 = min(x2, px_max)
        iy2 = min(y2, py_max)
        if ix2 <= ix1 or iy2 <= iy1:
            return 0.0
        w, h = ix2 - ix1, iy2 - iy1
        mask = np.zeros((h, w), dtype=np.uint8)
        shifted = (pts - np.array([ix1, iy1])).astype(np.int32)
        cv2.fillPoly(mask, [shifted], 1)
        return int(mask.sum()) / poly_area

    def _annotate(self, cam_idx: int, display, boxes):
        for bx1, by1, bx2, by2, conf in boxes:
            cv2.rectangle(display, (bx1, by1), (bx2, by2), (251, 146, 60), 2)
            cv2.putText(display, f"{conf:.0%}",
                        (bx1, max(by1 - 6, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (251, 146, 60), 1)
        for (cam_i, slot_i) in list(self.slot_state):
            if cam_i != cam_idx or slot_i >= len(self.slot_rois[cam_idx]):
                continue
            key     = (cam_i, slot_i)
            polygon = self.slot_rois[cam_idx][slot_i]
            pts     = self._poly_array(polygon)
            if pts is None:
                continue
            occupied = self.slot_state[key]
            color    = (241, 113, 113) if occupied else (74, 222, 128)
            cv2.polylines(display, [pts], isClosed=True, color=color, thickness=2)
            conf_pct = self.slot_confidence.get(key, 0.0)
            label    = f"C{cam_i+1}-S{slot_i+1}"
            if occupied and conf_pct > 0:
                label += f"  {conf_pct:.0%}"
            cv2.putText(display, label,
                        (int(pts[0][0]), int(pts[0][1])),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        _, jpeg = cv2.imencode(".jpg", display, [cv2.IMWRITE_JPEG_QUALITY, 75])
        self.state.update_frame(cam_idx, jpeg.tobytes())

    def _tick(self):
        if self._reload_flag.is_set():
            self._reload_flag.clear()
            self._do_reload()

        debounce_enter     = self.config.debounce_frames
        debounce_free      = self.config.debounce_frames_free
        overlap_threshold  = self.config.overlap_threshold
        for cam_idx in range(len(self.streams)):
            frame, boxes, frame_id = self.worker.get(cam_idx)
            if frame is None or frame_id == self.last_frame_ids[cam_idx]:
                continue
            self.last_frame_ids[cam_idx] = frame_id

            for (cam_i, slot_i) in list(self.slot_state):
                if cam_i != cam_idx or slot_i >= len(self.slot_rois[cam_idx]):
                    continue
                key      = (cam_i, slot_i)
                polygon  = self.slot_rois[cam_idx][slot_i]
                pts      = self._poly_array(polygon)
                if pts is None:
                    continue
                hits = [
                    b for b in boxes
                    if (
                        self._box_poly_overlap_ratio(pts, b[0], b[1], b[2], b[3])
                        >= overlap_threshold
                        and cv2.pointPolygonTest(
                            pts, ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2), True
                        ) >= -20
                    )
                ]
                detected = len(hits) > 0
                self.slot_confidence[key] = max((b[4] for b in hits), default=0.0)

                if detected:
                    self.slot_consec_free[key] = 0
                else:
                    self.slot_consec_free[key] = self.slot_consec_free.get(key, 0) + 1

                win = self.slot_window[key]
                win.append(detected)
                true_votes  = sum(win)
                false_votes = len(win) - true_votes

                currently = self.slot_state[key]
                # Fast-clear: N consecutive frames with zero hits overrides the vote window.
                # This fixes "slot stuck occupied while no detection box covers it."
                if currently and self.slot_consec_free[key] >= debounce_free:
                    stable = False
                elif not currently and true_votes >= debounce_enter:
                    stable = True
                elif currently and false_votes >= debounce_free:
                    stable = False
                else:
                    stable = currently

                if stable != self.slot_state[key]:
                    self.slot_state[key] = stable
                    slot_id = self.slot_ids.get(key)
                    if stable:
                        self.slot_enter_time[key] = datetime.now()
                        self.state.update_slot(cam_i, slot_i, True, self.slot_enter_time[key])
                        self.state.add_event("ENTER", cam_i, slot_i)
                        self._log(f"enter  cam{cam_i+1} slot{slot_i+1}")
                        if self.db_logger and slot_id:
                            self.db_logger.report_state(slot_id, "occupied",
                                                        confidence=self.slot_confidence.get(key))
                    else:
                        enter_time = self.slot_enter_time.get(key)
                        dur_str    = None
                        if enter_time:
                            dur = datetime.now() - enter_time
                            if dur.total_seconds() >= self.config.min_duration:
                                dur_str = str(dur).split(".")[0]
                        self.state.update_slot(cam_i, slot_i, False, None)
                        self.state.add_event("EXIT", cam_i, slot_i, dur_str)
                        self._log(f"exit   cam{cam_i+1} slot{slot_i+1}"
                                  + (f"  duration: {dur_str}" if dur_str else ""))
                        self.slot_enter_time[key] = None
                        if self.db_logger and slot_id:
                            self.db_logger.report_state(slot_id, "free",
                                                        confidence=None)

            self._annotate(cam_idx, frame, boxes)

    def run(self):
        self.api.start()
        self._log("Started" + (f" · lot {self.lot_id}" if self.lot_id else " · local config"))
        self._log(f"Dashboard : http://localhost:{self.config.api_port}/")
        self._log(f"Status    : http://localhost:{self.config.api_port}/status")
        self._log(f"Stream    : http://localhost:{self.config.api_port}/stream/0")
        self._log("Press Ctrl+C to stop")
        try:
            while self.running:
                self._tick()
                time.sleep(0.03)
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            self._log("Shutting down...")
            self.worker.stop()
            self.api.stop()
            for s in self.streams:
                s.release()


# =========================================================
# ENTRY POINT
# =========================================================
def main():
    parser = argparse.ArgumentParser(description="Smart Parking vision detector")
    parser.add_argument("--lot",      required=False, help="Lot UUID (required unless CAMERA_URL is set)")
    parser.add_argument("--model",    default="yolov8n.pt", help="YOLO model file (default: yolov8n.pt)")
    parser.add_argument("--email",    default=os.environ.get("GATEWAY_EMAIL", ""),    help="Gateway Supabase email")
    parser.add_argument("--password", default=os.environ.get("GATEWAY_PASSWORD", ""), help="Gateway Supabase password")
    args = parser.parse_args()

    db = SupabaseClient(email=args.email, password=args.password)

    lot_id       = args.lot
    camera_meta  = []
    slot_regions = []

    if db.available:
        if not lot_id:
            lots = db.list_lots()
            if not lots:
                sys.exit("No parking lots found in database.")
            if len(lots) == 1:
                lot_id = lots[0]["id"]
                print(f"[Vision] Using lot: {lots[0].get('name', lot_id)}", flush=True)
            else:
                sys.exit(
                    "Multiple lots found — pass --lot <uuid>:\n"
                    + "\n".join(f"  {l['id']}  {l.get('name', '')}" for l in lots)
                )
        camera_meta  = db.load_cameras(lot_id)
        slot_regions = db.load_slot_regions(lot_id)
        cfg          = db.load_settings(lot_id) or load_config()
        camera_urls  = [c["url"] for c in camera_meta]
        if not camera_urls:
            sys.exit(f"No cameras found for lot {lot_id} in Supabase.")
        print(f"[Supabase] Lot {lot_id}: "
              f"{len(camera_urls)} camera(s), {len(slot_regions)} slot region(s)", flush=True)
    else:
        camera_url = os.environ.get("CAMERA_URL")
        if not camera_url:
            sys.exit(
                "Supabase not configured and CAMERA_URL not set.\n"
                "Set SUPABASE_URL + SUPABASE_KEY in .env, or set CAMERA_URL."
            )
        print("[Warning] Supabase not configured — using CAMERA_URL env var.", flush=True)
        camera_urls = [camera_url]
        cfg         = load_config()

    runner = HeadlessRunner(
        camera_urls, cfg, args.model,
        lot_id=lot_id,
        db=db if db.available else None,
        camera_meta=camera_meta,
        slot_regions=slot_regions,
    )

    signal.signal(signal.SIGTERM, lambda *_: runner.__setattr__("running", False))

    runner.run()


if __name__ == "__main__":
    main()
