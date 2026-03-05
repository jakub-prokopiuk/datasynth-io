import { useState, useEffect } from 'react';
import { Download, Copy, Check, FileJson, AlertCircle, Info, Database, Table as TableIcon, Code } from 'lucide-react';
import { colors } from '../theme';

const ROW_LIMIT = 100;

function OutputDisplay({ loading, error, generatedData, config, onDownload, onPushToDb }) {
    const [copied, setCopied] = useState(false);
    const [activeTable, setActiveTable] = useState(null);
    const [viewMode, setViewMode] = useState('table');

    const rawData = generatedData?.data || generatedData;

    const isStructuredData = rawData && typeof rawData === 'object' && !Array.isArray(rawData);

    const tableNames = isStructuredData ? Object.keys(rawData) : [];

    useEffect(() => {
        if (tableNames.length > 0) {
            setActiveTable(tableNames[0]);
        }
    }, [generatedData]);

    const handleCopy = () => {
        if (!generatedData) return;
        const textToCopy = viewMode === 'table' && activeTable
            ? JSON.stringify(rawData[activeTable], null, 2)
            : JSON.stringify(rawData, null, 2);

        navigator.clipboard.writeText(textToCopy);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const renderCell = (value) => {
        if (value === null || value === undefined) return <span className="text-gray-600 italic">null</span>;
        if (typeof value === 'boolean') return <span className={value ? "text-green-400" : "text-red-400"}>{String(value)}</span>;
        if (typeof value === 'object') return JSON.stringify(value);
        return String(value);
    };

    if (loading) {
        return (
            <div className={`w-full md:w-7/12 lg:w-8/12 bg-[#0d1117] p-6 flex flex-col items-center justify-center text-center border-l ${colors.border}`}>
                <div className="relative w-24 h-24 mb-6">
                    <div className="absolute inset-0 border-4 border-blue-500/30 rounded-full animate-ping"></div>
                    <div className="absolute inset-0 border-4 border-t-blue-500 rounded-full animate-spin"></div>
                </div>
                <h3 className="text-xl font-bold text-white mb-2">Generating Dataset...</h3>
                <p className="text-gray-400 max-w-md">
                    Running complex Faker algorithms and resolving dependencies. <br />
                    Large datasets ({'>'}1000 rows) are processed asynchronously.
                </p>
            </div>
        );
    }

    if (error) {
        return (
            <div className={`w-full md:w-7/12 lg:w-8/12 bg-[#0d1117] p-6 flex flex-col items-center justify-center text-center border-l ${colors.border}`}>
                <div className="w-16 h-16 bg-red-900/20 text-red-500 rounded-full flex items-center justify-center mb-6 border border-red-500/20">
                    <AlertCircle size={32} />
                </div>
                <h3 className="text-xl font-bold text-white mb-2">Generation Failed</h3>
                <p className="text-red-400 max-w-md break-words font-mono text-sm bg-red-950/30 p-4 rounded border border-red-900/50">
                    {error}
                </p>
            </div>
        );
    }

    if (!generatedData) {
        return (
            <div className={`w-full md:w-7/12 lg:w-8/12 bg-[#0d1117] p-6 flex flex-col items-center justify-center text-center border-l ${colors.border}`}>
                <div className="w-16 h-16 bg-[#21262d] text-gray-500 rounded-full flex items-center justify-center mb-6">
                    <FileJson size={32} />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">Ready to Generate</h3>
                <p className="text-gray-400 text-sm max-w-sm">
                    Configure your schema on the left and click "Run Generation" to create your synthetic dataset.
                </p>
            </div>
        );
    }

    const currentRows = (isStructuredData && activeTable) ? rawData[activeTable] : [];
    const previewRows = currentRows.slice(0, ROW_LIMIT);
    const headers = previewRows.length > 0 ? Object.keys(previewRows[0]) : [];
    const totalRows = generatedData.total_rows || 0;
    const wasTruncated = totalRows > previewRows.length;

    return (
        <div className={`w-full md:w-7/12 lg:w-8/12 bg-[#0d1117] flex flex-col h-screen border-l ${colors.border}`}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-[#30363d] bg-[#161b22]">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-green-900/20 text-green-400 rounded border border-green-900/50">
                        <Check size={18} />
                    </div>
                    <div>
                        <h2 className="text-sm font-bold text-white">Generation Successful</h2>
                        <div className="flex items-center gap-2 text-xs text-gray-400">
                            <span>{totalRows} rows total</span>
                            <span className="w-1 h-1 bg-gray-600 rounded-full"></span>
                            <span className="uppercase">{config.output_format}</span>
                        </div>
                    </div>
                </div>

                <div className="flex gap-2">
                    <div className="flex bg-[#21262d] rounded-lg p-0.5 border border-[#30363d] mr-2">
                        <button
                            onClick={() => setViewMode('table')}
                            className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 transition ${viewMode === 'table' ? 'bg-[#30363d] text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'}`}
                        >
                            <TableIcon size={14} /> Table
                        </button>
                        <button
                            onClick={() => setViewMode('json')}
                            className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 transition ${viewMode === 'json' ? 'bg-[#30363d] text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'}`}
                        >
                            <Code size={14} /> JSON
                        </button>
                    </div>

                    <button
                        onClick={handleCopy}
                        className="p-2 text-gray-400 hover:text-white hover:bg-[#30363d] rounded transition"
                        title="Copy to Clipboard"
                    >
                        {copied ? <Check size={18} className="text-green-400" /> : <Copy size={18} />}
                    </button>

                    <button
                        onClick={onPushToDb}
                        className="flex items-center gap-2 bg-[#238636] hover:bg-[#2ea043] text-white px-4 py-2 rounded text-sm font-bold transition shadow-lg shadow-green-900/20"
                        title="Push directly to an external database"
                    >
                        <Database size={16} /> Push to DB
                    </button>

                    <button
                        onClick={onDownload}
                        className="flex items-center gap-2 bg-[#1f6feb] hover:bg-[#388bfd] text-white px-4 py-2 rounded text-sm font-bold transition shadow-lg shadow-blue-900/20"
                    >
                        <Download size={16} /> Download
                    </button>
                </div>
            </div>

            {isStructuredData && tableNames.length > 0 && viewMode === 'table' && (
                <div className="flex items-center gap-1 px-6 pt-4 border-b border-[#30363d] overflow-x-auto no-scrollbar">
                    {tableNames.map(name => (
                        <button
                            key={name}
                            onClick={() => setActiveTable(name)}
                            className={`px-4 py-2 text-xs font-bold uppercase tracking-wider border-b-2 transition whitespace-nowrap
                                ${activeTable === name
                                    ? 'border-blue-500 text-blue-400'
                                    : 'border-transparent text-gray-500 hover:text-gray-300 hover:border-gray-700'
                                }`}
                        >
                            {name} <span className="ml-1 opacity-50 text-[10px]">({rawData[name]?.length})</span>
                        </button>
                    ))}
                </div>
            )}

            {wasTruncated && (
                <div className="bg-blue-900/10 border-b border-blue-900/30 px-6 py-2 flex items-center gap-3">
                    <Info size={14} className="text-blue-400 flex-none" />
                    <p className="text-[11px] text-blue-300">
                        Preview truncated to first {ROW_LIMIT} rows. Download to see full data.
                    </p>
                </div>
            )}

            <div className="flex-1 overflow-auto bg-[#0d1117] relative p-6">

                {viewMode === 'table' && isStructuredData ? (
                    previewRows.length > 0 ? (
                        <div className="rounded-lg border border-[#30363d] overflow-hidden">
                            <table className="w-full text-left border-separate border-spacing-0">
                                <thead className="bg-[#161b22]">
                                    <tr>
                                        <th className="px-4 py-3 border-b border-r border-[#30363d] text-[10px] uppercase font-bold text-gray-400 w-12 text-center rounded-tl-lg">#</th>
                                        {headers.map((header, i) => (
                                            <th key={header} className={`px-4 py-3 border-b border-[#30363d] text-[10px] uppercase font-bold text-gray-400 whitespace-nowrap ${i === headers.length - 1 ? 'rounded-tr-lg' : 'border-r'}`}>
                                                {header}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-[#21262d]">
                                    {previewRows.map((row, idx) => (
                                        <tr key={idx} className="hover:bg-[#161b22] transition-colors group">
                                            <td className="px-4 py-2 border-r border-[#30363d] text-[10px] font-mono text-gray-600 text-center select-none bg-[#0d1117] group-hover:bg-[#161b22]">
                                                {idx + 1}
                                            </td>
                                            {headers.map((header, i) => (
                                                <td key={header} className={`px-4 py-2 text-xs font-mono text-gray-300 whitespace-nowrap max-w-[300px] overflow-hidden text-ellipsis ${i === headers.length - 1 ? '' : 'border-r border-[#30363d]'}`}>
                                                    {renderCell(row[header])}
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center h-full text-gray-500">
                            <p>No data in this table.</p>
                        </div>
                    )
                ) : (
                    <div className="rounded-lg border border-[#30363d] p-4 bg-[#0d1117] overflow-auto">
                        <pre className="font-mono text-xs leading-relaxed text-gray-300">
                            <code className="language-json">
                                {JSON.stringify(rawData, null, 2)}
                            </code>
                        </pre>
                    </div>
                )}
            </div>
        </div>
    );
}

export default OutputDisplay;