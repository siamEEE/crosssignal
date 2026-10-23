import { ArrowDown, ArrowUpRight, Disc3 } from 'lucide-react'
import type { Theme } from '@/lib/theme'
import type { Category } from '@/lib/types'
export function Hero({ categories, theme }: { categories: Category[]; theme: Theme }) {
 return <section id="top" className="editorial-hero">
 <div className="hero-layout mx-auto max-w-6xl px-4"><div className="hero-copy">
 <p className="eyebrow">{theme === 'daylight' ? 'Music, by way of the things you like' : 'CrossSignal / After Hours'}</p>
 <h1>{theme === 'daylight' ? <>Your world.<br />A different <em>soundtrack.</em></> : <>Stay a while.<br />Find another <em>frequency.</em></>}</h1>
 <p className="hero-deck">{theme === 'daylight' ? 'Start with a film, a book or a game you like. We use those interests to find artists through Qloo, then look up songs you can try.' : 'Choose a film, book or game you like. Listen to artists Qloo returns for those interests, and keep the songs you want to hear again.'}</p>
 <a href="#explore" className="hero-start">Find your frequency <ArrowDown size={19} /></a>
 </div><div className="signal-art" aria-hidden="true">
 <div className="art-caption">CROSSSIGNAL RECORD CLUB <ArrowUpRight size={18} /></div>
 <div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" />
 <div className="art-disc"><Disc3 /><span>YOUR WORLD / ON REPEAT</span></div>
 <span className="art-sticker">Choose your interests.<br /><em>Listen to the results.</em></span>
 <span className="art-bottom">SIDE A / OPEN TO DISCOVERY</span></div></div>
 <div className="journey-strip"><div className="mx-auto flex max-w-6xl flex-wrap px-4">
 <a href="#explore"><b>01</b> Collect your culture <ArrowUpRight size={15} /></a>
 <a href="#sound"><b>02</b> Shape your sound <span>optional</span></a>
 <a href="#tune"><b>03</b> Tune My Radio <ArrowUpRight size={15} /></a>
 <span className="journey-note">{categories.length || 8} categories to explore.</span></div></div></section>
}
