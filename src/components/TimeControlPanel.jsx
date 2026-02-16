import PropTypes from 'prop-types';
import DatePicker from 'react-datepicker';
import { CalendarClock, Clock3 } from 'lucide-react';
import { format } from 'date-fns';

function TimeControlPanel({ futureMode, onFutureModeChange, futureDate, onFutureDateChange, loading }) {
  return (
    <div className="pointer-events-auto absolute right-4 top-4 z-[1000] w-[320px] rounded-2xl border border-slate-700/80 bg-slate-900/50 p-4 shadow-2xl backdrop-blur-xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-slate-100">
          <Clock3 className="h-4 w-4 text-cyan-300" />
          <p className="text-sm font-semibold">Time Control</p>
        </div>
        <label className="inline-flex cursor-pointer items-center gap-2">
          <span className="text-xs text-slate-300">Current</span>
          <input
            type="checkbox"
            checked={futureMode}
            onChange={(event) => onFutureModeChange(event.target.checked)}
            className="peer sr-only"
          />
          <span className="relative h-6 w-11 rounded-full bg-slate-700 transition peer-checked:bg-cyan-500/70">
            <span className="absolute left-1 top-1 h-4 w-4 rounded-full bg-white transition peer-checked:translate-x-5" />
          </span>
          <span className="text-xs text-cyan-200">Future</span>
        </label>
      </div>

      <div className="mt-3">
        <p className="mb-2 text-xs text-slate-400">Target Date</p>
        <div className="flex items-center gap-2">
          <CalendarClock className="h-4 w-4 text-cyan-300" />
          <DatePicker
            selected={futureDate}
            onChange={onFutureDateChange}
            disabled={!futureMode}
            minDate={new Date()}
            dateFormat="yyyy-MM-dd"
            className="w-full rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400 disabled:cursor-not-allowed disabled:opacity-60"
            placeholderText="Select future date"
          />
        </div>
      </div>

      <div className="mt-3 text-xs text-slate-400">
        {futureMode ? (
          loading ? (
            <span className="text-cyan-300">Running Future Mode prediction...</span>
          ) : (
            <span>Future date: {futureDate ? format(futureDate, 'yyyy-MM-dd') : 'not selected'}</span>
          )
        ) : (
          <span>Showing current transformer state.</span>
        )}
      </div>
    </div>
  );
}

TimeControlPanel.propTypes = {
  futureMode: PropTypes.bool.isRequired,
  onFutureModeChange: PropTypes.func.isRequired,
  futureDate: PropTypes.instanceOf(Date),
  onFutureDateChange: PropTypes.func.isRequired,
  loading: PropTypes.bool.isRequired,
};

TimeControlPanel.defaultProps = {
  futureDate: null,
};

export default TimeControlPanel;
