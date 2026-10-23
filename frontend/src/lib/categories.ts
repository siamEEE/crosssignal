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
  /** Explicitly paired foreground/background for small signal badges only. */
  fill: string
  /** Soft tint for backgrounds. */
  tint: string
  /** Text colour readable on ivory. */
  text: string
}

export const CATEGORY_STYLE: Record<string, CategoryStyle> = {
  screen: { icon: Clapperboard, fill: 'signal-badge signal-coral', tint: 'bg-coral/15', text: 'text-coral-deep' },
  games: { icon: Gamepad2, fill: 'signal-badge signal-violet', tint: 'bg-violet/15', text: 'text-violet-deep' },
  books: { icon: BookOpen, fill: 'signal-badge signal-apricot', tint: 'bg-apricot/25', text: 'text-apricot-deep' },
  people: { icon: UserRound, fill: 'signal-badge signal-lime', tint: 'bg-lime/30', text: 'text-lime-deep' },
  podcasts: { icon: Mic, fill: 'signal-badge signal-violet', tint: 'bg-violet/15', text: 'text-violet-deep' },
  brands: { icon: ShoppingBag, fill: 'signal-badge signal-coral', tint: 'bg-coral/15', text: 'text-coral-deep' },
  places: { icon: MapPin, fill: 'signal-badge signal-lime', tint: 'bg-lime/30', text: 'text-lime-deep' },
  aesthetics: { icon: Sparkles, fill: 'signal-badge signal-apricot', tint: 'bg-apricot/25', text: 'text-apricot-deep' },
  liked: { icon: Headphones, fill: 'signal-badge signal-lime', tint: 'bg-lime/30', text: 'text-lime-deep' },
}

export function styleFor(category: string): CategoryStyle {
  return CATEGORY_STYLE[category] ?? CATEGORY_STYLE.screen
}
