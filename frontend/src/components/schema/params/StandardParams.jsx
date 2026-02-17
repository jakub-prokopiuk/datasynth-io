import { Hash, ToggleLeft, FileCode, Calendar, Link2, PieChart, Plus, Trash2, Percent, AlertTriangle, CheckCircle2, XCircle, Type } from 'lucide-react';
import { colors } from '../../../theme';
import CustomSelect from '../../ui/CustomSelect';

const NO_SPINNER_CLASS = "[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none";

const val = (v) => (v === undefined || v === null) ? "" : v;

const FAKER_OPTIONS = [
    { value: "uuid4", label: "UUID (Unique ID)" },
    { value: "name", label: "Full Name" },
    { value: "first_name", label: "First Name" },
    { value: "last_name", label: "Last Name" },
    { value: "user_name", label: "Username / Login" },
    { value: "email", label: "Email Address" },
    { value: "phone_number", label: "Phone Number" },
    { value: "job", label: "Job Title" },
    { value: "address", label: "Address (Full)" },
    { value: "street_address", label: "Street Address" },
    { value: "city", label: "City" },
    { value: "postcode", label: "Postal / Zip Code" },
    { value: "country", label: "Country" },
    { value: "state", label: "State / Province" },
    { value: "ipv4", label: "IP Address (v4)" },
    { value: "mac_address", label: "MAC Address" },
    { value: "url", label: "URL / Website" },
    { value: "file_name", label: "File Name" },
    { value: "file_extension", label: "File Extension" },
];

export function FakerParams({ params, onChange }) {
    return (
        <div>
            <label className={`block text-xs font-bold ${colors.textMuted} mb-1`}>Faker Method</label>
            <CustomSelect
                value={params.method || "uuid4"}
                onChange={val => onChange({ method: val })}
                options={FAKER_OPTIONS}
            />
        </div>
    );
}

export function IntegerParams({ params, onChange }) {
    const handleNum = (key, valueStr) => {
        if (valueStr === "") return onChange({ [key]: "" });
        const n = parseFloat(valueStr);
        onChange({ [key]: isNaN(n) ? valueStr : n });
    };

    return (
        <div className="space-y-3">
            <div className="flex items-start gap-2 p-2 rounded bg-indigo-900/20 border border-indigo-700/50 text-indigo-300 text-[10px] mb-2">
                <Hash size={12} className="mt-0.5 shrink-0" />
                <div><span className="font-bold">Number Range:</span> Generates random numbers between Min and Max (supports decimals).</div>
            </div>
            <div className="flex gap-4">
                <div className="flex-1">
                    <label className={`block text-xs font-bold ${colors.textMuted} mb-1`}>Min Value</label>
                    <input
                        type="number"
                        step="any"
                        value={val(params.min)}
                        onChange={e => handleNum("min", e.target.value)}
                        className={`w-full p-2 rounded border ${colors.border} bg-[#0d1117] text-white text-sm outline-none focus:border-blue-500 ${NO_SPINNER_CLASS}`}
                    />
                </div>
                <div className="flex-1">
                    <label className={`block text-xs font-bold ${colors.textMuted} mb-1`}>Max Value</label>
                    <input
                        type="number"
                        step="any"
                        value={val(params.max ?? 100)}
                        onChange={e => handleNum("max", e.target.value)}
                        className={`w-full p-2 rounded border ${colors.border} bg-[#0d1117] text-white text-sm outline-none focus:border-blue-500 ${NO_SPINNER_CLASS}`}
                    />
                </div>
            </div>
        </div>
    );
}

export function BooleanParams({ params, onChange }) {
    return (
        <div className="space-y-3">
            <div className="flex items-start gap-2 p-2 rounded bg-indigo-900/20 border border-indigo-700/50 text-indigo-300 text-[10px] mb-2">
                <ToggleLeft size={12} className="mt-0.5 shrink-0" />
                <div><span className="font-bold">Boolean Flag:</span> Generates True/False values.</div>
            </div>
            <div>
                <div className="flex justify-between items-center mb-1">
                    <label className={`block text-xs font-bold ${colors.textMuted}`}>Probability of TRUE</label>
                    <span className="text-xs font-mono text-blue-400">{params.probability ?? 50}%</span>
                </div>
                <input type="range" min="0" max="100" value={params.probability ?? 50} onChange={(e) => onChange({ probability: parseInt(e.target.value) })} className="w-full h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500" />
            </div>
        </div>
    );
}

