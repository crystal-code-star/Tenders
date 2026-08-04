import React, { useState, useEffect, useCallback } from 'react';
import {
  X, Plus, Trash2, Settings, Sliders, RefreshCw, Check, Info,
} from 'lucide-react';
import { API_URL, authHeaders } from './tenderUtils';

const FIELD_OPTIONS = [
  { value: 'turnover', label: 'Chiffre d\'affaires', suggestedWeight: 10, hint: 'Critère financier important' },
  { value: 'experience', label: 'Années d\'expérience', suggestedWeight: 5, hint: 'Expérience requise' },
  { value: 'estimated_amount', label: 'Montant estimé', suggestedWeight: 8, hint: 'Taille du projet' },
  { value: 'city', label: 'Ville', suggestedWeight: 3, hint: 'Proximité géographique' },
  { value: 'region', label: 'Région', suggestedWeight: 2, hint: 'Zone d\'intervention' },
  { value: 'acheteur', label: 'Acheteur', suggestedWeight: 8, hint: 'Client stratégique' },
  { value: 'objet', label: 'Objet', suggestedWeight: 10, hint: 'Mots-clés dans l\'objet' },
  { value: 'categorie', label: 'Catégorie', suggestedWeight: 5, hint: 'Type de prestation' },
  { value: 'lieu_execution', label: 'Lieu d\'exécution', suggestedWeight: 3, hint: 'Localisation' },
];

const OPERATOR_OPTIONS = [
  { value: '=', label: '=' }, { value: '<', label: '<' }, { value: '<=', label: '≤' },
  { value: '>', label: '>' }, { value: '>=', label: '≥' },
];

