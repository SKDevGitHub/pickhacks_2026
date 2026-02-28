import { useMemo, useState } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { useSearchParams } from 'react-router-dom';

const AUTH_SCOPE = 'openid profile email';
const AUTH_RETURN_TO_KEY = 'techsignals:returnTo';

export default function GenerateAuthBridge() {
  const { loginWithRedirect } = useAuth0();
  const [search] = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const audience = import.meta.env.VITE_AUTH0_AUDIENCE;
  const returnTo = useMemo(() => search.get('returnTo') || '/generate', [search]);

  async function handleContinue() {
    setLoading(true);
    setError('');
    try {
      try {
        sessionStorage.setItem(AUTH_RETURN_TO_KEY, returnTo);
      } catch {
        // ignore storage access errors
      }

      await loginWithRedirect({
        authorizationParams: {
          ...(audience ? { audience } : {}),
          scope: AUTH_SCOPE,
          prompt: 'consent',
        },
        appState: { returnTo },
      });
    } catch (err) {
      setError(err?.message || 'Unable to continue authorization.');
      setLoading(false);
    }
  }

  return (
    <div className="page-shell">
      <div className="page-header">
        <h1 className="page-title">Authorize Article Tools</h1>
        <p className="page-subtitle">
          One more step is needed to grant access to article generation features.
        </p>
      </div>

      <div className="gen-panel">
        <p className="page-subtitle">
          Continue to Auth0 to complete authorization, then you’ll be returned to Generate.
        </p>

        {error && (
          <div className="gen-error">
            <strong>Error:</strong> {error}
          </div>
        )}

        <div className="gen-controls">
          <button className="btn-primary" onClick={handleContinue} disabled={loading}>
            {loading ? 'Redirecting…' : 'Continue Authorization'}
          </button>
        </div>
      </div>
    </div>
  );
}
