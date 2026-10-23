import { AnimatePresence, motion } from 'motion/react'
import { AlertCircle, Check, Plus, Wand2 } from 'lucide-react'
import { useRef, useState } from 'react'
import { SectionTitle, Spinner } from '@/components/explore'
import { Button } from '@/components/ui/button'
import { api, ApiError } from '@/lib/api'
import { ERA_LABEL } from '@/lib/explain'
import { styleFor } from '@/lib/categories'
import { MAX_SIGNALS, toSignal } from '@/lib/profile'
import type { Candidate, GenreOptions, Interpretation, Signal } from '@/lib/types'
import { cn } from '@/lib/utils'

const EXAMPLES = [
  'I love Interstellar, Hollow Knight and dark academia. Mostly metalcore and shoegaze, no country.',
  'Spirited Away, Stardew Valley and cozy rainy days. Lo-fi and indie folk, hidden gems.',
  'Blade Runner 2049, Cyberpunk 2077 and Berserk. Synthwave and industrial metal from the 2010s.',
]

export function Describe({
  live,
  selected,
  genreOptions,
  onAdd,
  onApplyMusic,
}: {
  live: boolean
  selected: Signal[]
  genreOptions: GenreOptions | null
  onAdd: (signal: Signal, how: 'picked') => void
  onApplyMusic: (music: Interpretation['music']) => void
}) {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [reading, setReading] = useState<Interpretation | null>(null)
  const [applied, setApplied] = useState(false)
  const revision = useRef(0)

  function changeText(value: string) {
    revision.current++
    setText(value)
    setReading(null)
    setError(null)
    setLoading(false)
    setApplied(false)
  }

  async function interpret() {
    if (!text.trim()) return
    const version = ++revision.current
    setLoading(true)
    setError(null)
    setApplied(false)
    try {
      const next = await api.interpret(text.trim())
      if (version === revision.current) setReading(next)
    } catch (e) {
      if (version !== revision.current) return
      setError(e instanceof ApiError ? e : new ApiError('http', String(e), 0))
    } finally {
      if (version === revision.current) setLoading(false)
    }
  }

  const labels = new Map<string, string>()
  for (const g of genreOptions?.genres ?? []) {
    labels.set(g.id, g.label)
    for (const s of g.subgenres) labels.set(s.id, s.label)
  }
  const selectedIds = new Set(selected.map((s) => s.id))
  const full = selected.length >= MAX_SIGNALS
  const music = reading?.music
  const hasMusic = !!music && (music.preferred.length || music.avoided.length || music.era || music.discovery)

  return (
    <section id="describe" className="scroll-mt-20 bg-ink py-16 text-ivory">
      <div className="mx-auto max-w-6xl px-4">
        <SectionTitle kicker="02 · Describe" title="Or just tell us about your world" />
        <p className="mt-4 max-w-2xl text-ivory/70">
          CrossSignal pulls out titles, places and moods, looks each one up in Qloo and waits
          for you to confirm. Nothing joins your profile until you tap it.
        </p>

        <div className="mt-8 grid gap-6 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <label htmlFor="describe-text" className="sr-only">
              Describe your cultural world
            </label>
            <textarea
              id="describe-text"
              value={text}
              onChange={(e) => changeText(e.target.value)}
              maxLength={600}
              rows={5}
              disabled={!live}
              placeholder="I'm into Arrival, Outer Wilds and rainy city nights. Mostly post-rock, nothing too mainstream…"
              className="w-full resize-none rounded-[var(--radius-card)] border-2 border-ivory/20 bg-ink-2 p-5 text-lg leading-relaxed text-ivory placeholder:text-ivory/40 focus:border-lime focus:outline-none disabled:opacity-60"
            />
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <Button variant="accent" size="lg" onClick={interpret} disabled={!live || loading || !text.trim()}>
                {loading ? <Spinner /> : <Wand2 />} Read my description
              </Button>
              <span className="text-xs text-ivory/55">
                Rule-based reader, no AI model ({text.length}/600)
              </span>
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => changeText(example)}
                  className="rounded-full border border-ivory/20 px-3 py-1.5 text-left text-xs text-ivory/75 transition hover:border-lime hover:text-ivory cursor-pointer"
                >
                  {example.slice(0, 52)}…
                </button>
              ))}
            </div>
          </div>

          <div className="min-h-48 rounded-[var(--radius-card)] bg-ivory p-5 text-ink" aria-live="polite">
            {error && (
              <p className="flex items-start gap-2 text-sm text-coral-deep">
                <AlertCircle className="mt-0.5 size-4 shrink-0" /> {error.message}
              </p>
            )}
            {!reading && !error && (
              <p className="text-sm text-muted">
                Your reading shows up here: each phrase with Qloo&apos;s matches, plus any music
                preferences we spotted.
              </p>
            )}
            {reading && (
              <div className="space-y-5">
                {reading.mentions.length === 0 && (
                  <p className="text-sm text-muted">No titles, places or moods found. Try naming a few.</p>
                )}
                {reading.mentions.map((mention) => {
                  const candidates: Candidate[] = [
                    ...mention.resolution.candidates.slice(0, 3),
                    ...mention.tag_candidates.slice(0, 2),
                  ]
                  return (
                    <div key={mention.phrase}>
                      <p className="flex items-baseline justify-between gap-2">
                        <span className="font-display text-lg font-bold">“{mention.phrase}”</span>
                        <MatchBadge match={mention.resolution.match} />
                      </p>
                      {candidates.length === 0 && <p className="text-xs text-muted">No Qloo matches.</p>}
                      <ul className="mt-2 flex flex-wrap gap-2">
                        {candidates.map((c) => {
                          const added = selectedIds.has(c.id)
                          const style = styleFor(c.category)
                          return (
                            <li key={c.id}>
                              <button
                                type="button"
                                disabled={added || full}
                                onClick={() => onAdd(toSignal(c), 'picked')}
                                className={cn(
                                  'inline-flex items-center gap-1.5 rounded-full border-2 px-3 py-1 text-sm font-medium transition cursor-pointer disabled:cursor-default',
                                  added ? 'border-ink bg-lime' : 'border-ink/15 hover:border-ink',
                                )}
                              >
                                {added ? <Check className="size-3.5" /> : <Plus className="size-3.5" />}
                                {c.name}
                                <span className={cn('text-xs', style.text)}>
                                  {c.type_label}
                                  {c.year ? ` ${c.year}` : ''}
                                </span>
                              </button>
                            </li>
                          )
                        })}
                      </ul>
                    </div>
                  )
                })}
                <AnimatePresence>
                  {hasMusic && music && (
                    <motion.div
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="rounded-2xl bg-ivory-2 p-4"
                    >
                      <p className="text-xs font-bold tracking-widest text-muted uppercase">Music we spotted</p>
                      <ul className="mt-2 space-y-1 text-sm">
                        {music.preferred.length > 0 && (
                          <li>Prefer: {music.preferred.map((g) => labels.get(g) ?? g).join(', ')}</li>
                        )}
                        {music.avoided.length > 0 && (
                          <li>Avoid: {music.avoided.map((g) => labels.get(g) ?? g).join(', ')}</li>
                        )}
                        {music.era && <li>Era: {ERA_LABEL[music.era] ?? music.era}</li>}
                        {music.discovery && <li>Discovery: {music.discovery}</li>}
                      </ul>
                      <Button
                        size="sm"
                        className="mt-3"
                        disabled={applied}
                        onClick={() => {
                          onApplyMusic(music)
                          setApplied(true)
                        }}
                      >
                        {applied ? <Check /> : null} {applied ? 'Applied to Sound' : 'Apply to my Sound settings'}
                      </Button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}

function MatchBadge({ match }: { match: string }) {
  const copy: Record<string, [string, string]> = {
    exact: ['Exact match', 'bg-lime/50'],
    ambiguous: ['Pick one', 'bg-violet/20 text-violet-deep'],
    suggestions: ['Closest results', 'bg-apricot/30 text-apricot-deep'],
    none: ['No title match', 'bg-ink/10'],
  }
  const [label, tone] = copy[match] ?? copy.none
  return <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-[0.7rem] font-bold', tone)}>{label}</span>
}
