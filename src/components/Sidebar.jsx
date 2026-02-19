import PropTypes from 'prop-types';
import { Search, ThermometerSun, Building2, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const CURRENT_YEAR = new Date().getFullYear();
const LANGUAGE_OPTIONS = ['uz', 'ru', 'en'];

function Sidebar({
  searchTerm,
  onSearchChange,
  temperature,
  onTemperatureChange,
  construction,
  onConstructionChange,
  searchMatches,
  criticalStations,
  onSelectStation,
  redZoneActive,
  isDesktop,
  open,
  onClose,
}) {
  const { t, i18n } = useTranslation();
  const currentLanguage = LANGUAGE_OPTIONS.includes(i18n.resolvedLanguage)
    ? i18n.resolvedLanguage
    : 'en';

  const handleStationSelect = (station) => {
    onSearchChange(station.id);
    onSelectStation(station);
  };

  const panel = (
    <div className="flex h-full flex-col gap-4 bg-slate-900/90 px-5 py-5 text-slate-100 backdrop-blur-xl">
      <section className="rounded-2xl border border-slate-700 bg-slate-900/90 p-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[11px] uppercase tracking-[0.3em] text-slate-400">{t('language.label')}</p>
          <select
            value={currentLanguage}
            onChange={(event) => i18n.changeLanguage(event.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-100 focus:outline-none"
          >
            {LANGUAGE_OPTIONS.map((code) => (
              <option key={code} value={code}>
                {t(`language.${code}`)}
              </option>
            ))}
          </select>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-700 bg-slate-900/90 p-4">
        <p className="text-[11px] uppercase tracking-[0.3em] text-slate-400">{t('sidebar.searchJump')}</p>
        <label className="mt-3 flex items-center gap-3 rounded-xl border border-slate-700 bg-slate-900/90 px-3 py-2.5">
          <Search className="h-4 w-4 text-slate-400" />
          <input
            value={searchTerm}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder={t('sidebar.searchPlaceholder')}
            className="flex-1 bg-transparent text-sm text-slate-100 placeholder:text-slate-400 focus:outline-none"
          />
        </label>
        {searchTerm.trim().length > 0 && (
          <div className="mt-3 max-h-36 space-y-1 overflow-y-auto">
            {searchMatches.length > 0 ? (
              searchMatches.map((station) => (
                <button
                  key={station.id}
                  type="button"
                  onClick={() => handleStationSelect(station)}
                  className="flex w-full items-center justify-between rounded-lg border border-slate-700 bg-slate-900/90 px-3 py-2 text-left text-xs text-slate-100 transition hover:border-slate-500"
                >
                  <span>{station.id}</span>
                  <span className="text-slate-400">{station.district}</span>
                </button>
              ))
            ) : (
              <p className="text-xs text-slate-400">{t('sidebar.noMatch')}</p>
            )}
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-slate-700 bg-slate-900/90 p-4">
        <p className="text-[11px] uppercase tracking-[0.3em] text-slate-400">{t('sidebar.crisisSimulation')}</p>
        <div className="mt-4 space-y-5">
          <div>
            <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
              <span className="inline-flex items-center gap-2 text-slate-100">
                <ThermometerSun className="h-4 w-4 text-yellow-300" />
                {t('sidebar.environmentalStress')}
              </span>
              <span>{temperature.toFixed(0)} C</span>
            </div>
            <input
              type="range"
              min="-20"
              max="45"
              step="1"
              value={temperature}
              onChange={(event) => onTemperatureChange(Number(event.target.value))}
              className="w-full accent-yellow-300"
            />
          </div>
          <div>
            <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
              <span className="inline-flex items-center gap-2 text-slate-100">
                <Building2 className="h-4 w-4 text-emerald-300" />
                {t('sidebar.urbanExpansion')}
              </span>
              <span>+{construction}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="50"
              step="1"
              value={construction}
              onChange={(event) => onConstructionChange(Number(event.target.value))}
              className="w-full accent-emerald-300"
            />
          </div>
        </div>
      </section>

      <section className="flex min-h-0 flex-1 flex-col rounded-2xl border border-slate-700 bg-slate-900/90 p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-[11px] uppercase tracking-[0.3em] text-slate-400">{t('sidebar.criticalPriorities')}</p>
          <span className="text-xs text-red-300">{t('sidebar.criticalCount', { count: criticalStations.length })}</span>
        </div>
        <div className="space-y-2 overflow-y-auto">
          {criticalStations.length === 0 && <p className="text-xs text-slate-400">{t('sidebar.noCritical')}</p>}
          {criticalStations.map((station) => (
            <button
              key={station.id}
              type="button"
              onClick={() => handleStationSelect(station)}
              className={`w-full rounded-xl border border-slate-700 bg-slate-900/90 px-3 py-2 text-left text-xs text-slate-100 transition hover:border-slate-500 ${
                redZoneActive ? 'shadow-[0_0_18px_rgba(239,68,68,0.25)]' : ''
              } ${redZoneActive && station.projectedPercent > 90 ? 'animate-pulse' : ''}`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-slate-100">{station.id}</span>
                <span className="text-slate-500">|</span>
                <span className={`${
                  station.status === 'green' ? 'text-emerald-300' :
                  station.status === 'yellow' ? 'text-amber-300' :
                  station.status === 'red' ? 'text-red-300' :
                  'text-slate-300'
                }`}>{Math.round(station.projectedPercent)}%</span>
                <span className="text-slate-500">|</span>
                <span className="text-slate-400">
                  {station.installDate
                    ? t('sidebar.years', { count: CURRENT_YEAR - station.installDate })
                    : t('sidebar.na')}
                </span>
              </div>
            </button>
          ))}
        </div>
      </section>
    </div>
  );

  if (isDesktop) {
    return <aside className="hidden h-full w-[350px] flex-shrink-0 md:flex">{panel}</aside>;
  }

  return (
    <div
      className={`fixed inset-y-0 right-0 z-40 w-full max-w-sm transform bg-transparent transition-transform duration-300 ${
        open ? 'translate-x-0' : 'translate-x-full'
      }`}
    >
      <div className="absolute inset-0 bg-slate-950/40 backdrop-blur" onClick={onClose} />
      <div className="relative h-full w-full border-l border-slate-700 bg-slate-900/90 shadow-2xl shadow-slate-900/70 backdrop-blur-xl">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 z-10 rounded-full border border-slate-700 bg-slate-900/90 p-2 text-slate-100"
        >
          <X className="h-4 w-4" />
        </button>
        {panel}
      </div>
    </div>
  );
}

Sidebar.propTypes = {
  searchTerm: PropTypes.string.isRequired,
  onSearchChange: PropTypes.func.isRequired,
  temperature: PropTypes.number.isRequired,
  onTemperatureChange: PropTypes.func.isRequired,
  construction: PropTypes.number.isRequired,
  onConstructionChange: PropTypes.func.isRequired,
  searchMatches: PropTypes.arrayOf(PropTypes.object).isRequired,
  criticalStations: PropTypes.arrayOf(PropTypes.object).isRequired,
  onSelectStation: PropTypes.func.isRequired,
  redZoneActive: PropTypes.bool.isRequired,
  isDesktop: PropTypes.bool.isRequired,
  open: PropTypes.bool,
  onClose: PropTypes.func,
};

Sidebar.defaultProps = {
  open: true,
  onClose: () => {},
};

export default Sidebar;
