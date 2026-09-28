import { Link } from 'react-router-dom'

const FACTS = [
  { value: '1975', label: 'Serving Yale since' },
  { value: '57', label: 'Broadway, New Haven' },
  { value: '7', label: 'Days a week, doors open' },
]

export default function About() {
  return (
    <>
      <section className="page-hero">
        <div className="container">
          <p className="eyebrow">About Us</p>
          <h1>
            Five decades of <span className="accent">Bulldog blue</span> on Broadway.
          </h1>
          <p className="hero-lede">
            Campus Customs started on Broadway in 1975 and never left. We are the longest-running official Yale
            merchandise shop in New Haven, and still a neighborhood store at heart.
          </p>
        </div>
      </section>

      <section className="container section about-facts">
        {FACTS.map((f) => (
          <div key={f.label} className="fact">
            <p className="fact-value">{f.value}</p>
            <p className="muted">{f.label}</p>
          </div>
        ))}
      </section>

      <section className="container section about-grid">
        <article>
          <h2>Made down the block</h2>
          <p>
            Most of what we sell is printed or embroidered in our own workshop, which sits inside the old York Square
            Cinema building next door. Keeping production close means quicker turnarounds, sharper details, and a
            real person to talk to when you want something just right.
          </p>
        </article>
        <article>
          <h2>Something for every Eli</h2>
          <p>
            Students, alumni, parents, and the proud aunt who never misses a reunion all shop with us. You will find
            hoodies, crewnecks, tees, quarter-zips, and fleece, plus pieces for residential colleges, varsity sports,
            and the yearly showdown with Harvard.
          </p>
        </article>
        <article>
          <h2>Custom work</h2>
          <p>
            Teams, clubs, reunions, and offices come to us for screen printing, embroidery, and promotional items.
            Custom-made pieces are produced just for you, so they are final sale.
          </p>
        </article>
        <article>
          <h2>Returns &amp; help</h2>
          <p>
            Changed your mind? Unworn items with tags still attached can come back within 30 days of shipping. Reach
            our order team at <a href="mailto:orderdept@campuscustoms.com">orderdept@campuscustoms.com</a> or{' '}
            <a href="tel:+14753014205">(475) 301-4205</a>, or just ask the chat assistant.
          </p>
        </article>
      </section>

      <section className="container section cta">
        <h2>Come say hi, or shop from your dorm.</h2>
        <p className="muted">57 Broadway, New Haven, CT 06511 · Open 7 days a week</p>
        <Link to="/products" className="btn">
          Browse the shop
        </Link>
      </section>
    </>
  )
}
