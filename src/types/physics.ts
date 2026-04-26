export interface RectObstacle {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface OrbObstacle {
  x: number;
  y: number;
  r: number;
}

export type PhysicsObstacle = RectObstacle | OrbObstacle;

export interface CanvasContext {
  ctx: CanvasRenderingContext2D;
  width: number;
  height: number;
  dpr: number;
}
