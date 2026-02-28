import { useAuth0 } from '@auth0/auth0-react';
import { useLocation } from 'react-router-dom';

export default function Login() {
  const { loginWithRedirect, isLoading } = useAuth0();
  const location = useLocation();

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-primary)',
        padding: 'var(--sp-6)',
      }}
    >
      {/* Brand mark */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--sp-2)',
          marginBottom: 'var(--sp-12)',
        }}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: 'var(--accent-green)',
            display: 'inline-block',
            flexShrink: 0,
          }}
        />
        <span
          style={{
            fontSize: '1rem',
            fontWeight: 600,
            letterSpacing: '-0.01em',
            color: 'var(--text-primary)',
          }}
        >
          Tech Signals
        </span>
      </div>

      {/* Login card */}
      <div
        style={{
          width: '100%',
          maxWidth: 400,
          background: 'var(--bg-card)',
          border: '1px solid var(--border-primary)',
          borderRadius: 'var(--radius-xl)',
          padding: 'var(--sp-10) var(--sp-8)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--sp-6)',
        }}
      >
        <div>
          <h1
            style={{
              fontSize: '1.375rem',
              fontWeight: 600,
              letterSpacing: '-0.02em',
              marginBottom: 'var(--sp-2)',
            }}
          >
            Sign in
          </h1>
          <p
            style={{
              fontSize: '0.875rem',
              color: 'var(--text-secondary)',
              lineHeight: 1.6,
            }}
          >
            Forecast the environmental footprint of emerging technologies before
            they scale.
          </p>
        </div>

        <hr
          style={{
            height: 1,
            background: 'var(--border-primary)',
            border: 'none',
          }}
        />

        <button
          disabled={isLoading}
          onClick={() =>
            loginWithRedirect({
              appState: {
                returnTo: `${location.pathname}${location.search}${location.hash}`,
              },
            })
          }
          style={{
            width: '100%',
            height: 44,
            background: 'rgba(255,255,255,0.07)',
            border: '1px solid var(--border-primary)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--text-primary)',
            fontSize: '0.875rem',
            fontWeight: 600,
            cursor: isLoading ? 'not-allowed' : 'pointer',
            transition: 'background 150ms ease, border-color 150ms ease',
            opacity: isLoading ? 0.5 : 1,
          }}
          onMouseEnter={(e) => {
            if (!isLoading) e.currentTarget.style.background = 'rgba(255,255,255,0.11)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.07)';
          }}
        >
          {isLoading ? 'Loading…' : 'Continue with Auth0'}
        </button>

        <p
          style={{
            fontSize: '0.6875rem',
            color: 'var(--text-tertiary)',
            textAlign: 'center',
            lineHeight: 1.5,
          }}
        >
          Access is restricted to authorized users. Forecasts are based on
          aggregated lifecycle assessment data and environmental benchmarks.
        </p>
      </div>
    </div>
  );
}
