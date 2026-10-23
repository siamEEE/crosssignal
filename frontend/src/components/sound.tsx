import { AnimatePresence, motion } from 'motion/react'
import { Ban, ChevronDown, Heart, RotateCcw, ThumbsUp } from 'lucide-react'
import { useState } from 'react'
import { SectionTitle } from '@/components/explore'
import { Button } from '@/components/ui/button'
import { Segmented } from '@/components/ui/toggle-group'
import { ERA_LABEL } from '@/lib/explain'
import { genreState, type Action, type GenreState } from '@/lib/profile'
import type { Discovery, GenreOptions, Preferences } from '@/lib/types'
import { cn } from '@/lib/utils'

const STATE_STYLE: Record<Exclude<GenreState, null>, { cls: string; label: string; icon: typeof Heart }> = {
  preferred: { cls: 'bg-lime border-ink text-ink', label: 'Preferred', icon: Heart },
  open: { cls: 'bg-apricot border-ink text-ink', label: 'Open to', icon: ThumbsUp },
  avoided: { cls: 'bg-ink border-ink text-ivory line-through decoration-coral decoration-2', label: 'Avoid', icon: Ban },
}
const NEXT: Record<string, string> = {
  none: 'preferred',
  preferred: 'open to',
  open: 'avoided',
  avoided: 'no preference',
}

const DISCOVERY_OPTIONS: { value: Discovery; label: string; hint: string }[] = [
  { value: 'familiar', label: 'Familiar', hint: 'Asks Qloo for popularity ≥ 0.90 and favours the most popular' },
  { value: 'balanced', label: 'Balanced', hint: 'No popularity filter; Qloo relevance decides' },
  { value: 'adventurous', label: 'Adventurous', hint: 'Asks Qloo for popularity ≤ 0.85 and favours lesser-known' },
]

