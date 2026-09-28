import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import Markdown from 'react-markdown'
import { Link, useLocation } from 'react-router-dom'
import { ALERTS_CHANGED_EVENT, clearChatHistory, fetchChatHistory, formatPrice, streamChat } from '../api'
import { useAuth } from '../auth'
import { useChatResults } from '../chatResults'
import { pageContextFor } from '../pageContext'
import { RESULTS_ANCHOR } from './ChatResultsSection'
import type { ChatMessage, ChatProduct, PageResults, RestockAlert } from '../types'

/** Other components can open the chat with a prefilled question via this event. */
export const ASK_EVENT = 'cc:ask'

export function askChat(question: string) {
  window.dispatchEvent(new CustomEvent<string>(ASK_EVENT, { detail: question }))
}

function greeting(firstName?: string, returning = false): ChatMessage {
  const content = firstName
    ? returning
      ? `Welcome back, ${firstName}! Your earlier chat is below. What can I help you find today?`
      : `Hey ${firstName}! I'm the Campus Customs shop assistant. Ask me about sizes, prices, or what to wear to The Game.`
    : "Hey there, Bulldog! I'm the Campus Customs shop assistant. Ask me about sizes, prices, or what to wear to The Game."
  return { role: 'assistant', content, local: true }
}

function stockNote(p: ChatProduct) {
  if (p.total_stock === 0) return { text: 'Sold out', cls: 'stock-out' }
  const sizes = p.inventory.filter((s) => s.quantity > 0).map((s) => s.size)
  return { text: `In stock: ${sizes.join(', ')}`, cls: 'stock-ok' }
}

function ChatProducts({ products }: { products: ChatProduct[] }) {
  return (
    <div className="chat-products">
      {products.map((p) => {
        const note = stockNote(p)
        return (
          <Link key={p.product_id} to={`/products/${p.product_id}`} className="chat-product">
            <img src={p.image_url} alt="" loading="lazy" />
            <span className="chat-product-info">
              <span className="chat-product-name">{p.name}</span>
              <span className="chat-product-price">{formatPrice(p.price)}</span>
              <span className={`chat-product-stock ${note.cls}`}>{note.text}</span>
            </span>
          </Link>
        )
      })}
    </div>
  )
}

/** Small cards stay in the chat only for 1-2 item answers; bigger result sets live on the page. */
const MAX_INLINE_CARDS = 2

function PageResultsButton({ results }: { results: PageResults }) {
  const { results: current, show } = useChatResults()
  const onPage = current?.id === results.id
  function reveal() {
    show(results) // re-shows this set if the shopper cleared it or a newer answer replaced it
    setTimeout(() => document.getElementById(RESULTS_ANCHOR)?.scrollIntoView({ behavior: 'smooth' }), 50)
  }
  return (
    <button className="chat-page-link" onClick={reveal}>
      {onPage
        ? `↖ ${results.products.length} ${results.products.length === 1 ? 'item' : 'items'} on the page`
        : `↺ Show ${results.products.length === 1 ? 'this item' : `these ${results.products.length}`} on the page`}
    </button>
  )
}

function restockNotice(items: RestockAlert[]): ChatMessage {
  const lines = items.map((a) => `- **${a.name}** in **${a.size}** (${a.current_quantity} available)`)
  return {
    role: 'assistant',
    content: `🔔 **Good news: ${items.length === 1 ? 'an item you asked about is' : 'items you asked about are'} back in stock!**\n\n${lines.join('\n')}`,
    links: items.map((a) => ({ to: `/products/${a.product_id}`, label: `View ${a.name}` })),
    local: true,
  }
}

function AlertChips({ alerts }: { alerts: RestockAlert[] }) {
  return (
    <div className="alert-chips">
      {alerts.map((a) => (
        <Link key={`${a.product_id}-${a.size}`} to={`/products/${a.product_id}`} className="alert-chip">
          🔔 Restock alert set: {a.name} · {a.size}
        </Link>
      ))}
    </div>
  )
}

