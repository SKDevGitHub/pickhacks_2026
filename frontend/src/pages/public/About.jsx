import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';

/* ── Unsplash images (free, no-auth) ── */
const IMG = {
    hero: 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1920&q=80&auto=format',
    power: 'https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=800&q=80&auto=format',
    pollution: 'https://images.unsplash.com/photo-1532601224476-15c79f2f7a51?w=800&q=80&auto=format',
    water: 'https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=800&q=80&auto=format',
    tech1: 'https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&q=80&auto=format',
    tech2: 'https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=800&q=80&auto=format',
};

const PILLARS = [
    {
        key: 'power',
        title: 'Power',
        stat: 'Grid Load',
        desc: 'Demand growth, grid dependence, and concentrated load from emerging technologies.',
        img: IMG.power,
        color: 'var(--power-color)',
        bg: 'var(--power-bg)',
    },
    {
        key: 'pollution',
        title: 'Pollution',
        stat: 'Emissions',
        desc: 'Emission trajectories, toxicity profiles, and waste burden signals across the lifecycle.',
        img: IMG.pollution,
        color: 'var(--pollution-color)',
        bg: 'var(--pollution-bg)',
    },
    {
        key: 'water',
        title: 'Water',
        stat: 'Usage',
        desc: 'Consumption intensity, scarcity exposure, and contamination probability forecasts.',
        img: IMG.water,
        color: 'var(--water-color)',
        bg: 'var(--water-bg)',
    },
];

const FEATURES = [
    { icon: '◈', title: 'Forecast Engine', desc: '12–36 month outlooks for high-growth technologies where demand shifts quickly.' },
    { icon: '⊎', title: 'Explorer', desc: 'Browse all tracked technologies, compare impacts, and surface emerging patterns.' },
    { icon: '◇', title: 'Scenario Builder', desc: 'Run scale scenarios to model deployment plans before capital commitment.' },
    { icon: '◍', title: 'Learn Hub', desc: 'Deep-dive primers on each technology—significance, tradeoffs, and community action.' },
    { icon: '⊟', title: 'News & Research', desc: 'AI-curated articles on environmental externalities and technology developments.' },
    { icon: '◎', title: 'Radar Tracking', desc: 'Pin technologies to your personal radar for continuous monitoring and alerts.' },
];

const STEPS = [
    { num: '01', title: 'Explore', desc: 'Browse category-level environmental pressure across all tracked technologies.' },
    { num: '02', title: 'Inspect', desc: 'Drill into any technology for detailed driver breakdowns and forecast curves.' },
    { num: '03', title: 'Decide', desc: 'Run scenarios and compare deployment plans with confidence intervals.' },
];

