import { useEffect, useMemo, useRef, useState } from 'react'
import PropTypes from 'prop-types'
import { Bot, MessageSquare, Send, X } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import { useTranslation } from 'react-i18next'

const getDefaultApiBaseUrl = () => {
  if (
    typeof window !== 'undefined' &&
    window.location.hostname.endsWith('netlify.app')
  ) {
    return 'https://tashkent-city-grip-api.onrender.com'
  }
  return 'http://localhost:8000'
}

const API_BASE_URL = (
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  getDefaultApiBaseUrl()
).replace(/\/+$/, '')
const DEBUG_FLOW =
  import.meta.env.DEV || import.meta.env.VITE_DEBUG_FLOW === 'true'
const REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS || 90000)

const createRequestId = () => {
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.randomUUID === 'function'
  ) {
    return crypto.randomUUID()
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

const resolveSourceUrl = (sourceLabel, sourceUrl) => {
  if (sourceUrl) return sourceUrl
  if (!sourceLabel) return null
  if (sourceLabel.startsWith('http://') || sourceLabel.startsWith('https://'))
    return sourceLabel
  return `https://www.google.com/search?q=${encodeURIComponent(sourceLabel)}`
}

const normalizeSources = (rawSources, getFallbackLabel) => {
  if (!rawSources) return []
  const sourceList = Array.isArray(rawSources) ? rawSources : [rawSources]
  return sourceList
    .map((source, index) => {
      if (typeof source === 'string') {
        return {
          id: `${source}-${index}`,
          label: source,
          url: resolveSourceUrl(source)
        }
      }
      if (source && typeof source === 'object') {
        const label =
          source.label ||
          source.title ||
          source.source ||
          source.name ||
          getFallbackLabel(index + 1)
        const url = resolveSourceUrl(label, source.url || source.link)
        return {
          id: `${label}-${index}`,
          label,
          url
        }
      }
      return null
    })
    .filter(Boolean)
}

const extractAssistantPayload = (payload, getFallbackLabel, defaultText) => {
  const text =
    payload?.answer ||
    payload?.response ||
    payload?.output ||
    payload?.message ||
    payload?.text ||
    defaultText
  const sources = normalizeSources(
    payload?.sources ||
      payload?.citations ||
      payload?.references ||
      payload?.source ||
      payload?.citation,
    getFallbackLabel
  )
  return {
    text,
    sources
  }
}

const getFutureCriticalDistricts = (futureState) => {
  const districts = futureState?.district_predictions || []
  return [...districts]
    .sort((a, b) => (b.load_percentage || 0) - (a.load_percentage || 0))
    .slice(0, 3)
}

function TypingDots({ label }) {
  return (
    <div className='inline-flex items-center gap-2 rounded-2xl border border-slate-700 bg-slate-900/90 px-3 py-2'>
      <span className='h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400 [animation-delay:0ms]' />
      <span className='h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400 [animation-delay:150ms]' />
      <span className='h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400 [animation-delay:300ms]' />
      <span className='text-xs text-slate-300'>{label}</span>
    </div>
  )
}

TypingDots.propTypes = {
  label: PropTypes.string.isRequired
}

function Chatbot({
  temperature,
  construction,
  selectedTransformerId,
  futureMode,
  futureDate,
  futureSummary,
  activeSuggestedTp
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [lastTrace, setLastTrace] = useState(null)
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: t('chatbot.welcome'),
      sources: []
    }
  ])
  const messagesEndRef = useRef(null)
  const lastAutoReportKeyRef = useRef('')

  useEffect(() => {
    setMessages((prev) =>
      prev.map((message) =>
        message.id === 'welcome'
          ? { ...message, content: t('chatbot.welcome') }
          : message
      )
    )
  }, [t])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading, open])

  useEffect(() => {
    if (futureMode && futureDate) {
      setOpen(true)
    }
  }, [futureMode, futureDate])

  const contextState = useMemo(
    () => ({
      temperature,
      construction,
      selectedTransformerId: selectedTransformerId || null,
      futureMode: Boolean(futureMode),
      futureDate: futureDate || null,
      futureSummary: futureSummary || null,
      focusedSuggestedTp: activeSuggestedTp
        ? {
            id: activeSuggestedTp.id,
            district: activeSuggestedTp.district,
            expected_load_kw: activeSuggestedTp.expected_load_kw ?? null
          }
        : null,
      timestamp: new Date().toISOString()
    }),
    [
      temperature,
      construction,
      selectedTransformerId,
      futureMode,
      futureDate,
      futureSummary,
      activeSuggestedTp
    ]
  )

  const buildAutoFuturePrompt = () => {
    return `Provide a concise Future Mode executive summary for ${futureDate}: overall status, top 3 highest-risk districts, total transformers needed, and one immediate action. Do not include detailed per-TP reasons.`
  }

  const sendMessage = async (providedText = null, options = {}) => {
    const trimmed = (providedText ?? input).trim()
    if (!trimmed || isLoading) return

    const userMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: options.userLabel || trimmed,
      sources: []
    }
    setMessages((prev) => [...prev, userMessage])
    if (!providedText) {
      setInput('')
    }
    setIsLoading(true)

    const requestId = createRequestId()
    const startedAt = performance.now()
    const controller = new AbortController()
    const timeoutId = setTimeout(
      () => controller.abort('timeout'),
      REQUEST_TIMEOUT_MS
    )

    try {
      const response = await fetch(`${API_BASE_URL}/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Request-ID': requestId
        },
        signal: controller.signal,
        body: JSON.stringify({
          question: trimmed,
          query: trimmed,
          context: {
            ...contextState
          }
        })
      })
      clearTimeout(timeoutId)
      const responseRequestId =
        response.headers.get('x-request-id') || requestId

      if (!response.ok) {
        let errorMessage = `Request failed: ${response.status}`
        try {
          const errorPayload = await response.json()
          if (typeof errorPayload?.detail === 'string') {
            errorMessage = errorPayload.detail
          } else if (typeof errorPayload?.detail?.message === 'string') {
            errorMessage = errorPayload.detail.message
          }
        } catch {
          // Ignore parse issues and keep the status-based message.
        }
        throw new Error(errorMessage)
      }

      const payload = await response.json()
      const completedInMs = Math.round(performance.now() - startedAt)
      const assistantPayload = extractAssistantPayload(
        payload,
        (index) => t('chatbot.source', { index }),
        t('chatbot.noResponse')
      )
      const payloadRequestId = payload?.request_id || responseRequestId
      setLastTrace({
        requestId: payloadRequestId,
        status: response.status,
        durationMs: completedInMs
      })
      if (DEBUG_FLOW) {
        console.info('[Chatbot] request success', {
          requestId: payloadRequestId,
          status: response.status,
          durationMs: completedInMs,
          api: `${API_BASE_URL}/ask`
        })
      }
      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: assistantPayload.text,
          prediction:
            payload?.mode === 'prediction' ? payload?.prediction || null : null,
          futureState: payload?.future_state || null,
          sources: assistantPayload.sources
        }
      ])
    } catch (error) {
      const timedOut =
        error?.name === 'AbortError' ||
        controller.signal.aborted ||
        String(error?.message || '')
          .toLowerCase()
          .includes('aborted')
      const userErrorMessage = timedOut
        ? `${t('chatbot.backendError')} (${API_BASE_URL}/ask)\nRequest ID: ${requestId}\nTimeout: ${Math.round(
            REQUEST_TIMEOUT_MS / 1000
          )}s`
        : `${t('chatbot.backendError')} (${API_BASE_URL}/ask)\nRequest ID: ${requestId}`

      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-error-${Date.now()}`,
          role: 'assistant',
          content: userErrorMessage,
          sources: []
        }
      ])
      const completedInMs = Math.round(performance.now() - startedAt)
      setLastTrace({
        requestId,
        status: 'error',
        durationMs: completedInMs,
        error: error instanceof Error ? error.message : String(error)
      })
      console.error('[Chatbot] request failed', {
        requestId,
        durationMs: completedInMs,
        api: `${API_BASE_URL}/ask`,
        error: error instanceof Error ? error.message : String(error)
      })
    } finally {
      clearTimeout(timeoutId)
      setIsLoading(false)
    }
  }

  const onSubmit = async (event) => {
    event.preventDefault()
    await sendMessage()
  }

  useEffect(() => {
    const hasFuturePayload = futureSummary?.district_predictions?.length > 0
    if (!futureMode || !futureDate || !hasFuturePayload || isLoading) return

    const reportKey = `${futureDate}-${futureSummary?.request_id || futureSummary?.generated_at || 'na'}`
    if (lastAutoReportKeyRef.current === reportKey) return
    lastAutoReportKeyRef.current = reportKey
    setOpen(true)

    const autoPrompt = buildAutoFuturePrompt()
    void sendMessage(autoPrompt, {
      userLabel: t('chatbot.autoReportUser', { date: futureDate })
    })
  }, [futureMode, futureDate, futureSummary, isLoading])

  return (
    <div className='pointer-events-none fixed bottom-20 right-5 z-[1200] md:bottom-5'>
      <AnimatePresence>
        {open && (
          <motion.section
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.98 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            className='pointer-events-auto mb-3 flex h-[500px] w-[calc(100vw-2rem)] max-w-[380px] flex-col overflow-hidden rounded-2xl border border-slate-700 bg-slate-900/95 shadow-2xl backdrop-blur'
          >
            <header className='flex items-center justify-between border-b border-slate-700 px-4 py-3'>
              <div className='flex items-center gap-2'>
                <div className='rounded-lg bg-cyan-500/15 p-1.5 text-cyan-300'>
                  <Bot className='h-4 w-4' />
                </div>
                <div>
                  <p className='text-sm font-semibold text-slate-100'>
                    {t('chatbot.title')}
                  </p>
                  <p className='text-xs text-slate-400'>
                    {t('chatbot.subtitle')}
                  </p>
                </div>
              </div>
              <button
                type='button'
                onClick={() => setOpen(false)}
                className='rounded-lg border border-slate-700 bg-slate-900/90 p-1.5 text-slate-300 transition hover:text-slate-100'
              >
                <X className='h-4 w-4' />
              </button>
            </header>

            <div className='flex-1 space-y-3 overflow-y-auto px-4 py-4'>
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
                      message.role === 'user'
                        ? 'bg-cyan-500/20 text-slate-100'
                        : 'border border-slate-700 bg-slate-900/90 text-slate-100'
                    }`}
                  >
                    <p className='whitespace-pre-wrap leading-relaxed'>
                      {message.content}
                    </p>
                    {message.role === 'assistant' && message.prediction && (
                      <div className='mt-2 rounded-xl border border-slate-700 bg-slate-800/70 p-3 text-xs text-slate-200'>
                        <p>
                          <span className='text-slate-400'>
                            {t('chatbot.prediction.district')}:
                          </span>{' '}
                          {message.prediction.district}
                        </p>
                        <p>
                          <span className='text-slate-400'>
                            {t('chatbot.prediction.targetDate')}:
                          </span>{' '}
                          {message.prediction.target_date}
                        </p>
                        <p>
                          <span className='text-slate-400'>
                            {t('chatbot.prediction.predictedLoad')}:
                          </span>{' '}
                          {message.prediction.predicted_load_mw} MW
                        </p>
                        <p>
                          <span className='text-slate-400'>
                            {t('chatbot.prediction.capacity')}:
                          </span>{' '}
                          {message.prediction.current_capacity_mw} MW
                        </p>
                        <p>
                          <span className='text-slate-400'>
                            {t('chatbot.prediction.loadGap')}:
                          </span>{' '}
                          {message.prediction.load_gap_mw} MW
                        </p>
                        <p>
                          <span className='text-slate-400'>
                            {t('chatbot.prediction.riskScore')}:
                          </span>{' '}
                          <span
                            className={
                              message.prediction.risk_score >= 8
                                ? 'text-rose-300'
                                : message.prediction.risk_score >= 5
                                  ? 'text-amber-300'
                                  : 'text-emerald-300'
                            }
                          >
                            {message.prediction.risk_score}/10
                          </span>
                        </p>
                        <p>
                          <span className='text-slate-400'>
                            {t('chatbot.prediction.transformersNeeded')}:
                          </span>{' '}
                          {message.prediction.transformers_needed}
                        </p>
                      </div>
                    )}
                    {message.role === 'assistant' &&
                      message.futureState?.district_predictions?.length > 0 && (
                        <div className='mt-3 rounded-xl border border-cyan-500/30 bg-slate-900/80 p-3 text-xs text-slate-200'>
                          <p className='mb-2 text-[11px] uppercase tracking-[0.2em] text-cyan-300'>
                            Future Mode Report •{' '}
                            {message.futureState.target_date}
                          </p>
                          <div className='rounded-lg border border-slate-700/80 bg-slate-800/50 p-2'>
                            <p className='text-[11px] text-slate-300'>
                              Suggested TP markers:{' '}
                              <span className='font-semibold text-slate-100'>
                                {message.futureState.suggested_tps?.length || 0}
                              </span>
                            </p>
                          </div>

                          <div className='mt-2 rounded-lg border border-slate-700/80 bg-slate-800/50 p-2'>
                            <p className='text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-300'>
                              Top Critical Districts
                            </p>
                            <div className='mt-1 space-y-1 text-[11px] text-slate-200'>
                              {getFutureCriticalDistricts(
                                message.futureState
                              ).map((item) => (
                                <p
                                  key={`${message.id}-critical-${item.district}`}
                                >
                                  {item.district}:{' '}
                                  {(item.load_percentage ?? 0).toFixed(1)}% • TP{' '}
                                  {item.transformers_needed ?? 0}
                                </p>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}
                    {message.role === 'assistant' &&
                      message.sources?.length > 0 && (
                        <div className='mt-2 flex flex-wrap gap-1.5'>
                          {message.sources.map((source) => (
                            <a
                              key={source.id}
                              href={source.url || '#'}
                              target='_blank'
                              rel='noreferrer'
                              className='rounded-full border border-slate-700 bg-slate-800 px-2 py-0.5 text-[11px] text-cyan-200 transition hover:border-cyan-400'
                            >
                              {source.label}
                            </a>
                          ))}
                        </div>
                      )}
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className='flex justify-start'>
                  <TypingDots label={t('chatbot.typing')} />
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <form
              onSubmit={onSubmit}
              className='border-t border-slate-700 p-3'
            >
              <div className='flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900/90 px-2 py-2'>
                <input
                  type='text'
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder={t('chatbot.placeholder')}
                  className='flex-1 bg-transparent px-2 text-sm text-slate-100 placeholder:text-slate-400 focus:outline-none'
                />
                <button
                  type='submit'
                  disabled={isLoading || input.trim().length === 0}
                  className='rounded-lg bg-cyan-500/20 p-2 text-cyan-200 transition hover:bg-cyan-500/30 disabled:cursor-not-allowed disabled:opacity-40'
                >
                  <Send className='h-4 w-4' />
                </button>
              </div>
            </form>
            {DEBUG_FLOW && lastTrace && (
              <div className='border-t border-slate-800 px-3 py-2 text-[11px] text-slate-400'>
                Trace: {lastTrace.requestId} | {String(lastTrace.status)} |{' '}
                {lastTrace.durationMs}ms
              </div>
            )}
          </motion.section>
        )}
      </AnimatePresence>

      <button
        type='button'
        onClick={() => setOpen((prev) => !prev)}
        className='pointer-events-auto ml-auto inline-flex h-14 w-14 items-center justify-center rounded-full border border-slate-700 bg-slate-900/95 text-cyan-200 shadow-xl backdrop-blur transition hover:border-cyan-400 hover:text-cyan-100'
        aria-label={t('chatbot.openAria')}
      >
        <MessageSquare className='h-6 w-6' />
      </button>
    </div>
  )
}

Chatbot.propTypes = {
  temperature: PropTypes.number.isRequired,
  construction: PropTypes.number.isRequired,
  selectedTransformerId: PropTypes.string,
  futureMode: PropTypes.bool,
  futureDate: PropTypes.string,
  futureSummary: PropTypes.object,
  activeSuggestedTp: PropTypes.shape({
    id: PropTypes.string,
    district: PropTypes.string,
    expected_load_kw: PropTypes.number
  })
}

Chatbot.defaultProps = {
  selectedTransformerId: null,
  futureMode: false,
  futureDate: null,
  futureSummary: null,
  activeSuggestedTp: null
}

export default Chatbot
