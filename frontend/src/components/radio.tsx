import { AnimatePresence, motion } from 'motion/react'
import {
  AlertTriangle,
  ArrowDownToLine,
  ExternalLink,
  Info,
  Pause,
  Play,
  RefreshCcw,
  Shuffle,
  ThumbsDown,
  ThumbsUp,
  Undo2,
} from 'lucide-react'
import { SectionTitle } from '@/components/explore'
import { usePlayer } from '@/lib/player-context'
import { Button } from '@/components/ui/button'
import { Tooltip } from '@/components/ui/tooltip'
import { ApiError } from '@/lib/api'
import {
  AFFINITY_HELP,
  NOTICE_TEXT,
  eraLine,
  evidenceLine,
  exclusionSummary,
  genreLine,
  statusHeadline,
} from '@/lib/explain'
import { styleFor } from '@/lib/categories'
import type { Profile } from '@/lib/profile'
import type { Artist, DiscoverResult, Track } from '@/lib/types'
import { cn } from '@/lib/utils'
import { trackSearches } from '@/lib/listening'
import { useState } from 'react'
import { AddToPlaylist } from '@/components/playlist'
import { usePlaylist } from '@/lib/playlist-context'
import { trackKey } from '@/lib/playlist'

export type RadioState =
  | { status: 'idle' }
  | { status: 'loading'; previous: DiscoverResult | null }
  | { status: 'done'; result: DiscoverResult }
  | { status: 'error'; error: ApiError; previous: DiscoverResult | null }

export function RadioSection({
  state,
  profile,
  onLike,
  onDislike,
  onMoreLike,
  onRemix,
  onClearFeedback,
  onRetry,
  stale,
}: {
  state: RadioState
  profile: Profile
  onLike: (a: Artist) => void
  onDislike: (a: Artist) => void
  onMoreLike: (a: Artist) => void
  onRemix: () => void
  onClearFeedback: () => void
  onRetry: () => void
  stale: boolean
}) {
  const { add, playlist } = usePlaylist()
  if (state.status === 'idle') return null
  const result = state.status === 'done' ? state.result : state.previous
  const hidden = new Set(profile.disliked.map((d) => d.id))
  const likedIds = new Set(profile.liked.map((l) => l.id))
  const artists = result?.artists.filter((a) => !hidden.has(a.id)) ?? []
  const allAdded = artists.every(a => a.tracks.every(t => playlist.tracks.some(saved => trackKey(saved) === trackKey(t))))
  const feedbackCount = profile.liked.length + profile.disliked.length

  return (
    <section id="radio" className="radio-section scroll-mt-20 py-16">
      <div className="mx-auto max-w-6xl px-4">
        <SectionTitle kicker="03 / Now broadcasting" title={result ? statusHeadline(result) : state.status === 'error' ? 'A break in the signal' : 'Tuning in…'}>
          {result && (
            <div className="flex flex-wrap gap-2">
              <Button variant="accent" onClick={onRemix} disabled={state.status === 'loading' || result.page >= 20}>
                <Shuffle /> Not feeling it? Try another mix
              </Button>
              <Button variant="outline" onClick={() => add(artists.flatMap(a => a.tracks))} disabled={!artists.length || allAdded}>
                <ArrowDownToLine /> {allAdded && artists.length ? 'Visible tracks added' : 'Add visible tracks to My Playlist'}
              </Button>
              {feedbackCount > 0 && (
                <Button variant="quiet" size="sm" onClick={onClearFeedback}>
                  <Undo2 /> Clear feedback
                </Button>
              )}
            </div>
          )}
        </SectionTitle>
        {result && result.page >= 20 && <p role="status" className="mt-4 text-sm">You have reached the end of this session&apos;s 20-page search. Change an interest or tune again to start a new selection.</p>}
        {result && result.artists.length === 0 && result.page < 20 && <p role="status" className="mt-4 text-sm">No new eligible artists on this page. You can try the next mix without changing your preferences.</p>}
        {stale && state.status !== 'loading' && (
          <p role="status" className="mt-5 border-l-4 border-coral bg-coral/10 p-4 text-sm font-semibold">
            Your preferences changed. Tune again when you are ready; these results use the previous settings.
          </p>
        )}

        {state.status === 'error' && (
          <div role="alert" className="mt-6 flex flex-wrap items-center gap-3 rounded-2xl border-2 border-coral bg-coral/15 p-4 text-coral-deep">
            <AlertTriangle className="size-5" />
            <p className="flex-1 font-medium">
              {state.error.message} Your preferences are still here.
            </p>
            {state.error.retryable && (
              <Button variant="outline" size="sm" onClick={onRetry}>
                <RefreshCcw /> Try again
              </Button>
            )}
          </div>
        )}

        {state.status === 'loading' && <Loading />}

        {result && state.status !== 'loading' && <ResultMeta result={result} />}

        {result && result.status !== 'ok' && state.status !== 'loading' && (
          <div className="mt-6 rounded-2xl border-2 border-dashed border-ink/30 p-5">
            <p className="font-display text-xl font-bold">
              {result.status === 'empty'
                ? 'No new eligible artists on this page.'
                : 'CrossSignal shows only artists that passed the checks.'}
            </p>
            <p className="mt-1 text-sm text-ink/70">
              Try the next mix, or review your genre preferences. Your release eras are a soft preference and never exclude an artist.
            </p>
          </div>
        )}

        {state.status !== 'loading' && artists.length > 0 && (
          <ul className="mt-8 grid grid-cols-[minmax(0,1fr)] gap-6 md:grid-cols-2">
            <AnimatePresence>
              {artists.map((artist, i) => (
                <motion.li
                  key={artist.id}
                  layout
                  initial={{ opacity: 0, y: 24 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.92, transition: { duration: 0.2 } }}
                  transition={{ delay: Math.min(i * 0.06, 0.4), type: 'spring', stiffness: 220, damping: 26 }}
                >
                  <ArtistCard
                    artist={artist}
                    era={result?.preferences.eras ?? []}
                    liked={likedIds.has(artist.id)}
                    onLike={() => onLike(artist)}
                    onDislike={() => onDislike(artist)}
                    onMoreLike={() => onMoreLike(artist)}
                  />
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        )}
      </div>
    </section>
  )
}

function ResultMeta({ result }: { result: DiscoverResult }) {
  const exclusions = exclusionSummary(result.tally)
  return (
    <div className="mt-5 space-y-2 text-sm text-ink/75">
      <p>
        From {result.tally.qloo_candidates} artists Qloo returned for{' '}
        {result.signals.map((s) => s.name).join(', ')}
        {result.tag_signals.length > 0 && ` (with ${result.tag_signals.map((s) => s.name).join(', ')})`}
        , CrossSignal checked {result.tally.lookups} against Apple Music.
      </p>
      {exclusions && <p>{exclusions}</p>}
      {result.notices.map((notice) => (
        <p key={notice} className="flex items-start gap-2 text-violet-deep">
          <Info className="mt-0.5 size-4 shrink-0" /> {NOTICE_TEXT[notice] ?? notice}
        </p>
      ))}
    </div>
  )
}

function Loading() {
  return (
    <div className="mt-8" role="status" aria-label="Loading recommendations">
      <div className="flex items-end gap-1.5" aria-hidden>
        {[0, 1, 2, 3, 4].map((i) => (
          <span
            key={i}
            className="h-10 w-2.5 origin-bottom animate-eq rounded-full bg-violet"
            style={{ animationDelay: `${i * 0.12}s` }}
          />
        ))}
        <span className="ml-3 text-sm font-semibold">
          Asking Qloo, then checking each artist against Apple Music…
        </span>
      </div>
      <div className="mt-8 grid gap-6 md:grid-cols-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-80 animate-pulse rounded-[var(--radius-card)] bg-ink/8" />
        ))}
      </div>
    </div>
  )
}

