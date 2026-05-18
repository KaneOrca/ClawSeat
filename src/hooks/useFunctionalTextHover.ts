import { useEffect } from 'react';

export interface FunctionalTextRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface FunctionalTextHoverWindow extends Window {
  __activeFunctionalTextRects?: FunctionalTextRect[];
}

const FUNCTIONAL_TEXT_SELECTOR = '[data-functional-text="true"]';

function hoverWindow(): FunctionalTextHoverWindow | null {
  return typeof window === 'undefined' ? null : window as FunctionalTextHoverWindow;
}

function setActiveFunctionalTextRects(rects: FunctionalTextRect[]): void {
  const win = hoverWindow();
  if (!win) return;
  win.__activeFunctionalTextRects = rects;
}

export function getActiveFunctionalTextRects(): FunctionalTextRect[] {
  return hoverWindow()?.__activeFunctionalTextRects ?? [];
}

export function clearActiveFunctionalTextRects(): void {
  setActiveFunctionalTextRects([]);
}

function toFunctionalTextElement(element: Element): HTMLElement | null {
  if (element instanceof HTMLElement && element.matches(FUNCTIONAL_TEXT_SELECTOR)) {
    return element;
  }

  const closest = element.closest(FUNCTIONAL_TEXT_SELECTOR);
  return closest instanceof HTMLElement ? closest : null;
}

function readHoveredFunctionalTextRects(clientX: number, clientY: number): FunctionalTextRect[] {
  const elements = document.elementsFromPoint(clientX, clientY);
  const targets = new Set<HTMLElement>();

  for (const element of elements) {
    const target = toFunctionalTextElement(element);
    if (target) targets.add(target);
  }

  const rects: FunctionalTextRect[] = [];
  targets.forEach(target => {
    const rect = target.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return;
    rects.push({
      x: rect.left,
      y: rect.top,
      width: rect.width,
      height: rect.height,
    });
  });

  return rects;
}

/**
 * Tracks functional text under the pointer once per pointermove. Canvas physics
 * engines read this window-backed state inside their own RAF render loops.
 */
export function useFunctionalTextHover(): void {
  useEffect(() => {
    if (typeof document === 'undefined' || typeof window === 'undefined') return;

    const handlePointerMove = (event: PointerEvent) => {
      setActiveFunctionalTextRects(readHoveredFunctionalTextRects(event.clientX, event.clientY));
    };

    const clear = () => clearActiveFunctionalTextRects();

    document.addEventListener('pointermove', handlePointerMove, { passive: true });
    window.addEventListener('blur', clear);
    window.addEventListener('pointerleave', clear);
    clear();

    return () => {
      document.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('blur', clear);
      window.removeEventListener('pointerleave', clear);
      clear();
    };
  }, []);
}
