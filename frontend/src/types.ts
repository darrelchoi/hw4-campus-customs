export interface SizeStock {
  size: string
  quantity: number
}

export interface Product {
  product_id: string
  name: string
  garment_type: string
  description: string
  colors: string[]
  search_tags: string[]
  image_file_path: string
  image_url: string
  price: number
  total_stock: number
  inventory?: SizeStock[]
}

/** Product card returned by the chat agent (always rebuilt from the DB by the backend). */
export interface ChatProduct {
  product_id: string
  name: string
  garment_type: string
  description: string
  price: number
  colors: string[]
  image_url: string
  total_stock: number
  inventory: SizeStock[]
}

/** What a product card needs; both catalogue products and chat products satisfy it. */
export type CardProduct = Pick<
  Product,
  'product_id' | 'name' | 'garment_type' | 'description' | 'price' | 'image_url' | 'total_stock'
>

/** A restock alert for a sold-out size (backend RestockAlert). */
export interface RestockAlert {
  product_id: string
  name: string
  size: string
  created_at: string
  current_quantity: number
  back_in_stock: boolean
}

/** POST /api/chat response (backend/models.py ChatResponse). */
export interface ChatApiResponse {
  reply: string
  products: ChatProduct[]
  results_title: string | null
  search_query: string | null
  total_matches: number | null
  alerts_created: RestockAlert[]
}

/** GET /api/chat/history message (cards rebuilt from live data by the backend). */
export interface HistoryMessage {
  role: 'user' | 'assistant'
  content: string
  created_at: string
  products: ChatProduct[]
  results_title: string | null
  search_query: string | null
  total_matches: number | null
}

/** Sent with every chat message so the agent knows what "this" means (backend PageContext). */
export interface PageContext {
  path: string
  page_type: 'home' | 'products' | 'product' | 'about' | 'login' | 'create-account' | 'other'
  product_id?: string
  search_query?: string
  category?: string
}

/** Chat matches currently shown in the on-page "From your chat" grid. */
export interface PageResults {
  id: number
  title: string
  products: ChatProduct[]
  searchQuery: string | null
  totalMatches: number | null
  question: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  products?: ChatProduct[]
  results?: PageResults
  /** Restock alerts saved by this reply (confirmation chips). */
  alerts?: RestockAlert[]
  /** Product links for UI-only notices (e.g. "it's back in stock"). */
  links?: { to: string; label: string }[]
  /** UI-only (greeting, errors, notices): shown in the panel but never sent to the agent. */
  local?: boolean
}

export interface User {
  user_id: number
  first_name: string
  last_name: string
  email: string
  member_since: string
}

export interface SignupInput {
  first_name: string
  last_name: string
  email: string
  password: string
  confirm_password: string
}
