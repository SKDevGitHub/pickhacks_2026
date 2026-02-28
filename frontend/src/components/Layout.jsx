import { NavLink, useLocation } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/', label: 'Home' },
  { to: '/forecasts', label: 'Forecasts' },
  { to: '/scenarios', label: 'Scenarios' },
  { to: '/explorer', label: 'Explorer' },
  { to: '/about', label: 'About' },
];

const MOBILE_ICONS = {
  '/': '◉',
  '/forecasts': '◈',
  '/scenarios': '◇',
  '/explorer': '⊞',
  '/about': '⊘',
};

export default function Layout({ children }) {
  const location = useLocation();

  return (
    <div className="app-shell">
      {/* ── Desktop Navigation ── */}
      <nav className="nav-bar">
        <div className="nav-inner">
          <NavLink to="/" className="nav-brand">
            <span className="nav-brand-dot" />
            Tech Signals
          </NavLink>

          <div className="nav-links">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `nav-link${isActive ? ' active' : ''}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>

          <div className="nav-auth" />
        </div>
      </nav>

      {/* ── Page Content ── */}
      <main className="app-content fade-in" key={location.pathname}>
        {children}
      </main>

      {/* ── Mobile Navigation ── */}
      <nav className="mobile-nav">
        <div className="mobile-nav-inner">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `mobile-nav-link${isActive ? ' active' : ''}`
              }
            >
              <span className="mobile-nav-icon">
                {MOBILE_ICONS[item.to]}
              </span>
              {item.label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
