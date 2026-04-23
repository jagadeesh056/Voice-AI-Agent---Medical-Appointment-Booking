'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Mic,
  MicOff,
  Send,
  Phone,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Loader2,
  ShieldCheck,
  Play,
  Square,
} from 'lucide-react'

interface Message {
  type: 'user' | 'assistant' | 'error'
  text: string
  intent?: string
  timestamp: Date
  appointmentCard?: AppointmentCardData | null
}

interface AppointmentCardData {
  appointment_id: number
  patient_name: string
  medical_specialty?: string
  appointment_type: string
  doctor_name?: string
  clinic_name?: string
  appointment_date?: string
  status: string
  old_date?: string
  new_date?: string
}

interface SlotInfo {
  datetime: string
  time: string
  label: string
  available: boolean
  past: boolean
  appointment?: {
    id: number
    appointment_type: string
    doctor_name: string
    clinic_name?: string
    status: string
  }
}

interface SlotsData {
  date: string
  day_label: string
  total_slots: number
  available_count: number
  booked_count: number
  slots: SlotInfo[]
  message?: string
}

const BACKEND = 'http://127.0.0.1:8000'
const TIMEOUT = 65000

const LANG_STT: Record<string, string> = {
  en: 'en-US',
  hi: 'hi-IN',
  ta: 'ta-IN',
}

const intentMeta: Record<string, { color: string; icon: string }> = {
  book: { color: 'bg-emerald-100 text-emerald-700', icon: '📅' },
  reschedule: { color: 'bg-amber-100 text-amber-700', icon: '🔄' },
  cancel: { color: 'bg-rose-100 text-rose-700', icon: '❌' },
  query: { color: 'bg-sky-100 text-sky-700', icon: '🔍' },
  confirm: { color: 'bg-violet-100 text-violet-700', icon: '✅' },
  general: { color: 'bg-indigo-100 text-indigo-700', icon: '💬' },
  error: { color: 'bg-rose-100 text-rose-700', icon: '⚠️' },
}

function localDateString(d = new Date()) {
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function parseDateFromText(text: string): string | null {
  const lower = text.toLowerCase()
  const today = new Date()

  if (/\btoday\b/.test(lower)) return localDateString(today)

  if (/\btomorrow\b/.test(lower)) {
    const d = new Date(today)
    d.setDate(d.getDate() + 1)
    return localDateString(d)
  }

  if (/\bnext\s+week\b/.test(lower)) {
    const d = new Date(today)
    d.setDate(d.getDate() + 7)
    return localDateString(d)
  }

  const days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
  for (let i = 0; i < days.length; i++) {
    if (lower.includes(days[i])) {
      const d = new Date(today)
      const diff = (i - d.getDay() + 7) % 7 || 7
      d.setDate(d.getDate() + diff)
      return localDateString(d)
    }
  }

  const monthMap: Record<string, number> = {
    january: 0,
    february: 1,
    march: 2,
    april: 3,
    may: 4,
    june: 5,
    july: 6,
    august: 7,
    september: 8,
    october: 9,
    november: 10,
    december: 11,
  }

  const monthMatch = lower.match(
    /\b(\d{1,2})(?:st|nd|rd|th)?(?:\s+of)?\s+(january|february|march|april|may|june|july|august|september|october|november|december)(?:\s+(\d{4}))?\b/
  )
  if (monthMatch) {
    const day = parseInt(monthMatch[1], 10)
    const month = monthMap[monthMatch[2]]
    const year = monthMatch[3] ? parseInt(monthMatch[3], 10) : today.getFullYear()
    const d = new Date(year, month, day)
    if (!isNaN(d.getTime())) return localDateString(d)
  }

  const ex = lower.match(/\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b/)
  if (ex) {
    const d = new Date(+ex[3], +ex[2] - 1, +ex[1])
    if (!isNaN(d.getTime())) return localDateString(d)
  }

  return null
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-GB', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    })
  } catch {
    return iso
  }
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
}

