import React, { useState } from 'react';
import { LogIn, AlertCircle, Sparkles, Droplets } from 'lucide-react';

const Login = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Login failed');
      }
      const data = await response.json();
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('user_email', data.email);
      if (onLoginSuccess) onLoginSuccess(data.email);
    } catch (err) {
      setError(err.message || 'Invalid email or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex font-sans">

      {/* ── Left brand panel ── */}
      <div
        className="hidden lg:flex w-[460px] flex-col justify-between p-12 flex-shrink-0"
        style={{ background: 'linear-gradient(160deg, #2D2CF0 0%, #1a19b8 100%)' }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
            <Sparkles size={20} className="text-white" />
          </div>
          <span className="font-bold text-white text-xl tracking-tight">CrystalWater</span>
        </div>

        {/* Copy */}
        <div>
          <p className="text-white/40 text-xs font-bold uppercase tracking-widest mb-3">
            Procurement Intelligence
          </p>
          <h2 className="text-4xl font-bold text-white leading-snug mb-4">
            Monitor tenders.<br />Win more contracts.
          </h2>
          <p className="text-white/55 text-sm leading-relaxed">
            AI-powered tender tracking, DCE analysis, and real-time scoring
            for water and cooling projects across Africa.
          </p>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 gap-3">
          {[
            { label: 'Tenders tracked',  value: '2,400+' },
            { label: 'Countries covered', value: '18'     },
            { label: 'Avg. match score',  value: '82%'    },
            { label: 'DCE analysed',      value: '940+'   },
          ].map(s => (
            <div key={s.label} className="bg-white/10 rounded-xl p-4">
              <p className="text-white font-bold text-xl">{s.value}</p>
              <p className="text-white/45 text-xs mt-0.5">{s.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Right form panel ── */}
      <div className="flex-1 flex items-center justify-center bg-[#F0F2FA] p-6">
        <div className="w-full max-w-md">

          {/* Mobile-only logo */}
          <div className="lg:hidden flex items-center justify-center gap-2 mb-8">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center">
              <Sparkles size={18} className="text-white" />
            </div>
            <span className="font-bold text-gray-900 text-xl">CrystalWater</span>
          </div>

          <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
            <div className="mb-7">
              <h1 className="text-2xl font-bold text-gray-900">Welcome back</h1>
              <p className="text-gray-400 text-sm mt-1">Sign in to your account to continue</p>
            </div>

            {error && (
              <div className="mb-5 bg-red-50 border border-red-200 rounded-xl p-3.5 flex items-start gap-3">
                <AlertCircle size={18} className="text-red-500 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="email" className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1.5">
                  Email address
                </label>
                <input
                  id="email" type="email" value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 outline-none transition-all text-gray-900 placeholder:text-gray-300"
                  disabled={loading} required
                />
              </div>

              <div>
                <label htmlFor="password" className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1.5">
                  Password
                </label>
                <input
                  id="password" type="password" value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 outline-none transition-all text-gray-900"
                  disabled={loading} required
                />
              </div>

              <div className="pt-1">
                <button
                  type="submit" disabled={loading}
                  className="w-full py-3 rounded-xl font-bold text-sm text-white transition-all disabled:opacity-50 flex items-center justify-center gap-2 shadow-lg shadow-indigo-200"
                  style={{ background: 'linear-gradient(135deg, #2D2CF0 0%, #5554f0 100%)' }}
                >
                  {loading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Signing in…
                    </>
                  ) : (
                    <>
                      <LogIn size={16} />
                      Sign In
                    </>
                  )}
                </button>
              </div>
            </form>

            <p className="text-xs text-gray-400 text-center mt-6">
              Private application — authorised users only
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;