import type { PageContext } from './types'

/** Describes the current page for the chat agent (see backend PageContext). */
export function pageContextFor(pathname: string, search: string): PageContext {
  const params = new URLSearchParams(search)
  const productMatch = pathname.match(/^\/products\/([^/]+)$/)
  if (productMatch) {
    return { path: pathname, page_type: 'product', product_id: decodeURIComponent(productMatch[1]) }
  }
  if (pathname === '/products') {
    return {
      path: pathname + search,
      page_type: 'products',
      search_query: params.get('q') || undefined,
      category: params.get('category') || undefined,
    }
  }
  const byPath: Record<string, PageContext['page_type']> = {
    '/': 'home',
    '/about': 'about',
    '/login': 'login',
    '/create-account': 'create-account',
  }
  return { path: pathname, page_type: byPath[pathname] ?? 'other' }
}
