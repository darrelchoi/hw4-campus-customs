import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { useBag } from '../bag'
import { isMuted, setMuted } from '../celebrate'

// Main pages (Problem 3) first, then shop-by-category links like the Campus Customs menu bar.
const MAIN = [
  { to: '/', label: 'Home', end: true },
  { to: '/products', label: 'Products', end: true },
]
const CATEGORIES = [
  { key: 'hoodies', label: 'Hoodies' },
  { key: 'crewnecks', label: 'Crewnecks' },
  { key: 'tees', label: 'T-Shirts' },
  { key: 'quarter-zips', label: 'Quarter-Zips' },
  { key: 'jackets', label: 'Fleece & Jackets' },
]

export default function NavBar() {
  const [open, setOpen] = useState(false)
  const [muted, setMutedState] = useState(isMuted)
  const [query, setQuery] = useState('')
  const { user, loading, logout } = useAuth()
  const { count, bump, setOpen: openBag } = useBag()
  const navigate = useNavigate()
  const { search } = useLocation()
  const activeCategory = new URLSearchParams(search).get('category')
  const close = () => setOpen(false)

  // Replay the bag badge "pop" every time something is added.
  const [pop, setPop] = useState(false)
  useEffect(() => {
    if (!bump) return
    setPop(true)
    const t = setTimeout(() => setPop(false), 600)
    return () => clearTimeout(t)
  }, [bump])

  async function handleLogout() {
    close()
    await logout()
    navigate('/login', { state: { signedOut: true } })
  }

  function handleSearch(e: FormEvent) {
    e.preventDefault()
    const q = query.trim()
    navigate(q ? `/products?q=${encodeURIComponent(q)}` : '/products')
    close()
  }

  function toggleSound() {
    setMuted(!muted)
    setMutedState(!muted)
  }

  return (
    <header className="nav">
      <div className="utility-bar">
        <div className="container utility-inner">
          <span>Officially licensed Yale apparel · Printed &amp; stitched on Broadway since 1975</span>
          <span className="utility-right">57 Broadway, New Haven · Open 7 days</span>
        </div>
      </div>

      <div className="brand-bar">
        <div className="container brand-inner">
          <button className="nav-toggle" aria-label="Toggle menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
            ☰
          </button>
          <Link to="/" className="brand" onClick={close}>
            <span className="brand-mark">CC</span>
            <span className="brand-text">
              Campus Customs
              <small>Yale Bulldog Gear · Est. 1975</small>
            </span>
          </Link>

          <form className="header-search" onSubmit={handleSearch} role="search">
            <input
              type="search"
              placeholder="Search hoodies, hockey, bulldog…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Search products"
            />
            <button type="submit" aria-label="Search">
              ⌕
            </button>
          </form>

          <div className="header-actions">
            {!loading && user && (
              <>
                <span className="nav-user">Hi, {user.first_name}</span>
                <button className="header-link" onClick={handleLogout}>
                  Log Out
                </button>
              </>
            )}
            {!loading && !user && (
              <>
                <NavLink to="/login" className="header-link" onClick={close}>
                  Log In
                </NavLink>
                <NavLink to="/create-account" className="header-link header-link-strong" onClick={close}>
                  Create Account
                </NavLink>
              </>
            )}
            <button
              className="icon-btn"
              onClick={toggleSound}
              aria-label={muted ? 'Turn sounds on' : 'Turn sounds off'}
              title={muted ? 'Sounds off' : 'Sounds on'}
            >
              {muted ? '🔇' : '🔊'}
            </button>
            <button className={`bag-btn ${pop ? 'pop' : ''}`} onClick={() => openBag(true)} aria-label={`Bag, ${count} items`}>
              <span className="bag-icon">🛍</span>
              <span className="bag-label">Bag</span>
              {count > 0 && <span className="bag-count">{count}</span>}
            </button>
          </div>
        </div>
      </div>

      <nav className={`menu-bar ${open ? 'open' : ''}`} aria-label="Main">
        <ul className="container menu-inner">
          {MAIN.map((l) => (
            <li key={l.to}>
              <NavLink to={l.to} end={l.end} onClick={close} className={({ isActive }) => (isActive && !search ? 'active' : '')}>
                {l.label}
              </NavLink>
            </li>
          ))}
          {CATEGORIES.map((c) => (
            <li key={c.key}>
              <Link
                to={`/products?category=${c.key}`}
                onClick={close}
                className={activeCategory === c.key ? 'active' : ''}
              >
                {c.label}
              </Link>
            </li>
          ))}
          <li>
            <NavLink to="/about" onClick={close}>
              About Us
            </NavLink>
          </li>
          {!loading && !user && (
            <>
              <li className="menu-mobile-only">
                <NavLink to="/login" onClick={close}>
                  Log In
                </NavLink>
              </li>
              <li className="menu-mobile-only">
                <NavLink to="/create-account" onClick={close}>
                  Create Account
                </NavLink>
              </li>
            </>
          )}
        </ul>
      </nav>
    </header>
  )
}
