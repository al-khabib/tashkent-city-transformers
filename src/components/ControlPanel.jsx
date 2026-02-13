import PropTypes from 'prop-types';
import { Settings } from 'lucide-react';
import { useTranslation } from 'react-i18next';

function ControlPanel({ onToggle }) {
  const { t } = useTranslation();

  return (
    <button
      type="button"
      onClick={onToggle}
      className="fixed bottom-5 right-5 z-30 rounded-full border border-slate-700 bg-slate-900/90 p-4 text-slate-100 shadow-[0_15px_35px_rgba(15,23,42,0.7)] backdrop-blur-lg transition hover:border-slate-500 md:hidden"
      aria-label={t('controlPanel.open')}
    >
      <Settings className="h-5 w-5" />
    </button>
  );
}

ControlPanel.propTypes = {
  onToggle: PropTypes.func.isRequired,
};

export default ControlPanel;