export default function ChatWidget() {
  const { show } = useChatResults()
  const { user, loading: authLoading } = useAuth()
  const { pathname, search } = useLocation()
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([greeting()])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [steps, setSteps] = useState<string[]>([]) // live progress from /api/chat/stream
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Jump straight to the newest message when the panel opens or saved history loads; glide for new replies.
  const jumpRef = useRef(true)
  useEffect(() => {
    jumpRef.current = true
  }, [open, historyLoading])
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: jumpRef.current ? 'auto' : 'smooth' })
    jumpRef.current = false
  }, [messages, thinking, open, steps])

  // Log in -> load this shopper's saved chat. Log out -> start fresh as a guest.
  const userId = user?.user_id
  useEffect(() => {
    if (authLoading) return
    if (!userId) {
      setMessages([greeting()])
      return
    }
    let cancelled = false
    setHistoryLoading(true)
    fetchChatHistory()
      .then(({ messages: saved, restocked }) => {
        if (cancelled) return
        setMessages([
          greeting(user?.first_name, saved.length > 0),
          ...saved,
          ...(restocked.length ? [restockNotice(restocked)] : []),
        ])
        if (restocked.length) setOpen(true) // pop the chat open so the shopper sees the good news
      })
      .catch(() => {
        if (!cancelled) setMessages([greeting(user?.first_name)])
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [userId, authLoading]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleClear() {
    if (!window.confirm('Delete your saved chat with the shop assistant?')) return
    try {
      await clearChatHistory()
      setMessages([greeting(user?.first_name)])
    } catch (err) {
      setMessages((m) => [...m, { role: 'assistant', content: (err as Error).message, local: true }])
    }
  }

  useEffect(() => {
    const onAsk = (e: Event) => {
      setOpen(true)
      setInput((e as CustomEvent<string>).detail)
      setTimeout(() => inputRef.current?.focus(), 0)
    }
    window.addEventListener(ASK_EVENT, onAsk)
    return () => window.removeEventListener(ASK_EVENT, onAsk)
  }, [])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const text = input.trim()
    if (!text || thinking || historyLoading) return
    const history: ChatMessage[] = [...messages, { role: 'user', content: text }]
    setMessages(history)
    setInput('')
    setThinking(true)
    setSteps([])
    try {
      // UI-only messages (greeting, errors) are never sent. Page context tells the agent what "this" is.
      const reply = await streamChat(
        history.filter((m) => !m.local),
        pageContextFor(pathname, search),
        Boolean(user),
        (text) => setSteps((prev) => (prev[prev.length - 1] === text ? prev : [...prev, text])),
      )
      setMessages((m) => [...m, reply])
      if (reply.alerts?.length) window.dispatchEvent(new Event(ALERTS_CHANGED_EVENT))
      // Structured matches from the agent update the on-page product grid.
      if (reply.results) show(reply.results)
    } catch (err) {
      const content = err instanceof Error ? err.message : 'Sorry, something went wrong. Please try again.'
      setMessages((m) => [...m, { role: 'assistant', content, local: true }])
    } finally {
      setThinking(false)
      setSteps([])
    }
  }

  return (
    <div className={`chat ${open ? 'chat-open' : ''}`}>
      {open && (
        <section className="chat-panel" aria-label="Shop assistant chat">
          <header className="chat-header">
            <div>
              <p className="chat-title">Campus Customs Assistant</p>
              <p className="chat-sub">
                {user ? `Signed in as ${user.first_name} · chat saved` : 'Guest · log in to save your chat'}
              </p>
            </div>
            <div className="chat-header-actions">
              {user && messages.some((m) => !m.local) && (
                <button className="chat-clear" onClick={handleClear} title="Delete saved chat">
                  Clear
                </button>
              )}
              <button className="chat-close" aria-label="Close chat" onClick={() => setOpen(false)}>
                ×
              </button>
            </div>
          </header>

          <div className="chat-messages">
            {messages.map((m, i) =>
              m.role === 'assistant' ? (
                <div key={i} className="bubble-group">
                  <div className="bubble bubble-assistant markdown">
                    <Markdown>{m.content}</Markdown>
                  </div>
                  {m.products && m.products.length > 0 && m.products.length <= MAX_INLINE_CARDS && (
                    <ChatProducts products={m.products} />
                  )}
                  {m.results && <PageResultsButton results={m.results} />}
                  {m.alerts && m.alerts.length > 0 && <AlertChips alerts={m.alerts} />}
                  {m.links?.map((l) => (
                    <Link key={l.to} to={l.to} className="chat-page-link">
                      {l.label} →
                    </Link>
                  ))}
                </div>
              ) : (
                <div key={i} className="bubble bubble-user">
                  {m.content}
                </div>
              ),
            )}
            {historyLoading && <p className="chat-loading">Loading your saved chat…</p>}
            {thinking && (
              <div className="bubble bubble-assistant chat-steps" aria-live="polite" aria-label="Assistant is working">
                {steps.map((step, i) => (
                  <p key={i} className={i === steps.length - 1 ? 'step step-active' : 'step step-done'}>
                    <span className="step-icon">{i === steps.length - 1 ? '' : '✓'}</span>
                    {step}
                  </p>
                ))}
                {steps.length === 0 && (
                  <div className="typing">
                    <span />
                    <span />
                    <span />
                  </div>
                )}
              </div>
            )}
            <div ref={endRef} />
          </div>

          <form className="chat-form" onSubmit={handleSubmit}>
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about merch, sizes, stock…"
              aria-label="Chat message"
              maxLength={1000}
            />
            <button className="btn" type="submit" disabled={!input.trim() || thinking}>
              Send
            </button>
          </form>
        </section>
      )}

      <button className="chat-launcher" aria-label={open ? 'Close chat' : 'Open chat'} onClick={() => setOpen((o) => !o)}>
        <span className="chat-launcher-label">{open ? '▾ Minimize chat' : 'Chat with us'}</span>
      </button>
    </div>
  )
}
