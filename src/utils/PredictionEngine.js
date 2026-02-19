const CURRENT_YEAR = new Date().getFullYear();

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

export function calculateProjectedLoad(station, { temperature, construction }) {
  // For current view, use the backend-provided status and load_weight directly
  const currentLoad = station.load_weight ?? 60; // This is already a utilization percentage from backend
  
  // For projections, apply growth factors
  const temperatureFactor = temperature <= 0 ? 1 + Math.abs(temperature) / 60 : 1 + temperature / 90;
  const constructionFactor = 1 + construction / 100;
  const demographicFactor = station.demographic_growth ?? 1;

  // Projected percent applies growth factors to current load
  const projectedPercent = clamp(
    Number((currentLoad * temperatureFactor * constructionFactor * demographicFactor).toFixed(1)),
    0,
    150
  );

  const projectedKva = (currentLoad / 100) * station.capacity_kva;
  
  // Determine status based on projected load (temperature/construction adjusted)
  // This allows status to change when conditions change
  let status, riskLabel, isCritical;
  
  if (projectedPercent < 50) {
    status = 'green';
    riskLabel = 'Stable';
    isCritical = false;
  } else if (projectedPercent < 80) {
    status = 'yellow';
    riskLabel = 'Stable';
    isCritical = false;
  } else {
    status = 'red';
    riskLabel = 'Critical';
    isCritical = true;
  }
  
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
    status,  // Include calculated status
  };
}
