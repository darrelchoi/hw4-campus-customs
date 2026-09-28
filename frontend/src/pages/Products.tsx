import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CATEGORIES, categoryOf, fetchProducts } from '../api'
import ProductCard from '../components/ProductCard'
import type { Product } from '../types'

export default function Products() {
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [params, setParams] = useSearchParams()
  const category = params.get('category') ?? 'all'
  const query = params.get('q') ?? ''

  useEffect(() => {
    fetchProducts()
      .then(setProducts)
      .catch(() => setError('Could not load products. Is the backend running on port 8000?'))
      .finally(() => setLoading(false))
  }, [])

  function update(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value && value !== 'all') next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return products.filter((p) => {
      if (category !== 'all' && categoryOf(p.garment_type) !== category) return false
      if (!q) return true
      return [p.name, p.garment_type, p.description, ...p.colors, ...p.search_tags].some((s) =>
        s.toLowerCase().includes(q),
      )
    })
  }, [products, category, query])

  return (
    <section className="container section">
      <div className="section-head">
        <div>
          <p className="eyebrow">The Shop</p>
          <h1>All products</h1>
        </div>
        <input
          className="search"
          type="search"
          placeholder="Search hoodies, hockey, bulldog…"
          value={query}
          onChange={(e) => update('q', e.target.value)}
          aria-label="Search products"
        />
      </div>

      <div className="chips" role="tablist" aria-label="Categories">
        {[{ key: 'all', label: 'All' }, ...CATEGORIES].map((c) => (
          <button
            key={c.key}
            role="tab"
            aria-selected={category === c.key}
            className={`chip ${category === c.key ? 'chip-active' : ''}`}
            onClick={() => update('category', c.key)}
          >
            {c.label}
          </button>
        ))}
      </div>

      {loading && <p className="muted">Loading the racks…</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && (
        <>
          <p className="muted result-count">
            {visible.length} {visible.length === 1 ? 'item' : 'items'}
          </p>
          <div className="product-grid">
            {visible.map((p) => (
              <ProductCard key={p.product_id} product={p} />
            ))}
          </div>
          {visible.length === 0 && <p className="muted">No matches. Try a different search or category.</p>}
        </>
      )}
    </section>
  )
}
