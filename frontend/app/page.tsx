'use client'

import { useEffect, useRef, useState } from 'react'
import {
  AudioLines,
  CircleStop,
  Mic,
  Pause,
  Play,
  Plus,
  SlidersHorizontal,
  X,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'

 type Filter = {
  key: string
  value: string
}


type Vehicle = {
  id: number; make: string; model: string; year: number; price: number
  km_driven: number; fuel: string; payload_kg: number; gvw_kg: number
  body_type: string; city: string; papers_verified: number
}

type SearchResult = { results: Vehicle[]; total: number; filter: string }


type Turn = {
  transcript: string; action: string; results: Vehicle[]
  total: number; filter: string; latency: Record<string, number>
  answer: string
}

const EMPTY_SLOTS: Record<string, string | number | null> = {
  make: null, model: null, budget_max: null, body_type: null,
  fuel: null, city: null, purpose: null,
}
const FILTER_LABELS = [
  ['make', 'Make'], ['model', 'Model'],
  ['budget_max', 'Budget'], ['body_type', 'Body type'], ['fuel', 'Fuel'],
  ['city', 'City'], ['purpose', 'Purpose'],
] 

function showValue(key: string, v: string | number | null) {
  if (v === null) return 'Any'
  if (key === 'budget_max') return `Up to ₹${Number(v).toLocaleString('en-IN')}`
  return String(v).replace('_', ' ')
}


export default function Page() {
  
  const [recording, setRecording] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [recorded, setRecorded] = useState(false)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState('')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const stopTimeRef = useRef(0)
  const [firstAudioMs, setFirstAudioMs] = useState<number | null>(null)
  const [lastAudio, setLastAudio] = useState('')
  const [lastSearch, setLastSearch] = useState<SearchResult | null>(null)

  const bottomRef = useRef<HTMLDivElement>(null)

  const [turn, setTurn] = useState<Turn | null>(null)
  const [slots, setSlots] = useState(EMPTY_SLOTS)
  const [loading, setLoading] = useState(false)


  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [turn, loading])

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop())
    }
  }, [])


  
  function togglePause() {
    const audio = audioRef.current
    if (!audio) return
    if (audio.paused) audio.play()
    else audio.pause()
  }

  function playAnswer(b64: string) {
    if (!b64) return
    if (audioRef.current) {
      audioRef.current.onpause = null   // stop the old audio from changing the state
      audioRef.current.pause()
    }
    const audio = new Audio('data:audio/mpeg;base64,' + b64)
    audioRef.current = audio
    audio.onplay = () => setIsPlaying(true)
    audio.onpause = () => setIsPlaying(false)
    audio.onended = () => setIsPlaying(false)
    audio.onplaying = () => {
      if (stopTimeRef.current) {
        setFirstAudioMs(Math.round(performance.now() - stopTimeRef.current))
        stopTimeRef.current = 0
      }
    }
    audio.play().catch(() => setError('Tap Replay to hear the answer.'))
  }

  function handleResponse(data: any) {
    setSlots(data.slots)

    if (data.delta.action === 'search' || data.delta.action === 'new_search') {
      setLastSearch({
        results: data.results,
        total: data.total_matches,
        filter: data.filter,
      })
    }

    setTurn({
      transcript: data.transcript,
      action: data.delta.action,
      results: data.results,
      total: data.total_matches,
      filter: data.filter,
      latency: data.latency_ms,
      answer: data.answer_text,
    })
    setLastAudio(data.audio_b64)
    playAnswer(data.audio_b64)
  }

  function getSessionId() {
    let id = sessionStorage.getItem('session_id')
    if (!id) {
      id = crypto.randomUUID()
      sessionStorage.setItem('session_id', id)
    }
    return id
  }

  async function newSearch() {
    await fetch('http://127.0.0.1:8000/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: getSessionId() }),
    })
    setSlots(EMPTY_SLOTS)
    setLastSearch(null)
    setTurn(null)
    setError('')
  }

  async function toggleRecording() {


    if (recording) {
      // alert("Stopped")
      stopTimeRef.current = performance.now()
      recorderRef.current?.stop()
      streamRef.current?.getTracks().forEach((track) => track.stop())
      setRecording(false)
      setRecorded(true)
      return
    }



    try {

      console.log("started.....")
      // alert("Started")
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      const chunks: Blob[] = []

      recorder.ondataavailable = (event) => chunks.push(event.data)
      recorder.onstop = async () => {
        const blob = new Blob(chunks, { type: recorder.mimeType })
        setLoading(true)
        setError('')
        try {
          const ext = recorder.mimeType.includes('mp4') ? 'mp4' : 'webm'
          const form = new FormData()
          form.append('audio', blob, `recording.${ext}`)
          form.append('session_id', getSessionId())

          const res = await fetch('http://127.0.0.1:8000/voice-search', {
            method: 'POST',
            body: form,
          })
          if (!res.ok) setError('Search failed. Please try again.')
          handleResponse(await res.json())
        } catch {
          setError('Search failed. Please try again.')
        } finally {
          setLoading(false)
        }
      }


      

      streamRef.current = stream
      recorderRef.current = recorder
      recorder.start()
      setRecording(true)
      setRecorded(false)
    } catch {
      setError('Microphone access is unavailable. Please allow microphone access and try again.')
    }
  }

  function togglePlayback() {
    if (!audioRef.current) return

    if (playing) {
      audioRef.current.pause()
    } else {
      audioRef.current.play()
    }

    setPlaying(!playing)
  }


  function resetSearch() {
    setRecorded(false)
    setAudioUrl(null)
    setError('')
  }

  return (
    <main className="min-h-screen bg-[#f6f8f7] text-[#173f3a]">
      <header className="border-b border-[#dce6e2] bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 lg:px-8">
          <div className="flex items-center gap-2.5">
            <span className="grid size-9 place-items-center rounded-xl bg-[#173f3a] text-white">
              <AudioLines className="size-5" />
            </span>
            <span className="text-xl font-semibold tracking-tight">vyngo</span>
          </div>
        
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-5 py-10 lg:px-8 lg:py-14">
        <section className="mb-9 max-w-2xl">
          <Badge className="mb-4 rounded-full bg-[#e0eee9] px-3 py-1 text-[#267166] hover:bg-[#e0eee9]">
            <AudioLines data-icon="inline-start" />
            Audio search
          </Badge>
          <h1 className="text-4xl font-semibold tracking-[-0.04em] sm:text-5xl">
            Find the right commercial vehicle.
          </h1>
          <p className="mt-4 text-base leading-7 text-[#657773]">
            Tell us what you need using your voice. We&apos;ll apply the relevant filters for you.
          </p>
        </section>

        <section className="grid gap-6 lg:grid-cols-[1fr_340px]">
  {/* Mic + latest result */}
  <Card className="rounded-3xl border-[#dce6e2] bg-white shadow-[0_16px_50px_rgba(25,67,60,0.07)]">
    <CardHeader className="border-b border-[#edf1ef] px-6 pb-5 pt-6 sm:px-8">
      <CardTitle className="text-lg text-black">Describe what you&apos;re looking for</CardTitle>
      <p className="text-sm text-[#7b8985]">Tap the microphone and speak naturally.</p>
    </CardHeader>

    <CardContent className="flex flex-col items-center px-6 py-10 sm:px-8">
      <button
        type="button"
        aria-label={recording ? 'Stop recording' : 'Start recording'}
        onClick={toggleRecording}
        disabled={loading}
        className={`grid size-36 place-items-center rounded-full transition-all disabled:opacity-50 ${
          recording
            ? 'bg-[#d85f51] text-white shadow-[0_0_0_12px_#fbe5e1,0_0_0_24px_#fdf1ef]'
            : 'bg-[#e4f1ed] text-[#267166] shadow-[0_0_0_12px_#f1f8f5] hover:scale-105'
        }`}
      >
        {recording ? <CircleStop className="size-11" /> : <Mic className="size-11" />}
      </button>

      <p className="mt-6 font-medium text-[#264d47]">
        {recording ? 'Listening…' : loading ? 'Searching…' : 'Tap to speak'}
      </p>
      <p className="mt-1 text-sm text-[#8a9692]">
        {recording ? 'Tap again when you are done' : 'Use your voice to describe your vehicle needs'}
      </p>

      {recording && (
        <div className="mt-6 flex h-7 items-center gap-1" aria-label="Recording waveform">
          {[3, 7, 14, 22, 15, 8, 18, 10, 5, 16, 7, 12, 4, 9].map((height, index) => (
            <span key={index} className="w-1 animate-pulse rounded-full bg-[#2d8376]" style={{ height }} />
          ))}
        </div>
      )}

      {error && <p className="mt-5 max-w-sm text-center text-sm text-[#c24b40]" role="alert">{error}</p>}

      {/* Latest turn */}
      {turn && (
        <div className="mt-10 w-full space-y-4">
                  <div>
                    <p className="text-xs text-[#8a9994]">You said</p>
                    <p className="mt-1 rounded-xl bg-[#f1f6f4] px-4 py-3 text-sm text-[#264d47]">
                      {turn.transcript}
                    </p>
                  </div>

{turn.answer && (
  <div>
    <p className="text-xs text-[#8a9994]">Assistant says</p>
    <p className="mt-1 rounded-xl bg-[#e0eee9] px-4 py-3 text-sm text-[#264d47]">
      {turn.answer}
    </p>
    <div className="mt-2 flex gap-4">
      <button
        type="button"
        onClick={togglePause}
        className="text-sm font-medium text-[#398075] hover:text-[#267166]"
      >
        {isPlaying ? '⏸ Pause' : '▶ Resume'}
      </button>
      <button
        type="button"
        onClick={() => playAnswer(lastAudio)}
        className="text-sm font-medium text-[#398075] hover:text-[#267166]"
      >
        ↻ Replay
      </button>
    </div>
  </div>
)}

                  {lastSearch &&
                    (lastSearch.results.length > 0 ? (
                      <div className="space-y-2">
                        {lastSearch.results.map((v, i) => (
                          <div key={v.id} className="rounded-2xl border border-[#dce6e2] bg-white p-5 shadow-sm">
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="text-xs font-semibold uppercase tracking-wide text-[#267166]">
                                  #{i + 1} · {v.make}
                                </p>
                                <p className="mt-0.5 text-lg font-semibold">{v.model}</p>
                              </div>
                              <p className="text-xl font-semibold text-[#173f3a]">
                                ₹{v.price.toLocaleString('en-IN')}
                              </p>
                            </div>

                            <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-[#edf1ef] pt-4 sm:grid-cols-3">
                              <Spec label="Year" value={String(v.year)} />
                              <Spec label="Km driven" value={`${v.km_driven.toLocaleString('en-IN')} km`} />
                              <Spec label="Fuel" value={v.fuel} />
                              <Spec label="Body type" value={v.body_type.replace('_', ' ')} />
                              <Spec label="Payload" value={`${v.payload_kg.toLocaleString('en-IN')} kg`} />
                              <Spec label="City" value={v.city} />
                            </div>

                            <p
                              className={`mt-4 inline-block rounded-full px-3 py-1 text-xs font-medium ${v.papers_verified ? 'bg-[#e0eee9] text-[#267166]' : 'bg-[#fdf1ef] text-[#c24b40]'
                                }`}
                            >
                              {v.papers_verified ? 'Papers verified' : 'Papers not verified'}
                            </p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="rounded-xl bg-[#fbe5e1] p-4 text-sm text-[#c24b40]">
                        No vehicles match: {lastSearch.filter}
                      </p>
                    ))}

                  <p className="text-xs text-[#a1afaa]">
                    {turn.action !== 'vehicle_question' && `${turn.total} matches · `}
                    STT {turn.latency.stt} ms · LLM {turn.latency.llm} ms · search {turn.latency.search} ms · TTS {turn.latency.tts} ms
                    {firstAudioMs !== null && ` · tap to first audio ${firstAudioMs} ms`}
                  </p>
                </div>
              )}
    </CardContent>
  </Card>

  {/* Filters: read-only, driven by the backend */}
  <Card className="self-start rounded-3xl border-[#dce6e2] bg-[#edf5f2] shadow-none">
    <CardHeader className="px-6 pb-3 pt-6">
      <div className="flex items-center justify-between">
        <div>
          <CardTitle className="text-lg text-black">Applied filters</CardTitle>
          <p className="mt-1 text-sm text-[#71847e]">Updates after every turn.</p>
        </div>
        <SlidersHorizontal className="size-5 text-[#5d8d83]" />
        <button
  type="button"
  onClick={newSearch}
  className="text-sm font-medium text-[#398075] hover:text-[#267166]"
>
  New search
</button>
      </div>
    </CardHeader>
    <CardContent className="flex flex-col gap-3 px-6 pb-6">
      {FILTER_LABELS.map(([key, label]) => (
        <div
          key={key}
          className={`rounded-xl border border-[#cfe0da] bg-white px-3 py-3 ${
            slots[key] === null ? 'opacity-50' : ''
          }`}
        >
          <p className="text-xs text-[#8a9994]">{label}</p>
          <p className="mt-0.5 text-sm font-medium text-[#315e56]">{showValue(key, slots[key])}</p>
        </div>
      ))}
    </CardContent>
  </Card>
</section>
      </div>
    </main>
  )
}


function Spec({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-[#8a9994]">{label}</p>
      <p className="mt-0.5 text-sm font-medium text-[#264d47]">{value}</p>
    </div>
  )
}