import { createContext, useContext } from 'react'
import type { Track } from './types'

export interface PlayerState {
  current: Track | null
  playing: boolean
  failed: string | null
  toggle: (track: Track) => void
  stop: () => void
}

export const PlayerContext = createContext<PlayerState | null>(null)

export function usePlayer(): PlayerState {
  const context = useContext(PlayerContext)
  if (!context) throw new Error('usePlayer outside PlayerProvider')
  return context
}
