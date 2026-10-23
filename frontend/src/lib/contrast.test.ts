import { expect, it } from 'vitest'
// @ts-expect-error The browser audit is plain JS, shared with its Node runner.
import { composite, contrast } from '../../scripts/contrast-metrics.mjs'
import css from '../index.css?raw'

it('uses WCAG luminance and composites translucent foregrounds', () => {
  expect(contrast([0, 0, 0], [255, 255, 255])).toBe(21)
  expect(contrast([255, 255, 255], [0, 0, 0])).toBe(21)
  expect(composite([0, 0, 0, 0.5], [255, 255, 255])).toEqual([127.5, 127.5, 127.5])
  expect(contrast([127.5, 127.5, 127.5], [255, 255, 255])).toBeCloseTo(3.977, 2)
})

it('does not let accent utility classes recolor entire theme subtrees', () => {
  expect(css).not.toMatch(/\[data-theme=['"]after-hours['"]\]\s+\[class[~*]?=['"]bg-/)
  expect(css).not.toMatch(/\[data-theme=['"]after-hours['"]\]\s+\.bg-/)
})
