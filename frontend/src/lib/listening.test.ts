import { expect, it } from 'vitest'
import { trackSearches } from './listening'
it('searches each platform for artist and track with safe punctuation', () => {
 const links = trackSearches({ artist: 'AC/DC', title: 'Who & You?' })
 expect(links.map(l => l.label)).toEqual(['YouTube', 'YouTube Music', 'Spotify'])
 for (const link of links) {
 expect(decodeURIComponent(link.href)).toContain('AC/DC Who & You?')
 expect(link.href).toContain('%26')
 expect(link.href).toContain('%3F')
 }
})
