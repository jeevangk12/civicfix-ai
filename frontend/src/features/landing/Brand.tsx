import { Link } from 'react-router'

export function Brand() {
  return <Link className="brand nav__logo" to="/" aria-label="CivicFix AI home">
    <img src="/civicfix-mark.svg" alt="" width="42" height="42" />
    <span>CivicFix <span className="brand-ai">AI</span></span>
  </Link>
}
