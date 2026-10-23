import { Radio, RotateCcw, Moon, Sun } from 'lucide-react'
import type { Theme } from '@/lib/theme'
import type { Health } from '@/lib/types'
import { cn } from '@/lib/utils'

const NAV = [
  { href: '#explore', label: '01 / Culture' },
  { href: '#sound', label: '02 / Sound' },
  { href: '#tune', label: '03 / Tune My Radio' },
  { href: '#playlist', label: 'My Playlist' },
]

export function Header({ health, onReset, theme, onTheme }: { health: Health | null | 'error'; onReset: () => void; theme: Theme; onTheme: () => void }) {
  const live = health !== null && health !== 'error' && health.qloo_configured
  const label =
    health === null ? 'Connecting…' : health === 'error' ? 'Server offline' : live ? 'Qloo live' : 'Qloo not configured'
  return (
    <header className="sticky top-0 z-30 border-b border-ink/10 bg-ivory/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4">
        <a href="#top" className="flex items-center gap-2" aria-label="CrossSignal home">
          <span className="grid size-9 place-items-center rounded-full bg-ink text-lime">
            <Radio className="size-5" />
          </span>
          <span className="leading-none">
            <span className="block font-display text-lg font-black tracking-tight">CrossSignal</span>
            <span className="block text-[0.65rem] font-semibold tracking-[0.2em] text-muted uppercase">
              Culture Radio
            </span>
          </span>
        </a>
        <div className="header-tools ml-auto flex items-center gap-2">
          <button type="button" className="header-control" onClick={onTheme} aria-pressed={theme === 'after-hours'} aria-label="After Hours theme">
            {theme === 'daylight' ? <Sun size={15} /> : <Moon size={15} />}
            <span>{theme === 'daylight' ? 'Daylight' : 'After Hours'}</span>
          </button>
          <button type="button" className="header-control" onClick={onReset}><RotateCcw size={14} />Reset</button>
        </div>
        <nav aria-label="Sections" className="ml-auto flex gap-1 overflow-x-auto">
          {NAV.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="rounded-full px-3 py-1.5 text-sm font-medium text-ink/75 transition hover:bg-ink hover:text-ivory"
            >
              {item.label}
            </a>
          ))}
        </nav>
        <span
          className={cn(
            'ml-auto hidden items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold xl:inline-flex',
            live ? 'border-lime-deep/30 bg-lime/40 text-ink' : 'border-coral/40 bg-coral/15 text-coral-deep',
          )}
          title={health && health !== 'error' ? health.config_problem ?? undefined : undefined}
        >
          <span className={cn('size-2 rounded-full', live ? 'bg-lime-deep animate-pulse' : 'bg-coral-deep')} />
          {label}
        </span>
      </div>
    </header>
  )
}
