import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { formatPrice } from '../api'
import { useBag } from '../bag'
import { celebrate } from '../celebrate'

/** Slide-in mini bag. Checkout is a clearly labeled demo: no payment is taken and nothing is ordered. */
export default function BagDrawer() {
  const { items, count, subtotal, open, setOpen, setQty, remove, clear } = useBag()
  const [done, setDone] = useState(false)
  const checkoutRef = useRef<HTMLButtonElement>(null)

  function checkout() {
    celebrate(checkoutRef.current, true)
    setDone(true)
    clear()
  }

  function close() {
    setOpen(false)
    setDone(false)
  }

  return (
    <>
      <div className={`bag-backdrop ${open ? 'show' : ''}`} onClick={close} />
      <aside className={`bag-drawer ${open ? 'open' : ''}`} aria-label="Shopping bag" aria-hidden={!open}>
        <header className="bag-head">
          <h2>Your Bag {count > 0 && <span className="bag-head-count">({count})</span>}</h2>
          <button className="bag-close" onClick={close} aria-label="Close bag">
            ×
          </button>
        </header>

        {done ? (
          <div className="bag-done">
            <p className="bag-done-icon">🎉</p>
            <h3>Boola Boola, you're all set!</h3>
            <p className="muted">
              This is a class demo, so no payment was taken and no order was placed. To buy for real, visit us at 57
              Broadway or email orderdept@campuscustoms.com.
            </p>
            <button className="btn" onClick={close}>
              Keep shopping
            </button>
          </div>
        ) : items.length === 0 ? (
          <div className="bag-empty">
            <p>Your bag is empty.</p>
            <Link to="/products" className="btn" onClick={close}>
              Shop all gear
            </Link>
          </div>
        ) : (
          <>
            <ul className="bag-items">
              {items.map((i) => (
                <li key={`${i.product_id}-${i.size}`} className="bag-item">
                  <Link to={`/products/${i.product_id}`} onClick={close} className="bag-item-img">
                    <img src={i.image_url} alt="" />
                  </Link>
                  <div className="bag-item-info">
                    <Link to={`/products/${i.product_id}`} onClick={close} className="bag-item-name">
                      {i.name}
                    </Link>
                    <p className="bag-item-meta">Size {i.size}</p>
                    <div className="bag-item-row">
                      <div className="qty">
                        <button onClick={() => setQty(i.product_id, i.size, i.qty - 1)} disabled={i.qty <= 1} aria-label="Decrease">
                          −
                        </button>
                        <span>{i.qty}</span>
                        <button
                          onClick={() => setQty(i.product_id, i.size, i.qty + 1)}
                          disabled={i.qty >= i.max_qty}
                          aria-label="Increase"
                        >
                          +
                        </button>
                      </div>
                      <span className="bag-item-price">{formatPrice(i.price * i.qty)}</span>
                    </div>
                    {i.qty >= i.max_qty && <p className="bag-item-limit">That's all we have in {i.size}.</p>}
                    <button className="bag-remove" onClick={() => remove(i.product_id, i.size)}>
                      Remove
                    </button>
                  </div>
                </li>
              ))}
            </ul>
            <footer className="bag-foot">
              <div className="bag-subtotal">
                <span>Subtotal</span>
                <strong>{formatPrice(subtotal)}</strong>
              </div>
              <button ref={checkoutRef} className="btn btn-block btn-checkout" onClick={checkout}>
                Checkout (demo)
              </button>
              <p className="bag-note">Demo store: no payment is taken.</p>
            </footer>
          </>
        )}
      </aside>
    </>
  )
}
