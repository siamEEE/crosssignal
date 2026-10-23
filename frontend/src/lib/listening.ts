import type { Track } from './types'
/** Search destinations, never verified catalog links. */
export function trackSearches(track: Pick<Track, 'artist' | 'title'>) {
 const query = encodeURIComponent(`${track.artist} ${track.title}`)
 return [
 { label: 'YouTube', href: `https://www.youtube.com/results?search_query=${query}` },
 { label: 'YouTube Music', href: `https://music.youtube.com/search?q=${query}` },
 { label: 'Spotify', href: `https://open.spotify.com/search/${query}` },
 ]
}
