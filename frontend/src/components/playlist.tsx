import { useEffect, useState } from 'react'
import { ArrowDown, ArrowUp, Check, Copy, Download, ListMusic, Plus, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SectionTitle } from '@/components/explore'
import { PlaylistContext, usePlaylist } from '@/lib/playlist-context'
import { addTracks, loadPlaylist, moveTrack, playlistCsv, removeTrack, renamePlaylist, savePlaylist, trackKey, tracklist, PLAYLIST_LIMIT } from '@/lib/playlist'
import { trackSearches } from '@/lib/listening'
import type { Track } from '@/lib/types'

export function PlaylistProvider({ children }: { children: React.ReactNode }) {
  const [playlist, setPlaylist] = useState(loadPlaylist)
  const [notice, setNotice] = useState('')
  const [persistent, setPersistent] = useState(true)
  useEffect(() => {
    let active = true
    // Report the result of browser persistence without a synchronous effect render.
    queueMicrotask(() => { if (active) setPersistent(savePlaylist(playlist)) })
    return () => { active = false }
  }, [playlist])
  function add(tracks: Track[]) {
    const next = addTracks(playlist, tracks)
    const count = next.tracks.length - playlist.tracks.length
    setPlaylist(next)
    setNotice(count > 0 ? `Added ${count} song${count === 1 ? '' : 's'} to My Playlist.`
      : playlist.tracks.length >= PLAYLIST_LIMIT ? 'Your playlist has 300 songs. Remove a song to add another.'
      : 'Those songs are already in My Playlist.')
  }
  return <PlaylistContext.Provider value={{
    playlist, add, notice, persistent,
    remove: key => setPlaylist(current => removeTrack(current, key)),
    move: (from, to) => setPlaylist(current => moveTrack(current, from, to)),
    rename: name => setPlaylist(current => renamePlaylist(current, name)),
  }}>{children}</PlaylistContext.Provider>
}

export function AddToPlaylist({ track }: { track: Track }) {
  const { playlist, add } = usePlaylist()
  const added = playlist.tracks.some(t => trackKey(t) === trackKey(track))
  return <Button size="sm" variant={added ? 'accent' : 'outline'} disabled={added || playlist.tracks.length >= PLAYLIST_LIMIT}
    onClick={() => add([track])} aria-label={added ? `${track.title} is in My Playlist` : `Add ${track.title} to My Playlist`}>
    {added ? <Check /> : <Plus />}{added ? 'Added' : 'Playlist'}
  </Button>
}

export function PlaylistSection() {
  const { playlist, remove, move, rename, notice, persistent } = usePlaylist()
  const [message, setMessage] = useState('')
  async function copy() {
    try { await navigator.clipboard.writeText(tracklist(playlist)); setMessage('Tracklist copied.') }
    catch { setMessage('Copy is unavailable in this browser. You can export CSV instead.') }
  }
  function download() {
    const url = URL.createObjectURL(new Blob(['\uFEFF' + playlistCsv(playlist)], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = 'crosssignal-playlist.csv'
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return <section id="playlist" className="playlist-section scroll-mt-32 py-14">
    <div className="mx-auto max-w-6xl px-4">
      <SectionTitle kicker="Your own selection" title="My Playlist">
        <span className="text-sm text-muted">{playlist.tracks.length} / {PLAYLIST_LIMIT} songs</span>
      </SectionTitle>
      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="min-w-0 flex-1 text-xs font-semibold">Playlist name
          <input key={playlist.name} defaultValue={playlist.name} maxLength={80} onBlur={e => rename(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur() }}
            className="mt-2 block w-full rounded-lg border border-ink/30 bg-ivory p-3 text-base text-ink" />
        </label>
        <Button variant="outline" onClick={copy} disabled={!playlist.tracks.length}><Copy />Copy tracklist</Button>
        <Button variant="outline" onClick={download} disabled={!playlist.tracks.length}><Download />Export CSV</Button>
      </div>
      <p className="mt-3 text-xs text-muted">Saved in this browser. Apple Music opens the catalog song; other services open searches. No external playlists are created.</p>
      {!persistent && <p role="alert" className="mt-3 text-sm">Browser storage is unavailable. Export your playlist before closing this page.</p>}
      <p role="status" className="mt-3 text-sm">{message || notice}</p>
      {!playlist.tracks.length ? <div className="playlist-empty mt-5 border border-dashed border-ink/30 p-8">
        <ListMusic className="mb-3 size-7" /><h3 className="font-display text-2xl">A place for the songs you keep.</h3>
        <p className="mt-2 text-sm text-muted">Add a song from your recommendations, or add the whole visible selection. Artist likes only steer future recommendations.</p>
        <a href="#explore" className="mt-4 inline-block text-sm font-semibold underline">Choose some interests to start</a>
      </div> : <ol className="mt-5 divide-y divide-ink/15 border-y border-ink/20">
        {playlist.tracks.map((track, i) => <li key={trackKey(track)} className="playlist-row flex flex-wrap items-center gap-3 py-4">
          <span className="w-6 text-xs text-muted">{String(i + 1).padStart(2, '0')}</span>
          <div className="min-w-0 flex-1"><a href={track.url} target="_blank" rel="noopener noreferrer" className="font-semibold underline-offset-4 hover:underline">{track.title}</a><p className="text-sm text-muted">{track.artist}</p>
            <details className="mt-2 text-xs"><summary className="cursor-pointer">Listen elsewhere</summary><div className="mt-2 flex flex-wrap gap-3">{trackSearches(track).map(link => <a key={link.label} href={link.href} target="_blank" rel="noopener noreferrer" className="underline">{link.label} search</a>)}</div></details>
          </div>
          <div className="flex gap-1">
            <Button size="icon" variant="quiet" disabled={i === 0} onClick={() => move(i, i - 1)} aria-label={`Move ${track.title} up`}><ArrowUp /></Button>
            <Button size="icon" variant="quiet" disabled={i === playlist.tracks.length - 1} onClick={() => move(i, i + 1)} aria-label={`Move ${track.title} down`}><ArrowDown /></Button>
            <Button size="icon" variant="quiet" onClick={() => remove(trackKey(track)!)} aria-label={`Remove ${track.title}`}><X /></Button>
          </div>
        </li>)}
      </ol>}
    </div>
  </section>
}
