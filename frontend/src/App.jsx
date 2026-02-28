import { Routes, Route } from 'react-router-dom';
import AuthGuard from './components/AuthGuard';
import Layout from './components/Layout';
import Home from './pages/Home';
import Forecasts from './pages/Forecasts';
import TechnologyDetail from './pages/TechnologyDetail';
import Scenarios from './pages/Scenarios';
import Explorer from './pages/Explorer';
import About from './pages/About';

function Protected({ children }) {
  return <AuthGuard>{children}</AuthGuard>;
}

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/about" element={<About />} />
        <Route path="/forecasts" element={<Protected><Forecasts /></Protected>} />
        <Route path="/forecasts/:techId" element={<Protected><TechnologyDetail /></Protected>} />
        <Route path="/scenarios" element={<Protected><Scenarios /></Protected>} />
        <Route path="/explorer" element={<Protected><Explorer /></Protected>} />
      </Routes>
    </Layout>
  );
}