export function RegexParams({ params, onChange }) {
    return (
        <div className="space-y-3">
            <div className="flex items-start gap-2 p-2 rounded bg-pink-900/20 border border-pink-700/50 text-pink-300 text-[10px] mb-2">
                <FileCode size={12} className="mt-0.5 shrink-0" />
                <div><span className="font-bold">Regex Pattern:</span> Uses `rstr` to generate matching strings. Example: <code className="bg-black/30 px-1 rounded">\d{2}-[A-Z]{3}</code></div>
            </div>
            <div>
                <label className={`block text-xs font-bold ${colors.textMuted} mb-1`}>Pattern</label>
                <input type="text" value={params.pattern || "\\d{2}-\\d{3}"} onChange={e => onChange({ pattern: e.target.value })} className={`w-full p-2 rounded border ${colors.border} bg-[#0d1117] text-white text-sm font-mono`} />
            </div>
        </div>
    );
}

export function TimestampParams({ params, onChange }) {
    return (
        <div className="space-y-3">
            <div className="flex items-start gap-2 p-2 rounded bg-cyan-900/20 border border-cyan-700/50 text-cyan-300 text-[10px] mb-2">
                <Calendar size={12} className="mt-0.5 shrink-0" />
                <div><span className="font-bold">Time Range:</span> Supports 'now', '-1y', '+30d', or 'YYYY-MM-DD'.</div>
            </div>
            <div className="flex gap-4">
                <div className="flex-1">
                    <label className={`block text-xs font-bold ${colors.textMuted} mb-1`}>Start Date</label>
                    <input type="text" value={params.min_date || "-1y"} onChange={e => onChange({ min_date: e.target.value })} className={`w-full p-2 rounded border ${colors.border} bg-[#0d1117] text-white text-sm`} />
                </div>
                <div className="flex-1">
                    <label className={`block text-xs font-bold ${colors.textMuted} mb-1`}>End Date</label>
                    <input type="text" value={params.max_date || "now"} onChange={e => onChange({ max_date: e.target.value })} className={`w-full p-2 rounded border ${colors.border} bg-[#0d1117] text-white text-sm`} />
                </div>
            </div>
            <div>
                <label className={`block text-xs font-bold ${colors.textMuted} mb-1`}>Output Format</label>
                <input type="text" value={params.format || "%Y-%m-%d %H:%M:%S"} onChange={e => onChange({ format: e.target.value })} className={`w-full p-2 rounded border ${colors.border} bg-[#0d1117] text-white text-sm font-mono`} />
            </div>
        </div>
    );
}

