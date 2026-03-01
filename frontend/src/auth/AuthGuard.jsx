import { useAuth0 } from '@auth0/auth0-react';
import NotFound from '../pages/public/NotFound';

export default function AuthGuard({ children }) {
  const { isLoading, isAuthenticated } = useAuth0();

  if (isLoading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--bg-primary)',
          color: 'var(--text-tertiary)',
          fontSize: '0.875rem',
          letterSpacing: '0.04em',
        }}
      >
        <span
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: 'var(--accent-green)',
              animation: 'pulse 1.4s ease-in-out infinite',
              display: 'inline-block',
            }}
          />
          Initialising
        </span>
        <style>{`
          @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.25; }
          }
        `}</style>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <NotFound />;
  }

  return children;
}
