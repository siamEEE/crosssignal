import { motion } from 'motion/react'
import { ArrowDown, MessageSquareText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CATEGORY_STYLE } from '@/lib/categories'
import type { Category } from '@/lib/types'
import { cn } from '@/lib/utils'

export function Hero({ categories }: { categories: Category[] }) {
  const strip = categories.length ? categories : []
  return (
    <section id="top" className="editorial-hero relative overflow-hidden">
      <div className="record-sleeve" aria-hidden="true">
        <div className="vinyl-record"><span>CS<br />SIDE A</span></div>
        <p>SELECTED BY YOUR WORLD<br />PLAYED IN YOUR OWN KEY</p>
      </div>
      <div className="mx-auto max-w-6xl px-4 pt-12 pb-10 md:pt-20">
        <motion.p
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-5 inline-flex items-center gap-2 rounded-full border border-ink/15 bg-ivory-2 px-3 py-1 text-xs font-semibold tracking-wide"
        >
          <span className="size-1.5 rounded-full bg-coral" />
          THE CROSSSIGNAL EDIT · CULTURE INTO MUSIC
        </motion.p>
        <motion.h1
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05, duration: 0.5 }}
          className="relative max-w-4xl font-display text-[clamp(2.75rem,9vw,6.5rem)] leading-[0.92] font-black tracking-[-0.035em] text-balance"
        >
          Good taste.{' '}New{' '}
          <span className="relative inline-block italic">
            <span className="relative z-10">frequencies</span>
            <span aria-hidden className="absolute inset-x-0 bottom-[0.08em] -z-0 h-[0.32em] -rotate-1 rounded-sm bg-lime" />
          </span>
          .
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.12, duration: 0.5 }}
          className="mt-6 max-w-2xl text-lg leading-relaxed text-ink/75"
        >
          From the films you replay to the worlds you get lost in.
          Pick your cultural touchstones, shape the sound, then tune your own radio.
          Discover real artists with a reason behind every recommendation.
        </motion.p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button variant="accent" size="lg" asChild>
            <a href="#explore">
              Start with your culture <ArrowDown />
            </a>
          </Button>
          <Button size="lg" variant="outline" asChild>
            <a href="#describe">
              <MessageSquareText /> Describe your world
            </a>
          </Button>
        </div>
        <p className="mt-6 text-xs font-bold tracking-widest uppercase">01 Pick culture / 02 Shape sound / 03 Tune My Radio</p>
      </div>
      {strip.length > 0 && (
        <div className="border-y-2 border-ink bg-ink py-3 text-ivory" aria-hidden>
          <div className="flex w-max animate-marquee gap-3">
            {[...strip, ...strip, ...strip, ...strip].map((category, i) => {
              const style = CATEGORY_STYLE[category.id]
              const Icon = style?.icon
              return (
                <span key={`${category.id}-${i}`} className="flex items-center gap-2 px-3 font-display text-xl italic">
                  {Icon && (
                    <span className={cn('grid size-7 place-items-center rounded-full text-ink', style.fill)}>
                      <Icon className="size-4" />
                    </span>
                  )}
                  {category.label}
                </span>
              )
            })}
          </div>
        </div>
      )}
    </section>
  )
}
