// Every sentence here is derived from a field the API returned. Nothing
// infers taste, mood or personality; nothing restates scores as odds.
import type { Artist, DiscoverResult, Evidence, Tally } from './types'

export const ERA_LABEL: Record<string, string> = {
  'pre-1980': 'before 1980',
  '1980s': 'the 1980s',
  '1990s': 'the 1990s',
  '2000s': 'the 2000s',
  '2010s': 'the 2010s',
  '2020s': 'the 2020s',
  recent: 'the last five years',
}

export const AFFINITY_HELP =
  "Qloo's affinity ranks how strongly an artist is associated with this " +
  "interest's audience. It is not a probability that you'll like the artist."

export function evidenceLine(e: Evidence): string {
  return `Qloo placed this artist #${e.rank} for your interest in ${e.signal_name}.`
}

export function genreLine(artist: Artist): { text: string; tone: 'good' | 'soft' | 'plain' } {
  const { fit, support, related_only, matched, qloo_tags, catalog_genre } = artist.genre
  const labels = matched.map((m) => m.label).join(', ')
  if (fit === 'neutral') {
    if (qloo_tags.length) return { text: `Qloo genre tags: ${qloo_tags.slice(0, 3).join(', ')}`, tone: 'plain' }
    if (catalog_genre) return { text: `Apple Music genre: ${catalog_genre}`, tone: 'plain' }
    return { text: 'No genre data from Qloo or Apple Music', tone: 'soft' }
  }
  if (fit === 'unverified') {
    return { text: 'Genre unconfirmed: no genre data from Qloo or Apple Music', tone: 'soft' }
  }
  const wanted = fit === 'preferred' ? 'preferred' : 'open-to'
  if (support === 'both' && related_only) {
    return {
      text: `${labels} (${wanted}): Qloo tags it ${labels}; Apple Music files it under ${catalog_genre}, a related family`,
      tone: 'good',
    }
  }
  if (support === 'both') {
    return {
      text: `${labels} (${wanted}): Qloo tags and Apple Music (${catalog_genre}) agree`,
      tone: 'good',
    }
  }
  if (support === 'qloo') {
    return { text: `${labels} (${wanted}): Qloo genre tag only, not confirmed by Apple Music`, tone: 'soft' }
  }
  return {
    text: `${labels} family (${wanted}): Apple Music lists ${catalog_genre}; no Qloo genre tag`,
    tone: 'soft',
  }
}

export function eraLine(artist: Artist, era: string | string[] | null): string | null {
  const eras = typeof era === 'string' ? [era] : era ?? []
  if (!eras.length || !artist.era) return null
  const where = eras.map(e => ERA_LABEL[e] ?? e).join(', ')
  if (!artist.era.dated) return `No release years in this catalog sample to compare with ${where}`
  if (!artist.era.in_era) return `None of the ${artist.era.dated} sampled songs are from ${where}; other releases may be.`
  return `${artist.era.in_era} of ${artist.era.dated} sampled catalog songs are from ${where}`
}

/** One honest sentence about what was left out and why. */
export function exclusionSummary(tally: Tally): string | null {
  const parts: string[] = []
  if (tally.conflicting) parts.push(`${tally.conflicting} where Qloo and Apple Music genres disagreed`)
  if (tally.mismatched) parts.push(`${tally.mismatched} outside your genres`)
  if (tally.avoided) parts.push(`${tally.avoided} in genres you avoid`)
  if (tally.no_catalog_match) parts.push(`${tally.no_catalog_match} with no exact Apple Music match`)
  if (tally.catalog_errors) parts.push(`${tally.catalog_errors} the catalog couldn't check right now`)
  if (!parts.length) return null
  return `Left out: ${parts.join(', ')}.`
}

export function statusHeadline(result: DiscoverResult): string {
  const n = result.artists.length
  if (result.status === 'empty') return 'No compatible artists this time'
  if (result.status === 'insufficient') return `Only ${n} compatible artist${n === 1 ? '' : 's'} found`
  return `${n} artists on your frequency`
}

export const NOTICE_TEXT: Record<string, string> = {
  genre_fallback:
    'Your genre filter returned too few artists, so CrossSignal also ran one broader Qloo search and checked genres itself.',
  tag_signals_unmeasured:
    "Aesthetic tags were sent to Qloo as tag signals; Qloo doesn't report how much they changed the results.",
}
