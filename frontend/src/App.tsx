import { MotionConfig } from 'motion/react'
import { AlertTriangle, CheckCircle2 } from 'lucide-react'
import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import { PlaylistProvider, PlaylistSection } from '@/components/playlist'
import { DiscoverySession } from '@/lib/session'
import { initialTheme, applyTheme } from '@/lib/theme'
import { Describe } from '@/components/describe'
import { Explore } from '@/components/explore'
import { Header } from '@/components/header'
import { Hero } from '@/components/hero'
import { PlayerProvider } from '@/components/player'
import { RadioSection, type RadioState } from '@/components/radio'
import { Sound } from '@/components/sound'
import { Tray } from '@/components/tray'
import { TooltipProvider } from '@/components/ui/tooltip'
import { api, ApiError } from '@/lib/api'
import {
  blocker,
  emptyProfile,
  loadProfile,
  profileReducer,
  saveProfile,
  type Profile,
} from '@/lib/profile'
import type {
  Artist,
  Category,
  Collection,
  GenreOptions,
  Health,
  Interpretation,
  Signal,
} from '@/lib/types'

function asApiError(error: unknown): ApiError {
  return error instanceof ApiError ? error : new ApiError('http', String(error), 0)
}

export default function App() {
  const [health, setHealth] = useState<Health | null | 'error'>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [collections, setCollections] = useState<Collection[]>([])
  const [genreOptions, setGenreOptions] = useState<GenreOptions | null>(null)
  const [profile, dispatch] = useReducer(profileReducer, undefined, loadProfile)
  const [radio, setRadio] = useState<RadioState>({ status: 'idle' })
  const [tunedProfile, setTunedProfile] = useState<Profile | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const lastRequest = useRef<{ profile: Profile; page: number } | null>(null)
  const session = useRef(new DiscoverySession())
  const controller = useRef<AbortController | null>(null)
  const [resetKey, setResetKey] = useState(0)
  const [theme, setTheme] = useState(initialTheme)
  useEffect(() => applyTheme(theme), [theme])

  function reset() {
    if (!window.confirm('Reset your interests, preferences and discovery results? Your playlist and theme will stay.')) return
    controller.current?.abort()
    session.current.reset()
    lastRequest.current = null
    dispatch({ type: 'reset' })
    saveProfile(emptyProfile)
    setRadio({ status: 'idle' })
    setTunedProfile(null)
    setResetKey(k => k + 1)
    setToast('Taste profile reset. Your playlist is still here.')
  }

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth('error'))
    Promise.all([api.categories(), api.featured(), api.genres()])
      .then(([c, f, g]) => {
        setCategories(c)
        setCollections(f)
        setGenreOptions(g)
      })
      .catch(() => setHealth('error'))
  }, [])

  useEffect(() => saveProfile(profile), [profile])

  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), 2600)
    return () => clearTimeout(timer)
  }, [toast])

  const live = health !== null && health !== 'error' && health.qloo_configured

  const run = useCallback(
    async (snapshot: Profile, page: number, fresh = false) => {
      if (blocker(snapshot)) return
      controller.current?.abort()
      controller.current = new AbortController()
      const version = session.current.begin(snapshot, fresh)
      lastRequest.current = { profile: snapshot, page }
      setRadio((current) => ({
        status: 'loading',
        previous: current.status === 'done' ? current.result : current.status === 'idle' ? null : current.previous,
      }))
      requestAnimationFrame(() =>
        document.getElementById('radio')?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
      )
      try {
        const next = await api.discover({
          signals: snapshot.signals,
          preferences: snapshot.prefs,
          feedback: { liked: snapshot.liked, disliked: snapshot.disliked.map((d) => d.id) },
          page,
          exclude_artists: [...session.current.ids],
        }, controller.current.signal)
        const accepted = session.current.accept(version, next)
        if (accepted) {
          setTunedProfile(snapshot)
          setRadio({ status: 'done', result: accepted })
        }
      } catch (error) {
        if (version !== session.current.version) return
        setRadio((current) => ({
          status: 'error',
          error: asApiError(error),
          previous: current.status === 'loading' ? current.previous : null,
        }))
      }
    },
    [],
  )

  function addSignal(signal: Signal, how: 'exact' | 'picked') {
    if (profile.signals.some((s) => s.id === signal.id)) return
    if (profile.signals.length >= 5) {
      setToast('You already have 5 interests. Remove one first.')
      return
    }
    dispatch({ type: 'add', signal })
    setToast(how === 'exact' ? `Added ${signal.name} (exact Qloo match)` : `Added ${signal.name}`)
  }

  function applyMusic(music: Interpretation['music']) {
    for (const id of music.preferred) dispatch({ type: 'genre', id, state: 'preferred' })
    for (const id of music.avoided) dispatch({ type: 'genre', id, state: 'avoided' })
    if (music.eras.length) dispatch({ type: 'eras', eras: [...profile.prefs.eras, ...music.eras] })
    if (music.discovery) dispatch({ type: 'discovery', mode: music.discovery })
    setToast('Music preferences applied. Review them in Sound.')
  }

  function moreLike(artist: Artist) {
    const alreadyLiked = profile.liked.some((l) => l.id === artist.id)
    const next = alreadyLiked ? profile : profileReducer(profile, { type: 'like', artist })
    dispatch({ type: 'replace', profile: next })
    void run(next, 1)
  }

  const stop = blocker(profile)
  return (
    <MotionConfig reducedMotion="user">
      <TooltipProvider>
        <PlaylistProvider>
          <PlayerProvider key={resetKey}>
            <a
              href="#explore"
              className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-full focus:bg-ink focus:px-4 focus:py-2 focus:text-ivory"
            >
              Skip to explore
            </a>
            <Header health={health} onReset={reset} theme={theme} onTheme={() => setTheme(t => t === 'daylight' ? 'after-hours' : 'daylight')} />
            {(health === 'error' || (health !== null && !health.qloo_configured)) && (
              <div role="alert" className="border-b-2 border-coral bg-coral/15">
                <p className="mx-auto flex max-w-6xl items-start gap-2 px-4 py-3 text-sm text-coral-deep">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                  {health === 'error'
                    ? "Can't reach the music service right now. Please reload or try again later."
                    : 'Music discovery is temporarily unavailable. Please try again later.'}
                </p>
              </div>
            )}
            <main>
              <Hero categories={categories} theme={theme} />
              <Explore key={`explore-${resetKey}`}
                categories={categories}
                collections={collections}
                selected={profile.signals}
                live={live}
                onAdd={addSignal}
              />
              <Describe key={`describe-${resetKey}`}
                live={live}
                selected={profile.signals}
                genreOptions={genreOptions}
                onAdd={addSignal}
                onApplyMusic={applyMusic}
              />
              <Sound options={genreOptions} prefs={profile.prefs} dispatch={dispatch} />
              <RadioSection
                stale={!!tunedProfile && JSON.stringify(tunedProfile) !== JSON.stringify(profile)}
                state={radio}
                profile={profile}
                onLike={(artist) => dispatch({ type: 'like', artist })}
                onDislike={(artist) => dispatch({ type: 'dislike', artist })}
                onMoreLike={moreLike}
                onRemix={() => { const page = session.current.nextPage(profile); if (page) void run(profile, page) }}
                onClearFeedback={() => dispatch({ type: 'clear-feedback' })}
                onRetry={() => lastRequest.current && run(lastRequest.current.profile, lastRequest.current.page)}
              />
              <PlaylistSection />
              <footer className="mx-auto max-w-6xl px-4 py-12 text-xs leading-relaxed text-muted">
                Artist recommendations: Qloo Insights API (hackathon). Songs, artwork and 30-second
                previews: Apple iTunes Search API; titles open on Apple Music. Affinity is Qloo&apos;s
                association ranking, not a prediction of what you&apos;ll like.
              </footer>
            </main>
            <Tray
              profile={profile}
              dispatch={dispatch}
              blocker={live ? stop : 'Live Qloo backend unavailable.'}
              loading={radio.status === 'loading'}
              onTune={() => run(profile, 1, true)}
            />
            <div aria-live="polite" className="pointer-events-none fixed top-20 right-4 z-50">
              {toast && (
                <p className="flex items-center gap-2 rounded-full bg-ink px-4 py-2 text-sm font-semibold text-ivory shadow-pop">
                  <CheckCircle2 className="size-4 text-lime" /> {toast}
                </p>
              )}
            </div>
          </PlayerProvider>
        </PlaylistProvider>
      </TooltipProvider>
    </MotionConfig>
  )
}
