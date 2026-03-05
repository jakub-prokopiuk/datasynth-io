import { useState } from 'react';
import api from '../lib/api';
import { Lock, User, Database } from 'lucide-react';
import { colors } from '../theme';

function LoginPage({ onLogin }) {
    const [username, setUsername] = useState('admin');
    const [password, setPassword] = useState('admin');
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        try {
            const response = await api.post('/token', formData);
            const token = response.data.access_token;

            localStorage.setItem('token', token);

            onLogin(token);
        } catch (err) {
            setError("Invalid credentials. Try admin / admin");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className={`min-h-screen ${colors.bgMain} flex flex-col items-center justify-center p-4`}>
            <div className="flex items-center gap-3 mb-8">
                <div className="bg-blue-500/10 p-3 rounded-lg border border-blue-500/20">
                    <Database size={32} className="text-blue-400" />
                </div>
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-white">DataSynth<span className="text-blue-400">.io</span></h1>
                    <p className={`text-sm ${colors.textMuted}`}>Enterprise Data Generator</p>
                </div>
            </div>

            <div className={`w-full max-w-sm ${colors.bgPanel} border ${colors.border} rounded-xl p-8 shadow-2xl`}>
                <h2 className="text-xl font-bold text-white mb-6 text-center">Sign In</h2>

                {error && (
                    <div className="bg-red-900/20 border border-red-900/50 text-red-400 text-xs p-3 rounded mb-4 text-center">
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className={`block text-xs font-bold ${colors.textMuted} mb-1.5`}>Username</label>
                        <div className="relative">
                            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">
                                <User size={16} />
                            </div>
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className={`w-full pl-9 pr-3 py-2.5 rounded-md border ${colors.border} bg-[#0d1117] text-white text-sm outline-none focus:border-blue-500 transition`}
                                placeholder="Enter username"
                            />
                        </div>
                    </div>

                    <div>
                        <label className={`block text-xs font-bold ${colors.textMuted} mb-1.5`}>Password</label>
                        <div className="relative">
                            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">
                                <Lock size={16} />
                            </div>
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className={`w-full pl-9 pr-3 py-2.5 rounded-md border ${colors.border} bg-[#0d1117] text-white text-sm outline-none focus:border-blue-500 transition`}
                                placeholder="Enter password"
                            />
                        </div>
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-[#1f6feb] hover:bg-[#388bfd] text-white font-bold py-2.5 rounded-md transition shadow-lg shadow-blue-900/20 flex justify-center items-center gap-2 mt-4"
                    >
                        {loading ? 'Signing in...' : 'Sign In'}
                    </button>
                </form>

                <div className="mt-6 text-center">
                    <p className="text-[10px] text-gray-500">Default credentials: <code>admin</code> / <code>admin</code></p>
                </div>
            </div>
        </div>
    );
}

export default LoginPage;