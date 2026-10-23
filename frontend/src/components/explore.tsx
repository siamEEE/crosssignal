import { AnimatePresence, motion } from 'motion/react'
import { AlertCircle, Check, Loader2, Plus, Search, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { api, ApiError } from '@/lib/api'
import { ACCENT_FILL, styleFor } from '@/lib/categories'
import { MAX_SIGNALS, toSignal } from '@/lib/profile'
import type { Candidate, Category, Collection, Resolution, Signal } from '@/lib/types'
import { cn } from '@/lib/utils'

type SearchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'done'; resolution: Resolution }
  | { status: 'error'; error: ApiError }

export function Explore({
  categories,
  collections,
  selected,
  live,
  onAdd,
}: {
  categories: Category[]
  collections: Collection[]
  selected: Signal[]
  live: boolean
  onAdd: (signal: Signal, how: 'exact' | 'picked') => void
}) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState<string | null>(null)
  const [state, setState] = useState<SearchState>({ status: 'idle' })
  const [retry, setRetry] = useState(0)
  const autoAdd = useRef<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const q = query.trim()
    if (!q || !live) {
      setState({ status: 'idle' })
      return
    }
    const controller = new AbortController()
    const timer = setTimeout(() => {
      setState({ status: 'loading' })
      api
        .search(q, category, controller.signal)
        .then((resolution) => {
          if (controller.signal.aborted) return
          setState({ status: 'done', resolution })
          // Featured picks add themselves only when the match is certain.
          if (autoAdd.current === q && resolution.match === 'exact') {
            onAdd(toSignal(resolution.candidates[0]), 'exact')
          }
          autoAdd.current = null
        })
        .catch((error) => {
          if (controller.signal.aborted) return
          setState({ status: 'error', error: error instanceof ApiError ? error : new ApiError('http', String(error), 0) })
        })
    }, 320)
    return () => {
      controller.abort()
      clearTimeout(timer)
    }
    // onAdd is stable enough for this purpose; re-running on it would re-search.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, category, live, retry])

  const full = selected.length >= MAX_SIGNALS
  const selectedIds = new Set(selected.map((s) => s.id))
  const entityCategories = categories.filter((c) => c.kind === 'entity')

  function pickFeatured(item: { query: string; category: string }) {
    autoAdd.current = item.query
    setCategory(item.category)
    setQuery(item.query)
    setRetry((n) => n + 1)
    document.getElementById('culture-search')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <section id="explore" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-14">
      <SectionTitle kicker="01 / The culture crate" title="What’s in your world?"><a href="#describe" className="text-sm font-semibold underline underline-offset-4">Rather describe it? Write us a note</a></SectionTitle>
      <p className="mt-4 max-w-2xl text-ink/70">Pick up to five interests. Search a favorite, explore a category, or borrow a starting point below.</p>

      {/* Live search across every category. */}
      <div id="culture-search" className="culture-search mt-8 scroll-mt-24 border border-ink/20 bg-ivory p-4 md:p-6">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Category">
          <CategoryPill active={category === null} onClick={() => setCategory(null)} label="Everything" />
          {[...entityCategories, ...categories.filter((c) => c.kind === 'tag')].map((c) => (
            <CategoryPill
              key={c.id}
              active={category === c.id}
              onClick={() => setCategory(c.id)}
              label={c.label}
              categoryId={c.id}
            />
          ))}
        </div>
        <label className="relative mt-4 block">
          <span className="sr-only">Search Qloo</span>
          <Search className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted" />
          <input
            ref={inputRef}
            value={query}
            disabled={!live}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={
              live
                ? category
                  ? `Search ${categories.find((c) => c.id === category)?.hint.toLowerCase()}…`
                  : 'Search any film, show, anime, game, book, creator, brand or place…'
                : 'Search needs the live Qloo backend'
            }
            className="h-14 w-full rounded-full border-2 border-ink bg-ivory pr-12 pl-12 text-base font-medium placeholder:text-muted focus:outline-none focus-visible:shadow-[4px_4px_0_var(--color-violet)] disabled:opacity-60"
          />
          {query && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => {
                setQuery('')
                inputRef.current?.focus()
              }}
              className="absolute top-1/2 right-3 grid size-8 -translate-y-1/2 place-items-center rounded-full hover:bg-ink/10 cursor-pointer"
            >
              <X className="size-4" />
            </button>
          )}
        </label>
        {category === 'aesthetics' && (
          <p className="mt-3 text-sm text-muted">
            Aesthetics are Qloo <strong>tags</strong>, not titles. They travel alongside at least one
            title, person, brand or place and can&apos;t drive results on their own.
          </p>
        )}

        <div className="mt-5" aria-live="polite">
          <SearchResults
            state={state}
            full={full}
            selectedIds={selectedIds}
            onAdd={(c) => onAdd(toSignal(c), 'picked')}
            onRetry={() => setRetry((n) => n + 1)}
          />
        </div>
      </div>
<p className="eyebrow mt-10">Not sure where to start? Pull a thread.</p>
      {/* Featured collections: inspiration only, resolved live on click. */}
      <div className="collection-grid mt-8">
        {collections.map((collection, i) => (
          <motion.article
            key={collection.id}
            initial={{ opacity: 0, y: 14 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.05 }}
            className={cn(
              'culture-collection flex flex-col p-5',
              ACCENT_FILL[collection.accent] ?? ACCENT_FILL.ink,
            )}
          >
            <span className="collection-number" aria-hidden="true">0{i + 1} / CULTURE NOTES</span><div className={`collection-art collection-art-${i % 5}`} aria-hidden="true"><span /><span /><span /></div><h3 className="font-display text-2xl leading-tight font-black">{collection.title}</h3>
            <p className="mt-1 text-sm opacity-75">{collection.blurb}</p>
            <ul className="mt-4 flex flex-wrap gap-1.5">
              {collection.items.map((item) => (
                <li key={item.query}>
                  <button
                    type="button"
                    disabled={!live}
                    onClick={() => pickFeatured(item)}
                    className="rounded-full border border-current/30 bg-ivory/90 px-2.5 py-1 text-xs font-semibold text-ink transition hover:-translate-y-0.5 hover:bg-ivory disabled:opacity-50 cursor-pointer"
                  >
                    {item.query}
                  </button>
                </li>
              ))}
            </ul>
          </motion.article>
        ))}
      </div>


    </section>
  )
}

