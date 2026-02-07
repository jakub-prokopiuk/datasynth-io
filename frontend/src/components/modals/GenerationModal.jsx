import { useEffect, useState, useRef } from 'react';
import { CheckCircle2, AlertTriangle, FileDown } from 'lucide-react';
import { colors } from '../../theme';
import api from '../../lib/api';

function GenerationModal({ onClose, jobId, onComplete }) {
    const [status, setStatus] = useState("initializing");
    const [progress, setProgress] = useState(0);
    const [error, setError] = useState(null);
    const ws = useRef(null);

    useEffect(() => {
        if (!jobId) return;
        if (ws.current && ws.current.readyState !== WebSocket.CLOSED) {
            return;
        }

        const baseUrl = import.meta.env.API_URL || "http://localhost:8001";
        const wsUrl = baseUrl.replace(/^http/, 'ws') + `/ws/jobs/${jobId}`;

        console.log("Connecting WS to:", wsUrl);
        const socket = new WebSocket(wsUrl);
        ws.current = socket;

        socket.onopen = () => console.log("WS Connected");

        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.status) setStatus(data.status);
            if (data.progress !== undefined) setProgress(data.progress);
            if (data.status === "failed") setError(data.error || "Unknown error");
        };

        socket.onerror = (err) => {
            console.error("WS Error", err);
        };

        socket.onclose = () => {
            console.log("WS Closed");
        };

        return () => {
            if (socket.readyState === WebSocket.OPEN) {
                socket.close();
            }
        };
    }, [jobId]);

    const handleCancel = async () => {
        try {
            await api.delete(`/jobs/${jobId}`);
            setStatus("cancelled");
        } catch (e) {
            console.error(e);
        }
    };

    return (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/90 backdrop-blur-md p-4 animate-in fade-in duration-300">
            <div className={`w-full max-w-md bg-[#0d1117] border ${colors.border} rounded-xl shadow-2xl p-8 flex flex-col items-center text-center`}>

                {status === "running" || status === "initializing" || status === "pending" ? (
                    <>
                        <h3 className="text-xl font-bold text-white mb-2">Generating Data...</h3>
                        <p className="text-gray-400 text-sm mb-6">Using AI context and Faker algorithms</p>

                        <div className="w-full h-4 bg-[#21262d] rounded-full overflow-hidden mb-2 relative">
                            <div
                                className="h-full bg-blue-600 transition-all duration-300 ease-out relative"
                                style={{ width: `${progress}%` }}
                            >
                                <div className="absolute inset-0 bg-white/20 animate-pulse"></div>
                            </div>
                        </div>
                        <div className="flex justify-between w-full text-xs text-gray-400 font-mono mb-6">
                            <span>{progress}%</span>
                            <span>{status === "initializing" ? "Starting..." : "Processing..."}</span>
                        </div>

                        <button
                            onClick={handleCancel}
                            className="text-red-400 hover:text-red-300 text-sm border border-red-900/50 bg-red-900/10 px-4 py-2 rounded-md hover:bg-red-900/20 transition"
                        >
                            Cancel Generation
                        </button>
                    </>
                ) : status === "completed" ? (
                    <>
                        <div className="w-16 h-16 bg-green-900/20 text-green-400 rounded-full flex items-center justify-center mb-4 border border-green-900/50 animate-in zoom-in spin-in-12 duration-300">
                            <CheckCircle2 size={32} />
                        </div>
                        <h3 className="text-xl font-bold text-white mb-2">Generation Complete!</h3>
                        <p className="text-gray-400 text-sm mb-6">Your data is ready for download.</p>

                        <button
                            onClick={() => onComplete(jobId)}
                            className="bg-green-600 hover:bg-green-500 text-white font-bold px-6 py-2.5 rounded-md transition shadow-lg shadow-green-900/20 flex items-center gap-2 w-full justify-center"
                        >
                            <FileDown size={20} /> Download Result
                        </button>
                    </>
                ) : (
                    <>
                        <div className="w-16 h-16 bg-red-900/20 text-red-400 rounded-full flex items-center justify-center mb-4 border border-red-900/50">
                            <AlertTriangle size={32} />
                        </div>
                        <h3 className="text-xl font-bold text-white mb-2">
                            {status === "cancelled" ? "Cancelled" : "Failed"}
                        </h3>
                        <p className="text-red-300 text-sm mb-6">{error || "Operation was stopped."}</p>
                        <button
                            onClick={onClose}
                            className="bg-[#21262d] hover:bg-[#30363d] text-white px-6 py-2 rounded-md transition border border-[#30363d]"
                        >
                            Close
                        </button>
                    </>
                )}
            </div>
        </div>
    );
}

export default GenerationModal;