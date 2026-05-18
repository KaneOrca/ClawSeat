export type { Embed, FlowLine, FlowResult, FlowConfig, ResolvedEmbed } from 'pretext-flow';

export interface LegacyLine {
  text: string;
  x: number;
  y: number;
  opacity: number;
}

export interface LegacyResult {
  lines: LegacyLine[];
  height: number;
}

export type TextEngineResult = FlowResult | LegacyResult;
