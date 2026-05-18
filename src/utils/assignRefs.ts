import type { RefObject } from 'react';

export function assignRefs(node: HTMLElement | null, ...refs: Array<RefObject<HTMLElement | null>>) {
  refs.forEach(ref => {
    ref.current = node;
  });
}
