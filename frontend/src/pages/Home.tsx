import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CATEGORIES, categoryOf, fetchProducts } from '../api'
import { askChat } from '../components/ChatWidget'
import ProductCard from '../components/ProductCard'
import type { Product } from '../types'

// Rotating hero, like the content slider on campuscustoms.com. Images are real catalogue photos.
const SLIDES = [
  {
    eyebrow: 'The Hoodie Shop',
    title: 'Built for late nights at Sterling',
    text: 'Heavyweight Yale hoodies, printed and stitched down the block on Broadway.',
    cta: 'Shop Hoodies',
    to: '/products?category=hoodies',
    image: '/media/products/basic-hoodie-big-yale.jpg',
  },
  {
    eyebrow: 'Game Day',
    title: 'Loud enough for The Game',
    text: 'Harvard–Yale tees and team gear for the stands, the tailgate, and the bragging rights after.',
    cta: 'Shop T-Shirts',
    to: '/products?category=tees',
    image: '/media/products/2025-yale-vs-harvard-t-shirt.jpg',
  },
  {
    eyebrow: 'Layer Up',
    title: 'New Haven winters, handled',
    text: 'Fleece, quarter-zips, and jackets that go from Cross Campus to the office.',
    cta: 'Shop Fleece & Jackets',
    to: '/products?category=jackets',
    image: '/media/products/benjamin-franklin-fleece-jacket.jpg',
  },
]
const SLIDE_MS = 6000

const HIGHLIGHTS = [
  { icon: '🧵', title: 'Made on Broadway', text: 'Screen printing and embroidery happen in-house, a short walk from Old Campus.' },
  { icon: '🎓', title: 'Officially licensed', text: 'Real Yale marks on gear built to outlast your four years (and then some).' },
  { icon: '📦', title: 'Real-time stock', text: 'Every size shows live stock, so you know what is on the shelf before you ask.' },
]

function HeroSlider() {
  const [index, setIndex] = useState(0)
  const [paused, setPaused] = useState(false)

  useEffect(() => {
    if (paused || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const t = setInterval(() => setIndex((i) => (i + 1) % SLIDES.length), SLIDE_MS)
    return () => clearInterval(t)
  }, [paused])

  return (
    <section
      className="hero"
      aria-roledescription="carousel"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      {SLIDES.map((s, i) => (
        <div key={s.title} className={`slide ${i === index ? 'active' : ''}`} aria-hidden={i !== index}>
          <div className="container slide-inner">
            <div className="slide-copy">
              <p className="eyebrow eyebrow-light">{s.eyebrow}</p>
              <h1>{s.title}</h1>
              <p className="hero-lede">{s.text}</p>
              <div className="hero-actions">
                <Link to={s.to} className="btn btn-light" tabIndex={i === index ? 0 : -1}>
                  {s.cta}
                </Link>
                <button
                  className="btn btn-outline-light"
                  onClick={() => askChat('What should I wear to The Game?')}
                  tabIndex={i === index ? 0 : -1}
                >
                  Ask our assistant
                </button>
              </div>
            </div>
            <div className="slide-art">
              <img src={s.image} alt="" />
            </div>
          </div>
        </div>
      ))}
      <div className="slide-dots">
        {SLIDES.map((s, i) => (
          <button
            key={s.title}
            className={i === index ? 'active' : ''}
            onClick={() => setIndex(i)}
            aria-label={`Show slide ${i + 1}: ${s.eyebrow}`}
          />
        ))}
      </div>
    </section>
  )
}

export default function Home() {
  const [products, setProducts] = useState<Product[]>([])

  useEffect(() => {
    fetchProducts().then(setProducts).catch(() => setProducts([]))
  }, [])

  // One in-stock pick per category, then fill up to 8.
  const featured = (() => {
    const inStock = products.filter((p) => p.total_stock > 0)
    const picks = CATEGORIES.map((c) => inStock.find((p) => categoryOf(p.garment_type) === c.key)).filter(
      (p): p is Product => Boolean(p),
    )
    for (const p of inStock) {
      if (picks.length >= 8) break
      if (!picks.includes(p)) picks.push(p)
    }
    return picks.slice(0, 8)
  })()

  const categoryImage = (key: string) => products.find((p) => categoryOf(p.garment_type) === key)?.image_url

  return (
    <>
      <HeroSlider />

      <section className="trust-strip">
        <div className="container trust-inner">
          {HIGHLIGHTS.map((h) => (
            <div key={h.title} className="trust-item">
              <span className="trust-icon">{h.icon}</span>
              <div>
                <p className="trust-title">{h.title}</p>
                <p className="trust-text">{h.text}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="container section">
        <h2 className="section-title">Shop by Category</h2>
        <div className="category-grid">
          {CATEGORIES.map((c) => (
            <Link key={c.key} to={`/products?category=${c.key}`} className="category-tile">
              <span className="category-img">{categoryImage(c.key) && <img src={categoryImage(c.key)} alt="" loading="lazy" />}</span>
              <span className="category-label">{c.label}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="container section">
        <h2 className="section-title">Prime Selections</h2>
        <p className="section-sub">Fresh off the press and in stock now</p>
        <div className="product-grid">
          {featured.map((p) => (
            <ProductCard key={p.product_id} product={p} />
          ))}
        </div>
        <div className="center">
          <Link to="/products" className="btn btn-outline">
            View All Products
          </Link>
        </div>
      </section>

      <section className="story">
        <div className="container story-inner">
          <p className="eyebrow">Think tradition</p>
          <h2>A family shop on Broadway since 1975</h2>
          <p>
            Campus Customs has outfitted Yale students, alumni, and families for five decades, with most of it printed
            and embroidered in our own workshop next door. Stop by, or let our assistant find your size in seconds.
          </p>
          <Link to="/about" className="btn btn-light">
            Our Story
          </Link>
        </div>
      </section>
    </>
  )
}
