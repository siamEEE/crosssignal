/** Saved songs are independent of the bounded Qloo remix feedback. */
export interface Favorite {
  artist: string
  track: { title: string; artist: string; url: string }
}

const KEY = 'crosssignal.favorites.v1'

export function loadFavorites(): Favorite[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    if (!Array.isArray(value)) return []
    return value.filter((v): v is Favorite =>
      v && typeof v.artist === 'string' && v.track &&
      typeof v.track.title === 'string' && typeof v.track.artist === 'string' &&
      typeof v.track.url === 'string' &&
      /^https:\/\/(music\.apple\.com|itunes\.apple\.com)\//.test(v.track.url),
    ).slice(0, 100)
  } catch {
    return []
  }
}

export function saveFavorites(favorites: Favorite[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(favorites.slice(0, 100)))
  } catch {
    // Saving still works in memory when browser storage is unavailable.
  }
}

export function toggleFavorite(favorites: Favorite[], favorite: Favorite): Favorite[] {
  return favorites.some(f => f.track.url === favorite.track.url)
    ? favorites.filter(f => f.track.url !== favorite.track.url)
    : [favorite, ...favorites].slice(0, 100)
}
