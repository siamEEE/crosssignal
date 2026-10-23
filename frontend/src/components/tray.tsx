import { AnimatePresence, motion } from 'motion/react'
import { Radio, ThumbsDown, ThumbsUp, X } from 'lucide-react'
import { Spinner } from '@/components/explore'
import { Button } from '@/components/ui/button'
import { styleFor } from '@/lib/categories'
import { MAX_SIGNALS, type Action, type Profile } from '@/lib/profile'
import { cn } from '@/lib/utils'

/** The confirmed profile and the one button that tunes in. */
export function Tray({
  profile,
  dispatch,
  blocker,
  loading,
  onTune,
}: {
  profile: Profile
  dispatch: (action: Action) => void
  blocker: string | null
  loading: boolean
  onTune: () => void
}) {
  const { signals, liked, disliked } = profile
  return (
    <aside
      aria-label="Your cultural profile"
      id="tune"
      className="profile-tray sticky bottom-0 z-20 border-t-2 border-lime bg-ink text-ivory shadow-pop"
    >
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-3 md:flex-row md:items-center">
        <div className="min-w-0 flex-1">
          <p className="text-[0.7rem] font-bold tracking-[0.2em] text-ivory/65 uppercase">
            Your signal · {signals.length}/{MAX_SIGNALS}
          </p>
          <ul className="mt-1.5 flex gap-1.5 overflow-x-auto pb-1 [scrollbar-width:thin]">
            {signals.length === 0 && (
              <li className="text-sm text-ivory/70">Nothing yet. Add films, games, books, places or moods.</li>
            )}
            <AnimatePresence initial={false}>
              {signals.map((signal) => {
                const style = styleFor(signal.category)
                const Icon = style.icon
                return (
                  <motion.li
                    key={signal.id}
                    layout
                    initial={{ opacity: 0, scale: 0.7 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.7 }}
                    className={cn(
                      'flex shrink-0 items-center gap-1.5 rounded-full border-2 border-ink py-1 pr-1 pl-2 text-sm font-semibold',
                      style.fill,
                      signal.category === 'games' || signal.category === 'podcasts' ? 'text-ivory' : 'text-ink',
                    )}
                  >
                    <Icon className="size-3.5" />
                    <span className="max-w-[12rem] truncate">{signal.name}</span>
                    {signal.year ? <span className="opacity-70">{signal.year}</span> : null}
                    <button
                      type="button"
                      onClick={() => dispatch({ type: 'remove', id: signal.id })}
                      aria-label={`Remove ${signal.name}`}
                      className="grid size-6 place-items-center rounded-full bg-ink/15 hover:bg-ink/30 cursor-pointer"
                    >
                      <X className="size-3.5" />
                    </button>
                  </motion.li>
                )
              })}
            </AnimatePresence>
            {liked.map((artist) => (
              <li
                key={artist.id}
                className="flex shrink-0 items-center gap-1 rounded-full border-2 border-dashed border-lime-deep px-2 py-1 text-sm font-semibold"
                title="Liked: steers the next remix"
              >
                <ThumbsUp className="size-3.5 text-lime-deep" /> {artist.name}
              </li>
            ))}
            {disliked.length > 0 && (
              <li className="flex shrink-0 items-center gap-1 rounded-full border-2 border-dashed border-coral px-2 py-1 text-sm text-coral-deep">
                <ThumbsDown className="size-3.5" /> {disliked.length} hidden
              </li>
            )}
          </ul>
        </div>
        <div className="flex items-center gap-3">
          {blocker && <p className="max-w-xs text-xs text-ivory/70 md:text-right">{blocker}</p>}
          <Button variant="accent" size="lg" onClick={onTune} disabled={!!blocker || loading} className="shrink-0">
            {loading ? <Spinner /> : <Radio />} {loading ? 'Tuning in…' : 'Tune My Radio'}
          </Button>
        </div>
      </div>
    </aside>
  )
}
