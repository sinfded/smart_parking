// ============================================================================
// Lot Layout — shared TypeScript types
// Used by the admin layout editor and the mobile map viewer.
//
// Coordinate system: virtual canvas 0–10000 × 0–10000.
// 10 000 units ≈ 100 m, so 1 unit ≈ 1 cm.
// All element positions/sizes are in this unit space.
// Stage zoom/pan is a pure presentation concern handled by Konva.
// ============================================================================

export const CANVAS_SIZE  = 10_000 as const;
export const DEFAULT_GRID = 100    as const; // 1 m
export const SLOT_W       = 250    as const; // 2.5 m
export const SLOT_H       = 500    as const; // 5.0 m
export const ROAD_W       = 350    as const; // 3.5 m
export const MARKER_W     = 400    as const;
export const MARKER_H     = 280    as const;
export const CAMERA_R     = 80     as const;
export const SENSOR_R     = 70     as const;

// ── Tool types ────────────────────────────────────────────────────────────────

export type ToolType =
  | 'select'
  | 'slot'
  | 'road'
  | 'entrance'
  | 'exit'
  | 'camera'
  | 'sensor'
  | 'label'
  | 'delete';

// ── Element types ─────────────────────────────────────────────────────────────

export type SlotCategory = 'standard' | 'compact' | 'motorcycle' | 'pwd' | 'ev' | 'truck' | 'vip';
export type SlotStatus   = 'free' | 'occupied' | 'reserved' | 'disabled' | 'unknown';
export type RoadDir      = 'one-way' | 'two-way';

export type ElementType =
  | 'parking_slot'
  | 'road'
  | 'entrance'
  | 'exit'
  | 'camera'
  | 'sensor'
  | 'label';

interface Base {
  id:      string;
  locked:  boolean;
  visible: boolean;
}

export interface ParkingSlotEl extends Base {
  type:     'parking_slot';
  x:        number;
  y:        number;
  width:    number;
  height:   number;
  rotation: number;
  code:     string;
  category: SlotCategory;
  /** UUID of the matching row in `public.slots` */
  slotId?:  string;
  zoneId?:  string;
  color?:   string;
}

export interface RoadEl extends Base {
  type:        'road';
  /** Flat array [x0,y0, x1,y1, …] */
  points:      number[];
  strokeWidth: number;
  direction:   RoadDir;
  color:       string;
}

export interface EntranceEl extends Base {
  type:     'entrance';
  x:        number;
  y:        number;
  width:    number;
  height:   number;
  rotation: number;
  label:    string;
}

export interface ExitEl extends Base {
  type:     'exit';
  x:        number;
  y:        number;
  width:    number;
  height:   number;
  rotation: number;
  label:    string;
}

export interface CameraEl extends Base {
  type:     'camera';
  x:        number;
  y:        number;
  rotation: number;
  /** Field-of-view cone angle in degrees */
  fov:      number;
  /** Max detection range in canvas units */
  range:    number;
}

export interface SensorEl extends Base {
  type:       'sensor';
  x:          number;
  y:          number;
  sensorCode: string;
  /** UUID of the assigned slot */
  slotId?:    string;
}

export interface LabelEl extends Base {
  type:     'label';
  x:        number;
  y:        number;
  text:     string;
  fontSize: number;
  color:    string;
  rotation: number;
}

export type LotElement =
  | ParkingSlotEl
  | RoadEl
  | EntranceEl
  | ExitEl
  | CameraEl
  | SensorEl
  | LabelEl;

// ── Config types ──────────────────────────────────────────────────────────────

export interface BackgroundCfg {
  url:     string | null;
  x:       number;
  y:       number;
  width:   number;
  height:  number;
  opacity: number;
}

export interface GridCfg {
  size:    number;
  visible: boolean;
  snap:    boolean;
}

export interface LotMapConfig {
  version:    string;
  canvas:     { width: number; height: number };
  background: BackgroundCfg;
  grid:       GridCfg;
  elements:   LotElement[];
}

// ── Mobile viewer ─────────────────────────────────────────────────────────────

export interface LiveSlot {
  element: ParkingSlotEl;
  status:  SlotStatus;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

export function defaultConfig(): LotMapConfig {
  return {
    version:    '2.0',
    canvas:     { width: CANVAS_SIZE, height: CANVAS_SIZE },
    background: { url: null, x: 0, y: 0, width: CANVAS_SIZE, height: CANVAS_SIZE, opacity: 0.6 },
    grid:       { size: DEFAULT_GRID, visible: true, snap: true },
    elements:   [],
  };
}

export const SLOT_COLORS: Record<SlotCategory, string> = {
  standard:   '#6366f1',
  compact:    '#8b5cf6',
  motorcycle: '#f59e0b',
  pwd:        '#06b6d4',
  ev:         '#22c55e',
  truck:      '#64748b',
  vip:        '#f43f5e',
};

export const STATUS_COLORS: Record<SlotStatus, string> = {
  free:     '#22c55e',
  occupied: '#ef4444',
  reserved: '#3b82f6',
  disabled: '#d1d5db',
  unknown:  '#fbbf24',
};
