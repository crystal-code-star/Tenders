// ─── Shared helpers for Tenders + Dashboard ───────────────────
export const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const authHeaders = () => ({
  Authorization: `Bearer ${localStorage.getItem('access_token')}`,
  'Content-Type': 'application/json',
});

export const SCORE_TIER = (s) => {
  if (s >= 70) return { label: 'High', bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500', bar: '#10B981' };
  if (s >= 45) return { label: 'Med',  bg: 'bg-amber-100',   text: 'text-amber-700',   dot: 'bg-amber-500',   bar: '#F59E0B' };
  return         { label: 'Low',  bg: 'bg-gray-100',    text: 'text-gray-500',    dot: 'bg-gray-400',    bar: '#9CA3AF' };
};

export const STATUS_MAP = {
  new:       { label: 'New',       bg: 'bg-violet-50',     text: 'text-violet-700',     ring: 'ring-violet-200',   dot: 'bg-violet-400'    },
  contacted: { label: 'Contacted', bg: 'bg-emerald-50',  text: 'text-emerald-700',  ring: 'ring-emerald-200', dot: 'bg-emerald-400' },
  ignored:   { label: 'Ignored',   bg: 'bg-gray-100',    text: 'text-gray-400',     ring: 'ring-gray-200',    dot: 'bg-gray-300'    },
  archived:  { label: 'Archived',  bg: 'bg-slate-100',   text: 'text-slate-600',    ring: 'ring-slate-200',   dot: 'bg-slate-400'   },
};

export const COUNTRY_FLAGS = {
  Morocco:'🇲🇦',Maroc:'🇲🇦',Kenya:'🇰🇪',Senegal:'🇸🇳',Sénégal:'🇸🇳',
  Ghana:'🇬🇭',Nigeria:'🇳🇬','South Africa':'🇿🇦',Egypt:'🇪🇬',Tunisia:'🇹🇳',
  Tunisie:'🇹🇳',Algeria:'🇩🇿',Algérie:'🇩🇿','Ivory Coast':'🇨🇮',
  "Côte d'Ivoire":'🇨🇮',Ethiopia:'🇪🇹',Tanzania:'🇹🇿',Uganda:'🇺🇬',
  Cameroon:'🇨🇲',Cameroun:'🇨🇲',Zambia:'🇿🇲',Rwanda:'🇷🇼',
};

export const getFlag = (c) => {
  for (const [k, v] of Object.entries(COUNTRY_FLAGS))
    if ((c || '').toLowerCase().includes(k.toLowerCase())) return v;
  return '🌍';
};

export const fmtDate = (d) => {
  if (!d) return null;
  try { return new Date(d).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }); }
  catch { return d; }
};

export const getScore = (item) => {
  let s = item.relevance_score || 0;
  if (!s && item.dce_resume) {
    const m = item.dce_resume.match(/Score de pertinence\s*:\s*(\d+)/i);
    if (m) s = parseInt(m[1]);
  }
  return s;
};

export const parseResume = (text) => {
  if (!text) return [];
  const sections = [];
  const lines = text.split('\n');
  let cur = null, items = [];
  lines.forEach(l => {
    const t = l.trim();
    if (t.match(/^[A-Z][A-Z\s]{4,}$/) && !t.startsWith('-') && !t.startsWith('•')) {
      if (cur) sections.push({ title: cur, items });
      cur = t; items = [];
    } else if (t.startsWith('-') || t.startsWith('•')) {
      const txt = t.substring(1).trim();
      items.push({ text: txt, type: txt.includes('SOUMISSIONNER') ? 'submit' : txt.includes('VEILLE') ? 'watch' : txt.includes('IGNORER') ? 'ignore' : 'normal' });
    } else if (t) {
      items.push({ text: t, type: 'text' });
    }
  });
  if (cur) sections.push({ title: cur, items });
  return sections;
};