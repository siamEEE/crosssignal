import type {
  Category,
  Collection,
  DiscoverResult,
  GenreOptions,
  Health,
  Interpretation,
  Preferences,
  Resolution,
  Signal,
} from './types'

/** An error the API reported (or a network failure), safe to show. */
export class ApiError extends Error {
  readonly kind: string
  readonly status: number

  constructor(kind: string, message: string, status: number) {
    super(message)
    this.kind = kind
    this.status = status
  }

  get retryable(): boolean {
    return ['rate_limit', 'timeout', 'unavailable', 'network'].includes(this.kind)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError('network', "Couldn't reach the CrossSignal server.", 0)
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const error = body?.error
    throw new ApiError(
      error?.kind ?? 'http',
      error?.message ?? `The server answered ${response.status}.`,
      response.status,
    )
  }
  return body as T
}

/** Only the fields the API accepts; display extras are dropped. */
export function wireSignal({ id, kind, name, category, qloo_type }: Signal): Signal {
  return { id, kind, name, category, qloo_type }
}

export const api = {
  health: () => request<Health>('/api/health'),
  categories: () => request<Category[]>('/api/categories'),
  featured: () => request<Collection[]>('/api/featured'),
  genres: () => request<GenreOptions>('/api/genres'),
  search: (q: string, category: string | null, signal?: AbortSignal) => {
    const params = new URLSearchParams({ q, take: '12' })
    if (category) params.set('category', category)
    return request<Resolution>(`/api/search?${params}`, { signal })
  },
  interpret: (text: string) =>
    request<Interpretation>('/api/interpret', {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),
  discover: (body: {
    signals: Signal[]
    preferences: Preferences
    feedback: { liked: Signal[]; disliked: string[] }
    page: number
  }) =>
    request<DiscoverResult>('/api/discover', {
      method: 'POST',
      body: JSON.stringify({
        ...body,
        signals: body.signals.map(wireSignal),
        feedback: { ...body.feedback, liked: body.feedback.liked.map(wireSignal) },
      }),
    }),
}
