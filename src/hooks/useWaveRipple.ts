import { useCallback, useEffect } from 'react'
import { usePhysicsRegistry, type EnvironmentSettings } from '../context/PhysicsContext'

const BASE_AMPLITUDE = 60
const RIPPLE_AMPLITUDE = 120
const RIPPLE_DECAY_MS = 600
const FUNCTIONAL_TEXT_SELECTOR = '[data-functional-text], [data-pretext-engine], [data-pretext-state]'

/**
 * Global document-level hover tracking shared by all hook instances.
 * We keep a single listener and shared timer so adjacent atoms do not race
 * against each other.
 */
let activeRippleCount = 0
let rippleBaselineAmplitude: number | null = null
let latestAmplitude = BASE_AMPLITUDE
let documentListenerRefCount = 0
let rippleDecayTimer: ReturnType<typeof setTimeout> | null = null

const activeSetEnvironmentFns = new Set<(patch: Partial<EnvironmentSettings>) => void>()

function applyEnvironment(patch: Partial<EnvironmentSettings>) {
  activeSetEnvironmentFns.forEach(fn => fn(patch))
}

function isOverFunctionalText(x: number, y: number) {
  return document.elementsFromPoint(x, y).some(element => {
    const target = element as HTMLElement
    return target.matches(FUNCTIONAL_TEXT_SELECTOR)
  })
}

function beginRipple() {
  if (rippleDecayTimer) {
    window.clearTimeout(rippleDecayTimer)
    rippleDecayTimer = null
  }

  if (activeRippleCount > 0) return

  rippleBaselineAmplitude = latestAmplitude
  activeRippleCount = 1
  applyEnvironment({ waveAmplitude: RIPPLE_AMPLITUDE })
}

function scheduleRippleDecay() {
  if (rippleDecayTimer) window.clearTimeout(rippleDecayTimer)

  rippleDecayTimer = window.setTimeout(() => {
    activeRippleCount = 0
    applyEnvironment({ waveAmplitude: rippleBaselineAmplitude ?? BASE_AMPLITUDE })
    rippleBaselineAmplitude = null
    rippleDecayTimer = null
  }, RIPPLE_DECAY_MS)
}

function stopRipple() {
  if (activeRippleCount === 0) {
    scheduleRippleDecay()
    return
  }

  activeRippleCount = 0
  scheduleRippleDecay()
}

/**
 * Returns mouse event handlers that temporarily boost LabyrinthPhysic
 * wave amplitude when the user hovers over a UI element.
 *
 * setEnvironment now merges (Partial<EnvironmentSettings>) so
 * only waveAmplitude is touched — opacity/frequency are preserved.
 */
export function useWaveRipple() {
  const { environment, setEnvironment } = usePhysicsRegistry()

  useEffect(() => {
    latestAmplitude = environment.waveAmplitude ?? BASE_AMPLITUDE
  }, [environment.waveAmplitude])

  useEffect(() => {
    const onDocumentPointerMove = (event: PointerEvent) => {
      if (isOverFunctionalText(event.clientX, event.clientY)) {
        beginRipple()
        return
      }

      stopRipple()
    }

    if (documentListenerRefCount === 0) {
      document.addEventListener('pointermove', onDocumentPointerMove, true)
    }
    documentListenerRefCount += 1

    activeSetEnvironmentFns.add(setEnvironment)
    return () => {
      activeSetEnvironmentFns.delete(setEnvironment)
      documentListenerRefCount = Math.max(0, documentListenerRefCount - 1)

      if (activeSetEnvironmentFns.size === 0) {
        if (rippleDecayTimer) {
          clearTimeout(rippleDecayTimer)
          rippleDecayTimer = null
        }
        stopRipple()
      }

      if (documentListenerRefCount === 0) {
        document.removeEventListener('pointermove', onDocumentPointerMove, true)
      }
    }
  }, [setEnvironment])

  const onPointerEnter = useCallback(() => {
    // keep compatibility with current callsites; actual hover tracking is now document-level
  }, [])

  return { onPointerEnter, onTouchStart: onPointerEnter }
}
