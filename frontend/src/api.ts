import type {
  ChatApiResponse,
  ChatMessage,
  HistoryMessage,
  PageContext,
  PageResults,
  Product,
  RestockAlert,
  SignupInput,
  User,
} from './types'

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

async function postJson<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Something went wrong. Please try again.')
  return data as T
}

// ---------- accounts (session lives in an HttpOnly cookie set by the backend) ----------

export async function fetchMe(): Promise<User | null> {
  return (await getJson<{ user: User | null }>('/api/auth/me')).user
}

export async function login(email: string, password: string): Promise<User> {
  return (await postJson<{ user: User }>('/api/auth/login', { email, password })).user
}

export async function signup(input: SignupInput): Promise<User> {
  return (await postJson<{ user: User }>('/api/auth/signup', input)).user
}

export async function logout(): Promise<void> {
  await postJson('/api/auth/logout')
}

// ---------- catalogue ----------

export function fetchProducts(): Promise<Product[]> {
  return getJson<Product[]>('/api/products')
}

export function fetchProduct(productId: string): Promise<Product> {
  return getJson<Product>(`/api/products/${encodeURIComponent(productId)}`)
}

let resultsSeq = 0

/** Turns products + grid metadata from the API into the on-page "From your chat" results. */
function toPageResults(
  data: Pick<ChatApiResponse, 'products' | 'results_title' | 'search_query' | 'total_matches'>,
  question: string,
): PageResults | undefined {
  if (data.products.length === 0) return undefined
  return {
    id: Date.now() * 1000 + (resultsSeq++ % 1000),
    title: data.results_title ?? 'From your chat',
    products: data.products,
    searchQuery: data.search_query,
    totalMatches: data.total_matches,
    question,
  }
}

/**
 * Sends the newest user message to the FastAPI shop agent.
 * `history` is the whole conversation including the new message (last item). Guests send it along;
 * for logged-in shoppers the backend ignores it and uses their saved history from the database.
 */
export async function sendChat(history: ChatMessage[], page: PageContext, loggedIn: boolean): Promise<ChatMessage> {
  const last = history[history.length - 1]
  const earlier = loggedIn
    ? []
    : history.slice(0, -1).map(({ role, content, products }) => ({
        role,
        content,
        product_ids: (products ?? []).map((p) => p.product_id),
      }))
  const data = await postJson<ChatApiResponse>('/api/chat', { message: last.content, history: earlier, page })
  return {
    role: 'assistant',
    content: data.reply,
    products: data.products,
    results: toPageResults(data, last.content),
    alerts: data.alerts_created,
  }
}

/**
 * Streaming version of sendChat (POST /api/chat/stream, Server-Sent Events).
 * Calls onStatus with each progress step ("Checking live stock…"), resolves with the verified reply.
 * Falls back to the regular endpoint if streaming isn't available.
 */
export async function streamChat(
  history: ChatMessage[],
  page: PageContext,
  loggedIn: boolean,
  onStatus: (text: string) => void,
): Promise<ChatMessage> {
  const last = history[history.length - 1]
  const earlier = loggedIn
    ? []
    : history.slice(0, -1).map(({ role, content, products }) => ({
        role,
        content,
        product_ids: (products ?? []).map((p) => p.product_id),
      }))
  const res = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify({ message: last.content, history: earlier, page }),
  })
  if (!res.ok || !res.body) {
    if (res.status === 422) {
      const data = await res.json().catch(() => ({}))
      throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check your message and try again.')
    }
    return sendChat(history, page, loggedIn)
  }

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    // SSE frames are separated by a blank line: "event: x\ndata: {...}\n\n"
    let sep
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      const event = frame.match(/^event: (.*)$/m)?.[1]
      const data = JSON.parse(frame.match(/^data: (.*)$/m)?.[1] ?? '{}')
      if (event === 'status') onStatus(data.text)
      else if (event === 'error') throw new Error(data.detail)
      else if (event === 'done') {
        const reply = data as ChatApiResponse
        return {
          role: 'assistant',
          content: reply.reply,
          products: reply.products,
          results: toPageResults(reply, last.content),
          alerts: reply.alerts_created,
        }
      }
    }
  }
  throw new Error('The connection closed before the answer arrived. Please try again.')
}

/**
 * The logged-in shopper's saved chat, oldest first ([] for guests), plus any restock alerts
 * whose size is back in stock since their last visit (each is reported once).
 */
export async function fetchChatHistory(): Promise<{ messages: ChatMessage[]; restocked: RestockAlert[] }> {
  const data = await getJson<{ logged_in: boolean; messages: HistoryMessage[]; restocked: RestockAlert[] }>(
    '/api/chat/history',
  )
  let lastQuestion = ''
  const messages = data.messages.map((m): ChatMessage => {
    if (m.role === 'user') lastQuestion = m.content
    return { role: m.role, content: m.content, products: m.products, results: toPageResults(m, lastQuestion) }
  })
  return { messages, restocked: data.restocked ?? [] }
}

/** The logged-in shopper's active restock alerts ([] for guests). */
export function fetchRestockAlerts(): Promise<RestockAlert[]> {
  return getJson<RestockAlert[]>('/api/restock-alerts')
}

/** Fired when the chat saves an alert, so open product pages can refresh their size tiles. */
export const ALERTS_CHANGED_EVENT = 'cc:alerts-changed'

export async function clearChatHistory(): Promise<void> {
  const res = await fetch('/api/chat/history', { method: 'DELETE', credentials: 'same-origin' })
  if (!res.ok) throw new Error('Could not clear your chat. Please try again.')
}

export function formatPrice(price: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(price)
}

/** Groups the catalogue's inconsistent garment_type values into shopper-facing categories. */
export const CATEGORIES = [
  { key: 'hoodies', label: 'Hoodies', match: (t: string) => t.includes('hood') },
  { key: 'crewnecks', label: 'Crewnecks', match: (t: string) => t.includes('crewneck') && !t.includes('t-shirt') },
  { key: 'tees', label: 'T-Shirts', match: (t: string) => t.includes('t-shirt') },
  { key: 'quarter-zips', label: 'Quarter-Zips', match: (t: string) => t.includes('quarter-zip') },
  { key: 'jackets', label: 'Fleece & Jackets', match: (t: string) => t.includes('fleece') || t.includes('jacket') },
  // Catch-all for performance shirts, mocknecks, etc. Must stay last.
  { key: 'more', label: 'More Tops', match: () => true },
] as const

export function categoryOf(garmentType: string): string {
  const t = garmentType.toLowerCase()
  return CATEGORIES.find((c) => c.match(t))!.key
}
