import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

/** A line in the shopping bag. Stored in localStorage so the bag survives reloads. */
export interface BagItem {
  product_id: string
  name: string
  image_url: string
  price: number
  size: string
  qty: number
  max_qty: number // live stock for that size when added; the bag never exceeds it
}

interface BagState {
  items: BagItem[]
  count: number
  subtotal: number
  open: boolean
  bump: number // increments on every add, so the header icon can replay its bounce
  add: (item: Omit<BagItem, 'qty'>, qty: number) => void
  setQty: (product_id: string, size: string, qty: number) => void
  remove: (product_id: string, size: string) => void
  clear: () => void
  setOpen: (open: boolean) => void
}

const KEY = 'cc_bag'
const BagContext = createContext<BagState | null>(null)

function load(): BagItem[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '[]')
  } catch {
    return []
  }
}

export function BagProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<BagItem[]>(load)
  const [open, setOpen] = useState(false)
  const [bump, setBump] = useState(0)

  useEffect(() => localStorage.setItem(KEY, JSON.stringify(items)), [items])

  const add = useCallback((item: Omit<BagItem, 'qty'>, qty: number) => {
    setItems((prev) => {
      const i = prev.findIndex((p) => p.product_id === item.product_id && p.size === item.size)
      if (i === -1) return [...prev, { ...item, qty: Math.min(qty, item.max_qty) }]
      const next = [...prev]
      next[i] = { ...next[i], max_qty: item.max_qty, qty: Math.min(next[i].qty + qty, item.max_qty) }
      return next
    })
    setBump((b) => b + 1)
    setOpen(true)
  }, [])

  const setQty = useCallback((product_id: string, size: string, qty: number) => {
    setItems((prev) =>
      prev.map((p) =>
        p.product_id === product_id && p.size === size ? { ...p, qty: Math.max(1, Math.min(qty, p.max_qty)) } : p,
      ),
    )
  }, [])

  const remove = useCallback((product_id: string, size: string) => {
    setItems((prev) => prev.filter((p) => !(p.product_id === product_id && p.size === size)))
  }, [])

  const clear = useCallback(() => setItems([]), [])

  const count = items.reduce((n, i) => n + i.qty, 0)
  const subtotal = items.reduce((n, i) => n + i.qty * i.price, 0)

  return (
    <BagContext.Provider value={{ items, count, subtotal, open, bump, add, setQty, remove, clear, setOpen }}>
      {children}
    </BagContext.Provider>
  )
}

export function useBag(): BagState {
  const ctx = useContext(BagContext)
  if (!ctx) throw new Error('useBag must be used inside <BagProvider>')
  return ctx
}
