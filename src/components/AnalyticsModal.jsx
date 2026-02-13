import PropTypes from 'prop-types';
import { Fragment, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const rand = (min, max) => Math.random() * (max - min) + min;

const RANGE_OPTIONS = ['today', 'week', 'month', 'year', '5year'];

const buildForecastData = (station, temperature, construction) => {
  if (!station) return [];
  const sourceHistory = station.history || [];
  const baseLoad = sourceHistory.at(-1)?.load ?? station.projectedPercent;
  const months = [];
  let currentValue = baseLoad;
  const trendFactor = station.demographic_growth * (1 + construction / 120);
  const temperatureImpact = temperature <= 0 ? 1 + Math.abs(temperature) / 70 : 1 + temperature / 100;
  for (let i = 1; i <= 24; i += 1) {
    const seasonalBoost = ((i % 12) + 1) === 1 || ((i % 12) + 1) === 7 ? 1.08 : 1.02;
    currentValue = clamp(currentValue * trendFactor * seasonalBoost * temperatureImpact, 0, 150);
    months.push({
      date: `+${i}m`,
      load: Number(currentValue.toFixed(1)),
      type: 'forecast',
    });
  }
  return months;
};

const createHourlySeries = (history, station) => {
  const base = history.at(-1)?.load ?? station?.projectedPercent ?? 60;
  return Array.from({ length: 24 }, (_, index) => {
    const swing = Math.sin(((index + 6) / 24) * Math.PI * 2) * 6;
    const noise = rand(-2.5, 2.5);
    const load = clamp(base + swing + noise, 25, 140);
    return {
      date: `${String(index).padStart(2, '0')}:00`,
      load: Number(load.toFixed(1)),
      type: 'history',
    };
  });
};

const createRollingDailySeries = (history, station, days) => {
  const last = history.at(-1)?.load ?? station?.projectedPercent ?? 60;
  const prev = history.at(-2)?.load ?? last * 0.92;
  const slope = (last - prev) / days;
  const today = new Date();
  return Array.from({ length: days }, (_, index) => {
    const date = new Date(today);
    date.setDate(today.getDate() - (days - index));
    const variation = Math.sin(((index + rand(-0.5, 0.5)) / days) * Math.PI * 2) * 5;
    const seasonalSpike =
      (date.getMonth() === 0 ? rand(6, 12) : 0) + (date.getMonth() === 6 ? rand(4, 9) : 0);
    const load = clamp(prev + slope * index + variation + seasonalSpike + rand(-3, 3), 25, 140);
    return {
      date: date.toISOString().slice(5, 10),
      load: Number(load.toFixed(1)),
      type: 'history',
    };
  });
};

const createMonthlySeries = (history) => history.map((point) => ({ ...point, type: 'history' }));

const createYearSeries = (history) =>
  history.slice(-12).map((point) => ({ ...point, type: 'history' }));

const createYearlyBuckets = (history) => {
  const bucket = history.reduce((acc, point) => {
    const year = point.date.slice(0, 4);
    if (!acc[year]) acc[year] = [];
    acc[year].push(point.load);
    return acc;
  }, {});
  return Object.entries(bucket).map(([year, loads]) => ({
    date: year,
    load: Number((loads.reduce((sum, value) => sum + value, 0) / loads.length).toFixed(1)),
    type: 'history',
  }));
};

const createFiveYearSeries = (history) => createYearlyBuckets(history).slice(-5);

const RANGE_BUILDERS = {
  today: (history, station) => createHourlySeries(history, station),
  week: (history, station) => createRollingDailySeries(history, station, 7),
  month: (history, station) => createRollingDailySeries(history, station, 30),
  year: (history) => createYearSeries(history),
  '5year': (history) => createFiveYearSeries(history),
};

function AnalyticsModal({ open, station, onClose, temperature, construction }) {
  const { t } = useTranslation();
  const historySeries = station?.history ?? [];
  const [range, setRange] = useState('month');

  useEffect(() => {
    setRange('month');
  }, [station?.id]);

  const displaySeries = useMemo(() => {
    if (!historySeries.length) return [];
    const builder = RANGE_BUILDERS[range] || RANGE_BUILDERS.month;
    return builder(historySeries, station);
  }, [historySeries, range, station]);

  const forecastSeries = useMemo(
    () => buildForecastData(station, temperature, construction),
    [station, temperature, construction]
  );

  const showForecast = !['today', 'week'].includes(range);

  const outageDates = useMemo(
    () => new Set(station?.outages?.map((outage) => outage.date) || []),
    [station?.outages]
  );

  const annotatedSeries = useMemo(
    () =>
      displaySeries.map((point) => {
        let seasonalTag = null;
        if (typeof point.date === 'string' && point.date.includes('-')) {
          const month = point.date.split('-')[1];
          if (month === '01') seasonalTag = 'winter';
          if (month === '07') seasonalTag = 'summer';
        }
        const outageTag = typeof point.date === 'string' && outageDates.has(point.date);
        return { ...point, seasonalTag, outageTag };
      }),
    [displaySeries, outageDates]
  );

  const chartData = useMemo(() => {
    if (!station) return [];
    if (!showForecast) {
      return annotatedSeries;
    }
    return [...annotatedSeries, ...forecastSeries];
  }, [annotatedSeries, forecastSeries, showForecast, station]);

  const riskBadge = station?.replacementRecommended ? 'Replacement Recommended' : null;
  const riskLabel = t(`analytics.risk.${(station?.riskLabel || '').toLowerCase()}`, {
    defaultValue: station?.riskLabel || '',
  });

  const seasonalInsights = useMemo(() => {
    if (!historySeries.length) return null;
    const winterLoads = historySeries.filter((point) => point.date.endsWith('-01')).map((point) => point.load);
    const summerLoads = historySeries.filter((point) => point.date.endsWith('-07')).map((point) => point.load);
    if (!winterLoads.length || !summerLoads.length) return null;
    const avg = (arr) => arr.reduce((sum, value) => sum + value, 0) / arr.length;
    const winterAvg = Number(avg(winterLoads).toFixed(1));
    const summerAvg = Number(avg(summerLoads).toFixed(1));
    const annualAvg = Number(avg(historySeries.map((point) => point.load)).toFixed(1));
    return {
      winterAvg,
      summerAvg,
      winterDelta: Number((winterAvg - annualAvg).toFixed(1)),
      summerDelta: Number((summerAvg - annualAvg).toFixed(1)),
    };
  }, [historySeries]);

  const shouldHighlightSeasonal = ['month', 'year'].includes(range);

  const highlightDot = (props) => {
    const { cx, cy, payload } = props;
    if (!payload) return null;
    if (payload.outageTag) {
      return (
        <g>
          <circle cx={cx} cy={cy} r={6} fill="#f43f5e" stroke="#0f172a" strokeWidth={2} />
          <line x1={cx - 3} y1={cy - 3} x2={cx + 3} y2={cy + 3} stroke="#0f172a" strokeWidth={1.2} />
          <line x1={cx - 3} y1={cy + 3} x2={cx + 3} y2={cy - 3} stroke="#0f172a" strokeWidth={1.2} />
        </g>
      );
    }
    if (!shouldHighlightSeasonal || !payload.seasonalTag) return null;
    const color = payload.seasonalTag === 'winter' ? '#38bdf8' : '#f97316';
    return <circle cx={cx} cy={cy} r={5} fill={color} stroke="#0f172a" strokeWidth={1.5} />;
  };

  return createPortal(
    <AnimatePresence>
      {open && station ? (
        <motion.div
          className="fixed inset-0 z-[2000] flex items-stretch justify-center bg-slate-950/70 backdrop-blur md:items-center md:p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="relative z-[2001] flex h-full w-full flex-col overflow-hidden border border-slate-700 bg-slate-900/90 text-slate-100 backdrop-blur md:h-auto md:max-h-[90vh] md:max-w-4xl md:rounded-3xl"
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
          >
            <button
              type="button"
              onClick={onClose}
              className="absolute right-4 top-4 z-[2100] rounded-full border border-slate-700 bg-slate-900/90 p-2 text-slate-100"
            >
              <X className="h-4 w-4" />
            </button>
            <div className="flex-1 overflow-y-auto p-5 pt-16 md:p-6 md:pt-16">
              <div className="space-y-3 pr-8">
                <p className="text-xs uppercase tracking-[0.4em] text-slate-400">{t('analytics.title')}</p>
                <h2 className="text-2xl font-semibold text-slate-100">{station.name}</h2>
                <p className="text-sm text-slate-400">
                  {station.district} • {t('analytics.installed', { year: station.installDate })}
                </p>
              </div>

              <div className="mt-6 grid gap-6 md:grid-cols-4">
                <div className="rounded-2xl border border-slate-700 bg-slate-900/90 p-4">
                  <p className="text-xs uppercase text-slate-400">{t('analytics.projectedLoad')}</p>
                  <p className="text-4xl font-semibold text-slate-100">{station.projectedPercent}%</p>
                  <p className="text-sm text-slate-400">{station.projectedKva} kVA / {station.capacity_kva} kVA</p>
                </div>
                <div className="rounded-2xl border border-slate-700 bg-slate-900/90 p-4">
                  <p className="text-xs uppercase text-slate-400">{t('analytics.riskLevel')}</p>
                  <p className="text-3xl font-semibold text-slate-100">{riskLabel}</p>
                  {riskBadge && (
                    <span className="mt-2 inline-flex items-center rounded-full border border-rose-500/40 bg-rose-500/10 px-3 py-1 text-xs font-semibold text-rose-200">
                      {t('analytics.replacementRecommended')}
                    </span>
                  )}
                </div>
                <div className="rounded-2xl border border-slate-700 bg-slate-900/90 p-4">
                  <p className="text-xs uppercase text-slate-400">{t('analytics.stressInputs')}</p>
                  <p className="text-sm text-slate-100">
                    {t('analytics.temperature')}: <span className="font-semibold">{temperature.toFixed(0)}°C</span>
                  </p>
                  <p className="text-sm text-slate-100">
                    {t('analytics.constructionSurge')}:{' '}
                    <span className="font-semibold">+{construction}%</span>
                  </p>
                  <p className="mt-2 text-xs text-slate-400">
                    {t('analytics.demographicBase')}: {(station.demographic_growth ?? 1).toFixed(2)}x
                  </p>
                </div>
                {station.maintenance && (
                  <div className="rounded-2xl border border-slate-700 bg-slate-900/90 p-4">
                    <p className="text-xs uppercase text-slate-400">{t('analytics.maintenance')}</p>
                    <p className="text-lg text-slate-100">
                      {t('analytics.repairs')}: <span className="font-semibold">{station.maintenance.repairs}</span>
                    </p>
                    <p className="text-lg text-slate-100">
                      {t('analytics.highLoadFaults')}:{' '}
                      <span className="font-semibold">{station.maintenance.highLoadFailures}</span>
                    </p>
                    <p className="mt-1 text-xs text-slate-400">
                      {t('analytics.lastRepair')}: {station.maintenance.lastRepairDate}
                    </p>
                  </div>
                )}
              </div>

              <div className="mt-6 flex flex-wrap gap-2">
                {RANGE_OPTIONS.map((option) => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => setRange(option)}
                    className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
                      range === option
                        ? 'border-sky-500 bg-sky-500/20 text-sky-100'
                        : 'border-slate-700 text-slate-400 hover:border-slate-500'
                    }`}
                  >
                    {t(`analytics.range.${option}`)}
                  </button>
                ))}
              </div>

              {seasonalInsights && (
                <div className="mt-6 grid gap-4 md:grid-cols-2">
                  <div className="rounded-2xl border border-slate-700 bg-slate-900/90 p-4">
                    <p className="text-xs uppercase text-slate-400">{t('analytics.winterPeaks')}</p>
                    <p className="text-3xl font-semibold text-cyan-300">{seasonalInsights.winterAvg}%</p>
                    <p className="text-sm text-slate-400">
                      {t('analytics.overAnnual', { value: seasonalInsights.winterDelta })}
                    </p>
                    <p className="mt-2 text-xs text-slate-400">{t('analytics.winterInsight')}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-700 bg-slate-900/90 p-4">
                    <p className="text-xs uppercase text-slate-400">{t('analytics.summerPeaks')}</p>
                    <p className="text-3xl font-semibold text-amber-300">{seasonalInsights.summerAvg}%</p>
                    <p className="text-sm text-slate-400">
                      {t('analytics.overAnnual', { value: seasonalInsights.summerDelta })}
                    </p>
                    <p className="mt-2 text-xs text-slate-400">{t('analytics.summerInsight')}</p>
                  </div>
                </div>
              )}

              {station.outages?.length > 0 && (
                <div className="mt-6 rounded-2xl border border-rose-500/40 bg-rose-500/5 p-4">
                  <p className="text-xs font-semibold uppercase text-rose-200">{t('analytics.outageTimeline')}</p>
                  <ul className="mt-3 space-y-2 text-sm text-rose-100">
                    {station.outages.slice(-4).map((outage) => (
                      <li key={`${outage.date}-${outage.duration_hours}`} className="flex items-center justify-between">
                        <div>
                          <p className="font-semibold">{outage.date}</p>
                          <p className="text-xs text-rose-200/80">{outage.cause}</p>
                        </div>
                        <span>{outage.duration_hours}h</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="mt-8 h-72 rounded-3xl border border-slate-700 bg-slate-900/90 p-4">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ left: 0, right: 0, top: 20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="historyGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.35} />
                        <stop offset="95%" stopColor="#0f172a" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(148, 163, 184, 0.15)" vertical={false} />
                    <XAxis dataKey="date" stroke="#94a3b8" minTickGap={30} />
                    <YAxis stroke="#94a3b8" domain={[0, 140]} tickFormatter={(value) => `${value}%`} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0f172a',
                        border: '1px solid rgba(148,163,184,0.3)',
                        borderRadius: '12px',
                      }}
                      formatter={(value) => [`${value}%`, t('analytics.loadAxis')]}
                    />
                    <Area
                      type="monotone"
                      dataKey="load"
                      stroke="#38bdf8"
                      fill="url(#historyGradient)"
                      strokeWidth={2}
                      isAnimationActive={false}
                      name={t('analytics.history')}
                      dot={highlightDot}
                      activeDot={{ r: 4 }}
                      data={chartData.filter((point) => point.type === 'history')}
                    />
                    {showForecast && (
                      <Line
                        type="monotone"
                        dataKey="load"
                        data={chartData.filter((point) => point.type === 'forecast')}
                        stroke="#f97316"
                        strokeDasharray="6 4"
                        strokeWidth={2.2}
                        dot={false}
                        isAnimationActive={false}
                        name={t('analytics.forecast')}
                      />
                    )}
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="border-t border-slate-700 p-4 md:hidden">
              <button
                type="button"
                onClick={onClose}
                className="w-full rounded-xl border border-slate-700 bg-slate-900/90 px-4 py-3 text-sm font-semibold text-slate-100"
              >
                {t('analytics.close')}
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : (
        <Fragment />
      )}
    </AnimatePresence>,
    document.body
  );
}

AnalyticsModal.propTypes = {
  open: PropTypes.bool.isRequired,
  station: PropTypes.shape({
    name: PropTypes.string,
    district: PropTypes.string,
    history: PropTypes.array,
    installDate: PropTypes.number,
    projectedPercent: PropTypes.number,
    projectedKva: PropTypes.number,
    capacity_kva: PropTypes.number,
    riskLabel: PropTypes.string,
    replacementRecommended: PropTypes.bool,
    demographic_growth: PropTypes.number,
    maintenance: PropTypes.shape({
      repairs: PropTypes.number,
      highLoadFailures: PropTypes.number,
      lastRepairDate: PropTypes.string,
    }),
    outages: PropTypes.arrayOf(
      PropTypes.shape({
        date: PropTypes.string.isRequired,
        duration_hours: PropTypes.number,
        cause: PropTypes.string,
      })
    ),
  }),
  onClose: PropTypes.func.isRequired,
  temperature: PropTypes.number.isRequired,
  construction: PropTypes.number.isRequired,
};

AnalyticsModal.defaultProps = {
  station: null,
};

export default AnalyticsModal;
