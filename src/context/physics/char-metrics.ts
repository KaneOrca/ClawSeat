export interface CharRect {
  char: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

interface CharRectCache {
  text: string;
  font: string;
  relRects: { char: string; dx: number; dy: number; w: number; h: number }[];
}

const charRectCache = new Map<string, CharRectCache>();
let measureCanvas: HTMLCanvasElement | null = null;

export function clearCharRectCache(id: string): void {
  charRectCache.delete(id);
}

export function getCharRects(id: string, el: HTMLElement, bbox: DOMRect): CharRect[] | undefined {
  const text = el.textContent;
  if (!text || text.length < 2 || text.length > 100) return undefined;

  const style = getComputedStyle(el);
  const font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;

  const cached = charRectCache.get(id);
  if (cached && cached.text === text && cached.font === font) {
    return cached.relRects.map(r => ({
      char: r.char,
      x: bbox.left + r.dx,
      y: bbox.top + r.dy,
      w: r.w,
      h: r.h,
    }));
  }

  const relRects: CharRectCache['relRects'] = [];
  let measured = false;

  const textNode = findFirstTextNode(el);
  if (textNode && textNode.textContent === text) {
    try {
      const range = document.createRange();
      for (let i = 0; i < text.length; i++) {
        if (text[i] === ' ' || text[i] === '\n' || text[i] === '\t') continue;
        range.setStart(textNode, i);
        range.setEnd(textNode, i + 1);
        const cr = range.getBoundingClientRect();
        if (cr.width < 0.5) continue;
        relRects.push({
          char: text[i],
          dx: cr.left - bbox.left,
          dy: cr.top - bbox.top,
          w: cr.width,
          h: cr.height,
        });
      }
      range.detach();
      measured = relRects.length > 0;
    } catch {
      // Range API failed — fall through to measureText
    }
  }

  if (!measured) {
    if (!measureCanvas) measureCanvas = document.createElement('canvas');
    const ctx = measureCanvas.getContext('2d');
    if (ctx) {
      ctx.font = font;
      let cursorX = 0;
      for (let i = 0; i < text.length; i++) {
        const ch = text[i];
        const w = ctx.measureText(ch).width;
        if (ch !== ' ' && ch !== '\n' && ch !== '\t') {
          relRects.push({ char: ch, dx: cursorX, dy: 0, w, h: bbox.height });
        }
        cursorX += w;
      }
    }
  }

  if (relRects.length === 0) return undefined;

  charRectCache.set(id, { text, font, relRects });

  return relRects.map(r => ({
    char: r.char,
    x: bbox.left + r.dx,
    y: bbox.top + r.dy,
    w: r.w,
    h: r.h,
  }));
}

function findFirstTextNode(el: Node): Text | null {
  if (el.nodeType === Node.TEXT_NODE) return el as Text;
  for (let i = 0; i < el.childNodes.length; i++) {
    const found = findFirstTextNode(el.childNodes[i]);
    if (found) return found;
  }
  return null;
}
