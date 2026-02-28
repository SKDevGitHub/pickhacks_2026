function parseCsv(value) {
  return String(value || '')
    .split(',')
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

const allowedEmails = parseCsv(import.meta.env.VITE_GENERATE_ALLOWED_EMAILS);
const allowedSubs = parseCsv(import.meta.env.VITE_GENERATE_ALLOWED_SUBS);

export function isEduEmail(user) {
  const email = String(user?.email || '').trim().toLowerCase();
  if (!email) return false;
  const domain = email.split('@').pop() || '';
  return domain.endsWith('.edu') || domain.includes('.edu.');
}

export function canAccessGenerate(user) {
  if (!user) return false;

  const permissions = Array.isArray(user?.permissions) ? user.permissions : [];
  if (permissions.includes('manage:articles')) return true;

  if (allowedEmails.length === 0 && allowedSubs.length === 0) {
    return false;
  }

  const email = String(user?.email || '').trim().toLowerCase();
  const sub = String(user?.sub || '').trim().toLowerCase();

  return (email && allowedEmails.includes(email)) || (sub && allowedSubs.includes(sub));
}
