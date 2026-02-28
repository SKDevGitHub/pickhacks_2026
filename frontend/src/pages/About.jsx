export default function About() {
  return (
    <div className="fade-in about-content">
      <div className="page-intro">
        <h1 className="page-title">About Tech Signals</h1>
        <p className="page-subtitle">
          A Predictive Environmental Externality Engine forecasting the
          environmental consequences of emerging technology adoption before
          large-scale deployment occurs.
        </p>
      </div>

      <h2>Mission</h2>
      <p>
        Tech Signals exists to model the environmental externalities of
        technology adoption — Power, Pollution, and Water — enabling proactive
        capital allocation and policy decisions 12–36 months ahead of
        irreversible deployment commitments.
      </p>

      <h2>Three Dimensions</h2>
      <p>
        Every technology in our platform is evaluated across three parallel
        intelligence streams, presented with equal analytical weight:
      </p>
      <ul>
        <li>
          <strong style={{ color: 'var(--power-color)' }}>Power</strong> —
          Energy demand projections, grid carbon exposure index, and load
          concentration risk.
        </li>
        <li>
          <strong style={{ color: 'var(--pollution-color)' }}>Pollution</strong>{' '}
          — Lifecycle emission deltas, toxicity tier classification, and waste
          burden assessments.
        </li>
        <li>
          <strong style={{ color: 'var(--water-color)' }}>Water</strong> —
          Consumption projections (m³/yr), scarcity exposure index, and
          contamination probability.
        </li>
      </ul>

      <h2>Methodology</h2>
      <p>
        Forecasts are derived from aggregated lifecycle assessment data (ISO
        14040/44), regional grid carbon intensity datasets, water stress indices,
        and technology-specific scaling assumptions. Our models incorporate:
      </p>
      <ul>
        <li>Energy intensity benchmarks from published LCA literature</li>
        <li>
          Grid marginal emission factors calibrated to regional energy mixes
          (2025 baseline)
        </li>
        <li>
          Mining and mineral extraction intensity factors for supply chain
          assessment
        </li>
        <li>
          Cooling demand and water consumption assumptions from facility-level
          data
        </li>
        <li>
          Deployment growth rate projections from industry analyst consensus
        </li>
      </ul>

      <h2>Uncertainty & Transparency</h2>
      <p>
        All projections include uncertainty ranges visualized as translucent
        confidence bands. Forecast horizons default to 12–36 months. Model
        inputs, assumptions, and driver breakdowns are accessible on every
        technology detail page.
      </p>
      <p>
        We clearly distinguish between observed (solid lines) and projected
        (dotted lines) data throughout the platform. No single environmental
        pillar is allowed to visually dominate — Power, Pollution, and Water are
        always presented as equal, parallel analytical streams.
      </p>

      <h2>Intended Audience</h2>
      <p>
        Tech Signals is designed for environmental strategists, infrastructure
        investors, policy analysts, and technology leadership teams evaluating
        deployment decisions with material environmental consequences. The
        interface is optimized for executive presentations and board-level
        reporting.
      </p>

      <h2>Data Sources</h2>
      <ul>
        <li>IEA World Energy Outlook — grid carbon intensity baselines</li>
        <li>WRI Aqueduct — global water stress indices</li>
        <li>
          Ecoinvent / GaBi — lifecycle inventory databases
        </li>
        <li>US EPA TRI — toxics release inventory data</li>
        <li>IRENA — renewable energy capacity and projection datasets</li>
        <li>
          Industry-specific whitepapers and analyst reports for deployment
          forecasts
        </li>
      </ul>

      <hr className="divider" style={{ marginTop: 'var(--sp-12)' }} />

      <p className="microcopy" style={{ borderTop: 'none', paddingTop: 0 }}>
        Tech Signals is a research and analysis platform. Forecasts are
        model-derived projections and should not be interpreted as guaranteed
        outcomes. Always validate findings with domain-specific expertise before
        making capital or policy decisions.
      </p>
    </div>
  );
}
