import { createContext, useCallback, useContext, useState } from 'react'
import type { ReactNode } from 'react'
import type { PageResults } from './types'

/**
 * Shared state for the on-page "From your chat" grid.
 * ChatWidget writes results here; ChatResultsSection (rendered by App on every page) reads them.
 */
interface ChatResultsState {
  results: PageResults | null
  collapsed: boolean
  show: (results: PageResults) => void
  setCollapsed: (collapsed: boolean) => void
  clear: () => void
}

const ChatResultsContext = createContext<ChatResultsState | null>(null)

export function ChatResultsProvider({ children }: { children: ReactNode }) {
  const [results, setResults] = useState<PageResults | null>(null)
  const [collapsed, setCollapsed] = useState(false)

  const show = useCallback((next: PageResults) => {
    setResults(next)
    setCollapsed(false)
  }, [])

  const clear = useCallback(() => setResults(null), [])

  return (
    <ChatResultsContext.Provider value={{ results, collapsed, show, setCollapsed, clear }}>
      {children}
    </ChatResultsContext.Provider>
  )
}

export function useChatResults(): ChatResultsState {
  const ctx = useContext(ChatResultsContext)
  if (!ctx) throw new Error('useChatResults must be used inside <ChatResultsProvider>')
  return ctx
}
