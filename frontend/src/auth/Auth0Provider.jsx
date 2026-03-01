import { Auth0Provider } from '@auth0/auth0-react';
import { useNavigate } from 'react-router-dom';

const AUTH_RETURN_TO_KEY = 'techsignals:returnTo';

function normalizeReturnTo(value) {
  const raw = String(value || '').trim();
  if (!raw) return '/';
  if (raw.startsWith('/')) return raw;

  try {
    const asUrl = new URL(raw, window.location.origin);
    if (asUrl.origin === window.location.origin) {
      return `${asUrl.pathname}${asUrl.search}${asUrl.hash}`;
    }
  } catch {
    // ignore malformed return path
  }

  return '/';
}

export default function Auth0ProviderWithNavigate({ children }) {
  const navigate = useNavigate();
  const domain = import.meta.env.VITE_AUTH0_DOMAIN;
  const clientId = import.meta.env.VITE_AUTH0_CLIENT_ID;

  function onRedirectCallback(appState) {
    let fallbackReturnTo = '/';
    try {
      const stored = sessionStorage.getItem(AUTH_RETURN_TO_KEY);
      if (stored) {
        fallbackReturnTo = stored;
        sessionStorage.removeItem(AUTH_RETURN_TO_KEY);
      }
    } catch {
      // ignore storage access errors
    }

    const target = normalizeReturnTo(appState?.returnTo || fallbackReturnTo || '/');
    navigate(target, { replace: true });
  }

  return (
    <Auth0Provider
      domain={domain}
      clientId={clientId}
      authorizationParams={{
        redirect_uri: window.location.origin,
        scope: 'openid profile email',
      }}
      onRedirectCallback={onRedirectCallback}
      cacheLocation="localstorage"
      useRefreshTokens={false}
    >
      {children}
    </Auth0Provider>
  );
}
