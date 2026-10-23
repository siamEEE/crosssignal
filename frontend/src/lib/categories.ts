import {
  BookOpen,
  Clapperboard,
  Gamepad2,
  Headphones,
  MapPin,
  Mic,
  ShoppingBag,
  Sparkles,
  UserRound,
  type LucideIcon,
} from 'lucide-react'

export interface CategoryStyle {
  icon: LucideIcon
  /** Solid fill for chips and tiles; text on it is always ink. */
  fill: string
  /** Soft tint for backgrounds. */
  tint: string
  /** Text colour readable on ivory. */
  text: string
}

export const CATEGORY_STYLE: Record<string, CategoryStyle> = {
  screen: { icon: Clapperboard, fill: 'bg-coral', tint: 'bg-coral/15', text: 'text-coral-deep' },
  games: { icon: Gamepad2, fill: 'bg-violet', tint: 'bg-violet/15', text: 'text-violet-deep' },
  books: { icon: BookOpen, fill: 'bg-apricot', tint: 'bg-apricot/25', text: 'text-apricot-deep' },
  people: { icon: UserRound, fill: 'bg-lime', tint: 'bg-lime/30', text: 'text-lime-deep' },
  podcasts: { icon: Mic, fill: 'bg-violet', tint: 'bg-violet/15', text: 'text-violet-deep' },
  brands: { icon: ShoppingBag, fill: 'bg-coral', tint: 'bg-coral/15', text: 'text-coral-deep' },
  places: { icon: MapPin, fill: 'bg-lime', tint: 'bg-lime/30', text: 'text-lime-deep' },
  aesthetics: { icon: Sparkles, fill: 'bg-apricot', tint: 'bg-apricot/25', text: 'text-apricot-deep' },
  liked: { icon: Headphones, fill: 'bg-lime', tint: 'bg-lime/30', text: 'text-lime-deep' },
}

export function styleFor(category: string): CategoryStyle {
  return CATEGORY_STYLE[category] ?? CATEGORY_STYLE.screen
}

export const ACCENT_FILL: Record<string, string> = {
  violet: 'bg-violet text-ivory',
  lime: 'bg-lime text-ink',
  apricot: 'bg-apricot text-ink',
  coral: 'bg-coral text-ink',
  ink: 'bg-ink text-ivory',
}
