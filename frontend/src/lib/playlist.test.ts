import { afterEach, expect, it, vi } from 'vitest'
import { addTracks, EMPTY_PLAYLIST, loadPlaylist, moveTrack, PLAYLIST_KEY, playlistCsv, removeTrack, renamePlaylist, savePlaylist, trackKey, tracklist } from './playlist'
import type { Track } from './types'

const song = (id: number, title = `Song ${id}`): Track => ({
  title, artist: 'Test Artist', album: null, year: '2004', genre: 'Rock',
  url: `https://music.apple.com/us/album/test/90?i=${id}`, artwork_small: null, artwork_large: null, preview_url: null,
})
afterEach(() => vi.unstubAllGlobals())

it('adds individual or visible tracks once using cross-region Apple track ids', () => {
  const playlist = addTracks(EMPTY_PLAYLIST, [song(1), song(2), { ...song(1), url: 'https://music.apple.com/gb/song/other-title/1' }])
  expect(playlist.tracks.map(trackKey)).toEqual(['apple:1', 'apple:2'])
  expect(addTracks(playlist, [song(2)]).tracks).toHaveLength(2)
  expect(trackKey({ url: 'https://music.apple.com/' })).toBeNull()
  expect(trackKey({ url: 'https://music.apple.com.evil.example/us/song/123' })).toBeNull()
})
it('removes and reorders without mutating or losing songs', () => {
  const playlist = addTracks(EMPTY_PLAYLIST, [song(1), song(2), song(3)])
  expect(moveTrack(playlist, 2, 0).tracks.map(t => t.title)).toEqual(['Song 3', 'Song 1', 'Song 2'])
  expect(moveTrack(playlist, 0, -1)).toBe(playlist)
  expect(removeTrack(playlist, 'apple:2').tracks.map(trackKey)).toEqual(['apple:1', 'apple:3'])
  expect(playlist.tracks).toHaveLength(3)
})
it('renames and persists a validated playlist', () => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value) })
  const playlist = renamePlaylist(addTracks(EMPTY_PLAYLIST, [song(1)]), '  Evening notes  ')
  expect(savePlaylist(playlist)).toBe(true)
  expect(loadPlaylist()).toEqual(playlist)
  data.set(PLAYLIST_KEY, JSON.stringify({ name: 'Unsafe', tracks: [null, { url: 'javascript:alert(1)', title: 'X', artist: 'Y' }, song(1)] }))
  expect(loadPlaylist().tracks).toEqual([song(1)])
  data.set(PLAYLIST_KEY, '{bad')
  expect(loadPlaylist()).toEqual(EMPTY_PLAYLIST)
})
it('migrates the old saved rotation without creating a second collection', () => {
  vi.stubGlobal('localStorage', { getItem: (key: string) => key === PLAYLIST_KEY ? null : JSON.stringify([{ artist: 'Test Artist', track: song(1) }, { track: song(1) }]) })
  expect(loadPlaylist().tracks).toEqual([song(1)])
})
it('exports readable text and CSV with quoting and formula protection', () => {
  const playlist = addTracks(EMPTY_PLAYLIST, [song(1, 'A "quote", a comma'), song(2, '=HYPERLINK("bad")')])
  expect(tracklist(playlist)).toContain('1. Test Artist - A "quote", a comma')
  expect(playlistCsv(playlist)).toContain('"A ""quote"", a comma"')
  expect(playlistCsv(playlist)).toContain('"\'=HYPERLINK(')
  expect(playlistCsv(playlist).split('\r\n')).toHaveLength(3)
})
it('bounds storage and handles blocked persistence', () => {
  expect(addTracks(EMPTY_PLAYLIST, Array.from({ length: 350 }, (_, i) => song(i))).tracks).toHaveLength(300)
  vi.stubGlobal('localStorage', { getItem: () => { throw new Error('blocked') }, setItem: () => { throw new Error('blocked') } })
  expect(loadPlaylist()).toEqual(EMPTY_PLAYLIST)
  expect(savePlaylist(EMPTY_PLAYLIST)).toBe(false)
})
