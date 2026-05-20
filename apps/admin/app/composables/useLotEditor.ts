import type {
  LotElement,
  LotMapConfig,
  ParkingSlotEl,
  RoadEl,
  EntranceEl,
  ExitEl,
  CameraEl,
  SensorEl,
  LabelEl,
  ToolType,
} from '@smart-parking/types';
import {
  SLOT_W,
  SLOT_H,
  ROAD_W,
  MARKER_W,
  MARKER_H,
  defaultConfig,
} from '@smart-parking/types';
import { useHistory } from './useHistory';

function uid() { return crypto.randomUUID(); }

// ── Debounce ──────────────────────────────────────────────────────────────────

function debounce<T extends (...args: any[]) => void>(fn: T, ms: number): T {
  let timer: ReturnType<typeof setTimeout>;
  return ((...args: any[]) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  }) as T;
}

// ── Editor state ──────────────────────────────────────────────────────────────

export function useLotEditor(lotId: string, supabase: ReturnType<typeof useSupabaseClient<any>>) {
  // ── Core layout state ───────────────────────────────────────────────────────

  const layout = ref<LotMapConfig>(defaultConfig());

  const elements = computed({
    get: () => layout.value.elements,
    set: (v) => { layout.value.elements = v; },
  });

  const { checkpoint, undo, redo, clear: clearHistory, canUndo, canRedo } = useHistory(elements);

  // ── Derived element views ───────────────────────────────────────────────────

  const slots    = computed(() => elements.value.filter((e): e is ParkingSlotEl => e.type === 'parking_slot'));
  const roads    = computed(() => elements.value.filter((e): e is RoadEl        => e.type === 'road'));
  const markers  = computed(() => elements.value.filter(
    (e): e is EntranceEl | ExitEl | CameraEl | SensorEl | LabelEl =>
      ['entrance', 'exit', 'camera', 'sensor', 'label'].includes(e.type)
  ));

  // ── Tool + selection ────────────────────────────────────────────────────────

  const activeTool  = ref<ToolType>('select');
  const selectedIds = ref<Set<string>>(new Set());
  const clipboard   = ref<LotElement[]>([]);

  const selectedElements = computed(() =>
    elements.value.filter((e) => selectedIds.value.has(e.id))
  );
  const selectedElement = computed<LotElement | null>(() =>
    selectedElements.value.length === 1 ? selectedElements.value[0]! : null
  );

  function setTool(t: ToolType) {
    activeTool.value = t;
    if (t !== 'select') clearSelection();
  }

  function selectElement(id: string, multi = false) {
    if (multi) {
      const next = new Set(selectedIds.value);
      next.has(id) ? next.delete(id) : next.add(id);
      selectedIds.value = next;
    } else {
      selectedIds.value = new Set([id]);
    }
  }

  function selectAll() {
    selectedIds.value = new Set(elements.value.filter((e) => !e.locked).map((e) => e.id));
  }

  function selectByRect(x1: number, y1: number, x2: number, y2: number) {
    const rLeft   = Math.min(x1, x2);
    const rRight  = Math.max(x1, x2);
    const rTop    = Math.min(y1, y2);
    const rBottom = Math.max(y1, y2);

    const ids = new Set<string>();
    for (const el of elements.value) {
      if (el.locked || !el.visible) continue;
      const cx = (el as any).x ?? 0;
      const cy = (el as any).y ?? 0;
      if (cx >= rLeft && cx <= rRight && cy >= rTop && cy <= rBottom) {
        ids.add(el.id);
      }
    }
    selectedIds.value = ids;
  }

  function clearSelection() {
    selectedIds.value = new Set();
  }

  // ── Element CRUD ────────────────────────────────────────────────────────────

  function getElementById(id: string): LotElement | undefined {
    return elements.value.find((e) => e.id === id);
  }

  function addElement(el: LotElement) {
    checkpoint();
    layout.value.elements = [...layout.value.elements, el];
    selectedIds.value = new Set([el.id]);
    scheduleSave();
  }

  function updateElement(id: string, patch: Partial<LotElement>) {
    checkpoint();
    layout.value.elements = layout.value.elements.map((e) =>
      e.id === id ? ({ ...e, ...patch } as LotElement) : e
    );
    scheduleSave();
  }

  function updateElements(updates: Array<{ id: string; patch: Partial<LotElement> }>) {
    checkpoint();
    const map = new Map(updates.map((u) => [u.id, u.patch]));
    layout.value.elements = layout.value.elements.map((e) =>
      map.has(e.id) ? ({ ...e, ...map.get(e.id) } as LotElement) : e
    );
    scheduleSave();
  }

  function removeElement(id: string) {
    checkpoint();
    layout.value.elements = layout.value.elements.filter((e) => e.id !== id);
    selectedIds.value.delete(id);
    scheduleSave();
  }

  function removeSelected() {
    if (!selectedIds.value.size) return;
    checkpoint();
    const ids = selectedIds.value;
    layout.value.elements = layout.value.elements.filter((e) => !ids.has(e.id) || e.locked);
    clearSelection();
    scheduleSave();
  }

  function toggleLock(id: string) {
    const el = getElementById(id);
    if (!el) return;
    updateElement(id, { locked: !el.locked });
  }

  function toggleVisibility(id: string) {
    const el = getElementById(id);
    if (!el) return;
    updateElement(id, { visible: !el.visible });
  }

  // ── Copy / paste ────────────────────────────────────────────────────────────

  const PASTE_OFFSET = 80;

  function copySelected() {
    clipboard.value = JSON.parse(JSON.stringify(selectedElements.value));
  }

  function paste() {
    if (!clipboard.value.length) return;
    checkpoint();
    const pasted = clipboard.value.map((el) => ({
      ...el,
      id: uid(),
      ...'x' in el ? { x: (el as any).x + PASTE_OFFSET } : {},
      ...'y' in el ? { y: (el as any).y + PASTE_OFFSET } : {},
    })) as LotElement[];
    layout.value.elements = [...layout.value.elements, ...pasted];
    selectedIds.value = new Set(pasted.map((e) => e.id));
    scheduleSave();
  }

  function duplicate(id: string) {
    const el = getElementById(id);
    if (!el) return;
    clipboard.value = [JSON.parse(JSON.stringify(el))];
    paste();
  }

  // ── Grid / snap ─────────────────────────────────────────────────────────────

  function snapVal(v: number): number {
    if (!layout.value.grid.snap) return v;
    const g = layout.value.grid.size;
    return Math.round(v / g) * g;
  }

  function snapPos(pos: { x: number; y: number }) {
    return { x: snapVal(pos.x), y: snapVal(pos.y) };
  }

  // ── Auto-naming ─────────────────────────────────────────────────────────────

  function nextSlotCode(): string {
    const codes = new Set(slots.value.map((s) => s.code));
    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    for (const L of letters) {
      for (let n = 1; n <= 999; n++) {
        const code = `${L}${n}`;
        if (!codes.has(code)) return code;
      }
    }
    return `S${slots.value.length + 1}`;
  }

  // ── Element factories ────────────────────────────────────────────────────────

  function newSlot(x: number, y: number, w = SLOT_W, h = SLOT_H): ParkingSlotEl {
    const snapped = snapPos({ x, y });
    return {
      id: uid(), type: 'parking_slot',
      x: snapped.x, y: snapped.y,
      width: w, height: h, rotation: 0,
      code: nextSlotCode(), category: 'standard',
      locked: false, visible: true,
    };
  }

  function newEntrance(x: number, y: number): EntranceEl {
    const snapped = snapPos({ x, y });
    return {
      id: uid(), type: 'entrance',
      x: snapped.x, y: snapped.y,
      width: MARKER_W, height: MARKER_H, rotation: 0,
      label: 'Entrance', locked: false, visible: true,
    };
  }

  function newExit(x: number, y: number): ExitEl {
    const snapped = snapPos({ x, y });
    return {
      id: uid(), type: 'exit',
      x: snapped.x, y: snapped.y,
      width: MARKER_W, height: MARKER_H, rotation: 0,
      label: 'Exit', locked: false, visible: true,
    };
  }

  function newCamera(x: number, y: number): CameraEl {
    const snapped = snapPos({ x, y });
    return {
      id: uid(), type: 'camera',
      x: snapped.x, y: snapped.y,
      rotation: 0, fov: 90, range: 1500,
      locked: false, visible: true,
    };
  }

  function newSensor(x: number, y: number): SensorEl {
    const snapped = snapPos({ x, y });
    const sensorCount = elements.value.filter((e) => e.type === 'sensor').length;
    return {
      id: uid(), type: 'sensor',
      x: snapped.x, y: snapped.y,
      sensorCode: `S${String(sensorCount + 1).padStart(3, '0')}`,
      locked: false, visible: true,
    };
  }

  function newRoad(points: number[]): RoadEl {
    return {
      id: uid(), type: 'road',
      points, strokeWidth: ROAD_W,
      direction: 'two-way', color: '#374151',
      locked: false, visible: true,
    };
  }

  function newLabel(x: number, y: number): LabelEl {
    const snapped = snapPos({ x, y });
    return {
      id: uid(), type: 'label',
      x: snapped.x, y: snapped.y,
      text: 'Label', fontSize: 200, color: '#374151', rotation: 0,
      locked: false, visible: true,
    };
  }

  // ── Background ───────────────────────────────────────────────────────────────

  function updateBackground(patch: Partial<typeof layout.value.background>) {
    layout.value.background = { ...layout.value.background, ...patch };
    scheduleSave();
  }

  function updateGrid(patch: Partial<typeof layout.value.grid>) {
    layout.value.grid = { ...layout.value.grid, ...patch };
  }

  // ── Save / load ──────────────────────────────────────────────────────────────

  type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';
  const saveStatus = ref<SaveStatus>('idle');
  const isDirty   = ref(false);

  async function save() {
    saveStatus.value = 'saving';
    isDirty.value = false;
    try {
      await supabase
        .from('lots')
        .update({ map_config: layout.value as any })
        .eq('id', lotId);
      saveStatus.value = 'saved';
      setTimeout(() => { if (saveStatus.value === 'saved') saveStatus.value = 'idle'; }, 2000);
    } catch {
      saveStatus.value = 'error';
      isDirty.value = true;
    }
  }

  const scheduleSave = debounce(() => {
    isDirty.value = true;
    save();
  }, 2000);

  async function loadFromDb() {
    const { data } = await supabase
      .from('lots')
      .select('map_config')
      .eq('id', lotId)
      .single();

    if (data?.map_config && (data.map_config as any).version) {
      layout.value = data.map_config as unknown as LotMapConfig;
    }
    clearHistory();
  }

  // ── Import / export ──────────────────────────────────────────────────────────

  function exportJSON(): string {
    return JSON.stringify(layout.value, null, 2);
  }

  function importJSON(json: string): boolean {
    try {
      const parsed = JSON.parse(json) as LotMapConfig;
      if (!parsed.version || !Array.isArray(parsed.elements)) return false;
      checkpoint();
      layout.value = parsed;
      clearHistory();
      scheduleSave();
      return true;
    } catch {
      return false;
    }
  }

  return {
    // state
    layout,
    elements,
    slots,
    roads,
    markers,
    activeTool,
    selectedIds,
    selectedElements,
    selectedElement,
    clipboard,
    saveStatus,
    isDirty,
    // history
    canUndo,
    canRedo,
    undo: () => { undo(); scheduleSave(); },
    redo: () => { redo(); scheduleSave(); },
    // tools
    setTool,
    // selection
    selectElement,
    selectAll,
    selectByRect,
    clearSelection,
    // CRUD
    getElementById,
    addElement,
    updateElement,
    updateElements,
    removeElement,
    removeSelected,
    toggleLock,
    toggleVisibility,
    // clipboard
    copySelected,
    paste,
    duplicate,
    // grid
    snapVal,
    snapPos,
    // factories
    newSlot,
    newEntrance,
    newExit,
    newCamera,
    newSensor,
    newRoad,
    newLabel,
    // background / grid config
    updateBackground,
    updateGrid,
    // persistence
    save,
    loadFromDb,
    exportJSON,
    importJSON,
  };
}

export type LotEditor = ReturnType<typeof useLotEditor>;
