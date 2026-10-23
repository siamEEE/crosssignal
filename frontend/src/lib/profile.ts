import type { Artist, Candidate, Discovery, Preferences, Signal } from './types'

export const MAX_SIGNALS = 5
export const MAX_LIKED = 3

export type GenreState = 'preferred' | 'open' | 'avoided' | null

export interface Profile {
  signals: Signal[]
  prefs: Preferences
  liked: Signal[] // artists that steer the next remix
  disliked: { id: string; name: string }[]
}

export const emptyProfile: Profile = {
  signals: [],
  prefs: { preferred: [], open_to: [], avoided: [], eras: [], discovery: 'balanced' },
  liked: [],
  disliked: [],
}

export type Action =
  | { type: 'add'; signal: Signal }
  | { type: 'remove'; id: string }
  | { type: 'genre'; id: string; state: GenreState }
  | { type: 'cycle-genre'; id: string }
  | { type: 'era'; era: string | null }
  | { type: 'eras'; eras: string[] }
  | { type: 'discovery'; mode: Discovery }
  | { type: 'like'; artist: Artist }
  | { type: 'dislike'; artist: Artist }
  | { type: 'clear-feedback' }
  | { type: 'reset' }
  | { type: 'replace'; profile: Profile }

const CYCLE: GenreState[] = [null, 'preferred', 'open', 'avoided']

export function genreState(prefs: Preferences, id: string): GenreState {
  if (prefs.preferred.includes(id)) return 'preferred'
  if (prefs.open_to.includes(id)) return 'open'
  if (prefs.avoided.includes(id)) return 'avoided'
  return null
}

function withGenre(prefs: Preferences, id: string, state: GenreState): Preferences {
  const drop = (list: string[]) => list.filter((g) => g !== id)
  const next = {
    ...prefs,
    preferred: drop(prefs.preferred),
    open_to: drop(prefs.open_to),
    avoided: drop(prefs.avoided),
  }
  if (state === 'preferred') next.preferred = [...next.preferred, id]
  if (state === 'open') next.open_to = [...next.open_to, id]
  if (state === 'avoided') next.avoided = [...next.avoided, id]
  return next
}

/** A Qloo search candidate the user confirmed, as a profile signal. */
export function toSignal(c: Candidate): Signal {
  return {
    id: c.id,
    kind: c.kind,
    name: c.name,
    category: c.category,
    qloo_type: c.qloo_type,
    type_label: c.type_label,
    year: c.year,
    image_url: c.image_url,
  }
}

export function artistSignal(artist: Artist): Signal {
  return {
    id: artist.id,
    kind: 'entity',
    name: artist.name,
    category: 'liked',
    qloo_type: 'urn:entity:artist',
    image_url: artist.image_url,
  }
}

export function profileReducer(profile: Profile, action: Action): Profile {
  switch (action.type) {
    case 'add': {
      if (profile.signals.some((s) => s.id === action.signal.id)) return profile
      if (profile.signals.length >= MAX_SIGNALS) return profile
      return { ...profile, signals: [...profile.signals, action.signal] }
    }
    case 'remove':
      return { ...profile, signals: profile.signals.filter((s) => s.id !== action.id) }
    case 'genre':
      return { ...profile, prefs: withGenre(profile.prefs, action.id, action.state) }
    case 'cycle-genre': {
      const current = CYCLE.indexOf(genreState(profile.prefs, action.id))
      const next = CYCLE[(current + 1) % CYCLE.length]
      return { ...profile, prefs: withGenre(profile.prefs, action.id, next) }
    }
    case 'era': {
      const eras = action.era === null ? [] : profile.prefs.eras.includes(action.era)
        ? profile.prefs.eras.filter(e => e !== action.era)
        : [...profile.prefs.eras, action.era]
      return { ...profile, prefs: { ...profile.prefs, eras: normalizeEras(eras) } }
    }
    case 'eras':
      return { ...profile, prefs: { ...profile.prefs, eras: normalizeEras(action.eras) } }
    case 'discovery':
      return { ...profile, prefs: { ...profile.prefs, discovery: action.mode } }
    case 'like': {
      const { artist } = action
      const disliked = profile.disliked.filter((d) => d.id !== artist.id)
      if (profile.liked.some((l) => l.id === artist.id)) {
        return { ...profile, disliked, liked: profile.liked.filter((l) => l.id !== artist.id) }
      }
      // Keep the most recent likes when over the limit.
      const liked = [...profile.liked, artistSignal(artist)].slice(-MAX_LIKED)
      return { ...profile, liked, disliked }
    }
    case 'dislike': {
      const { artist } = action
      const liked = profile.liked.filter((l) => l.id !== artist.id)
      if (profile.disliked.some((d) => d.id === artist.id)) {
        return { ...profile, liked, disliked: profile.disliked.filter((d) => d.id !== artist.id) }
      }
      return { ...profile, liked, disliked: [...profile.disliked, { id: artist.id, name: artist.name }].slice(-50) }
    }
    case 'clear-feedback':
      return { ...profile, liked: [], disliked: [] }
    case 'reset':
      return emptyProfile
    case 'replace':
      return action.profile
  }
}

