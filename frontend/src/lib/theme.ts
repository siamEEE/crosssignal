export type Theme = 'daylight' | 'after-hours'
export const THEME_KEY = 'crosssignal.theme.v1'
export function chooseTheme(saved: unknown, prefersDark: boolean): Theme {
  return saved === 'daylight' || saved === 'after-hours' ? saved : prefersDark ? 'after-hours' : 'daylight'
}
export function initialTheme(): Theme {
  try { return chooseTheme(localStorage.getItem(THEME_KEY), matchMedia('(prefers-color-scheme: dark)').matches) }
  catch { return chooseTheme(null, typeof matchMedia !== 'undefined' && matchMedia('(prefers-color-scheme: dark)').matches) }
}
export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
  document.documentElement.style.colorScheme = theme === 'after-hours' ? 'dark' : 'light'
  try { localStorage.setItem(THEME_KEY, theme) } catch { /* Remains usable for this visit. */ }
}
