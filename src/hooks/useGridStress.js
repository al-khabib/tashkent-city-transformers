import { useMemo } from 'react';
import { useStressTest } from '../context/StressTestContext.jsx';
import { calculateProjectedLoad } from '../utils/PredictionEngine.js';

export function useGridStress(stations, searchTerm) {
  const { temperature, construction, setTemperature, setConstruction } = useStressTest();

  const computedStations = useMemo(
    () =>
      stations.map((station) => {
        const projection = calculateProjectedLoad(station, { temperature, construction });
        return { ...station, ...projection };
      }),
    [stations, temperature, construction]
  );

  const searchMatches = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    if (!query) return [];
    return computedStations
      .filter(
        (station) =>
          station.id.toLowerCase().includes(query) ||
          station.district.toLowerCase().includes(query) ||
          station.name.toLowerCase().includes(query)
      )
      .slice(0, 8);
  }, [computedStations, searchTerm]);

  const filteredStations = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    if (!query) return computedStations;
    return computedStations.filter(
      (station) =>
        station.id.toLowerCase().includes(query) ||
        station.district.toLowerCase().includes(query) ||
        station.name.toLowerCase().includes(query)
    );
  }, [computedStations, searchTerm]);

  const criticalStations = useMemo(
    () =>
      computedStations
        .filter((station) => station.projectedPercent >= 90)
        .sort((a, b) => b.projectedPercent - a.projectedPercent)
        .slice(0, 5),
    [computedStations]
  );

  const redZoneActive = criticalStations.length > 0;

  return {
    stations: computedStations,
    filteredStations,
    searchMatches,
    criticalStations,
    redZoneActive,
    temperature,
    construction,
    setTemperature,
    setConstruction,
  };
}
