import { flowLayout, type FlowConfig, type FlowResult } from 'pretext-flow';

export async function textEngine(config: FlowConfig): Promise<FlowResult> {
  return flowLayout(config);
}
