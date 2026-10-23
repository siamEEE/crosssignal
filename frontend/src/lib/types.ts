// Types mirroring the FastAPI responses in src/crosssignal/api.py.

export type Kind = 'entity' | 'tag'
export type Match = 'exact' | 'ambiguous' | 'suggestions' | 'none'
export type Discovery = 'familiar' | 'balanced' | 'adventurous'
export type GenreFit =
  | 'preferred'
  | 'open'
  | 'neutral'
  | 'unverified'
  | 'conflict'
  | 'mismatch'
  | 'avoided'
export type Support = 'both' | 'qloo' | 'catalog' | null
export type Status = 'ok' | 'insufficient' | 'empty'

export interface Health {
  status: 'ok'
  qloo_configured: boolean
  config_problem: string | null
  interpreter: string
}

export interface Category {
  id: string
  label: string
  hint: string
  kind: Kind
}

export interface Candidate {
  id: string
  kind: Kind
  name: string
  category: string
  qloo_type: string
  type_label: string
  year: number | null
  disambiguation: string | null
  image_url: string | null
  popularity: number | null
}

export interface Resolution {
  query: string
  category: string | null
  match: Match
  candidates: Candidate[]
}

export interface Collection {
  id: string
  title: string
  blurb: string
  accent: string
  items: { query: string; category: string }[]
}

export interface GenreNode {
  id: string
  label: string
  subgenres: { id: string; label: string; advanced: boolean }[]
}

export interface GenreOptions {
  genres: GenreNode[]
  eras: string[]
  discovery_modes: Discovery[]
  limits: { signals: number; liked: number }
}

/** A user-confirmed Qloo entity or tag, as sent to /api/discover. */
export interface Signal {
  id: string
  kind: Kind
  name: string
  category: string
  qloo_type: string
  // Display-only extras, stripped before sending.
  type_label?: string
  year?: number | null
  image_url?: string | null
}

export interface Preferences {
  preferred: string[]
  open_to: string[]
  avoided: string[]
  era: string | null
  discovery: Discovery
}

export interface Track {
  title: string
  artist: string
  album: string | null
  year: string | null
  url: string
  artwork_small: string | null
  artwork_large: string | null
  preview_url: string | null
  genre: string | null
}

export interface Evidence {
  signal_id: string
  signal_name: string
  category: string
  rank: number
  affinity: number | null
  explained_share: number | null
}

export interface Artist {
  id: string
  name: string
  image_url: string | null
  source: 'filtered' | 'unfiltered'
  popularity: number | null
  genre: {
    fit: GenreFit
    support: Support
    related_only: boolean
    matched: { id: string; label: string }[]
    qloo_tags: string[]
    catalog_genre: string | null
  }
  era: { in_era: number; dated: number } | null
  evidence: Evidence[]
  tracks: Track[]
}

export interface Tally {
  qloo_candidates: number
  avoided: number
  mismatched: number
  conflicting: number
  no_catalog_match: number
  catalog_errors: number
  lookups: number
  fallback_used: boolean
  excluded: Record<string, string[]>
}

export interface DiscoverResult {
  status: Status
  page: number
  notices: string[]
  signals: Signal[]
  tag_signals: Signal[]
  preferences: Preferences
  tally: Tally
  artists: Artist[]
}

export interface Interpretation {
  interpreter: string
  mentions: { phrase: string; resolution: Resolution; tag_candidates: Candidate[] }[]
  music: {
    preferred: string[]
    avoided: string[]
    era: string | null
    discovery: Discovery | null
  }
}

export interface ApiErrorBody {
  error: { kind: string; message: string }
}
