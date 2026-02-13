import PropTypes from 'prop-types';
import { createContext, useContext, useMemo, useState } from 'react';

const StressTestContext = createContext(null);

export function StressTestProvider({ children }) {
  const [temperature, setTemperature] = useState(18); // °C
  const [construction, setConstruction] = useState(0); // %

  const value = useMemo(
    () => ({
      temperature,
      construction,
      setTemperature,
      setConstruction,
    }),
    [temperature, construction]
  );

  return <StressTestContext.Provider value={value}>{children}</StressTestContext.Provider>;
}

StressTestProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

export function useStressTest() {
  const context = useContext(StressTestContext);
  if (!context) {
    throw new Error('useStressTest must be used within a StressTestProvider');
  }
  return context;
}
