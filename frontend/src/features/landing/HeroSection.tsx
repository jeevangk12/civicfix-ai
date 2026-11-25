import { Link } from 'react-router'
import { CityIllustration } from './CityIllustration'
import { Icon } from './Icon'

export function HeroSection() {
  return (
    <section className="hero" aria-labelledby="hero-title" data-enter>
      <div className="wrap hero-wrap">
        <div className="hero-copy">
          <p className="hero-kicker" data-animate="copy"><span aria-hidden="true" />Smarter communities start with your voice.</p>
          <h1 id="hero-title" data-animate="copy">
            Make Your City Better, <span>One Report at a Time.</span>
          </h1>
          <p className="hero-lead hero__lead" data-animate="copy">
            Report civic issues, track their progress, and help build cleaner, safer and smarter communities.
          </p>
          <div className="hero-actions" data-animate="copy">
            <Link className="button button-primary" to="/citizen/complaints/new">
              Report an Issue <Icon name="arrow" size={19} />
            </Link>
            <Link className="button button-secondary" to="/map">
              <Icon name="map" size={18} /> Explore Public Map
            </Link>
          </div>
        </div>
        <CityIllustration />
      </div>
    </section>
  )
}
