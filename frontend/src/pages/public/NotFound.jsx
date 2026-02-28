import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="page-shell notfound-shell">
      <div className="notfound-card">
        <div className="notfound-code">404</div>
        <h1 className="page-title notfound-title">Page not found</h1>
        <p className="page-subtitle notfound-subtitle">
          The page you’re looking for doesn’t exist.
        </p>
        <div className="notfound-actions">
          <Link to="/" className="btn-primary notfound-home-btn">
            Return to Home
          </Link>
        </div>
      </div>
    </div>
  );
}