export function Sound({
  options,
  prefs,
  dispatch,
}: {
  options: GenreOptions | null
  prefs: Preferences
  dispatch: (action: Action) => void
}) {
  const [open, setOpen] = useState<string | null>(null)
  const [advanced, setAdvanced] = useState(false)
  const genres = options?.genres ?? []
  const anySet = prefs.preferred.length + prefs.open_to.length + prefs.avoided.length > 0

  return (
    <section id="sound" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-16">
      <SectionTitle kicker="03 · Sound" title="Tune the music side (optional)">
        {anySet && (
          <Button
            variant="quiet"
            size="sm"
            onClick={() => {
              for (const id of [...prefs.preferred, ...prefs.open_to, ...prefs.avoided]) {
                dispatch({ type: 'genre', id, state: null })
              }
            }}
          >
            <RotateCcw /> Clear genres
          </Button>
        )}
      </SectionTitle>
      <p className="mt-4 max-w-2xl text-ink/70">
        Tap a genre to cycle it: <strong>preferred</strong> → <strong>open to</strong> →{' '}
        <strong>avoid</strong> → off. Preferred and open-to genres filter Qloo&apos;s search;
        a match only counts as <em>confirmed</em> when Qloo&apos;s genre tags and Apple Music agree.
      </p>

      <div className="mt-6 flex flex-wrap gap-2 text-xs font-semibold" aria-hidden>
        {Object.values(STATE_STYLE).map(({ cls, label, icon: Icon }) => (
          <span key={label} className={cn('inline-flex items-center gap-1 rounded-full border-2 px-2.5 py-1', cls)}>
            <Icon className="size-3" /> {label}
          </span>
        ))}
      </div>

      <div className="mt-6 grid grid-cols-[repeat(2,minmax(0,1fr))] gap-2 sm:grid-cols-3 sm:gap-3 lg:grid-cols-5">
        {genres.map((genre) => {
          const state = genreState(prefs, genre.id)
          const subs = genre.subgenres.filter((s) => advanced || !s.advanced)
          const activeSubs = genre.subgenres.filter((s) => genreState(prefs, s.id)).length
          return (
            <div key={genre.id} className={cn(open === genre.id && 'col-span-2 sm:col-span-3 lg:col-span-5')}>
              <div className="flex items-stretch gap-1">
                <GenreChip
                  id={genre.id}
                  label={genre.label}
                  state={state}
                  big
                  onClick={() => dispatch({ type: 'cycle-genre', id: genre.id })}
                />
                {genre.subgenres.length > 0 && (
                  <button
                    type="button"
                    aria-expanded={open === genre.id}
                    aria-label={`${genre.label} subgenres`}
                    onClick={() => setOpen(open === genre.id ? null : genre.id)}
                    className="relative grid w-8 shrink-0 place-items-center sm:w-10 rounded-2xl border-2 border-ink/15 bg-ivory transition hover:border-ink cursor-pointer"
                  >
                    <ChevronDown className={cn('size-4 transition', open === genre.id && 'rotate-180')} />
                    {activeSubs > 0 && (
                      <span className="absolute -top-1.5 -right-1.5 grid size-5 place-items-center rounded-full bg-violet text-[0.65rem] font-bold text-ivory">
                        {activeSubs}
                      </span>
                    )}
                  </button>
                )}
              </div>
              <AnimatePresence initial={false}>
                {open === genre.id && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="mt-2 flex flex-wrap gap-2 rounded-2xl bg-ivory-2 p-3">
                      {subs.map((sub) => (
                        <GenreChip
                          key={sub.id}
                          id={sub.id}
                          label={sub.label}
                          state={genreState(prefs, sub.id)}
                          onClick={() => dispatch({ type: 'cycle-genre', id: sub.id })}
                        />
                      ))}
                      {genre.subgenres.some((s) => s.advanced) && (
                        <button
                          type="button"
                          onClick={() => setAdvanced((a) => !a)}
                          className="rounded-full px-3 py-1.5 text-xs font-semibold text-violet-deep underline-offset-4 hover:underline cursor-pointer"
                        >
                          {advanced ? 'Hide' : 'Show'} advanced subgenres
                        </button>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )
        })}
      </div>

      <div className="mt-10 grid gap-8 lg:grid-cols-2">
        <div>
          <h3 className="font-display text-2xl font-bold">Release era</h3>
          <p className="mt-1 text-sm text-muted">
            Qloo can&apos;t filter artists by year, so era reorders artists using their Apple
            Music release dates and picks in-era songs first.
          </p>
          <div className="mt-4 flex flex-wrap gap-2" role="radiogroup" aria-label="Release era">
            {[null, ...(options?.eras ?? [])].map((era) => (
              <button
                key={era ?? 'any'}
                type="button"
                role="radio"
                aria-checked={prefs.era === era}
                onClick={() => dispatch({ type: 'era', era })}
                className={cn(
                  'rounded-full border-2 px-3.5 py-1.5 text-sm font-semibold transition cursor-pointer',
                  prefs.era === era ? 'border-ink bg-violet text-ivory' : 'border-ink/15 hover:border-ink',
                )}
              >
                {era ? capitalize(ERA_LABEL[era] ?? era) : 'Any era'}
              </button>
            ))}
          </div>
        </div>
        <div>
          <h3 className="font-display text-2xl font-bold">Discovery</h3>
          <p className="mt-1 text-sm text-muted">Uses Qloo&apos;s popularity percentile (0–1).</p>
          <Segmented
            className="mt-4"
            label="Discovery mode"
            value={prefs.discovery}
            onChange={(mode) => dispatch({ type: 'discovery', mode })}
            options={DISCOVERY_OPTIONS}
          />
        </div>
      </div>
    </section>
  )
}

function capitalize(text: string) {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function GenreChip({
  id,
  label,
  state,
  big,
  onClick,
}: {
  id: string
  label: string
  state: GenreState
  big?: boolean
  onClick: () => void
}) {
  const style = state ? STATE_STYLE[state] : null
  const Icon = style?.icon
  return (
    <motion.button
      type="button"
      layout
      whileTap={{ scale: 0.94 }}
      data-genre={id}
      onClick={onClick}
      aria-label={`${label}: ${state ? STATE_STYLE[state].label.toLowerCase() : 'no preference'}. Activate to set ${NEXT[state ?? 'none']}.`}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-2xl border-2 font-semibold transition-colors cursor-pointer',
        big ? 'min-h-14 min-w-0 flex-1 px-3 text-left text-base sm:px-4' : 'px-3 py-1.5 text-sm',
        style?.cls ?? 'border-ink/15 bg-ivory hover:border-ink',
      )}
    >
      {Icon && <Icon className="size-4 shrink-0" />}
      <span className={cn(big && 'min-w-0 font-display text-base leading-tight font-bold break-words sm:text-lg')}>{label}</span>
    </motion.button>
  )
}
