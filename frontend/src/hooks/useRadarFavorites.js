import { useEffect, useMemo, useState } from 'react';

const STORAGE_KEY = 'techsignals-radar-favorites';

function loadFavorites() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function useRadarFavorites() {
  const [favoriteIds, setFavoriteIds] = useState(loadFavorites);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(favoriteIds));
  }, [favoriteIds]);

  const favoriteSet = useMemo(() => new Set(favoriteIds), [favoriteIds]);

  const isFavorite = (techId) => favoriteSet.has(techId);

  const toggleFavorite = (techId) => {
    setFavoriteIds((prev) =>
      prev.includes(techId)
        ? prev.filter((id) => id !== techId)
        : [...prev, techId]
    );
  };

  return {
    favoriteIds,
    isFavorite,
    toggleFavorite,
  };
}
