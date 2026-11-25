import { Component, lazy, Suspense, useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { Icon } from './Icon'
import { sceneIssues } from './sceneIssues'

const SmartCityScene = lazy(() => import('./SmartCityScene'))

function useMediaQuery(query: string) {
  const subscribe = useCallback((notify: () => void) => {
    const media = window.matchMedia(query)
    media.addEventListener('change', notify)
    return () => media.removeEventListener('change', notify)
  }, [query])
  return useSyncExternalStore(subscribe, () => window.matchMedia(query).matches, () => false)
}

function subscribeVisibility(notify: () => void) {
  document.addEventListener('visibilitychange', notify)
  return () => document.removeEventListener('visibilitychange', notify)
}

function supportsWebGL() {
  try {
    const context = document.createElement('canvas').getContext('webgl2')
    context?.getExtension('WEBGL_lose_context')?.loseContext()
    return Boolean(context)
  } catch {
    return false
  }
}

class SceneBoundary extends Component<{ children: ReactNode; onUnavailable: () => void }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch() {
    this.props.onUnavailable()
  }

  render() {
    return this.state.failed ? null : this.props.children
  }
}

export function CityIllustration() {
  const visual = useRef<HTMLDivElement>(null)
  const checked = useRef(false)
  const [requested, setRequested] = useState(false)
  const [visible, setVisible] = useState(false)
  const [ready, setReady] = useState(false)
  const [failed, setFailed] = useState(false)
  const [paused, setPaused] = useState(false)
  const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')
  const compact = useMediaQuery('(max-width: 720px)')
  const pageVisible = useSyncExternalStore(subscribeVisibility, () => !document.hidden, () => true)
  const markReady = useCallback(() => setReady(true), [])
  const markUnavailable = useCallback(() => setFailed(true), [])

  useEffect(() => {
    const element = visual.current
    if (!element || reducedMotion || !('IntersectionObserver' in window)) return
    const observer = new IntersectionObserver(([entry]) => {
      setVisible(entry.isIntersecting)
      if (!entry.isIntersecting || checked.current) return
      checked.current = true
      if (supportsWebGL()) setRequested(true)
      else markUnavailable()
    }, { threshold: 0.1 })
    observer.observe(element)
    return () => observer.disconnect()
  }, [markUnavailable, reducedMotion])

  const showScene = requested && !failed && !reducedMotion
  const frameReady = ready && showScene

  return (
    <div className="city-stage hero__media" data-animate="city">
      <div className="city-toolbar">
        <p className="city-label"><Icon name="pin" size={15} /> Illustrative city</p>
        {frameReady && (
          <button type="button" className="icon-button motion-toggle" onClick={() => setPaused(!paused)}
            aria-label={paused ? 'Play city animation' : 'Pause city animation'}
            title={paused ? 'Play city animation' : 'Pause city animation'}>
            <Icon name={paused ? 'play' : 'pause'} size={17} />
          </button>
        )}
      </div>
      <div ref={visual} className="city-visual" data-visual data-mode={frameReady ? 'live' : 'still'}>
        <img className="city-poster" src="/city-poster.webp" width="1014" height="859" fetchPriority="high"
          alt="Isometric miniature city with roads, buildings, trees and example civic issue markers." />
        {showScene && (
          <div className="city-render" aria-hidden="true">
            <SceneBoundary onUnavailable={markUnavailable}>
              <Suspense fallback={null}>
                <SmartCityScene compact={compact} animate={visible && pageVisible && !paused}
                  onReady={markReady} onUnavailable={markUnavailable} />
              </Suspense>
            </SceneBoundary>
          </div>
        )}
      </div>
      <ul className="city-legend" aria-label="Illustrative issue categories">
        {sceneIssues.map(({ icon, label, color }) => (
          <li key={label} style={{ '--issue-color': color } as CSSProperties}>
            <Icon name={icon} size={16} /> {label}
          </li>
        ))}
      </ul>
    </div>
  )
}
