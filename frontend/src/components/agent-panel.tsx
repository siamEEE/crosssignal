import { useState } from 'react'
import { MessageCircle, Send, X, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import type { Profile } from '@/lib/profile'
import type { DiscoverResult, Preferences, Signal } from '@/lib/types'

type Turn = { role: 'user' | 'model'; content: string }
type AgentAnswer = { reply: string; trace: string[]; signals: Signal[]; preferences: Preferences; result: DiscoverResult | null; page: number }

export function AgentPanel({ profile, currentPage, seen, onResult }: {
  profile: Profile
  currentPage: number
  seen: string[]
  onResult: (answer: AgentAnswer) => void
}) {
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [trace, setTrace] = useState<string[]>([])

  async function send() {
    const text = message.trim()
    if (!text || busy) return
    const next: Turn[] = [...turns, { role: 'user', content: text }]
    setTurns(next)
    setMessage('')
    setError('')
    setTrace([])
    setBusy(true)
    try {
      const answer = await api.agent({
        message: text,
        signals: profile.signals,
        preferences: profile.prefs,
        feedback: { liked: profile.liked, disliked: profile.disliked.map(d => d.id) },
        history: turns.slice(-6),
        seen,
        page: currentPage,
      })
      setTurns([...next, { role: 'model', content: answer.reply }])
      setTrace(answer.trace)
      onResult(answer)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The radio host is unavailable right now.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed bottom-24 right-4 z-40 sm:bottom-6 sm:right-6">
      {open ? (
        <section aria-label="AI Radio Host" className="flex h-[min(72vh,570px)] w-[min(92vw,400px)] flex-col overflow-hidden rounded-2xl border-2 border-violet bg-ivory text-ink shadow-2xl">
          <div className="flex items-center justify-between border-b border-ink/20 bg-ivory-2 px-4 py-3">
            <div><h2 className="font-display text-lg font-bold">AI Radio Host</h2><p className="text-xs text-muted">Gemini + real Qloo music discovery</p></div>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close AI Radio Host" className="rounded-full p-2 hover:bg-ink/10"><X size={18}/></button>
          </div>
          <div className="flex-1 space-y-3 overflow-y-auto p-4" role="log" aria-live="polite">
            {turns.length === 0 && <p className="text-sm text-muted">Tell me what you like, or ask for another mix. I'll use Qloo to find artists and check their songs.</p>}
            {turns.map((t, i) => (
              <p key={i} className={`max-w-[95%] rounded-xl p-3 text-sm leading-relaxed ${t.role === 'user' ? 'ml-auto bg-violet text-ivory' : 'bg-ivory-2'}`}>{t.content}</p>
            ))}
            {trace.length > 0 && <div className="rounded-xl border border-ink/20 p-3"><p className="text-xs font-bold">Tools used</p><ul className="mt-1 list-inside list-disc text-xs text-muted">{trace.map((t,i)=><li key={i}>{t}</li>)}</ul></div>}
            {busy && <p className="flex items-center gap-2 text-xs text-muted"><Loader2 size={15} className="animate-spin"/> Checking Qloo and the catalog…</p>}
            {error && <p role="alert" className="rounded-lg border border-coral p-2 text-sm">{error}</p>}
          </div>
          <form className="flex gap-2 border-t border-ink/20 p-3" onSubmit={e=>{e.preventDefault();void send()}}>
            <input aria-label="Message to AI Radio Host" className="min-w-0 flex-1 rounded-xl border border-ink/30 bg-ivory px-3 py-2 text-sm" value={message} maxLength={600} onChange={e=>setMessage(e.target.value)} placeholder="Try: more 2000s indie rock…" />
            <button type="submit" disabled={busy || !message.trim()} aria-label="Send message" className="rounded-xl bg-violet px-3 py-2 text-ivory disabled:opacity-40"><Send size={18}/></button>
          </form>
        </section>
      ) : (
        <button type="button" onClick={() => setOpen(true)} className="flex items-center gap-2 rounded-full border-2 border-violet bg-ivory px-4 py-3 font-semibold text-ink shadow-xl hover:bg-ivory-2" aria-label="Open AI Radio Host">
          <MessageCircle size={20}/> AI Radio Host
        </button>
      )}
    </div>
  )
}
