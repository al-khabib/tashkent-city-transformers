import PropTypes from 'prop-types';

function TrendSparkline({ history, stroke = '#38bdf8' }) {
  const recent = history.slice(-12);
  const width = 160;
  const height = 40;

  if (!recent.length) {
    return (
      <div className="flex h-10 items-center justify-center text-xs text-slate-500">
        No trend data
      </div>
    );
  }

  const values = recent.map((point) => point.load);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const points = recent.map((point, index) => {
    const x = recent.length === 1 ? width / 2 : (index / (recent.length - 1)) * (width - 4) + 2;
    const y = height - 2 - ((point.load - min) / range) * (height - 4);
    return { x: Number(x.toFixed(2)), y: Number(y.toFixed(2)) };
  });
  const pathData = points
    .map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x},${point.y}`)
    .join(' ');

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="presentation">
      <defs>
        <linearGradient id="sparklineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.1" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0.25" />
        </linearGradient>
      </defs>
      <path
        d={pathData}
        fill="none"
        stroke={stroke}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {points.length > 1 && (
        <path
          d={`${pathData} L${points[points.length - 1]?.x || 0},${height} L${points[0]?.x || 0},${height} Z`}
          fill="url(#sparklineGradient)"
          opacity="0.3"
        />
      )}
    </svg>
  );
}

TrendSparkline.propTypes = {
  history: PropTypes.arrayOf(
    PropTypes.shape({
      date: PropTypes.string.isRequired,
      load: PropTypes.number.isRequired,
    })
  ).isRequired,
  stroke: PropTypes.string,
};

export default TrendSparkline;
