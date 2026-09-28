import { useEffect, useRef } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useChatResults } from '../chatResults'
import ProductCard from './ProductCard'

export const RESULTS_ANCHOR = 'chat-results'

/** On-page grid of products the chat agent matched. Rendered above every page's content. */
export default function ChatResultsSection() {
  const { results, collapsed, setCollapsed, clear } = useChatResults()
  const { pathname } = useLocation()
  const ref = useRef<HTMLElement>(null)
  const onDetailPage = pathname.startsWith('/products/')

  // New results: scroll the grid into view.
  useEffect(() => {
    if (results) ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [results?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Opening a product's detail page tucks the grid away so the detail view is front and center.
  useEffect(() => {
    if (onDetailPage) setCollapsed(true)
  }, [pathname]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!results) return null

  const { title, products, totalMatches, searchQuery } = results
  const count =
    totalMatches && totalMatches > products.length
      ? `Showing ${products.length} of ${totalMatches} matches`
      : `${products.length} ${products.length === 1 ? 'match' : 'matches'}`

  return (
    <section
      id={RESULTS_ANCHOR}
      ref={ref}
      className={`chat-results ${collapsed ? 'chat-results-collapsed' : ''}`}
      aria-label="Products from your chat"
    >
      <div className="container">
        <div className="chat-results-head">
          <div>
            <p className="eyebrow">✨ From your chat</p>
            <h2 className="chat-results-title">{title}</h2>
            <p className="muted chat-results-meta">
              {count}
              {searchQuery && totalMatches && totalMatches > products.length && (
                <>
                  {' · '}
                  <Link to={`/products?q=${encodeURIComponent(searchQuery)}`} className="link">
                    See all in the shop →
                  </Link>
                </>
              )}
            </p>
          </div>
          <div className="chat-results-actions">
            <button className="btn btn-small btn-ghost" onClick={() => setCollapsed(!collapsed)} aria-expanded={!collapsed}>
              {collapsed ? `Show ${products.length}` : 'Hide'}
            </button>
            <button className="chat-results-clear" onClick={clear} aria-label="Clear chat results">
              ×
            </button>
          </div>
        </div>

        {!collapsed && (
          <div key={results.id} className="product-grid chat-results-grid">
            {products.map((p) => (
              <ProductCard key={p.product_id} product={p} />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
