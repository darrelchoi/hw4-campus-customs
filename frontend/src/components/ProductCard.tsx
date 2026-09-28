import { Link } from 'react-router-dom'
import { formatPrice } from '../api'
import type { CardProduct } from '../types'

const LOW_TOTAL_STOCK = 15 // honest urgency: only shown when real stock is this low

export default function ProductCard({ product }: { product: CardProduct }) {
  const soldOut = product.total_stock === 0
  const low = !soldOut && product.total_stock <= LOW_TOTAL_STOCK

  return (
    <Link to={`/products/${product.product_id}`} className="card">
      <div className="card-image">
        <img src={product.image_url} alt={product.name} loading="lazy" />
        {soldOut && <span className="badge badge-out">Sold out</span>}
        {low && <span className="badge badge-low">Only {product.total_stock} left</span>}
        <span className="card-cta">View Details</span>
      </div>
      <div className="card-body">
        <p className="card-type">{product.garment_type}</p>
        <h3 className="card-title">{product.name}</h3>
        <p className="card-desc">{product.description}</p>
        <p className="card-price">{formatPrice(product.price)}</p>
      </div>
    </Link>
  )
}
