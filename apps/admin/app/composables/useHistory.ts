import type { LotElement } from '@smart-parking/types';

const MAX_HISTORY = 50;

/**
 * Undo/redo history for the layout editor.
 * Snapshots are deep-clones of the elements array; the caller provides
 * a writable computed ref so history can restore state atomically.
 */
export function useHistory(elements: WritableComputedRef<LotElement[]> | Ref<LotElement[]>) {
  const past   = ref<LotElement[][]>([]);
  const future = ref<LotElement[][]>([]);

  function clone(): LotElement[] {
    return JSON.parse(JSON.stringify(elements.value));
  }

  /** Call before mutating elements to push the current state onto the undo stack. */
  function checkpoint() {
    past.value.push(clone());
    if (past.value.length > MAX_HISTORY) past.value.shift();
    future.value = [];
  }

  function undo() {
    if (!past.value.length) return;
    future.value.push(clone());
    elements.value = past.value.pop()!;
  }

  function redo() {
    if (!future.value.length) return;
    past.value.push(clone());
    elements.value = future.value.pop()!;
  }

  function clear() {
    past.value  = [];
    future.value = [];
  }

  return {
    checkpoint,
    undo,
    redo,
    clear,
    canUndo: computed(() => past.value.length > 0),
    canRedo: computed(() => future.value.length > 0),
  };
}