const CW_THEME_STYLE = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  .cw-theme { font-family: 'Inter', -apple-system, BlinkMacSystemFont, ui-sans-serif, sans-serif; background-color: #F8FAFC; }
  * { transition-property: background-color, border-color, color, fill, stroke, opacity, box-shadow, transform; transition-duration: 150ms; transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1); }
  .weight-indicator { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 20px; font-size: 10px; font-weight: 600; }
  .weight-high { background: #FEE2E2; color: #DC2626; }
  .weight-medium { background: #FEF9C3; color: #CA8A04; }
  .weight-low { background: #DCFCE7; color: #16A34A; }
  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
  .animate-spin { animation: spin 1s linear infinite; }
`;

export default function ScoringManager({ isOpen, onClose }) {
  const [criteria, setCriteria] = useState([]);
  const [loading, setLoading] = useState(true);
  const [recalcMsg, setRecalcMsg] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingId, setEditingId] = useState(null);

  const [newField, setNewField] = useState('objet');
  const [newOperator, setNewOperator] = useState('=');
  const [newValue, setNewValue] = useState('');
  const [newWeight, setNewWeight] = useState(10);

  const [editField, setEditField] = useState('objet');
  const [editOperator, setEditOperator] = useState('=');
  const [editValue, setEditValue] = useState('');
  const [editWeight, setEditWeight] = useState(1);

  const fetchCriteria = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/scoring-criteria`, { headers: authHeaders() });
      const data = await response.json();
      if (data.success) setCriteria(data.criteria || []);
    } catch (error) { console.error('Error fetching scoring criteria:', error); }
    setLoading(false);
  }, []);

  useEffect(() => { if (isOpen) fetchCriteria(); }, [isOpen, fetchCriteria]);

  const handleFieldChange = (fieldName) => {
    setNewField(fieldName);
    const field = FIELD_OPTIONS.find(f => f.value === fieldName);
    if (field) setNewWeight(field.suggestedWeight);
  };

  const addCriteria = async () => {
    if (!newValue.trim()) return;
    try {
      setRecalcMsg('Ajout + recalcul en cours...');
      await fetch(`${API_URL}/scoring-criteria`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ field_name: newField, operator: newOperator, value: newValue.trim(), weight: newWeight })
      });
      setNewValue(''); setNewWeight(10); setShowAddModal(false);
      await fetchCriteria();
      setTimeout(() => setRecalcMsg(''), 3000);
    } catch (error) { console.error(error); setRecalcMsg(''); }
  };

  const deleteCriteria = async (id) => {
    try {
      setRecalcMsg('Suppression + recalcul en cours...');
      await fetch(`${API_URL}/scoring-criteria/${id}`, { method: 'DELETE', headers: authHeaders() });
      await fetchCriteria();
      setTimeout(() => setRecalcMsg(''), 3000);
    } catch (error) { console.error(error); setRecalcMsg(''); }
  };

  const toggleActive = async (id, isActive) => {
    try {
      setRecalcMsg('Mise à jour + recalcul en cours...');
      await fetch(`${API_URL}/scoring-criteria/${id}`, {
        method: 'PATCH',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !isActive })
      });
      await fetchCriteria();
      setTimeout(() => setRecalcMsg(''), 3000);
    } catch (error) { console.error(error); setRecalcMsg(''); }
  };

  const startEdit = (item) => {
    setEditingId(item.id); setEditField(item.field_name); setEditOperator(item.operator);
    setEditValue(item.value); setEditWeight(item.weight);
  };

  const saveEdit = async () => {
    try {
      setRecalcMsg('Modification + recalcul en cours...');
      await fetch(`${API_URL}/scoring-criteria/${editingId}`, {
        method: 'PATCH',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ field_name: editField, operator: editOperator, value: editValue, weight: editWeight })
      });
      setEditingId(null); await fetchCriteria();
      setTimeout(() => setRecalcMsg(''), 3000);
    } catch (error) { console.error(error); setRecalcMsg(''); }
  };

  const getFieldLabel = (fn) => FIELD_OPTIONS.find(f => f.value === fn)?.label || fn;
  const getFieldHint = (fn) => FIELD_OPTIONS.find(f => f.value === fn)?.hint || '';
  const getWeightClass = (w) => w >= 8 ? 'weight-high' : w >= 5 ? 'weight-medium' : 'weight-low';
  const getWeightLabel = (w) => w >= 8 ? 'Fort' : w >= 5 ? 'Moyen' : 'Faible';
  const getTotalWeight = () => criteria.filter(c => c.is_active).reduce((s, c) => s + (c.weight || 0), 0);

  if (!isOpen) return null;

  return (
    <div className="cw-theme min-h-screen">
      <style>{CW_THEME_STYLE}</style>
      <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-sm p-4 mb-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-[#EFF6FF] flex items-center justify-center"><Info size={16} className="text-[#2563EB]" /></div>
              <div>
                <p className="text-sm font-medium text-[#0F172A]">
                  Total des poids actifs : <span className="text-[#2563EB] font-bold">{getTotalWeight()} points</span>
                  <span className="text-[#94A3B8]"> • Score normalisé sur 100</span>
                  <span className="text-[#94A3B8]"> • {criteria.filter(c => c.is_active).length} critères actifs</span>
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="weight-indicator weight-high">Fort ≥8</span>
                  <span className="weight-indicator weight-medium">Moyen 5-7</span>
                  <span className="weight-indicator weight-low">Faible 1-4</span>
                </div>
              </div>
            </div>
            {recalcMsg && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-[#EFF6FF] rounded-xl">
                <RefreshCw size={14} className="text-[#2563EB] animate-spin" />
                <span className="text-xs font-medium text-[#2563EB]">{recalcMsg}</span>
              </div>
            )}
          </div>
        </div>

        <div className="bg-white rounded-3xl border border-[#E2E8F0] shadow-sm overflow-hidden mb-6">
          <div className="p-4">
            <div className="flex gap-3 items-center">
              <div className="relative flex-1">
                <input type="text" placeholder="Rechercher un critère..." className="w-full pl-4 pr-4 py-3 text-sm border border-[#E2E8F0] rounded-2xl focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none text-[#0F172A] placeholder-[#94A3B8] bg-[#F8FAFC]" />
              </div>
              <button onClick={() => setShowAddModal(true)} className="px-6 py-3 bg-[#111827] text-white rounded-2xl text-sm font-medium hover:bg-[#1E293B] transition-all duration-200 flex items-center gap-2 shadow-sm active:scale-95">
                <Plus size={14} />Ajouter un critère
              </button>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-3xl border border-[#E2E8F0] shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-12 text-center"><RefreshCw size={28} className="text-[#2563EB] animate-spin mx-auto mb-3" /><p className="text-sm font-medium text-[#64748B]">Chargement...</p></div>
          ) : criteria.length === 0 ? (
            <div className="p-12 text-center">
              <div className="w-14 h-14 rounded-2xl bg-[#F8FAFC] flex items-center justify-center mx-auto mb-3"><Sliders size={24} className="text-[#94A3B8]" /></div>
              <p className="text-sm font-semibold text-[#475569]">Aucun critère</p>
              <p className="text-xs text-[#94A3B8] mt-1">Ajoutez des critères pour le scoring automatique (score sur 100)</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead><tr className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
                  <th className="text-left px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">Champ</th>
                  <th className="text-center px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">Op</th>
                  <th className="text-left px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">Valeur</th>
                  <th className="text-center px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">Poids</th>
                  <th className="text-center px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">Impact</th>
                  <th className="text-center px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">Actif</th>
                  <th className="text-center px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">Actions</th>
                </tr></thead>
                <tbody className="divide-y divide-[#E2E8F0]">
                  {criteria.map(item => (
                    <tr key={item.id} className={`hover:bg-[#F8FAFC]/50 transition-colors ${!item.is_active ? 'opacity-40' : ''}`}>
                      {editingId === item.id ? (
                        <>
                          <td className="px-3 py-3"><select value={editField} onChange={e => setEditField(e.target.value)} className="w-full px-2 py-2 text-xs border border-[#E2E8F0] rounded-lg focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none text-[#0F172A]">{FIELD_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}</select></td>
                          <td className="px-3 py-3"><select value={editOperator} onChange={e => setEditOperator(e.target.value)} className="w-full px-2 py-2 text-xs text-center border border-[#E2E8F0] rounded-lg focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none text-[#0F172A]">{OPERATOR_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}</select></td>
                          <td className="px-3 py-3"><input type="text" value={editValue} onChange={e => setEditValue(e.target.value)} className="w-full px-2 py-2 text-xs border border-[#E2E8F0] rounded-lg focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none text-[#0F172A]" /></td>
                          <td className="px-3 py-3"><input type="number" value={editWeight} onChange={e => setEditWeight(parseInt(e.target.value) || 1)} min="1" max="100" className="w-20 px-2 py-2 text-xs text-center border border-[#E2E8F0] rounded-lg focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none text-[#0F172A]" /></td>
                          <td className="px-3 py-3"></td>
                          <td className="px-3 py-3"><div className="flex items-center justify-center gap-1"><button onClick={saveEdit} className="p-1.5 text-[#16A34A] hover:bg-[#DCFCE7] rounded-lg transition-all"><Check size={14} /></button><button onClick={() => setEditingId(null)} className="p-1.5 text-[#DC2626] hover:bg-[#FEE2E2] rounded-lg transition-all"><X size={14} /></button></div></td>
                        </>
                      ) : (
                        <>
                          <td className="px-5 py-3"><div><span className="text-sm text-[#0F172A]">{getFieldLabel(item.field_name)}</span><p className="text-[10px] text-[#94A3B8]">{getFieldHint(item.field_name)}</p></div></td>
                          <td className="px-5 py-3 text-center"><span className="text-xs font-mono font-semibold text-[#0F172A] bg-[#F8FAFC] px-2 py-0.5 rounded-lg border border-[#E2E8F0]">{item.operator}</span></td>
                          <td className="px-5 py-3"><span className="text-sm font-medium text-[#0F172A]">{item.value}</span></td>
                          <td className="px-5 py-3 text-center"><span className="text-xs font-semibold text-[#2563EB] bg-[#EFF6FF] px-2 py-0.5 rounded-lg">×{item.weight}</span></td>
                          <td className="px-5 py-3 text-center"><span className={`weight-indicator ${getWeightClass(item.weight)}`}>{getWeightLabel(item.weight)}</span></td>
                          <td className="px-5 py-3 text-center"><button onClick={() => toggleActive(item.id, item.is_active)} className={`w-5 h-5 rounded-lg border-2 transition-all flex items-center justify-center mx-auto ${item.is_active ? 'bg-[#2563EB] border-[#2563EB]' : 'border-[#CBD5E1] hover:border-[#2563EB]/40'}`}>{item.is_active && <Check size={11} className="text-white" strokeWidth={3} />}</button></td>
                          <td className="px-5 py-3 text-center"><div className="flex items-center justify-center gap-1"><button onClick={() => startEdit(item)} className="p-1.5 text-[#94A3B8] hover:text-[#2563EB] hover:bg-[#EFF6FF] rounded-lg transition-all"><Settings size={13} /></button><button onClick={() => deleteCriteria(item.id)} className="p-1.5 text-[#94A3B8] hover:text-[#DC2626] hover:bg-[#FEE2E2] rounded-lg transition-all"><Trash2 size={13} /></button></div></td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0F172A]/40 backdrop-blur-sm">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden border border-[#E2E8F0]">
            <div className="p-6 border-b border-[#E2E8F0]"><div className="flex items-center justify-between"><div className="flex items-center gap-3"><div className="w-10 h-10 rounded-2xl bg-[#111827] flex items-center justify-center shadow-sm"><Plus size={18} className="text-white" /></div><div><h3 className="font-semibold text-[#0F172A] text-base">Ajouter un critère</h3><p className="text-xs text-[#64748B]">{FIELD_OPTIONS.find(f => f.value === newField)?.hint || 'Définissez une règle de scoring'} • Score normalisé sur 100</p></div></div><button onClick={() => setShowAddModal(false)} className="p-2 text-[#94A3B8] hover:text-[#0F172A] hover:bg-[#F8FAFC] rounded-xl transition-colors"><X size={18} /></button></div></div>
            <div className="p-6 space-y-4">
              <div><label className="block text-xs font-semibold text-[#64748B] mb-1.5">Champ à vérifier</label><select value={newField} onChange={e => handleFieldChange(e.target.value)} className="w-full px-3 py-3 text-sm border border-[#E2E8F0] rounded-2xl focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none text-[#0F172A] bg-[#F8FAFC]">{FIELD_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label} (poids suggéré: {opt.suggestedWeight})</option>)}</select></div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="block text-xs font-semibold text-[#64748B] mb-1.5">Opérateur</label><select value={newOperator} onChange={e => setNewOperator(e.target.value)} className="w-full px-3 py-3 text-sm border border-[#E2E8F0] rounded-2xl focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none text-[#0F172A] bg-[#F8FAFC]">{OPERATOR_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}</select></div>
                <div><label className="block text-xs font-semibold text-[#64748B] mb-1.5">Valeur</label><input type="text" value={newValue} onChange={e => setNewValue(e.target.value)} placeholder={newOperator === '=' ? "Ex: Casablanca" : "Ex: 20000"} className="w-full px-3 py-3 text-sm border border-[#E2E8F0] rounded-2xl focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none text-[#0F172A] placeholder-[#94A3B8] bg-[#F8FAFC]" /></div>
              </div>
              <div>
                <div className="flex items-center justify-between mb-1.5"><label className="block text-xs font-semibold text-[#64748B]">Poids</label><span className={`weight-indicator ${getWeightClass(newWeight)}`}>{getWeightLabel(newWeight)} impact</span></div>
                <input type="range" value={newWeight} onChange={e => setNewWeight(parseInt(e.target.value))} min="1" max="20" className="w-full h-2 bg-[#E2E8F0] rounded-lg appearance-none cursor-pointer accent-[#2563EB]" />
                <div className="flex justify-between mt-1"><span className="text-[10px] text-[#94A3B8]">1 (faible)</span><span className="text-xs font-bold text-[#2563EB]">{newWeight} points</span><span className="text-[10px] text-[#94A3B8]">20 (max)</span></div>
                <div className="mt-2 flex gap-2">
                  {[3,5,8,10].map(w => (
                    <button key={w} onClick={() => setNewWeight(w)} className={`text-[10px] px-2 py-1 rounded-lg border transition-all ${newWeight === w ? (w>=8?'bg-[#FEE2E2] border-[#DC2626] text-[#DC2626]':w>=5?'bg-[#FEF9C3] border-[#CA8A04] text-[#CA8A04]':'bg-[#DCFCE7] border-[#16A34A] text-[#16A34A]') : 'border-[#E2E8F0] text-[#64748B] hover:border-[#2563EB]'}`}>{w === 3 ? 'Faible (3)' : w === 5 ? 'Moyen (5)' : w === 8 ? 'Fort (8)' : 'Très fort (10)'}</button>
                  ))}
                </div>
              </div>
            </div>
            <div className="p-6 border-t border-[#E2E8F0] bg-[#F8FAFC] flex gap-3">
              <button onClick={() => setShowAddModal(false)} className="flex-1 py-3 bg-white border border-[#E2E8F0] text-[#475569] rounded-2xl text-sm font-medium hover:bg-[#F8FAFC] transition-all duration-200">Annuler</button>
              <button onClick={addCriteria} className="flex-1 py-3 bg-[#111827] text-white rounded-2xl text-sm font-medium hover:bg-[#1E293B] transition-all duration-200 shadow-sm active:scale-[0.98]">Ajouter (+{newWeight} pts)</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}