function ArtistCard({
  artist,
  era,
  liked,
  onLike,
  onDislike,
  onMoreLike,
}: {
  artist: Artist
  era: string[]
  liked: boolean
  onLike: () => void
  onDislike: () => void
  onMoreLike: () => void
}) {
  const cover = artist.tracks.find((t) => t.artwork_large)?.artwork_large ?? artist.image_url
  const lead = artist.evidence[0]
  const style = styleFor(lead?.category ?? 'screen')
  const genre = genreLine(artist)
  const eraText = eraLine(artist, era)
  return (
    <article className="record-card flex h-full flex-col overflow-hidden bg-ivory">
      <div className={cn('record-art relative aspect-[4/3] overflow-hidden', style.tint)}>
        {cover ? (
          <img src={cover} alt={`Artwork for ${artist.name}`} loading="lazy" className="size-full object-cover" />
        ) : (
          <div className="grid size-full place-items-center font-display text-6xl font-black opacity-30">
            {artist.name.slice(0, 1)}
          </div>
        )}
        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-ink/85 to-transparent p-4 pt-16">
          <h3 className="font-display text-3xl leading-none font-black text-ivory">{artist.name}</h3>
        </div>
        {artist.source === 'unfiltered' && (
          <Tooltip content="Found in a broader Qloo search after the genre-filtered one returned too few. Its genre was checked here instead.">
            <span className="absolute top-3 left-3 rounded-full bg-ivory px-2.5 py-1 text-xs font-bold">Broader search</span>
          </Tooltip>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-3 p-5">
        <ul className="space-y-1">
          {artist.evidence.map((e) => {
            const s = styleFor(e.category)
            const Icon = s.icon
            return (
              <li key={e.signal_id} className="flex items-start gap-2 text-sm">
                <span className={cn('mt-0.5 grid size-5 shrink-0 place-items-center rounded-full', s.fill)}>
                  <Icon className="size-3 text-ink" />
                </span>
                <span>
                  {evidenceLine(e)}
                  {e.affinity !== null && (
                    <Tooltip content={AFFINITY_HELP}>
                      <button type="button" className="ml-1.5 rounded-full bg-ink/8 px-1.5 text-xs font-semibold text-muted cursor-help">
                        affinity {e.affinity.toFixed(2)}
                      </button>
                    </Tooltip>
                  )}
                </span>
              </li>
            )
          })}
        </ul>
        <p
          className={cn(
            'rounded-xl px-3 py-2 text-sm',
            genre.tone === 'good' && 'bg-lime/40 font-medium',
            genre.tone === 'soft' && 'bg-apricot/20 text-ink/80',
            genre.tone === 'plain' && 'bg-ink/5 text-ink/80',
          )}
        >
          {genre.text}
        </p>
        {eraText && <p className="text-xs text-muted">{eraText}</p>}

        <ol className="mt-1 space-y-1.5">
          {artist.tracks.map((track) => (
            <TrackRow key={track.url} track={track} />
          ))}
        </ol>

        <div className="mt-auto flex flex-wrap items-center gap-2 border-t border-ink/10 pt-3">
          <Button
            size="sm"
            variant={liked ? 'accent' : 'outline'}
            onClick={onLike}
            aria-pressed={liked}
            aria-label={liked ? `Stop steering with ${artist.name}` : `Like ${artist.name} to steer the next remix`}
          >
            <ThumbsUp /> {liked ? 'Steering / liked' : 'Like & steer'}
          </Button>
          <Button size="sm" variant="outline" onClick={onDislike} aria-label={`Hide ${artist.name} and exclude from remixes`}>
            <ThumbsDown /> Not for me
          </Button>
          <Button size="sm" variant="ghost" onClick={onMoreLike} className="ml-auto">
            <Shuffle /> More like this
          </Button>
        </div>
      </div>
    </article>
  )
}

function TrackRow({ track }: { track: Track }) {
  const { current, playing, failed, toggle } = usePlayer()
  const [expanded, setExpanded] = useState(false)
  const active = current?.url === track.url
  const meta = [track.album, track.year].filter(Boolean).join(' · ')
  return (
    <li className="rounded-xl p-2 transition hover:bg-ink/5"><div className="flex items-center gap-3">
      <button
        type="button"
        disabled={!track.preview_url}
        onClick={() => toggle(track)}
        aria-label={
          !track.preview_url ? `No preview for ${track.title}` : active && playing ? `Pause ${track.title}` : `Play preview of ${track.title}`
        }
        className={cn(
          'relative grid size-11 shrink-0 place-items-center overflow-hidden rounded-lg bg-ink/10 cursor-pointer disabled:cursor-not-allowed',
          active && playing && 'ring-2 ring-violet',
        )}
      >
        {track.artwork_small && <img src={track.artwork_small} alt="" className="absolute inset-0 size-full object-cover" />}
        {track.preview_url && (
          <span className="relative grid size-7 place-items-center rounded-full bg-ivory/90 text-ink">
            {active && playing ? <Pause className="size-3.5" /> : <Play className="size-3.5 translate-x-px" />}
          </span>
        )}
      </button>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">{track.title}</p>
        <p className="truncate text-xs text-muted">
          {failed === track.url ? 'Preview unavailable right now' : meta}
        </p>
      </div>
      <a
        href={track.url}
        target="_blank"
        rel="noreferrer"
        className="grid size-8 shrink-0 place-items-center rounded-full text-muted hover:bg-ink hover:text-ivory"
        aria-label={`Open ${track.title} on Apple Music`}
      >
        <ExternalLink className="size-4" />
      </a>
      <AddToPlaylist track={track} />
      </div>
      <button type="button" onClick={() => setExpanded(!expanded)} aria-expanded={expanded} className="mt-2 ml-14 cursor-pointer text-xs font-semibold underline underline-offset-4">{expanded ? 'Hide listening options' : 'Listen elsewhere'}</button>
      {expanded && (
        <div className="mt-3 border-t border-ink/15 pt-3">
          <p className="mb-2 text-xs text-muted">
            Search for {track.artist} + {track.title}. Results may vary.
          </p>
          <div className="flex flex-wrap gap-2">
            {trackSearches(track).map(({ label, href }) => (
              <a key={label} href={href} target="_blank" rel="noopener noreferrer"
                className="rounded-full border border-ink/25 px-3 py-2 text-xs font-semibold hover:bg-ink hover:text-ivory">
                {label} search
              </a>
            ))}
          </div>
        </div>
      )}
    </li>
  )
}