/** Why discovery can't run yet, or null if it can. Mirrors the API rules. */
export function blocker(profile: Profile): string | null {
  const entities = profile.signals.filter((s) => s.kind === 'entity')
  if (!entities.length && !profile.liked.length) {
    return profile.signals.length
      ? 'Add at least one title, person, brand or place. Aesthetics alone are too weak a signal.'
      : 'Pick at least one cultural interest to tune in.'
  }
  return null
}

export function hasGenrePrefs(prefs: Preferences): boolean {
  return prefs.preferred.length + prefs.open_to.length + prefs.avoided.length > 0
}

export const ERA_IDS = ['pre-1980', '1980s', '1990s', '2000s', '2010s', '2020s', 'recent']
export function normalizeEras(value: unknown): string[] {
  return ERA_IDS.filter(era => Array.isArray(value) && value.includes(era))
}
const STORAGE_KEY = 'crosssignal.profile.v1'

/** Per-viewer convenience only; the app works the same without storage. */
export function loadProfile(): Profile {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return emptyProfile
    const parsed = JSON.parse(raw) as Partial<Profile>
    const validSignal = (s: Signal) => s && typeof s.id === 'string' &&
      typeof s.name === 'string' && typeof s.category === 'string' &&
      typeof s.qloo_type === 'string' && ['entity', 'tag'].includes(s.kind)
    const lists = [parsed.prefs?.preferred, parsed.prefs?.open_to, parsed.prefs?.avoided]
    if (!parsed.prefs || !lists.every((list) => Array.isArray(list) && list.every((id) => typeof id === 'string')) ||
        !['familiar', 'balanced', 'adventurous'].includes(parsed.prefs.discovery)) return emptyProfile
    const legacy = parsed.prefs as Preferences & { era?: unknown }
    const eras = normalizeEras(Array.isArray(legacy.eras) ? legacy.eras : typeof legacy.era === 'string' ? [legacy.era] : [])
    return {
      signals: Array.isArray(parsed.signals) ? parsed.signals.filter(validSignal).slice(0, MAX_SIGNALS) : [],
      prefs: { preferred: parsed.prefs.preferred, open_to: parsed.prefs.open_to, avoided: parsed.prefs.avoided, discovery: parsed.prefs.discovery, eras },
      liked: Array.isArray(parsed.liked) ? parsed.liked.filter(validSignal).slice(0, MAX_LIKED) : [],
      disliked: Array.isArray(parsed.disliked) ? parsed.disliked.filter((d) => d && typeof d.id === 'string' && typeof d.name === 'string').slice(-50) : [],
    }
  } catch {
    return emptyProfile
  }
}

export function saveProfile(profile: Profile): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile))
  } catch {
    // Private mode or blocked storage: keep working in memory.
  }
}
