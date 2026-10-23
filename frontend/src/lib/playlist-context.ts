import { createContext, useContext } from 'react'
import type { Playlist } from './playlist'
import type { Track } from './types'

export const PlaylistContext = createContext<{
  playlist: Playlist
  add: (tracks: Track[]) => void
  remove: (key: string) => void
  clear: () => void
  move: (from: number, to: number) => void
  rename: (name: string) => void
  notice: string
  persistent: boolean
} | null>(null)

export function usePlaylist() {
  const value = useContext(PlaylistContext)
  if (!value) throw new Error('PlaylistProvider is missing')
  return value
}
