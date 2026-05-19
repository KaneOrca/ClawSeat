import type { Embed, FlowResult, ResolvedEmbed } from 'pretext-flow';

export const createHiDPICanvas = (container: HTMLDivElement, dpr: number) => {
  const canvas = document.createElement('canvas');
  const rect = container.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width * dpr));
  const height = Math.max(1, Math.floor(rect.height * dpr));
  canvas.width = width;
  canvas.height = height;
  canvas.style.width = Math.max(1, Math.floor(rect.width)) + "px";
  canvas.style.height = Math.max(1, Math.floor(rect.height)) + "px";
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Canvas 2D context unavailable');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { canvas, ctx };
};

export const renderLines = (
  ctx: CanvasRenderingContext2D,
  result: FlowResult,
  font: string,
  colorFn: (index: number, total: number) => string,
) => {
  ctx.save();
  ctx.textBaseline = 'top';
  ctx.font = font;

  result.lines.forEach((line, index) => {
    const color = colorFn(index, result.lines.length);
    if (line.characters) {
      line.characters.forEach(ch => {
        const opacity = (ch as any).opacity ?? 1;
        if (opacity <= 0) return;
        ctx.fillStyle = color;
        ctx.globalAlpha = opacity;
        // In pretext-flow 1.0, CharacterPosition uses x only, y is inherited from line
        ctx.fillText(ch.char, ch.x, line.y);
      });
    } else {
      ctx.fillStyle = color;
      ctx.globalAlpha = 1;
      ctx.fillText(line.text, line.x, line.y);
    }
  });

  ctx.restore();
};

export const renderEmbeds = (
  ctx: CanvasRenderingContext2D,
  result: FlowResult,
  renderFn: (ctx: CanvasRenderingContext2D, embed: Embed, resolved: ResolvedEmbed, index: number) => void,
) => {
  const embeds = result.embeds as ResolvedEmbed[] | undefined;
  if (!embeds || embeds.length === 0) return;

  embeds.forEach((embed, index) => {
    renderFn(ctx, embed.embed, embed, index);
  });
};
