import { Routes, Route } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import AuthGuard from './auth/AuthGuard';
import Layout from './components/Layout';
import Forecasts from './pages/protected/Forecasts';
import TechnologyDetail from './pages/protected/TechnologyDetail';
import Scenarios from './pages/protected/Scenarios';
import Explorer from './pages/public/Explorer';
import Learn from './pages/public/Learn';
import Radar from './pages/protected/Radar';
import News from './pages/public/News';
import NewsArticle from './pages/public/NewsArticle';
import GenerateAdmin from './pages/protected/GenerateAdmin';
import About from './pages/public/About';
import AskGemini from './pages/protected/AskGemini';
import GenerateAuthBridge from './pages/public/GenerateAuthBridge';
import NotFound from './pages/public/NotFound';
import { canAccessGenerate, isEduEmail } from './auth/authz';

function Protected({ children }) {
  return <AuthGuard>{children}</AuthGuard>;
}

function EduProtected({ children }) {
  const { isLoading, isAuthenticated, user } = useAuth0();

  if (isLoading) {
    return <div className="page-subtitle">Loading…</div>;
  }

  if (!isAuthenticated) {
    return <NotFound />;
  }

  if (!isEduEmail(user)) {
    return <NotFound />;
  }

  return <>{children}</>;
}

function GenerateProtected({ children }) {
  const { isLoading, isAuthenticated, user } = useAuth0();

  if (isLoading) {
    return <div className="page-subtitle">Loading…</div>;
  }

  if (!isAuthenticated) {
    return <NotFound />;
  }

  if (!canAccessGenerate(user)) {
    return <NotFound />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<About />} />
        <Route path="/forecasts" element={<EduProtected><Forecasts /></EduProtected>} />
        <Route path="/forecasts/:techId" element={<EduProtected><TechnologyDetail /></EduProtected>} />
        <Route path="/scenarios" element={<EduProtected><Scenarios /></EduProtected>} />
        <Route path="/explorer" element={<Explorer />} />
        <Route path="/learn" element={<Learn />} />
        <Route path="/radar" element={<Protected><Radar /></Protected>} />
        <Route path="/ask" element={<EduProtected><AskGemini /></EduProtected>} />
        <Route path="/news" element={<News />} />
        <Route path="/news/:articleId" element={<NewsArticle />} />
        <Route path="/generate-auth" element={<GenerateAuthBridge />} />
        <Route path="/generate" element={<Protected><GenerateProtected><GenerateAdmin /></GenerateProtected></Protected>} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  );
}
