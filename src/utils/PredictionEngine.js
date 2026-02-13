const CURRENT_YEAR = new Date().getFullYear();

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

export function calculateProjectedLoad(station, { temperature, construction }) {
  const latestLoad = station.history?.at(-1)?.load ?? station.load_weight ?? 60;
  const temperatureFactor = temperature <= 0 ? 1 + Math.abs(temperature) / 60 : 1 + temperature / 90;
  const constructionFactor = 1 + construction / 100;
  const demographicFactor = station.demographic_growth ?? 1;

  const projectedPercent = clamp(
    Number((latestLoad * temperatureFactor * constructionFactor * demographicFactor).toFixed(1)),
    0,
    150
  );

  const projectedKva = (projectedPercent / 100) * station.capacity_kva;
  const isCritical = projectedPercent >= 95;
  const riskLabel = isCritical ? 'Critical' : projectedPercent >= 80 ? 'Watch' : 'Stable';
  const markerScale = clamp(0.85 + projectedPercent / 180, 0.9, 1.4);

  const replacementRecommended =
    (CURRENT_YEAR - (station.installDate || CURRENT_YEAR) > 25 && projectedPercent > 85) ||
    (station.maintenance?.repairs ?? 0) >= 4;

  return {
    projectedPercent,
    projectedKva: Number(projectedKva.toFixed(1)),
    isCritical,
    riskLabel,
    replacementRecommended,
    markerScale,
  };
}
