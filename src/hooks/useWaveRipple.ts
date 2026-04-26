import { useCallback, useEffect, useRef } from 'react'
import { usePhysicsRegistry } from '../context/PhysicsContext'

const BASE_AMPLITUDE = 60
const RIPPLE_AMPLITUDE = 120
const RIPPLE_DECAY_MS = 600

/**
 * Global counter of active ripple timers across all useWaveRipple instances.
 * A decay only fires when no other component has a pending ripple,
 * preventing one component's timeout from cutting another's short.
 */
let activeRippleCount = 0
let rippleBaselineAmplitude: number | null = null

/**
 * Returns mouse event handlers that temporarily boost LabyrinthPhysic
 * wave amplitude when the user hovers over a UI element.
 *
 * setEnvironment now merges (Partial<EnvironmentSettings>) so
 * only waveAmplitude is touched — opacity/frequency are preserved.
 */
export function useWaveRipple() {
  const { environment, setEnvironment } = usePhysicsRegistry()
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
        activeRippleCount = Math.max(0, activeRippleCount - 1)
        if (activeRippleCount === 0) {
          setEnvironment({ waveAmplitude: rippleBaselineAmplitude ?? BASE_AMPLITUDE })
          rippleBaselineAmplitude = null
        }
        timerRef.current = null
      }
    }
  }, [setEnvironment])

  const onPointerEnter = useCallback(() => {
    // Clear any existing timer for this instance
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      activeRippleCount = Math.max(0, activeRippleCount - 1)
    }

    if (activeRippleCount === 0) {
      rippleBaselineAmplitude = environment.waveAmplitude ?? BASE_AMPLITUDE
    }
    activeRippleCount++
    setEnvironment({ waveAmplitude: RIPPLE_AMPLITUDE })

    timerRef.current = setTimeout(() => {
      activeRippleCount = Math.max(0, activeRippleCount - 1)
      timerRef.current = null
      // Only decay if no other component is mid-ripple
      if (activeRippleCount === 0) {
        setEnvironment({ waveAmplitude: rippleBaselineAmplitude ?? BASE_AMPLITUDE })
        rippleBaselineAmplitude = null
      }
    }, RIPPLE_DECAY_MS)
  }, [environment.waveAmplitude, setEnvironment])

  return { onPointerEnter, onTouchStart: onPointerEnter }
}