export default function About() {
    const navigate = useNavigate();
    const { isAuthenticated, loginWithRedirect } = useAuth0();

    return (
        <div className="landing">

            {/* ════════ HERO ════════ */}
            <section className="landing-hero">
                <div className="landing-hero-bg">
                    <img src={IMG.hero} alt="" className="landing-hero-img" />
                    <div className="landing-hero-overlay" />
                </div>
                <div className="landing-hero-content">
                    <p className="landing-hero-eyebrow">Predictive Environmental Externality Engine</p>
                    <h1 className="landing-hero-title">
                        Understand the environmental cost<br />
                        <span className="landing-hero-accent">before you scale.</span>
                    </h1>
                    <p className="landing-hero-subtitle">
                        Chartr models Power, Pollution, and Water externalities for emerging
                        technologies—giving product, policy, and investment teams the foresight to act earlier.
                    </p>
                    <div className="landing-hero-actions">
                        <button className="landing-btn landing-btn-primary" onClick={() => navigate('/explorer')}>
                            Explore Technologies
                        </button>
                        <button className="landing-btn landing-btn-secondary" onClick={() => navigate('/learn')}>
                            Learn More
                        </button>
                    </div>
                </div>
            </section>

            {/* ════════ STATS BAR ════════ */}
            <section className="landing-stats">
                <div className="landing-stats-inner">
                    <div className="landing-stat">
                        <span className="landing-stat-number">6</span>
                        <span className="landing-stat-label">Technologies Tracked</span>
                    </div>
                    <div className="landing-stat-divider" />
                    <div className="landing-stat">
                        <span className="landing-stat-number">3</span>
                        <span className="landing-stat-label">Environmental Dimensions</span>
                    </div>
                    <div className="landing-stat-divider" />
                    <div className="landing-stat">
                        <span className="landing-stat-number">∞</span>
                        <span className="landing-stat-label">Scenario Simulations</span>
                    </div>
                </div>
            </section>

            {/* ════════ THREE PILLARS ════════ */}
            <section className="landing-section">
                <div className="landing-section-header">
                    <p className="landing-section-eyebrow">Environmental Dimensions</p>
                    <h2 className="landing-section-title">Three lenses. One decision.</h2>
                    <p className="landing-section-subtitle">
                        Every technology is evaluated across three environmental externality dimensions
                        to provide a complete environmental picture.
                    </p>
                </div>
                <div className="landing-pillars">
                    {PILLARS.map((p) => (
                        <article key={p.key} className={`landing-pillar landing-pillar--${p.key}`}>
                            <div className="landing-pillar-img-wrap">
                                <img src={p.img} alt={p.title} className="landing-pillar-img" />
                                <div className="landing-pillar-img-overlay" style={{ background: `linear-gradient(180deg, transparent 20%, ${p.bg} 100%)` }} />
                            </div>
                            <div className="landing-pillar-body">
                                <div className="landing-pillar-badge" style={{ color: p.color, background: p.bg }}>{p.stat}</div>
                                <h3 className="landing-pillar-title" style={{ color: p.color }}>{p.title}</h3>
                                <p className="landing-pillar-desc">{p.desc}</p>
                            </div>
                        </article>
                    ))}
                </div>
            </section>

            {/* ════════ FEATURES GRID ════════ */}
            <section className="landing-section landing-section--dark">
                <div className="landing-section-header">
                    <p className="landing-section-eyebrow">Platform</p>
                    <h2 className="landing-section-title">Everything you need to evaluate tech impact.</h2>
                </div>
                <div className="landing-features">
                    {FEATURES.map((f, i) => (
                        <article key={i} className="landing-feature">
                            <span className="landing-feature-icon">{f.icon}</span>
                            <h3 className="landing-feature-title">{f.title}</h3>
                            <p className="landing-feature-desc">{f.desc}</p>
                        </article>
                    ))}
                </div>
            </section>

            {/* ════════ HOW IT WORKS ════════ */}
            <section className="landing-section">
                <div className="landing-section-header">
                    <p className="landing-section-eyebrow">Workflow</p>
                    <h2 className="landing-section-title">Three steps to better decisions.</h2>
                </div>
                <div className="landing-steps">
                    {STEPS.map((s) => (
                        <div key={s.num} className="landing-step">
                            <span className="landing-step-num">{s.num}</span>
                            <h3 className="landing-step-title">{s.title}</h3>
                            <p className="landing-step-desc">{s.desc}</p>
                        </div>
                    ))}
                    <div className="landing-steps-line" aria-hidden="true" />
                </div>
            </section>

            {/* ════════ SHOWCASE BANNER ════════ */}
            <section className="landing-showcase">
                <div className="landing-showcase-inner">
                    <div className="landing-showcase-text">
                        <p className="landing-section-eyebrow">Built for Impact</p>
                        <h2 className="landing-showcase-title">
                            From sustainability analysts to infrastructure planners—make evidence-based
                            technology decisions.
                        </h2>
                        <p className="landing-showcase-desc">
                            Whether you're evaluating data center expansion, autonomous vehicle fleets, or
                            semiconductor fabrication plants, Chartr surfaces the environmental tradeoffs
                            that matter most.
                        </p>
                        {!isAuthenticated && (
                            <button className="landing-btn landing-btn-primary" onClick={() => loginWithRedirect()}>
                                Get Started — Free
                            </button>
                        )}
                    </div>
                    <div className="landing-showcase-img-wrap">
                        <img src={IMG.tech2} alt="Data center infrastructure" className="landing-showcase-img" />
                    </div>
                </div>
            </section>

            {/* ════════ CTA ════════ */}
            <section className="landing-cta">
                <h2 className="landing-cta-title">Ready to see the full picture?</h2>
                <p className="landing-cta-desc">
                    Explore environmental forecasts for emerging technologies today.
                </p>
                <div className="landing-hero-actions">
                    <button className="landing-btn landing-btn-primary" onClick={() => navigate('/explorer')}>
                        Open Explorer
                    </button>
                    <button className="landing-btn landing-btn-secondary" onClick={() => navigate('/news')}>
                        Read Latest News
                    </button>
                </div>
            </section>

            {/* ════════ FOOTER NOTE ════════ */}
            <footer className="landing-footer">
                <p>
                    Forecasts are model-derived and directional. Use these insights as a
                    decision-support layer alongside domain and regional expertise.
                </p>
            </footer>
        </div>
    );
}
