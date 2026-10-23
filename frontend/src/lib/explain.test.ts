import { describe, expect, it } from 'vitest'
import { eraLine, evidenceLine, exclusionSummary, genreLine, statusHeadline } from './explain'
import type { Artist, DiscoverResult, Tally } from './types'

function artist(genre: Partial<Artist['genre']>, era: Artist['era'] = null): Artist {
  return {
    id: 'a',
    name: 'A',
    image_url: null,
    source: 'filtered',
    popularity: 0.5,
    genre: { fit: 'neutral', support: null, related_only: false, matched: [], qloo_tags: [], catalog_genre: null, ...genre },
    era,
    evidence: [],
    tracks: [],
  }
}

const metal = [{ id: 'metal', label: 'Metal' }]

describe('grounded explanations', () => {
  it('names the rank and the interest Qloo used', () => {
    expect(
      evidenceLine({ signal_id: 'g', signal_name: 'Cyberpunk 2077', category: 'games', rank: 2, affinity: 0.9, explained_share: 1 }),
    ).toBe("Qloo placed this artist #2 for your interest in Cyberpunk 2077.")
    expect(
      evidenceLine({ signal_id: 'a', signal_name: 'Spiritbox', category: 'liked', rank: 4, affinity: null, explained_share: null }),
    ).toBe("Qloo placed this artist #4 for your interest in Spiritbox.")
  })

  it('distinguishes confirmed, single-source and missing genre evidence', () => {
    expect(genreLine(artist({ fit: 'preferred', support: 'both', matched: metal, catalog_genre: 'Metal' })))
      .toEqual({ text: 'Metal (preferred): Qloo tags and Apple Music (Metal) agree', tone: 'good' })
    // A related family is not described as the catalog agreeing.
    expect(
      genreLine(artist({ fit: 'preferred', support: 'both', related_only: true, matched: [{ id: 'electronic', label: 'Electronic' }], catalog_genre: 'Pop' })).text,
    ).toBe('Electronic (preferred): Qloo tags it Electronic; Apple Music files it under Pop, a related family')
    expect(genreLine(artist({ fit: 'open', support: 'qloo', matched: metal })).text)
      .toMatch(/Qloo genre tag only, not confirmed/)
    expect(genreLine(artist({ fit: 'preferred', support: 'catalog', matched: [{ id: 'rock', label: 'Rock' }], catalog_genre: 'Alternative' })).text)
      .toBe('Rock family (preferred): Apple Music lists Alternative; no Qloo genre tag')
    expect(genreLine(artist({ fit: 'unverified' })).tone).toBe('soft')
    expect(genreLine(artist({ qloo_tags: ['Ambient', 'Electronic', 'Piano', 'Drone'] })).text)
      .toBe('Qloo genre tags: Ambient, Electronic, Piano')
  })

  it('reports era evidence as counts, or says it is missing', () => {
    expect(eraLine(artist({}, { in_era: 3, dated: 4 }), '2010s')).toBe('3 of 4 sampled catalog songs are from the 2010s')
    expect(eraLine(artist({}, { in_era: 0, dated: 0 }), 'recent')).toMatch(/No release years/)
    expect(eraLine(artist({}), null)).toBeNull()
    expect(eraLine(artist({}, { in_era: 0, dated: 4 }), ['1980s', '2000s', '2010s']))
      .toBe('None of the 4 sampled songs are from the 1980s, the 2000s, the 2010s; other releases may be.')
  })

  it('summarises exclusions and status without padding', () => {
    const tally = { conflicting: 1, mismatched: 2, avoided: 0, no_catalog_match: 1, catalog_errors: 0 } as Tally
    expect(exclusionSummary(tally)).toBe(
      'Left out: 1 where Qloo and Apple Music genres disagreed, 2 outside your genres, 1 with no exact Apple Music match.',
    )
    const result = { status: 'insufficient', artists: [artist({})] } as unknown as DiscoverResult
    expect(statusHeadline(result)).toBe('Only 1 compatible artist found')
  })
})
