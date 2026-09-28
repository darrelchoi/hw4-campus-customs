import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ALERTS_CHANGED_EVENT, fetchProduct, fetchRestockAlerts, formatPrice } from '../api'
import { useAuth } from '../auth'
import { useBag } from '../bag'
import { celebrate } from '../celebrate'
import { askChat } from '../components/ChatWidget'
import type { Product, RestockAlert } from '../types'

const LOW_STOCK = 5

function stockLabel(quantity: number) {
  if (quantity === 0) return { text: 'Sold out', cls: 'stock-out' }
  if (quantity <= LOW_STOCK) return { text: `Only ${quantity} left`, cls: 'stock-low' }
  return { text: `${quantity} in stock`, cls: 'stock-ok' }
}

export default function ProductDetail() {
  const { productId = '' } = useParams()
  const [product, setProduct] = useState<Product | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { user } = useAuth()
  const [alerts, setAlerts] = useState<RestockAlert[]>([])
  const { add } = useBag()
  const [size, setSize] = useState<string | null>(null)
  const [qty, setQty] = useState(1)
  const [added, setAdded] = useState(false)
  const [sizeHint, setSizeHint] = useState(false)
  const addRef = useRef<HTMLButtonElement>(null)

  // The shopper's restock alerts, refreshed when the chat saves a new one.
  useEffect(() => {
    if (!user) {
      setAlerts([])
      return
    }
    const load = () => fetchRestockAlerts().then(setAlerts).catch(() => setAlerts([]))
    load()
    window.addEventListener(ALERTS_CHANGED_EVENT, load)
    return () => window.removeEventListener(ALERTS_CHANGED_EVENT, load)
  }, [user])

  useEffect(() => {
    setProduct(null)
    setError(null)
    setSize(null)
    setQty(1)
    setAdded(false)
    fetchProduct(productId)
      .then(setProduct)
      .catch(() => setError('We could not find that product.'))
  }, [productId])

  if (error) {
    return (
      <section className="container section">
        <p className="error">{error}</p>
        <Link to="/products" className="link">
          ← Back to all products
        </Link>
      </section>
    )
  }

  if (!product) {
    return (
      <section className="container section">
        <p className="muted">Loading…</p>
      </section>
    )
  }

  const inventory = product.inventory ?? []
  const selected = inventory.find((s) => s.size === size)
  const maxQty = selected?.quantity ?? 1

  function addToBag() {
    if (!product || !selected) {
      setSizeHint(true)
      return
    }
    add(
      { product_id: product.product_id, name: product.name, image_url: product.image_url, price: product.price, size: selected.size, max_qty: selected.quantity },
      qty,
    )
    celebrate(addRef.current) // confetti + cha-ching
    setAdded(true)
    setTimeout(() => setAdded(false), 1800)
  }

  return (
    <section className="container section">
      <Link to="/products" className="link back-link">
        ← All products
      </Link>

      <div className="detail">
        <div className="detail-image">
          <img src={product.image_url} alt={product.name} />
        </div>

        <div className="detail-info">
          <p className="eyebrow">{product.garment_type}</p>
          <h1>{product.name}</h1>
          <p className="detail-price">{formatPrice(product.price)}</p>
          <p className="detail-desc">{product.description}</p>

          <h2 className="detail-heading">Colors</h2>
          <div className="chips">
            {product.colors.map((c) => (
              <span key={c} className="chip chip-static">
                {c}
              </span>
            ))}
          </div>

          <h2 className="detail-heading">
            Select size <span className="muted">({product.total_stock} in stock)</span>
          </h2>
          <div className="size-grid" role="radiogroup" aria-label="Size">
            {inventory.map((s) => {
              const label = stockLabel(s.quantity)
              const alertSet = alerts.some((a) => a.product_id === product.product_id && a.size === s.size)
              if (s.quantity === 0) {
                return (
                  <div key={s.size} className={`size ${label.cls}`}>
                    <span className="size-name">{s.size}</span>
                    <span className="size-stock">{label.text}</span>
                    {alertSet ? (
                      <span className="size-alert size-alert-set">🔔 Alert set</span>
                    ) : (
                      <button
                        className="size-alert"
                        onClick={() => askChat(`Please notify me when the ${product.name} is back in size ${s.size}.`)}
                      >
                        🔔 Notify me
                      </button>
                    )}
                  </div>
                )
              }
              return (
                <button
                  key={s.size}
                  role="radio"
                  aria-checked={size === s.size}
                  className={`size size-pick ${label.cls} ${size === s.size ? 'selected' : ''}`}
                  onClick={() => {
                    setSize(s.size)
                    setQty(1)
                    setSizeHint(false)
                  }}
                >
                  <span className="size-name">{s.size}</span>
                  <span className="size-stock">{label.text}</span>
                </button>
              )
            })}
          </div>

          {selected && selected.quantity <= LOW_STOCK && (
            <p className="urgency">🔥 Only {selected.quantity} left in {selected.size}. Real-time stock.</p>
          )}
          {sizeHint && <p className="form-error">Pick a size first.</p>}

          <div className="buy-row">
            <div className="qty qty-lg" aria-label="Quantity">
              <button onClick={() => setQty((q) => Math.max(1, q - 1))} disabled={qty <= 1} aria-label="Decrease quantity">
                −
              </button>
              <span>{qty}</span>
              <button
                onClick={() => setQty((q) => Math.min(maxQty, q + 1))}
                disabled={!selected || qty >= maxQty}
                aria-label="Increase quantity"
              >
                +
              </button>
            </div>
            <button
              ref={addRef}
              className={`btn btn-buy ${added ? 'btn-added' : ''}`}
              onClick={addToBag}
              disabled={product.total_stock === 0}
            >
              {product.total_stock === 0 ? 'Sold Out' : added ? '✓ Added to Bag!' : `Add to Bag · ${formatPrice(product.price * qty)}`}
            </button>
          </div>

          <button
            className="btn btn-outline detail-ask"
            onClick={() => askChat(`Tell me about the ${product.name}. What sizes are available?`)}
          >
            Ask the assistant about this item
          </button>

          {product.search_tags.length > 0 && (
            <p className="tags muted">Tags: {product.search_tags.join(' · ')}</p>
          )}
        </div>
      </div>
    </section>
  )
}
