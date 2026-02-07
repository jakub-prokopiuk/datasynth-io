import { useState, useEffect } from 'react';
import { Wand2 } from 'lucide-react';
import { colors } from '../../theme';

import FieldHeader from './FieldHeader';
import ParamsManager from './params/ParamsManager';
import FieldActions from './FieldActions';

function SchemaBuilder({ onAddField, onUpdateField, onCancelEdit, existingFields, fieldToEdit, tables, activeTableId }) {
    const [fieldData, setFieldData] = useState({
        name: "",
        type: "faker",
        is_unique: false,
        dependencies: [],
        params: {}
    });

    useEffect(() => {
        if (fieldToEdit) {
            setFieldData({
                name: fieldToEdit.name,
                type: fieldToEdit.type,
                is_unique: fieldToEdit.is_unique || false,
                dependencies: fieldToEdit.dependencies || [],
                params: fieldToEdit.params || {}
            });
        } else {
            resetForm();
        }
    }, [fieldToEdit]);

    const resetForm = () => {
        setFieldData({
            name: "",
            type: "faker",
            is_unique: false,
            dependencies: [],
            params: { method: "uuid4" }
        });
    };

    const handleParamChange = (newParams) => {
        setFieldData(prev => {
            const updatedParams = { ...prev.params, ...newParams };
            let newDependencies = [];

            if (prev.type === 'template' && updatedParams.template) {
                const matches = updatedParams.template.match(/\{\{\s*([a-zA-Z0-9_.]+)\s*(?:\|[^}]+)?\}\}/g);
                if (matches) {
                    matches.forEach(m => {
                        const clean = m.replace(/\{\{|\}\}/g, '').split('|')[0].trim();
                        if (existingFields.some(f => f.name === clean)) {
                            newDependencies.push(clean);
                        } else if (clean.includes('.')) {
                            const parts = clean.split('.');
                            if (existingFields.some(f => f.name === parts[0])) {
                                newDependencies.push(parts[0]);
                            }
                        }
                    });
                }
            } else if (prev.type === 'foreign_key' && updatedParams.table_id) {
                const targetTable = tables.find(t => t.id === updatedParams.table_id);
                if (targetTable) {
                    newDependencies.push(`Table: ${targetTable.name}`);
                }
            }

            newDependencies = [...new Set(newDependencies)];

            return {
                ...prev,
                params: updatedParams,
                dependencies: newDependencies
            };
        });
    };

    const handleTypeChange = (newType) => {
        let defaultParams = {};
        if (newType === 'faker') defaultParams = { method: 'uuid4' };
        if (newType === 'integer') defaultParams = { min: 0, max: 100 };
        if (newType === 'boolean') defaultParams = { probability: 50 };
        if (newType === 'llm') defaultParams = { temperature: 1.0, top_p: 1.0 };

        setFieldData(prev => ({
            ...prev,
            type: newType,
            params: defaultParams
        }));
    };

    const handleSubmit = () => {
        if (!fieldData.name) return;

        const payload = { ...fieldData };

        if (fieldToEdit) {
            onUpdateField(payload);
        } else {
            onAddField(payload);
            resetForm();
        }
    };

    return (
        <section className="flex-1">
            <h2 className={`text-xs font-bold ${colors.textMuted} uppercase tracking-wider flex items-center gap-2 mb-4`}>
                <Wand2 size={14} /> Schema Builder
            </h2>

            <div className={`p-4 rounded-md border ${colors.border} ${fieldToEdit ? 'bg-blue-900/10 border-blue-500/30' : 'bg-[#0d1117]'} mb-6 transition-colors`}>

                <FieldHeader
                    name={fieldData.name}
                    type={fieldData.type}
                    isEditing={!!fieldToEdit}
                    onNameChange={(val) => setFieldData(prev => ({ ...prev, name: val }))}
                    onTypeChange={handleTypeChange}
                />

                <div className={`mb-4 p-3 rounded border border-dashed border-gray-700 bg-[#161b22]/50`}>
                    <ParamsManager
                        type={fieldData.type}
                        params={fieldData.params}
                        onChange={handleParamChange}
                        context={{
                            existingFields,
                            currentFieldName: fieldData.name,
                            tables,
                            activeTableId
                        }}
                    />
                </div>

                <FieldActions
                    isUnique={fieldData.is_unique}
                    onUniqueChange={(val) => setFieldData(prev => ({ ...prev, is_unique: val }))}
                    isEditing={!!fieldToEdit}
                    onCancel={onCancelEdit}
                    onSubmit={handleSubmit}
                />
            </div>
        </section>
    );
}

export default SchemaBuilder;