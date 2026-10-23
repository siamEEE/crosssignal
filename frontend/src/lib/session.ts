import type { Artist, DiscoverResult } from './types'
import type { Profile } from './profile'

export function tasteKey(profile: Profile): string {
  // Feedback can change between mixes without forgetting artists already heard.
  return JSON.stringify([profile.signals, profile.prefs])
}

/** One bounded, in-memory discovery session. Reset invalidates every old token. */
export class DiscoverySession {
  version = 0
  page = 0
  key = ''
  ids: string[] = []
  names: string[] = []

  reset() {
    this.version++
    this.page = 0
    this.key = ''
    this.ids = []
    this.names = []
  }

  nextPage(profile: Profile): number | null {
    if (tasteKey(profile) !== this.key) return 1
    return this.page < 20 ? this.page + 1 : null
  }

  begin(profile: Profile, fresh: boolean): number {
    if (fresh || tasteKey(profile) !== this.key) this.reset()
    this.key = tasteKey(profile)
    return ++this.version
  }

  accept(version: number, result: DiscoverResult): DiscoverResult | null {
    if (version !== this.version) return null
    const artists = result.artists.filter(a => !this.ids.includes(a.id) && !this.names.includes(this.normalize(a)))
    this.ids = [...new Set([...this.ids, ...artists.map(a => a.id)])].slice(-160)
    this.names = [...new Set([...this.names, ...artists.map(a => this.normalize(a))])].slice(-160)
    this.page = result.page
    return { ...result, artists, status: artists.length === 0 ? 'empty' : artists.length < 3 ? 'insufficient' : result.status }
  }

  private normalize(artist: Artist): string {
    return artist.name.normalize('NFKC').toLocaleLowerCase('en').trim()
  }
}
