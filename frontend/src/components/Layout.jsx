import { NavLink, useLocation } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { canAccessGenerate, isEduEmail } from '../auth/authz';

const NAV_ITEMS = [
    { to: '/', label: 'Home' },
    { to: '/learn', label: 'Learn' },
    { to: '/explorer', label: 'Explorer' },
    { to: '/radar', label: 'Radar' },
    { to: '/forecasts', label: 'Forecasts' },
    { to: '/scenarios', label: 'Scenarios' },
    { to: '/ask', label: 'Chartr AI' },
    { to: '/news', label: 'News' },
    { to: '/generate', label: 'Generate' },
];

const MOBILE_ICONS = {
    '/': '◉',
    '/forecasts': '◈',
    '/scenarios': '◇',
    '/explorer': '⊞',
    '/learn': '◍',
    '/radar': '◎',
    '/news': '⊟',
    '/ask': '✦',
    '/generate': '⊕',
};

export default function Layout({ children }) {
    const { isAuthenticated, user, loginWithRedirect, logout } = useAuth0();
    const location = useLocation();
    const generateAllowed = isAuthenticated && canAccessGenerate(user);
    const eduOnlyTabs = new Set(['/forecasts', '/scenarios', '/ask']);
    const authOnlyTabs = new Set(['/radar']);
    const eduAllowed = isAuthenticated && isEduEmail(user);
    const visibleNavItems = NAV_ITEMS.filter((item) => {
        if (eduOnlyTabs.has(item.to) && !eduAllowed) return false;
        if (authOnlyTabs.has(item.to) && !isAuthenticated) return false;
        if (item.to === '/generate' && !generateAllowed) return false;
        return true;
    });

    return (
        <div className="app-shell">
            {/* ── Desktop Navigation ── */}
            <nav className="nav-bar">
                <div className="nav-inner">
                    <NavLink to="/" className="nav-brand">
                        <span className="nav-brand-dot" />
                        Chartr
                    </NavLink>

                    <div className="nav-links">
                        {visibleNavItems.map((item) => (
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

                    <div className="nav-auth">
                        {isAuthenticated ? (
                            <div className="nav-user">
                                {user?.picture && (
                                    <img
                                        src={user.picture}
                                        alt=""
                                        className="nav-avatar"
                                    />
                                )}
                                <span className="nav-user-name">{user?.name}</span>
                                <button
                                    className="btn-auth btn-logout"
                                    onClick={() =>
                                        logout({ logoutParams: { returnTo: window.location.origin } })
                                    }
                                >
                                    Log out
                                </button>
                            </div>
                        ) : (
                            <button
                                className="btn-auth btn-login"
                                onClick={() =>
                                    loginWithRedirect({
                                        appState: {
                                            returnTo: `${location.pathname}${location.search}${location.hash}`,
                                        },
                                    })
                                }
                            >
                                Sign in
                            </button>
                        )}
                    </div>
                </div>
            </nav>

            {/* ── Page Content ── */}
            <main className="app-content fade-in" key={location.pathname}>
                {children}
            </main>

            {/* ── Mobile Navigation ── */}
            <nav className="mobile-nav">
                <div className="mobile-nav-inner">
                    {visibleNavItems.map((item) => (
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
