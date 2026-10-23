import { expect, it, vi } from 'vitest'
import { loadFavorites, saveFavorites, toggleFavorite } from './favorites'
import type { Favorite } from './favorites'
const favorite = { artist: 'Artist', track: { url: 'https://music.apple.com/us/song/123', title: 'Song', artist: 'Artist' } } as Favorite
it('keeps favorites independent and toggles by exact track URL', () => {
 const list = toggleFavorite([], favorite)
 expect(list).toEqual([favorite])
 expect(toggleFavorite(list, favorite)).toEqual([])
})
it('handles corrupt storage and rejects unsafe saved links', () => {
 vi.stubGlobal('localStorage', { getItem: () => '{broken', setItem: () => { throw new Error('blocked') } })
 expect(loadFavorites()).toEqual([])
 expect(() => saveFavorites([favorite])).not.toThrow()
 vi.stubGlobal('localStorage', { getItem: () => JSON.stringify([favorite, { ...favorite, track: { ...favorite.track, url: 'javascript:alert(1)' } }]) })
 expect(loadFavorites()).toEqual([favorite])
 vi.unstubAllGlobals()
})
