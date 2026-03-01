/**
 * Static mock data supplementing the backend API for homepage display.
 * Momentum scores + AI insights are homepage-specific signals.
 */

export const MOMENTUM_SUPPLEMENTS = {
  'llm-training-clusters':   { momentum: 94, delta: +6.2, insight: 'Projected data center expansion may increase regional water stress in the U.S. Southwest within 18 months.' },
  'gpu-data-centers':        { momentum: 88, delta: +4.8, insight: 'Grid carbon exposure is rising as GPU cluster density outpaces renewable procurement in key regions.' },
  'edge-ai-processors':      { momentum: 71, delta: +3.1, insight: 'Distributed edge deployment is producing a long-tail waste burden that aggregate metrics currently undercount.' },
  'lithium-ion-gigafactories':{ momentum: 82, delta: +2.4, insight: 'Lithium brine extraction rates in South America are approaching regulatory thresholds in three basins.' },
  'solid-state-batteries':   { momentum: 58, delta: +5.6, insight: 'Solid electrolyte supply chains remain constrained; scaled production could shift toxicity profiles significantly.' },
  'grid-scale-storage':      { momentum: 67, delta: +1.9, insight: 'Flow battery deployments are reducing peaker plant reliance, with measurable grid-carbon co-benefits.' },
  'green-hydrogen-electrolysis':{ momentum: 75, delta: +7.2, insight: 'Electrolysis scaling in arid regions risks compounding existing water scarcity without desalination pairing.' },
  'blue-hydrogen-ccs':       { momentum: 49, delta: -1.4, insight: 'Methane leakage rates in blue hydrogen supply chains continue to challenge lifecycle emission claims.' },
  'semiconductor-fabs':      { momentum: 79, delta: +3.6, insight: 'Ultrapure water demand at advanced nodes is on course to exceed sustainable basin extraction limits by 2027.' },
  '3d-printing-scale':       { momentum: 53, delta: +2.1, insight: 'Polymer particulate emissions from industrial-scale additive manufacturing require updated occupational standards.' },
  'carbon-fiber-production':  { momentum: 61, delta: +1.8, insight: 'Acrylonitrile precursor production is the dominant emission driver; bio-based substitutes remain unscaled.' },
  'superconducting-quantum':  { momentum: 44, delta: +2.9, insight: 'Helium-3 cooling demand for sub-Kelvin processors is creating supply chain fragility at projected qubit counts.' },
  'photonic-quantum':         { momentum: 38, delta: +3.4, insight: 'Room-temperature photonic approaches offer lower cooling overhead but face fabrication-yield environmental trade-offs.' },
};

export const TRENDING_SIGNALS = [
  { name: 'LLM Training Clusters', delta: +6.2, id: 'llm-training-clusters' },
  { name: 'Green H₂ Electrolysis', delta: +7.2, id: 'green-hydrogen-electrolysis' },
  { name: 'Semiconductor Fabs',    delta: +3.6, id: 'semiconductor-fabs' },
  { name: 'Solid-State Batteries', delta: +5.6, id: 'solid-state-batteries' },
  { name: 'GPU Data Centers',      delta: +4.8, id: 'gpu-data-centers' },
  { name: 'Grid-Scale Storage',    delta: +1.9, id: 'grid-scale-storage' },
];

export const LATEST_NEWS = [
  { headline: 'IEA warns AI data center power demand could double by 2026', source: 'IEA', date: 'Feb 26', tag: 'Power' },
  { headline: 'New TSMC fab in Arizona draws scrutiny over groundwater use', source: 'Reuters', date: 'Feb 25', tag: 'Water' },
  { headline: 'EU mandates lifecycle emission disclosures for battery manufacturers', source: 'Euractiv', date: 'Feb 24', tag: 'Pollution' },
  { headline: 'Hydrogen council revises blue hydrogen emission factors downward', source: 'Bloomberg', date: 'Feb 23', tag: 'Pollution' },
  { headline: 'California grid operator flags AI workload clustering risk', source: 'CAISO', date: 'Feb 22', tag: 'Power' },
  { headline: 'Solid-state battery pilot yields lower cobalt intensity than Li-ion', source: 'Nature Energy', date: 'Feb 21', tag: 'Pollution' },
];
