import { afterEach, expect, it, vi } from 'vitest'
import { applyTheme, chooseTheme, initialTheme, THEME_KEY } from './theme'

afterEach(() => vi.unstubAllGlobals())
it('respects explicit choices ahead of the system preference', () => {
  expect(chooseTheme('daylight', true)).toBe('daylight')
  expect(chooseTheme('after-hours', false)).toBe('after-hours')
  expect(chooseTheme('invalid', true)).toBe('after-hours')
  expect(chooseTheme(null, false)).toBe('daylight')
})
it('persists the theme and sets native control color scheme', () => {
  const data = new Map<string, string>()
  const root = { dataset: {} as Record<string, string>, style: { colorScheme: '' } }
  vi.stubGlobal('document', { documentElement: root })
  vi.stubGlobal('matchMedia', () => ({ matches: false }))
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key), setItem: (key: string, value: string) => data.set(key, value) })
  applyTheme('after-hours')
  expect(data.get(THEME_KEY)).toBe('after-hours')
  expect(initialTheme()).toBe('after-hours')
  expect(root.style.colorScheme).toBe('dark')
  expect(root.dataset.theme).toBe('after-hours')
})
it('works when browser storage is unavailable', () => {
  vi.stubGlobal('localStorage', { getItem: () => { throw Error() } })
  vi.stubGlobal('matchMedia', () => ({ matches: true }))
  expect(initialTheme()).toBe('after-hours')
})
