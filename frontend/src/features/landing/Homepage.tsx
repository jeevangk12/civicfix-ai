import { useRef } from 'react'
import { HeroSection } from './HeroSection'
import { Icon, type IconName } from './Icon'
import { gsap, useGSAP } from './motion'
import { Navbar } from './Navbar'

const steps: { title: string; text: string; icon: IconName }[] = [
  { title: 'Report an issue', text: 'Describe what you spotted and mark where it happened.', icon: 'report' },
  { title: 'Review and assignment', text: 'Authorized staff review the report and route it to the responsible team.', icon: 'review' },
  { title: 'Follow its progress', text: 'Use the tracking reference to check the status and read shared updates.', icon: 'track' },
]

export function Homepage() {
  const page = useRef<HTMLDivElement>(null)

  useGSAP(() => {
    const motion = gsap.matchMedia()
    motion.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.timeline({ defaults: { ease: 'power2.out' } })
        .from('[data-animate="nav"]', { opacity: 0, y: -9, duration: 0.42 })
        .from('[data-animate="copy"]', { opacity: 0, y: 16, duration: 0.53, stagger: 0.085 }, 0.14)
        .from('[data-animate="city"]', { opacity: 0, y: 10, duration: 0.7 }, 0.24)
    })
    return () => motion.revert()
  }, { scope: page })

  return (
    <div className="homepage" ref={page}>
      <Navbar />
      <main id="main-content" tabIndex={-1}>
        <HeroSection />
        <section className="how-section" id="how-it-works" aria-labelledby="how-title" tabIndex={-1}>
          <div className="wrap">
            <h2 id="how-title">How It Works</h2>
            <p className="how-lead">From spotting an issue to following the repair.</p>
            <ol className="steps">
              {steps.map(({ title, text, icon }) => (
                <li className="step card" key={title}>
                  <span className="step-icon"><Icon name={icon} size={25} /></span>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>
      </main>
      <footer className="site-footer footer">
        <div className="wrap footer-wrap">
          <p>CivicFix AI is a civic issue reporting and tracking platform prototype. It is not an emergency-response service. For emergencies, contact the appropriate official emergency services.</p>
        </div>
      </footer>
    </div>
  )
}
