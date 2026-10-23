import { expect, it } from 'vitest'
import { DiscoverySession } from './session'
import { emptyProfile, profileReducer } from './profile'
import type { Artist, DiscoverResult } from './types'

// Synthetic, minimal state fixtures; never used as application/provider data.
const artist = (id: string, name = id) => ({ id, name }) as Artist
const result = (page: number, artists: Artist[]) => ({ page, artists, status: 'ok' }) as DiscoverResult

it('advances pages, suppresses previously shown ids and name aliases, and handles exhaustion', () => {
  const session = new DiscoverySession()
  const profile = { ...emptyProfile, prefs: { ...emptyProfile.prefs, eras: ['1980s', '2000s', '2010s'] } }
  expect(session.nextPage(profile)).toBe(1)
  session.accept(session.begin(profile, true), result(1, [artist('a')]))
  expect(session.nextPage(profile)).toBe(2)
  const second = session.accept(session.begin(profile, false), result(2, [artist('a'), artist('alias', 'A'), artist('b')]))
  expect(second?.artists.map(a => a.id)).toEqual(['b'])
  expect(session.ids).toEqual(['a', 'b'])
  expect(session.nextPage({ ...profile, liked: [{ id: 'liked', kind: 'entity', category: 'liked', name: 'Liked', qloo_type: 'urn:entity:artist' }] })).toBe(3)
  const empty = session.accept(session.begin(profile, false), result(3, [artist('a')]))
  expect(empty?.status).toBe('empty')
  expect(session.nextPage(profile)).toBe(4)
  session.accept(session.begin(profile, false), result(20, []))
  expect(session.nextPage(profile)).toBeNull()
  expect(profile.prefs.eras).toEqual(['1980s', '2000s', '2010s'])
})
it('reset invalidates pending results and clears reroll history and preferences', () => {
  const session = new DiscoverySession()
  const profile = { ...emptyProfile, prefs: { ...emptyProfile.prefs, eras: ['1980s'], discovery: 'adventurous' as const } }
  const pending = session.begin(profile, true)
  session.reset()
  expect(session.accept(pending, result(1, [artist('old')]))).toBeNull()
  expect(session.page).toBe(0)
  expect(session.ids).toEqual([])
  expect(profileReducer(profile, { type: 'reset' })).toEqual(emptyProfile)
})
it('ignores superseded requests, retains dislikes and bounds session history', () => {
  const session = new DiscoverySession()
  const profile = { ...emptyProfile, disliked: [{ id: 'avoid', name: 'Avoid' }] }
  const old = session.begin(profile, true)
  const newer = session.begin(profile, false)
  expect(session.accept(old, result(1, [artist('old')]))).toBeNull()
  session.accept(newer, result(1, Array.from({ length: 200 }, (_, i) => artist(String(i)))))
  expect(session.ids).toHaveLength(160)
  expect(profile.disliked).toEqual([{ id: 'avoid', name: 'Avoid' }])
})
