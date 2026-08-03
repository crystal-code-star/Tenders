import React from 'react';
import { Globe, BarChart2, Target, Sparkles } from 'lucide-react';
import { getScore } from './tenderUtils';

const COLORS = {
  indigo:  'bg-indigo-50  text-indigo-600',
  emerald: 'bg-emerald-50 text-emerald-600',
  amber:   'bg-amber-50   text-amber-600',
  violet:  'bg-violet-50  text-violet-600',
};

export function KpiCard({ label, value, icon: Icon, color }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm flex items-center gap-4">
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 ${COLORS[color] || COLORS.indigo}`}>
        <Icon size={20} />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-xs text-gray-400 mt-0.5">{label}</p>
      </div>
    </div>
  );
}

// Computes the 4 headline numbers from raw tenders/suppliers/sectors arrays
// and renders them as a KPI row. Drop this anywhere — it owns its own layout.
export default function KpiStats({ tenders = [], suppliers = [], sectors = [] }) {
  const allItems  = [...tenders, ...suppliers, ...sectors];
  const highCount = allItems.filter(t => getScore(t) >= 70).length;
  const newCount  = allItems.filter(t => t.status === 'new').length;
  const dceCount  = allItems.filter(t => t.dce_resume || t.dce_zip_url).length;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <KpiCard label="Total tenders"    value={tenders.length} icon={Globe}     color="indigo"  />
      <KpiCard label="High priority"    value={highCount}      icon={BarChart2} color="emerald" />
      <KpiCard label="New (unreviewed)" value={newCount}       icon={Target}    color="amber"   />
      <KpiCard label="DCE analysed"     value={dceCount}       icon={Sparkles}  color="violet"  />
    </div>
  );
}