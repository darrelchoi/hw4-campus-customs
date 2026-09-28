import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <section className="container section cta">
      <h1>Page not found</h1>
      <p className="muted">That page wandered off campus.</p>
      <Link to="/" className="btn">
        Back home
      </Link>
    </section>
  )
}