function fmtDateLabel(s: string): string {
  const [y, mo, d] = s.split('-').map(Number)
  return new Date(y, mo - 1, d).toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

function AppointmentCard({ data }: { data: AppointmentCardData }) {
  const cfg =
    {
      booked: {
        grad: 'from-emerald-500 to-teal-600',
        icon: '✅',
        title: 'Appointment Confirmed!',
      },
      rescheduled: {
        grad: 'from-amber-500 to-orange-500',
        icon: '🔄',
        title: 'Appointment Rescheduled',
      },
      cancelled: {
        grad: 'from-rose-500 to-pink-600',
        icon: '❌',
        title: 'Appointment Cancelled',
      },
    }[data.status] ?? {
      grad: 'from-indigo-500 to-violet-600',
      icon: '📅',
      title: 'Appointment Updated',
    }

  const isReschedule = data.status === 'rescheduled'
  const isCancel = data.status === 'cancelled'
  const isBooked = data.status === 'booked'

  return (
    <div
      className="mt-3 overflow-hidden rounded-2xl border border-white/60 shadow-lg"
      style={{ animation: 'cardPop 0.35s cubic-bezier(0.34,1.56,0.64,1) forwards' }}
    >
      <div className={`bg-gradient-to-r ${cfg.grad} flex items-center gap-2 px-4 py-3`}>
        <span className="text-xl">{cfg.icon}</span>
        <div>
          <p className="text-sm font-bold text-white">{cfg.title}</p>
          <p className="text-[10px] text-white/70">
            Token ID: <strong>#{data.appointment_id}</strong>
          </p>
        </div>
      </div>

      <div className="space-y-2.5 bg-white px-4 py-3">
        {[
          { icon: '👤', label: 'Patient', val: data.patient_name },
          { icon: '🏥', label: 'Specialty', val: data.medical_specialty || data.appointment_type },
          { icon: '👨‍⚕️', label: 'Doctor', val: data.doctor_name || 'Any Available Doctor' },
          { icon: '🏢', label: 'Clinic', val: data.clinic_name || 'Main Clinic' },
        ].map(
          (r) =>
            r.val && (
              <div key={r.label} className="flex items-center gap-2.5">
                <span className="w-5 text-center text-base leading-none">{r.icon}</span>
                <div>
                  <p className="text-[10px] leading-none text-gray-400">{r.label}</p>
                  <p className="mt-0.5 text-xs font-semibold text-gray-800">{r.val}</p>
                </div>
              </div>
            )
        )}

        {isReschedule && data.old_date && data.new_date ? (
          <div className="flex items-start gap-2.5">
            <span className="w-5 text-center text-base">📅</span>
            <div>
              <p className="text-[10px] text-gray-400">Rescheduled</p>
              <p className="text-xs text-gray-300 line-through">
                {fmtDate(data.old_date)} · {fmtTime(data.old_date)}
              </p>
              <p className="text-xs font-semibold text-amber-700">
                {fmtDate(data.new_date)} · {fmtTime(data.new_date)}
              </p>
            </div>
          </div>
        ) : !isCancel && data.appointment_date ? (
          <div className="flex items-start gap-2.5">
            <span className="w-5 text-center text-base">📅</span>
            <div>
              <p className="text-[10px] text-gray-400">Date &amp; Time</p>
              <p className="text-xs font-semibold text-gray-800">{fmtDate(data.appointment_date)}</p>
              <p className="text-xs font-medium text-indigo-600">{fmtTime(data.appointment_date)}</p>
            </div>
          </div>
        ) : null}

        {isBooked && (
          <div className="mt-1 flex items-start gap-2 rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2">
            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-emerald-600" />
            <p className="text-[10px] leading-relaxed text-emerald-700">
              Save your token ID <strong>#{data.appointment_id}</strong>. You’ll need it with your
              name and phone number to reschedule or cancel.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

function SlotPicker({
  slotsData,
  loading,
  onSelect,
  onDateChange,
  selectedDate,
}: {
  slotsData: SlotsData | null
  loading: boolean
  onSelect: (s: SlotInfo) => void
  onDateChange: (d: string) => void
  selectedDate: string
}) {
  const shift = (n: number) => {
    const [y, mo, d] = selectedDate.split('-').map(Number)
    const dt = new Date(y, mo - 1, d + n)
    onDateChange(localDateString(dt))
  }

  const disablePrev = selectedDate <= localDateString()

  return (
    <div className="mt-3 overflow-hidden rounded-2xl border border-indigo-100 bg-white/90 shadow-md">
      <div className="flex items-center justify-between border-b border-indigo-100 bg-indigo-50/80 px-3 py-2">
        <button
          onClick={() => shift(-1)}
          disabled={disablePrev}
          className="rounded-lg p-1.5 text-indigo-600 transition-colors hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>

        <div className="text-center">
          <p className="text-xs font-semibold text-indigo-700">{fmtDateLabel(selectedDate)}</p>
          {slotsData && (
            <p className="mt-0.5 text-[10px] text-indigo-400">
              {slotsData.available_count} available · {slotsData.booked_count} booked
            </p>
          )}
        </div>

        <button
          onClick={() => shift(1)}
          className="rounded-lg p-1.5 text-indigo-600 transition-colors hover:bg-indigo-100"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="p-3">
        {loading ? (
          <div className="flex items-center justify-center gap-2 py-5 text-indigo-400">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-xs">Loading slots…</span>
          </div>
        ) : !slotsData ? (
          <p className="py-4 text-center text-xs text-gray-400">No data available</p>
        ) : slotsData.message ? (
          <p className="py-4 text-center text-xs text-rose-500">{slotsData.message}</p>
        ) : (
          <div className="grid grid-cols-3 gap-1.5">
            {slotsData.slots.map((slot) => (
              <button
                key={slot.time}
                disabled={!slot.available}
                onClick={() => slot.available && onSelect(slot)}
                title={
                  slot.appointment
                    ? `${slot.appointment.appointment_type} – ${slot.appointment.doctor_name}`
                    : slot.available
                    ? 'Available'
                    : 'Past'
                }
                className={[
                  'rounded-xl px-2 py-1.5 text-center text-xs font-medium transition-all',
                  slot.past
                    ? 'cursor-not-allowed bg-gray-50 text-gray-200'
                    : slot.appointment
                    ? 'cursor-not-allowed bg-rose-50 text-rose-300 line-through'
                    : 'cursor-pointer bg-emerald-50 text-emerald-700 hover:scale-105 hover:bg-emerald-100 active:scale-95',
                ].join(' ')}
              >
                {slot.label}
              </button>
            ))}
          </div>
        )}

        <div className="mt-2.5 flex gap-3 border-t border-gray-100 pt-2">
          {[
            ['bg-emerald-100', 'Available'],
            ['bg-rose-100', 'Booked'],
            ['bg-gray-100', 'Past'],
          ].map(([cls, lbl]) => (
            <div key={lbl} className="flex items-center gap-1">
              <span className={`inline-block h-2.5 w-2.5 rounded ${cls}`} />
              <span className="text-[10px] text-gray-400">{lbl}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function VoiceChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isRecording, setIsRecording] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [processingLabel, setProcessingLabel] = useState('Thinking…')
  const [language, setLanguage] = useState('en')
  const [textInput, setTextInput] = useState('')
  const [connStatus, setConnStatus] = useState<'disconnected' | 'connecting' | 'connected'>(
    'disconnected'
  )
  const [liveTranscript, setLiveTranscript] = useState('')
  const [showSlots, setShowSlots] = useState(false)
  const [slotsDate, setSlotsDate] = useState(() => localDateString())
  const [slotsData, setSlotsData] = useState<SlotsData | null>(null)
  const [slotsLoading, setSlotsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sessionActive, setSessionActive] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const recRef = useRef<any>(null)
  const liveRef = useRef('')
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const sendRef = useRef<(t: string) => void>(() => {})

  useEffect(() => {
    liveRef.current = liveTranscript
  }, [liveTranscript])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isProcessing, liveTranscript])

  useEffect(() => {
    if (!textareaRef.current) return
    textareaRef.current.style.height = 'auto'
    textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`
  }, [textInput])

  const clearTimer = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }

  const markDone = useCallback(() => {
    clearTimer()
    setIsProcessing(false)
    setProcessingLabel('Thinking…')
  }, [])

  const fetchSlots = useCallback(async (dateStr: string) => {
    setSlotsLoading(true)
    setSlotsDate(dateStr)
    setSlotsData(null)

    try {
      const r = await fetch(`${BACKEND}/api/slots/?date=${dateStr}`)
      const data = await r.json()
      setSlotsData(data)
    } catch {
      setSlotsData(null)
    } finally {
      setSlotsLoading(false)
    }
  }, [])

  const resetConversationUI = useCallback(() => {
    setMessages([])
    setTextInput('')
    setLiveTranscript('')
    setShowSlots(false)
    setSlotsData(null)
    setSlotsDate(localDateString())
    setSessionId(null)
    setSessionActive(false)
    setConnStatus('disconnected')
    markDone()
  }, [markDone])

  const startSession = async () => {
    if (sessionActive) return

    setConnStatus('connecting')
    setMessages([])

    try {
      const res = await fetch(`${BACKEND}/api/sessions/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Guest', language }),
      })

      if (!res.ok) throw new Error('Could not create session')

      const data = await res.json()
      setSessionId(data.session_id)
      setSessionActive(true)
      connectWS(data.session_id)
      fetchSlots(localDateString())

      setTimeout(() => {
        setMessages([
          {
            type: 'assistant',
            text: '👋 Hello! I can help you book, reschedule, or cancel an appointment. How may I assist you today?',
            timestamp: new Date(),
          },
        ])
      }, 250)
    } catch {
      setConnStatus('disconnected')
    }
  }

  const endSession = async () => {
    try {
      if (sessionId) {
        await fetch(`${BACKEND}/api/sessions/end`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            end_reason: 'user_ended',
          }),
        })
      }
    } catch {}

    try {
      wsRef.current?.close()
    } catch {}

    resetConversationUI()
  }

  const connectWS = (sid: string) => {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//127.0.0.1:8000/api/voice/ws/${sid}`)

    ws.onopen = () => setConnStatus('connected')

    ws.onerror = () => {
      setConnStatus('disconnected')
      markDone()
    }

    ws.onclose = () => {
      setConnStatus('disconnected')
      markDone()
    }

    ws.onmessage = ({ data }) => {
      const msg = JSON.parse(data)

      if (msg.type === 'processing') {
        setIsProcessing(true)
        setProcessingLabel('Assistant is thinking…')
        clearTimer()
        timerRef.current = setTimeout(() => {
          setIsProcessing(false)
          setMessages((p) => [
            ...p,
            {
              type: 'error',
              text: '⚠ Timed out. Please try again.',
              timestamp: new Date(),
            },
          ])
        }, TIMEOUT)
        return
      }

      if (msg.type === 'transcription') {
        return
      }

      if (msg.type === 'response') {
        const lower = String(msg.message || '').toLowerCase()
        const card: AppointmentCardData | null = msg.appointment ?? null

        if (card?.status === 'booked' || card?.status === 'rescheduled' || card?.status === 'cancelled') {
          setShowSlots(false)

          if (card.appointment_date) {
            const d = new Date(card.appointment_date)
            fetchSlots(localDateString(d))
          } else {
            fetchSlots(localDateString())
          }
        } else if (
          /\b(choose|pick|select|which\s+(?:date|time|slot)|what\s+(?:date|time)|prefer(?:red)?\s+(?:date|time)|available\s+slot|would\s+you\s+like\s+(?:a\s+)?(?:date|time))\b/.test(lower)
        ) {
          setShowSlots(true)
        } else if (card === null || card === undefined) {
          // Hide slots once the user's message was processed without producing a card
          // (prevents stale calendar from persisting between intents)
        }
        setMessages((p) => [
          ...p,
          {
            type: 'assistant',
            text: msg.message,
            intent: msg.intent,
            timestamp: new Date(),
            appointmentCard: card,
          },
        ])

        markDone()
        return
      }

      if (msg.type === 'error') {
        setMessages((p) => [
          ...p,
          {
            type: 'error',
            text: `⚠ ${msg.message}`,
            timestamp: new Date(),
          },
        ])
        markDone()
      }
    }

    wsRef.current = ws
  }

  const sendInternal = useCallback(
    (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || !sessionActive || wsRef.current?.readyState !== WebSocket.OPEN) return

      const found = parseDateFromText(trimmed)
      if (found) {
        fetchSlots(found)
        setShowSlots(true)
      }

      setMessages((p) => [...p, { type: 'user', text: trimmed, timestamp: new Date() }])
      setIsProcessing(true)
      setProcessingLabel('Assistant is thinking…')

      wsRef.current.send(
        JSON.stringify({
          type: 'text',
          message: trimmed,
          language,
        })
      )
    },
    [language, fetchSlots, sessionActive]
  )

  useEffect(() => {
    sendRef.current = sendInternal
  }, [sendInternal])

  const sendText = () => {
    if (!textInput.trim()) return
    const t = textInput
    setTextInput('')
    sendInternal(t)
  }

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendText()
    }
  }

  const startRecording = () => {
    if (!sessionActive) return

    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SR) {
      alert('Speech recognition requires Chrome or Edge.')
      return
    }

    const rec: any = new SR()
    rec.lang = LANG_STT[language] || 'en-US'
    rec.interimResults = true
    rec.continuous = false

    rec.onstart = () => {
      setIsRecording(true)
      setLiveTranscript('')
    }

    rec.onresult = (e: any) => {
      let t = ''
      for (let i = 0; i < e.results.length; i++) t += e.results[i][0].transcript
      setLiveTranscript(t)
    }

    rec.onend = () => {
      setIsRecording(false)
      const finalText = liveRef.current.trim()
      setLiveTranscript('')
      if (finalText) sendRef.current(finalText)
    }

    rec.onerror = (e: any) => {
      setIsRecording(false)
      setLiveTranscript('')
      if (e.error !== 'aborted' && e.error !== 'no-speech') {
        setMessages((p) => [
          ...p,
          {
            type: 'error',
            text: `⚠ Mic: ${e.error}`,
            timestamp: new Date(),
          },
        ])
      }
    }

    recRef.current = rec
    rec.start()
  }

  const stopRecording = () => recRef.current?.stop?.()

  const handleSlotSelect = (slot: SlotInfo) => {
    sendInternal(`I would like ${slot.label} on ${slotsData?.day_label || fmtDateLabel(slotsDate)}`)
    setShowSlots(false)
  }

  const handleReconnect = () => {
    if (!sessionId) return
    try {
      wsRef.current?.close()
    } catch {}
    markDone()
    connectWS(sessionId)
  }

  const canInteract = sessionActive && connStatus === 'connected' && !isProcessing

  const statusCfg = {
    connected: { dot: 'bg-emerald-400 animate-pulse', label: 'Online' },
    connecting: { dot: 'bg-amber-400 animate-pulse', label: 'Connecting…' },
    disconnected: { dot: 'bg-rose-400', label: sessionActive ? 'Offline' : 'Not started' },
  }[connStatus]

  return (
    <div
      className="flex h-screen flex-col"
      style={{ background: 'linear-gradient(135deg,#eef2ff 0%,#faf5ff 50%,#ecfdf5 100%)' }}
    >
      <style jsx global>{`
        @keyframes fadeUp {
          from {
            opacity: 0;
            transform: translateY(8px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        @keyframes cardPop {
          from {
            opacity: 0;
            transform: scale(0.96);
          }
          to {
            opacity: 1;
            transform: scale(1);
          }
        }
        @keyframes bounceDot {
          0%, 80%, 100% {
            transform: scale(0.8);
            opacity: 0.5;
          }
          40% {
            transform: scale(1);
            opacity: 1;
          }
        }
      `}</style>

      <header className="flex-shrink-0 border-b border-white/60 bg-white/80 shadow-sm backdrop-blur-sm">
        <div className="mx-auto flex max-w-2xl items-center justify-between px-5 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-md">
              <span className="text-lg">🏥</span>
            </div>

            <div>
              <h1 className="text-sm font-bold text-gray-900">MedAssist</h1>
              <div className="mt-0.5 flex items-center gap-1.5">
                <span className={`h-1.5 w-1.5 rounded-full ${statusCfg.dot}`} />
                <span className="text-[10px] text-gray-400">{statusCfg.label}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-600"
            >
              <option value="en">🇬🇧 English</option>
              <option value="hi">🇮🇳 हिंदी</option>
              <option value="ta">🇮🇳 தமிழ்</option>
            </select>

            {!sessionActive ? (
              <button
                onClick={startSession}
                className="flex items-center gap-1 rounded-lg bg-emerald-500 px-3 py-2 text-xs font-medium text-white hover:bg-emerald-600"
              >
                <Play className="h-3.5 w-3.5" />
                Start
              </button>
            ) : (
              <button
                onClick={endSession}
                className="flex items-center gap-1 rounded-lg bg-rose-500 px-3 py-2 text-xs font-medium text-white hover:bg-rose-600"
              >
                <Square className="h-3.5 w-3.5" />
                End
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl space-y-4 px-4 py-5">
          {!sessionActive && (
            <div className="rounded-2xl border border-dashed border-indigo-200 bg-white/80 px-6 py-10 text-center shadow-sm">
              <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50">
                <Phone className="h-6 w-6 text-indigo-400" />
              </div>
              <p className="text-sm font-medium text-gray-700">Start a new customer conversation</p>
              <p className="mt-1 text-xs text-gray-400">
                Click Start to begin booking, rescheduling, or cancelling an appointment.
              </p>
            </div>
          )}

          {messages.map((msg, idx) => {
            const isUser = msg.type === 'user'
            const isErr = msg.type === 'error'
            const isLast = idx === messages.length - 1
            const meta = msg.intent ? intentMeta[msg.intent] : null

            if (isErr) {
              return (
                <div key={idx} className="flex justify-center">
                  <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-center text-xs text-rose-600">
                    {msg.text.replace('⚠ ', '')}
                  </div>
                </div>
              )
            }

            return (
              <div
                key={idx}
                className={`flex items-end gap-2 ${isUser ? 'justify-end' : 'justify-start'}`}
                style={{ animation: 'fadeUp 0.22s ease-out forwards' }}
              >
                {!isUser && (
                  <div className="mb-5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 text-sm shadow-sm">
                    🏥
                  </div>
                )}

                <div className="flex max-w-[78%] flex-col gap-1">
                  <div
                    className={`rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                      isUser
                        ? 'rounded-br-sm bg-gradient-to-br from-indigo-500 to-indigo-600 text-white'
                        : 'rounded-bl-sm border border-gray-100 bg-white text-gray-800'
                    }`}
                  >
                    {msg.text}

                    {!isUser && msg.appointmentCard && <AppointmentCard data={msg.appointmentCard} />}

                    {!isUser && isLast && showSlots && !msg.appointmentCard && (
                      <SlotPicker
                        slotsData={slotsData}
                        loading={slotsLoading}
                        onSelect={handleSlotSelect}
                        onDateChange={fetchSlots}
                        selectedDate={slotsDate}
                      />
                    )}
                  </div>

                  <div className={`flex items-center gap-2 px-1 ${isUser ? 'justify-end' : 'justify-start'}`}>
                    <span className="text-[10px] text-gray-400">
                      {msg.timestamp.toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                    {meta && (
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${meta.color}`}>
                        {meta.icon} {msg.intent}
                      </span>
                    )}
                  </div>
                </div>

                {isUser && (
                  <div className="mb-5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-400 to-indigo-500 text-xs font-bold text-white shadow-sm">
                    U
                  </div>
                )}
              </div>
            )
          })}

          {liveTranscript && (
            <div className="flex items-end justify-end gap-2" style={{ animation: 'fadeUp 0.15s ease-out forwards' }}>
              <div className="max-w-[78%] rounded-2xl rounded-br-sm bg-indigo-400/70 px-4 py-3 text-sm italic text-white shadow-sm">
                🎙 {liveTranscript}
                <span className="ml-1 inline-block h-4 w-0.5 animate-pulse rounded-sm bg-white/70 align-middle" />
              </div>
              <div className="mb-5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-400 to-indigo-500 text-xs font-bold text-white shadow-sm">
                U
              </div>
            </div>
          )}

          {isProcessing && (
            <div className="flex items-end justify-start gap-2" style={{ animation: 'fadeUp 0.2s ease-out forwards' }}>
              <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 text-sm shadow-sm">
                🏥
              </div>
              <div className="rounded-2xl rounded-bl-sm border border-gray-100 bg-white px-4 py-3 shadow-sm">
                <div className="flex items-center gap-1.5">
                  <span
                    className="h-2 w-2 rounded-full bg-indigo-400"
                    style={{ animation: 'bounceDot 1.2s infinite' }}
                  />
                  <span
                    className="h-2 w-2 rounded-full bg-indigo-400"
                    style={{ animation: 'bounceDot 1.2s infinite 0.15s' }}
                  />
                  <span
                    className="h-2 w-2 rounded-full bg-indigo-400"
                    style={{ animation: 'bounceDot 1.2s infinite 0.3s' }}
                  />
                </div>
                <p className="mt-2 text-[10px] text-gray-400">{processingLabel}</p>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </main>

      <footer className="flex-shrink-0 border-t border-white/60 bg-white/80 backdrop-blur-sm">
        <div className="mx-auto max-w-2xl px-4 py-4">
          <div className="flex items-end gap-2 rounded-2xl border border-white/70 bg-white/90 p-2 shadow-md">
            <button
              onClick={isRecording ? stopRecording : startRecording}
              disabled={!canInteract}
              className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl transition-all ${
                isRecording
                  ? 'bg-rose-500 text-white hover:bg-rose-600'
                  : 'bg-indigo-50 text-indigo-600 hover:bg-indigo-100'
              } disabled:cursor-not-allowed disabled:opacity-50`}
              title={isRecording ? 'Stop recording' : 'Start voice input'}
            >
              {isRecording ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
            </button>

            <textarea
              ref={textareaRef}
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              onKeyDown={handleKey}
              disabled={!sessionActive || !canInteract}
              placeholder={
                !sessionActive
                  ? 'Click Start to begin conversation'
                  : connStatus === 'connected'
                  ? 'Type your message...'
                  : 'Connection offline'
              }
              rows={1}
              className="max-h-[120px] min-h-[44px] flex-1 resize-none bg-transparent px-2 py-2 text-sm text-gray-800 outline-none placeholder:text-gray-400 disabled:cursor-not-allowed"
            />

            {sessionActive && connStatus === 'disconnected' && (
              <button
                onClick={handleReconnect}
                className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-amber-50 text-amber-600"
                title="Reconnect"
              >
                <RefreshCw className="h-4.5 w-4.5" />
              </button>
            )}

            <button
              onClick={sendText}
              disabled={!canInteract || !textInput.trim()}
              className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-40"
              title="Send"
            >
              <Send className="h-4.5 w-4.5" />
            </button>
          </div>

          <div className="mt-2 flex items-center justify-between px-1">
            <p className="text-[10px] text-gray-400">
              Use name + phone number + token ID for update or cancellation.
            </p>
            <p className="text-[10px] text-gray-400">
              {!sessionActive ? 'Conversation not started' : canInteract ? 'Ready' : 'Unavailable'}
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}