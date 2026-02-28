import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import Forecasts from './pages/Forecasts';
import TechnologyDetail from './pages/TechnologyDetail';
import Scenarios from './pages/Scenarios';
import Explorer from './pages/Explorer';
import About from './pages/About';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/about" element={<About />} />
        <Route path="/forecasts" element={<Forecasts />} />
        <Route path="/forecasts/:techId" element={<TechnologyDetail />} />
        <Route path="/scenarios" element={<Scenarios />} />
        <Route path="/explorer" element={<Explorer />} />
      </Routes>
    </Layout>
  );
}
