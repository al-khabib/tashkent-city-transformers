import PropTypes from 'prop-types'
import DatePicker from 'react-datepicker'
import { CalendarClock, Clock3 } from 'lucide-react'
import { addMonths, addYears, format } from 'date-fns'

function TimeControlPanel({
  futureMode,
  onFutureModeChange,
  futureDate,
  onFutureDateChange,
  loading
}) {
  const applyQuickDate = offset => {
    const now = new Date()
    const nextDate =
      offset.type === 'months'
        ? addMonths(now, offset.value)
        : addYears(now, offset.value)
    if (!futureMode) {
      onFutureModeChange(true)
    }
    onFutureDateChange(nextDate)
  }

  return (
    <div className='pointer-events-auto absolute right-4 top-4 z-[1000] w-[320px] rounded-2xl border border-slate-700/80 bg-slate-900/50 p-4 shadow-2xl backdrop-blur-xl'>
      <div className='flex items-center justify-between'>
        <div className='flex items-center gap-2 text-slate-100'>
          <Clock3 className='h-4 w-4 text-cyan-300' />
          <p className='text-sm font-semibold'>Time Control</p>
        </div>
        <div className='inline-flex items-center gap-2'>
          <span className='text-xs text-slate-300'>Future</span>
          <button
            type='button'
            onClick={() => onFutureModeChange(!futureMode)}
            aria-pressed={futureMode}
            className={`relative h-6 w-11 rounded-full transition ${
              futureMode ? 'bg-cyan-500/70' : 'bg-slate-700'
            }`}
          >
            <span
              style={{ marginLeft: '-1.2rem' }}
              className={`absolute top-1 h-4 w-4 rounded-full bg-white transition-transform duration-200 ${
                futureMode ? 'translate-x-0' : 'translate-x-6'
              }`}
            />
          </button>
          <span className='text-xs text-cyan-200'>Current</span>
        </div>
      </div>

      <div className='mt-3'>
        <p className='mb-2 text-xs text-slate-400'>Target Date</p>
        <div className='flex items-center gap-2'>
          <CalendarClock className='h-4 w-4 text-cyan-300' />
          <DatePicker
            selected={futureDate}
            onChange={onFutureDateChange}
            disabled={!futureMode}
            minDate={new Date()}
            dateFormat='yyyy-MM-dd'
            className='w-full rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400 disabled:cursor-not-allowed disabled:opacity-60'
            placeholderText='Select future date'
          />
        </div>
      </div>

      <div className='mt-3 text-xs text-slate-400'>
        {futureMode ? (
          loading ? (
            <span className='text-cyan-300'>
              Running Future Mode prediction...
            </span>
          ) : (
            <span>
              Future date:{' '}
              {futureDate ? format(futureDate, 'yyyy-MM-dd') : 'not selected'}
            </span>
          )
        ) : (
          <span>Showing current transformer state.</span>
        )}
      </div>

      {futureMode && (
        <div className='mt-3 border-t border-slate-700/70 pt-3'>
          <p className='mb-2 text-[11px] uppercase tracking-[0.2em] text-slate-400'>
            Quick Future Dates
          </p>
          <div className='grid grid-cols-2 gap-2'>
            <button
              type='button'
              onClick={() => applyQuickDate({ type: 'months', value: 3 })}
              className='rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 text-xs text-slate-100 transition hover:border-cyan-400'
            >
              +3 Months
            </button>
            <button
              type='button'
              onClick={() => applyQuickDate({ type: 'months', value: 6 })}
              className='rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 text-xs text-slate-100 transition hover:border-cyan-400'
            >
              +6 Months
            </button>
            <button
              type='button'
              onClick={() => applyQuickDate({ type: 'years', value: 1 })}
              className='rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 text-xs text-slate-100 transition hover:border-cyan-400'
            >
              +1 Year
            </button>
            <button
              type='button'
              onClick={() => applyQuickDate({ type: 'years', value: 3 })}
              className='rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 text-xs text-slate-100 transition hover:border-cyan-400'
            >
              +3 Years
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

TimeControlPanel.propTypes = {
  futureMode: PropTypes.bool.isRequired,
  onFutureModeChange: PropTypes.func.isRequired,
  futureDate: PropTypes.instanceOf(Date),
  onFutureDateChange: PropTypes.func.isRequired,
  loading: PropTypes.bool.isRequired
}

TimeControlPanel.defaultProps = {
  futureDate: null
}

export default TimeControlPanel