export function DistributionParams({ params, onChange }) {
    const options = params.options || ["Option A", "Option B"];
    const weights = params.weights || [50, 50];

    const totalWeight = weights.reduce((a, b) => a + (parseFloat(b) || 0), 0);
    const isExact = Math.abs(totalWeight - 100) < 0.01;
    const isZero = totalWeight === 0;

    const handleUpdateOption = (index, value) => {
        const newOptions = [...options];
        newOptions[index] = value;
        onChange({ options: newOptions, weights: weights });
    };

    const handleUpdateWeight = (index, valueStr) => {
        const newWeights = [...weights];
        if (valueStr === "") {
            newWeights[index] = "";
        } else {
            const n = parseFloat(valueStr);
            newWeights[index] = isNaN(n) ? valueStr : n;
        }
        onChange({ options: options, weights: newWeights });
    };

    const handleAdd = () => {
        onChange({
            options: [...options, `Option ${options.length + 1}`],
            weights: [...weights, 10]
        });
    };

    const handleRemove = (index) => {
        if (options.length <= 1) return;
        const newOptions = options.filter((_, i) => i !== index);
        const newWeights = weights.filter((_, i) => i !== index);
        onChange({ options: newOptions, weights: newWeights });
    };

    return (
        <div className="space-y-3">
            <div className="flex items-start gap-2 p-2 rounded bg-orange-900/20 border border-orange-700/50 text-orange-300 text-[10px] mb-2">
                <PieChart size={12} className="mt-0.5 shrink-0" />
                <div><span className="font-bold">Weighted Random:</span> Define options and their relative probability weights.</div>
            </div>

            <div className="space-y-2">
                <div className="flex justify-between text-[10px] text-gray-500 font-bold px-1">
                    <span>Option Label</span>
                    <span>Weight</span>
                </div>

                {options.map((opt, i) => (
                    <div key={i} className="flex gap-2 items-center">
                        <input
                            type="text"
                            value={opt}
                            onChange={(e) => handleUpdateOption(i, e.target.value)}
                            className={`flex-1 p-2 rounded border ${colors.border} bg-[#0d1117] text-white text-sm`}
                            placeholder="Value"
                        />
                        <div className="relative w-20">
                            <input
                                type="number"
                                step="any"
                                value={val(weights[i])}
                                onChange={(e) => handleUpdateWeight(i, e.target.value)}
                                className={`w-full p-2 rounded border ${colors.border} bg-[#0d1117] text-white text-sm text-right pr-6 outline-none focus:border-blue-500 ${NO_SPINNER_CLASS}`}
                            />
                            <div className="absolute right-2 top-2.5 text-gray-500 pointer-events-none">
                                <Percent size={10} />
                            </div>
                        </div>
                        <button
                            onClick={() => handleRemove(i)}
                            className="p-2 text-gray-500 hover:text-red-400 hover:bg-gray-800 rounded transition"
                            disabled={options.length <= 1}
                        >
                            <Trash2 size={14} />
                        </button>
                    </div>
                ))}
            </div>

            <div className="flex justify-between items-center pt-2 border-t border-[#30363d] mt-2">
                <div className={`text-[10px] flex items-center gap-1.5 ${isZero ? 'text-red-400' : (isExact ? 'text-green-500' : 'text-orange-400')}`}>
                    {isZero ? <XCircle size={12} /> : (isExact ? <CheckCircle2 size={12} /> : <AlertTriangle size={12} />)}
                    <span className="font-bold">Total: {totalWeight.toFixed(2)}</span>
                </div>
                <button
                    onClick={handleAdd}
                    className="text-[10px] flex items-center gap-1 bg-gray-800 hover:bg-gray-700 text-gray-200 px-2 py-1 rounded border border-gray-700 transition"
                >
                    <Plus size={10} /> Add Option
                </button>
            </div>
        </div>
    );
}

export function ForeignKeyParams({ params, onChange, context }) {
    const { tables, activeTableId } = context;
    const targetTableObj = tables.find(t => t.id === params.table_id);
    const targetColumns = targetTableObj ? targetTableObj.fields : [];

    const tableOptions = tables
        .filter(t => t.id !== activeTableId)
        .map(t => ({ value: t.id, label: `${t.name} (${t.rows_count} rows)` }));

    const columnOptions = targetColumns.map(col => ({
        value: col.name,
        label: `${col.name} (${col.type})`
    }));

    return (
        <div className="space-y-3">
            <div className="flex items-start gap-2 p-2 rounded bg-blue-900/20 border border-blue-700/50 text-blue-300 text-[10px] mb-2"><Link2 size={12} className="mt-0.5 shrink-0" /><div><span className="font-bold">Relation:</span> Select a source table.</div></div>
            <div>
                <label className={`block text-xs font-bold ${colors.textMuted} mb-1`}>Source Table</label>
                <CustomSelect
                    value={params.table_id || ""}
                    onChange={val => onChange({ table_id: val, column_name: "" })}
                    options={tableOptions}
                    placeholder="-- Select Table --"
                />
            </div>
            <div>
                <label className={`block text-xs font-bold ${colors.textMuted} mb-1`}>Source Column</label>
                <CustomSelect
                    value={params.column_name || ""}
                    onChange={val => onChange({ column_name: val })}
                    options={columnOptions}
                    disabled={!params.table_id}
                    placeholder="-- Select Column --"
                />
            </div>
        </div>
    );
}