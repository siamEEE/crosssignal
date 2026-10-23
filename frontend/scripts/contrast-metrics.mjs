/** WCAG relative luminance, with sRGB alpha composition for rendered CSS colors. */
export function composite(foreground, background) {
  const alpha = foreground[3] ?? 1
  return foreground.slice(0, 3).map((v, i) => v * alpha + background[i] * (1 - alpha))
}

export function contrast(a, b) {
  const luminance = rgb => rgb.slice(0, 3).map(v => {
    const s = v / 255
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }).reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0)
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (light + 0.05) / (dark + 0.05)
}

/** Runs inside the browser. Gradient stop combinations form a conservative
 * envelope; image-backed text still needs screenshot/manual review. */
export function measureDocument(composite, contrast) {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = 1
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  function color(css) {
    ctx.clearRect(0, 0, 1, 1)
    ctx.fillStyle = css
    ctx.fillRect(0, 0, 1, 1)
    const rgba = [...ctx.getImageData(0, 0, 1, 1).data]
    rgba[3] /= 255
    return rgba
  }
  function splitLayers(value) {
    let depth = 0, start = 0
    const layers = []
    for (let i = 0; i < value.length; i++) {
      if (value[i] === '(') depth++
      if (value[i] === ')') depth--
      if (value[i] === ',' && !depth) { layers.push(value.slice(start, i)); start = i + 1 }
    }
    return [...layers, value.slice(start)]
  }
  const cache = new Map()
  function backgrounds(element) {
    if (!element) return [[255, 255, 255]]
    if (cache.has(element)) return cache.get(element)
    const style = getComputedStyle(element)
    let colors = backgrounds(element.parentElement).map(bg => composite(color(style.backgroundColor), bg))
    for (const layer of splitLayers(style.backgroundImage).reverse()) {
      const stops = layer.match(/(?:rgba?|color|oklch|oklab)\([^)]*\)|#[a-f\d]{3,8}/gi)
      if (stops) colors = colors.flatMap(bg => stops.map(stop => composite(color(stop), bg)))
    }
    colors = [...new Map(colors.map(c => [c.map(Math.round).join(), c])).values()]
    cache.set(element, colors)
    return colors
  }
  const visible = element => {
    const s = getComputedStyle(element)
    const r = element.getBoundingClientRect()
    return s.visibility !== 'hidden' && s.display !== 'none' && r.width > 2 && r.height > 2 &&
      !element.closest('[hidden],.sr-only') && Number(s.opacity) > 0
  }
  const label = element => `${element.tagName.toLowerCase()}${element.id ? '#' + element.id : ''}.${String(element.className).split(' ').slice(0, 2).join('.')}`
  const nodes = new Set()
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  while (walker.nextNode()) {
    if (walker.currentNode.textContent.trim()) nodes.add(walker.currentNode.parentElement)
  }
  const text = []
  for (const element of nodes) {
    if (!visible(element) || element.closest('script,style,svg,[aria-hidden="true"]:not(.collection-number)')) continue
    const style = getComputedStyle(element)
    const size = parseFloat(style.fontSize)
    const minimum = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 700) ? 3 : 4.5
    const foreground = color(style.color)
    let opacity = 1
    for (let e = element; e; e = e.parentElement) opacity *= Number(getComputedStyle(e).opacity)
    foreground[3] *= opacity
    const ratio = Math.min(...backgrounds(element).map(bg => contrast(composite(foreground, bg), bg)))
    text.push({ element: label(element), text: element.textContent.trim().slice(0, 100), ratio, minimum })
  }
  for (const element of document.querySelectorAll('input[placeholder],textarea[placeholder]')) {
    if (!visible(element)) continue
    const style = getComputedStyle(element, '::placeholder')
    const foreground = color(style.color)
    foreground[3] *= Number(style.opacity)
    const ratio = Math.min(...backgrounds(element).map(bg => contrast(composite(foreground, bg), bg)))
    text.push({ element: label(element) + '::placeholder', text: element.placeholder, ratio, minimum: 4.5 })
  }
  const controls = []
  for (const element of document.querySelectorAll('.collection-pick,.category-toggle,[data-genre],.era-toggle,.discovery-mode,.cs-button,.header-control,input,textarea,.description-example,.listening-search,.subgenre-toggle')) {
    if (!visible(element)) continue
    const style = getComputedStyle(element)
    const parent = backgrounds(element.parentElement)
    const border = color(style.borderTopColor)
    const fill = color(style.backgroundColor)
    const ratio = Math.min(...parent.map(bg => Math.max(
      parseFloat(style.borderTopWidth) ? contrast(composite(border, bg), bg) : 1,
      contrast(composite(fill, bg), bg),
    )))
    // Borderless text links/quiet buttons are identified by their readable text.
    if (parseFloat(style.borderTopWidth) || element.matches('input,textarea')) {
      controls.push({ element: label(element), text: element.textContent.trim().slice(0, 60), ratio, minimum: 3 })
    }
  }
  const collections = [...document.querySelectorAll('.culture-collection')].map(card => ({
    title: card.querySelector('h3').textContent,
    background: getComputedStyle(card).backgroundColor,
    foreground: getComputedStyle(card).color,
    text: text.filter(t => [card.querySelector('h3').textContent, card.querySelector('p').textContent].includes(t.text)),
    artworkRatio: Math.min(...backgrounds(card).map(bg => contrast(color(getComputedStyle(card.querySelector('.collection-art')).color), bg))),
  }))
  const focus = [...document.querySelectorAll(':focus-visible')].filter(visible).map(element => {
    const style = getComputedStyle(element)
    const outline = color(style.outlineColor)
    const halo = color(getComputedStyle(document.documentElement).getPropertyValue('--focus-halo'))
    return { element: label(element), text: 'Focus ring against its contrasting halo', ratio: contrast(outline, halo), minimum: 3 }
  })
  const artwork = collections.map(card => ({ element: card.title, text: 'Geometric artwork', ratio: card.artworkRatio, minimum: 3 }))
  return { text, controls, focus, collections, failures: [...text, ...controls, ...focus, ...artwork].filter(v => v.ratio < v.minimum) }
}
