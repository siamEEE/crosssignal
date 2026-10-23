import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { expect, it } from 'vitest'
import { Header } from '@/components/header'
import { Sound } from '@/components/sound'
import { Explore } from '@/components/explore'
import { emptyProfile } from './profile'

it('exposes reset, playlist navigation and the persistent theme toggle in the header', () => {
  const html = renderToStaticMarkup(createElement(Header, {
    health: null, onReset: () => {}, onTheme: () => {}, theme: 'after-hours',
  }))
  expect(html).toContain('Reset</button>')
  expect(html).toContain('aria-label="After Hours theme"')
  expect(html).toContain('aria-pressed="true"')
  expect(html).toContain('href="#playlist"')
})

it('uses semantic collection surfaces rather than shared badge utility classes', () => {
  const accents = ['violet', 'lime', 'apricot', 'coral', 'ink']
  const html = renderToStaticMarkup(createElement(Explore, {
    categories: [], selected: [], live: true, onAdd: () => {},
    collections: accents.map(accent => ({
      id: accent, title: accent, blurb: 'Test collection', accent,
      items: [{ query: 'Arrival', category: 'screen' }],
    })),
  }))
  const articles = html.match(/<article[^>]*>/g) ?? []
  expect(articles).toHaveLength(5)
  articles.forEach((article, i) => {
    expect(article).toContain(`data-accent="${accents[i]}"`)
    expect(article).not.toMatch(/bg-(lime|coral|apricot|violet|ink)/)
  })
})

it('renders multiple era buttons with accessible toggle states, not exclusive radios', () => {
  const html = renderToStaticMarkup(createElement(Sound, {
    options: { genres: [], eras: ['1980s', '2000s', '2010s'], discovery_modes: [], limits: { signals: 5, liked: 3 } },
    prefs: { ...emptyProfile.prefs, eras: ['1980s', '2000s', '2010s'] }, dispatch: () => {},
  }))
  const eraControls = html.slice(html.indexOf('aria-label="Release eras"'), html.indexOf('>Discovery</h3>'))
  expect(eraControls.match(/aria-pressed="true"/g)).toHaveLength(3)
  expect(eraControls).toContain('aria-pressed="false"')
  expect(eraControls).not.toContain('role="radio"')
})
