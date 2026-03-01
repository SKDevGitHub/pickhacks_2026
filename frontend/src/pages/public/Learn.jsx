import { useEffect, useMemo, useState } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { api } from '../../api';

export default function Learn() {
  const { isAuthenticated } = useAuth0();
  const [technologies, setTechnologies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [petitionCounts, setPetitionCounts] = useState({});
  const [petitionedTechIds, setPetitionedTechIds] = useState({});
  const [cities, setCities] = useState([]);
  const [petitionTech, setPetitionTech] = useState(null);
  const [selectedCity, setSelectedCity] = useState('');
  const [otherCity, setOtherCity] = useState('');
  const [petitionMessage, setPetitionMessage] = useState('');

  useEffect(() => {
    try {
      const raw = JSON.parse(localStorage.getItem('techsignals-petitions') || '[]');
      const seen = new Set();
      const deduped = [];

      for (const item of raw) {
        const techId = item?.techId;
        if (!techId || seen.has(techId)) continue;
        seen.add(techId);
        deduped.push(item);
      }

      if (deduped.length !== raw.length) {
        localStorage.setItem('techsignals-petitions', JSON.stringify(deduped));
      }

      const counts = deduped.reduce((acc, item) => {
        const techId = item?.techId;
        if (!techId) return acc;
        acc[techId] = (acc[techId] || 0) + 1;
        return acc;
      }, {});

      const petitioned = deduped.reduce((acc, item) => {
        const techId = item?.techId;
        if (!techId) return acc;
        acc[techId] = true;
        return acc;
      }, {});

      setPetitionCounts(counts);
      setPetitionedTechIds(petitioned);
    } catch {
      setPetitionCounts({});
      setPetitionedTechIds({});
    }
  }, []);

  useEffect(() => {
    api
      .technologies({ sortBy: 'power' })
      .then(setTechnologies)
      .catch(() => setTechnologies([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    api
      .cities()
      .then((data) => {
        const names = (data || [])
          .map((city) => city?.name)
          .filter(Boolean)
          .slice(0, 5);
        setCities(names);
      })
      .catch(() => setCities([]));
  }, []);

  const featured = useMemo(() => technologies.slice(0, 6), [technologies]);

  function openPetitionModal(tech) {
    if (petitionedTechIds[tech.id]) {
      setPetitionMessage(`You already petitioned for ${tech.name}.`);
      return;
    }

    setPetitionTech(tech);
    setSelectedCity('');
    setOtherCity('');
    setPetitionMessage('');
  }

  function closePetitionModal() {
    setPetitionTech(null);
    setSelectedCity('');
    setOtherCity('');
  }

  function submitPetition() {
    if (!petitionTech) return;
    if (petitionedTechIds[petitionTech.id]) {
      setPetitionMessage(`You already petitioned for ${petitionTech.name}.`);
      closePetitionModal();
      return;
    }

    const cityName = selectedCity === 'other'
      ? String(otherCity || '').trim()
      : String(selectedCity || '').trim();

    if (!cityName) return;

    const petition = {
      techId: petitionTech.id,
      techName: petitionTech.name,
      city: cityName,
      createdAt: new Date().toISOString(),
    };

    const existing = JSON.parse(localStorage.getItem('techsignals-petitions') || '[]');
    const alreadyExists = existing.some((item) => item?.techId === petitionTech.id);
    if (alreadyExists) {
      setPetitionMessage(`You already petitioned for ${petitionTech.name}.`);
      closePetitionModal();
      return;
    }

    existing.push(petition);
    localStorage.setItem('techsignals-petitions', JSON.stringify(existing));

    setPetitionCounts((prev) => ({
      ...prev,
      [petitionTech.id]: (prev[petitionTech.id] || 0) + 1,
    }));

    setPetitionedTechIds((prev) => ({
      ...prev,
      [petitionTech.id]: true,
    }));

    setPetitionMessage(`Petition submitted for ${petitionTech.name} in ${cityName}.`);
    closePetitionModal();
  }

  return (
    <div className="fade-in page-shell learn-page">
      <div className="page-header">
        <h1 className="page-title">Learn Emerging Technology</h1>
        <p className="page-subtitle">
          Explore what each technology is, why it matters, and how its
          environmental footprint changes over time.
        </p>
      </div>

      <section className="learn-section">
        <h2 className="section-title">Featured Emerging Technologies</h2>
        {petitionMessage && <p className="learn-petition-feedback">{petitionMessage}</p>}
        {loading ? (
          <p className="page-subtitle">Loading technologies…</p>
        ) : featured.length === 0 ? (
          <p className="page-subtitle">No technologies are available yet.</p>
        ) : (
          <div className="learn-tech-grid">
            {featured.map((tech) => (
              <article key={tech.id} className="learn-tech-card">
                <div className="learn-tech-top">
                  <h3>{tech.name}</h3>
                </div>
                <p className="learn-tech-meta">{tech.category}</p>
                <p className="learn-tech-desc">{tech.learn?.description || tech.description}</p>

                <div className="learn-detail-block">
                  <h4>Why this matters</h4>
                  <p>{tech.learn?.significance || 'Significance details are not available yet.'}</p>
                </div>

                <div className="learn-detail-block">
                  <h4>Value it can add</h4>
                  <p>{tech.learn?.valueAdd || 'Value-add details are not available yet.'}</p>
                </div>

                {isAuthenticated && (
                  <div className="learn-petition-row">
                    <button
                      className="btn-secondary learn-open-btn"
                      onClick={() => openPetitionModal(tech)}
                      disabled={Boolean(petitionedTechIds[tech.id])}
                    >
                      {petitionedTechIds[tech.id] ? 'Petition submitted' : 'Petition to bring to my city'}
                    </button>
                    <span className="learn-petition-count">
                      {(petitionCounts[tech.id] || 0)} petitions
                    </span>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </section>

      {petitionTech && (
        <div className="learn-modal-overlay" onClick={closePetitionModal}>
          <div className="learn-modal" onClick={(event) => event.stopPropagation()}>
            <h3 className="learn-modal-title">Petition for {petitionTech.name}</h3>
            <p className="learn-modal-subtitle">Choose one of the available cities or select Other.</p>

            <div className="learn-modal-cities">
              {cities.map((cityName) => (
                <button
                  key={cityName}
                  className={`learn-city-option${selectedCity === cityName ? ' active' : ''}`}
                  onClick={() => setSelectedCity(cityName)}
                >
                  {cityName}
                </button>
              ))}

              <button
                className={`learn-city-option${selectedCity === 'other' ? ' active' : ''}`}
                onClick={() => setSelectedCity('other')}
              >
                Other
              </button>
            </div>

            {selectedCity === 'other' && (
              <input
                className="learn-other-input"
                type="text"
                placeholder="Enter your city"
                value={otherCity}
                onChange={(event) => setOtherCity(event.target.value)}
              />
            )}

            <div className="learn-modal-actions">
              <button
                className="btn-primary"
                onClick={submitPetition}
                disabled={!selectedCity || (selectedCity === 'other' && !otherCity.trim())}
              >
                Submit petition
              </button>
              <button className="btn-secondary" onClick={closePetitionModal}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