export function SectionTitle({ kicker, title, children }: { kicker: string; title: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="text-xs font-bold tracking-[0.25em] text-muted uppercase">{kicker}</p>
        <h2 className="mt-2 font-display text-[clamp(2rem,5vw,3.25rem)] leading-none font-black tracking-tight text-balance">
          {title}
        </h2>
      </div>
      {children}
    </div>
  )
}

function CategoryPill({
  active,
  onClick,
  label,
  categoryId,
}: {
  active: boolean
  onClick: () => void
  label: string
  categoryId?: string
}) {
  const style = categoryId ? styleFor(categoryId) : null
  const Icon = style?.icon
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border-2 px-3 py-1.5 text-sm font-semibold transition cursor-pointer',
        active ? 'border-ink bg-ink text-ivory' : 'border-ink/15 bg-ivory hover:border-ink',
      )}
    >
      {Icon && <Icon className={cn('size-4', active ? 'text-lime' : style?.text)} />}
      {label}
    </button>
  )
}

const MATCH_COPY = {
  exact: null,
  ambiguous: (q: string, n: number) => `${n} matches share the name "${q}". Pick the one you mean.`,
  suggestions: (q: string) =>
    `No exact match for "${q}". These are Qloo's closest results; add one only if it's what you meant.`,
  none: (q: string) => `Qloo found nothing for "${q}". Try another spelling or category.`,
}

function SearchResults({
  state,
  full,
  selectedIds,
  onAdd,
  onRetry,
}: {
  state: SearchState
  full: boolean
  selectedIds: Set<string>
  onAdd: (c: Candidate) => void
  onRetry: () => void
}) {
  if (state.status === 'idle') {
    return <p className="text-sm text-muted">Type to search Qloo&apos;s catalog, or tap a featured pick below.</p>
  }
  if (state.status === 'loading') {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="h-24 animate-pulse rounded-2xl bg-ink/8" />
        ))}
      </div>
    )
  }
  if (state.status === 'error') {
    return (
      <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-coral/15 p-4 text-sm text-coral-deep">
        <AlertCircle className="size-5" />
        <span className="flex-1">{state.error.message}</span>
        {state.error.retryable && (
          <Button size="sm" variant="outline" onClick={onRetry}>
            Try again
          </Button>
        )}
      </div>
    )
  }
  const { resolution } = state
  const copy = MATCH_COPY[resolution.match]
  const message = copy?.(resolution.query, resolution.candidates.length)
  return (
    <div>
      {message && (
        <p
          className={cn(
            'mb-4 rounded-2xl px-4 py-3 text-sm font-medium',
            resolution.match === 'ambiguous' ? 'bg-violet/15 text-violet-deep' : 'bg-apricot/25 text-apricot-deep',
          )}
        >
          {message}
        </p>
      )}
      {full && (
        <p className="mb-4 text-sm font-semibold text-coral-deep">
          You have {MAX_SIGNALS} interests. Remove one to add another.
        </p>
      )}
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <AnimatePresence initial={false}>
          {resolution.candidates.map((candidate, i) => (
            <motion.li
              key={candidate.id}
              layout
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.025 }}
            >
              <CandidateCard
                candidate={candidate}
                added={selectedIds.has(candidate.id)}
                disabled={full}
                onAdd={() => onAdd(candidate)}
              />
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>
    </div>
  )
}

function CandidateCard({
  candidate,
  added,
  disabled,
  onAdd,
}: {
  candidate: Candidate
  added: boolean
  disabled: boolean
  onAdd: () => void
}) {
  const [broken, setBroken] = useState(false)
  const style = styleFor(candidate.category)
  const Icon = style.icon
  // Qloo's disambiguation is often just the year again; show each fact once.
  const meta = [...new Set([candidate.type_label, candidate.year?.toString(), candidate.disambiguation])]
    .filter(Boolean)
    .join(' · ')
  return (
    <div className="group flex h-full items-center gap-3 rounded-2xl border-2 border-ink/10 bg-ivory p-2.5 transition hover:border-ink">
      <div className={cn('relative size-16 shrink-0 overflow-hidden rounded-xl', style.tint)}>
        <Icon className={cn('absolute inset-0 m-auto size-7', style.text)} />
        {candidate.image_url && !broken && (
          <img
            src={candidate.image_url}
            alt=""
            loading="lazy"
            onError={() => setBroken(true)}
            className="relative size-full object-cover"
          />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="line-clamp-2 leading-tight font-semibold">{candidate.name}</p>
        <p className="mt-0.5 truncate text-xs text-muted">{meta}</p>
      </div>
      <Button
        size="icon"
        variant={added ? 'accent' : 'outline'}
        disabled={added || disabled}
        onClick={onAdd}
        aria-label={added ? `${candidate.name} added` : `Add ${candidate.name}`}
      >
        {added ? <Check /> : disabled ? <Plus /> : <Plus />}
      </Button>
    </div>
  )
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn('size-4 animate-spin', className)} />
}
