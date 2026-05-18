import { ambientDrift, cursorRipple, wave } from 'pretext-flow';

export const defaultEffects = () => [
  ambientDrift({ amplitude: 0.3 }),
  cursorRipple({ strength: 0.8 }),
  wave({ amplitude: 1, frequency: 0.012 }),
];

export const zenEffects = () => [
  ambientDrift({ amplitude: 0.15 }),
  wave({ amplitude: 0.5, frequency: 0.006 }),
];
