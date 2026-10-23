import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  MAX_LIKED,
  MAX_SIGNALS,
  blocker,
  emptyProfile,
  genreState,
  loadProfile,
  profileReducer as reduce,
  type Profile,
} from './profile'
import type { Artist, Signal } from './types'

afterEach(() => vi.unstubAllGlobals())

describe('stored profiles', () => {
  it('migrates a single era and sanitizes multi-era persistence', () => {
    vi.stubGlobal('localStorage', { getItem: () => JSON.stringify({ ...emptyProfile, prefs: { ...emptyProfile.prefs, eras: undefined, era: '2000s' } }) })
    expect(loadProfile().prefs.eras).toEqual(['2000s'])
    vi.stubGlobal('localStorage', { getItem: () => JSON.stringify({ ...emptyProfile, prefs: { ...emptyProfile.prefs, eras: ['2010s', 'bad', '1980s', '2010s', '2000s'] } }) })
    expect(loadProfile().prefs.eras).toEqual(['1980s', '2000s', '2010s'])
  })
  it('recovers from malformed preference lists', () => {
    vi.stubGlobal('localStorage', { getItem: () => JSON.stringify({ ...emptyProfile, prefs: { preferred: null } }) })
    expect(loadProfile()).toEqual(emptyProfile)
  })
  it('drops malformed signals and bounds persisted feedback', () => {
    vi.stubGlobal('localStorage', { getItem: () => JSON.stringify({
      ...emptyProfile, signals: [null, { id: 'broken' }],
      disliked: Array.from({ length: 70 }, (_, i) => ({ id: String(i), name: 'Hidden' })),
    }) })
    expect(loadProfile().signals).toEqual([])
    expect(loadProfile().disliked).toHaveLength(50)
  })
})

it('toggles several eras and clears them with Any era', () => {
  let profile = emptyProfile
  for (const era of ['1980s', '2000s', '2010s']) profile = reduce(profile, { type: 'era', era })
  expect(profile.prefs.eras).toEqual(['1980s', '2000s', '2010s'])
  profile = reduce(profile, { type: 'era', era: '2000s' })
  expect(profile.prefs.eras).toEqual(['1980s', '2010s'])
  expect(reduce(profile, { type: 'era', era: null }).prefs.eras).toEqual([])
})

const film = (id: string): Signal => ({
  id,
  kind: 'entity',
  name: `Film ${id}`,
  category: 'screen',
  qloo_type: 'urn:entity:movie',
})
const mood: Signal = {
  id: 'urn:tag:ambience:qloo:rainy',
  kind: 'tag',
  name: 'Rainy',
  category: 'aesthetics',
  qloo_type: 'urn:tag:ambience:qloo',
}
const artist = (id: string): Artist => ({
  id,
  name: `Artist ${id}`,
  image_url: null,
  source: 'filtered',
  popularity: 0.5,
  genre: { fit: 'neutral', support: null, related_only: false, matched: [], qloo_tags: [], catalog_genre: null },
  era: null,
  evidence: [],
  tracks: [],
})

describe('interests', () => {
  it('adds once and respects the five-interest limit', () => {
    let p: Profile = emptyProfile
    for (let i = 0; i < MAX_SIGNALS + 2; i++) p = reduce(p, { type: 'add', signal: film(`f${i}`) })
    p = reduce(p, { type: 'add', signal: film('f0') })
    expect(p.signals.map((s) => s.id)).toEqual(['f0', 'f1', 'f2', 'f3', 'f4'])
    expect(reduce(p, { type: 'remove', id: 'f2' }).signals).toHaveLength(4)
  })

  it('blocks discovery until there is an entity, with a reason', () => {
    expect(blocker(emptyProfile)).toMatch(/at least one cultural interest/)
    const tagOnly = reduce(emptyProfile, { type: 'add', signal: mood })
    expect(blocker(tagOnly)).toMatch(/Aesthetics alone/)
    expect(blocker(reduce(tagOnly, { type: 'add', signal: film('f') }))).toBeNull()
  })
})

describe('genres', () => {
  it('cycles none -> preferred -> open -> avoided -> none', () => {
    const states = []
    let p = emptyProfile
    for (let i = 0; i < 4; i++) {
      p = reduce(p, { type: 'cycle-genre', id: 'metal' })
      states.push(genreState(p.prefs, 'metal'))
    }
    expect(states).toEqual(['preferred', 'open', 'avoided', null])
  })

  it('keeps a genre in exactly one list', () => {
    let p = reduce(emptyProfile, { type: 'genre', id: 'rock', state: 'preferred' })
    p = reduce(p, { type: 'genre', id: 'rock', state: 'avoided' })
    expect(p.prefs.preferred).toEqual([])
    expect(p.prefs.avoided).toEqual(['rock'])
  })
})

describe('feedback', () => {
  it('like and dislike are exclusive toggles', () => {
    let p = reduce(emptyProfile, { type: 'like', artist: artist('a') })
    expect(p.liked.map((l) => l.qloo_type)).toEqual(['urn:entity:artist'])
    p = reduce(p, { type: 'dislike', artist: artist('a') })
    expect(p.liked).toEqual([])
    expect(p.disliked).toEqual([{ id: 'a', name: 'Artist a' }])
    p = reduce(p, { type: 'dislike', artist: artist('a') })
    expect(p.disliked).toEqual([])
  })

  it('keeps only the most recent likes', () => {
    let p = emptyProfile
    for (const id of ['a', 'b', 'c', 'd']) p = reduce(p, { type: 'like', artist: artist(id) })
    expect(p.liked.map((l) => l.id)).toEqual(['b', 'c', 'd'])
    expect(p.liked).toHaveLength(MAX_LIKED)
  })

  it('a liked artist alone can drive a remix', () => {
    expect(blocker(reduce(emptyProfile, { type: 'like', artist: artist('a') }))).toBeNull()
  })
})
