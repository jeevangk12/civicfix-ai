import { useRef, useState } from 'react'
import { Link } from 'react-router'
import { Brand } from './Brand'
import { Icon } from './Icon'

export function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuButton = useRef<HTMLButtonElement>(null)

  return (
    <header className="site-header nav" data-animate="nav" onKeyDown={(event) => {
      if (event.key === 'Escape' && menuOpen) {
        setMenuOpen(false)
        menuButton.current?.focus()
      }
    }}>
      <div className="wrap nav-wrap">
        <a className="skip-link" href="#main-content">Skip to content</a>
        <Brand />
        <button className="menu-toggle nav__toggle icon-button" type="button" ref={menuButton}
          aria-expanded={menuOpen} aria-controls="primary-navigation"
          aria-label={menuOpen ? 'Close navigation' : 'Open navigation'}
          onClick={() => setMenuOpen(!menuOpen)}>
          <Icon name={menuOpen ? 'close' : 'menu'} />
        </button>
        <nav className="site-nav" id="primary-navigation" aria-label="Main navigation" data-open={menuOpen}>
          <div className="nav-links">
            <a href="#how-it-works" onClick={() => setMenuOpen(false)}>How It Works</a>
            <Link to="/map" onClick={() => setMenuOpen(false)}>Public Map</Link>
            <Link to="/login" onClick={() => setMenuOpen(false)}>Login</Link>
          </div>
          <Link className="button button-primary nav-cta" to="/citizen/complaints/new" onClick={() => setMenuOpen(false)}>
            Get Started <Icon name="arrow" size={17} />
          </Link>
        </nav>
      </div>
    </header>
  )
}
