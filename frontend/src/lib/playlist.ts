import type { Track } from './types'
import { loadFavorites } from './favorites'

export interface Playlist { name: string; tracks: Track[] }
export const EMPTY_PLAYLIST: Playlist = { name: 'My Playlist', tracks: [] }
export const PLAYLIST_KEY = 'crosssignal.playlist.v1'
export const PLAYLIST_LIMIT = 300

/** Apple track ids are stable across regional URLs and tracking parameters. */
export function trackKey(track: Pick<Track, 'url'>): string | null {
  try {
    const url = new URL(track.url)
    if (url.protocol !== 'https:' || url.username || url.password || !['music.apple.com', 'itunes.apple.com'].includes(url.hostname)) return null
    const id = url.searchParams.get('i') ?? url.pathname.match(/\/(?:id)?(\d+)\/?$/)?.[1]
    return id && /^\d+$/.test(id) ? `apple:${id}` : null
  } catch { return null }
}

function optional(value: unknown): string | null {
  return typeof value === 'string' ? value.slice(0, 1000) : null
}

function safeMedia(value: unknown): string | null {
  if (typeof value !== 'string') return null
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && (url.hostname.endsWith('.mzstatic.com') || url.hostname.endsWith('.itunes.apple.com')) ? url.href : null
  } catch { return null }
}

export function parseTrack(value: unknown): Track | null {
  if (!value || typeof value !== 'object') return null
  const t = value as Record<string, unknown>
  if (typeof t.url !== 'string' || !trackKey({ url: t.url }) ||
      typeof t.artist !== 'string' || !t.artist.trim() || typeof t.title !== 'string' || !t.title.trim()) return null
  return {
    url: t.url, title: t.title.slice(0, 300), artist: t.artist.slice(0, 300),
    album: optional(t.album), year: optional(t.year), genre: optional(t.genre),
    artwork_small: safeMedia(t.artwork_small), artwork_large: safeMedia(t.artwork_large),
    preview_url: safeMedia(t.preview_url),
  }
}

export function addTracks(playlist: Playlist, tracks: Track[]): Playlist {
  const keys = new Set(playlist.tracks.map(trackKey))
  const next = [...playlist.tracks]
  for (const candidate of tracks) {
    const track = parseTrack(candidate)
    const key = track && trackKey(track)
    if (!track || !key || keys.has(key) || next.length >= PLAYLIST_LIMIT) continue
    keys.add(key)
    next.push(track)
  }
  return { ...playlist, tracks: next }
}

export function removeTrack(playlist: Playlist, key: string): Playlist {
  return { ...playlist, tracks: playlist.tracks.filter(t => trackKey(t) !== key) }
}

export function moveTrack(playlist: Playlist, from: number, to: number): Playlist {
  if (from < 0 || to < 0 || from >= playlist.tracks.length || to >= playlist.tracks.length) return playlist
  const tracks = [...playlist.tracks]
  tracks.splice(to, 0, tracks.splice(from, 1)[0])
  return { ...playlist, tracks }
}

export function renamePlaylist(playlist: Playlist, name: string): Playlist {
  return { ...playlist, name: name.trim().slice(0, 80) || 'My Playlist' }
}

export function loadPlaylist(): Playlist {
  try {
    const raw = localStorage.getItem(PLAYLIST_KEY)
    if (raw !== null) {
      const value = JSON.parse(raw)
      if (!value || !Array.isArray(value.tracks)) return EMPTY_PLAYLIST
      return addTracks(renamePlaylist(EMPTY_PLAYLIST, typeof value.name === 'string' ? value.name : ''), value.tracks)
    }
    // One collection: migrate the previous saved rotation, preserving its order.
    return addTracks(EMPTY_PLAYLIST, loadFavorites().map(f => parseTrack(f.track)).filter((t): t is Track => t !== null))
  } catch { return EMPTY_PLAYLIST }
}

export function savePlaylist(playlist: Playlist): boolean {
  try { localStorage.setItem(PLAYLIST_KEY, JSON.stringify(playlist)); return true } catch { return false }
}

export function tracklist(playlist: Playlist): string {
  return [playlist.name, ...playlist.tracks.map((t, i) => `${i + 1}. ${t.artist} - ${t.title}\n   ${t.url}`)].join('\n')
}

export function playlistCsv(playlist: Playlist): string {
  const cell = (value: string) => `"${(/^[\s]*[=+@-]/.test(value) ? "'" + value : value).replaceAll('"', '""')}"`
  return [['Artist', 'Track', 'Album', 'Apple Music URL'], ...playlist.tracks.map(t => [t.artist, t.title, t.album ?? '', t.url])]
    .map(row => row.map(cell).join(',')).join('\r\n')
}
