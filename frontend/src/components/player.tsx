import { AnimatePresence, motion } from 'motion/react'
import { Pause, Square } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { PlayerContext, usePlayer } from '@/lib/player-context'
import type { Track } from '@/lib/types'

/** One shared <audio> element: starting a preview stops the previous one. */
export function PlayerProvider({ children }: { children: React.ReactNode }) {
  const audio = useRef<HTMLAudioElement | null>(null)
  const [current, setCurrent] = useState<Track | null>(null)
  const [playing, setPlaying] = useState(false)
  const [failed, setFailed] = useState<string | null>(null)

  useEffect(() => {
    const element = new Audio()
    element.preload = 'none'
    element.onended = () => setPlaying(false)
    element.onpause = () => setPlaying(false)
    element.onplay = () => setPlaying(true)
    audio.current = element
    return () => element.pause()
  }, [])

  const stop = useCallback(() => {
    audio.current?.pause()
    setCurrent(null)
  }, [])

  const toggle = useCallback(
    (track: Track) => {
      const element = audio.current
      if (!element || !track.preview_url) return
      if (current?.url === track.url && playing) {
        element.pause()
        return
      }
      if (current?.url !== track.url) element.src = track.preview_url
      setCurrent(track)
      setFailed(null)
      element.play().catch(() => {
        setPlaying(false)
        setFailed(track.url)
      })
    },
    [current, playing],
  )

  return (
    <PlayerContext.Provider value={{ current, playing, failed, toggle, stop }}>
      {children}
      <NowPlaying />
    </PlayerContext.Provider>
  )
}

function NowPlaying() {
  const { current, playing, toggle, stop } = usePlayer()
  return (
    <AnimatePresence>
      {current && (
        <motion.div
          role="status"
          aria-live="polite"
          initial={{ y: 80, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 80, opacity: 0 }}
          className="now-playing fixed bottom-40 left-1/2 z-40 flex md:bottom-28 w-[min(28rem,calc(100%-2rem))] -translate-x-1/2 items-center gap-3 rounded-full bg-ink py-2 pr-2 pl-2 text-ivory shadow-pop"
        >
          {current.artwork_small ? (
            <img
              src={current.artwork_small}
              alt=""
              className={`size-10 rounded-full object-cover ${playing ? 'animate-spin-slow' : ''}`}
            />
          ) : (
            <span className="size-10 rounded-full bg-violet" />
          )}
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{current.title}</p>
            <p className="truncate text-xs text-ivory/65">
              {current.artist} · 30-second Apple preview
            </p>
          </div>
          <button
            type="button"
            onClick={() => (playing ? toggle(current) : stop())}
            className="grid size-10 place-items-center rounded-full bg-lime text-ink cursor-pointer"
            aria-label={playing ? 'Pause preview' : 'Close player'}
          >
            {playing ? <Pause className="size-4" /> : <Square className="size-3.5" />}
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
