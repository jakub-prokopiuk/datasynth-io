import { useState, useEffect } from 'react';

export function useSchema(initialTables) {
    const [tables, setTables] = useState(() => {
        const saved = sessionStorage.getItem('datasynth_tables');
        return saved ? JSON.parse(saved) : initialTables;
    });
    const [activeTableId, setActiveTableId] = useState(tables[0]?.id || null);
    const [editingIndex, setEditingIndex] = useState(null);

    useEffect(() => {
        sessionStorage.setItem('datasynth_tables', JSON.stringify(tables));
    }, [tables]);

    const activeTable = tables.find(t => t.id === activeTableId) || tables[0];
    const activeFields = activeTable ? activeTable.fields : [];

    const generateId = () => Math.random().toString(36).substring(2, 11);

    const addTable = () => {
        const newId = `t_${generateId()}`;
        const newTable = {
            id: newId,
            name: `table_${tables.length + 1}`,
            rows_count: 10,
            fields: [
                { name: "id", type: "faker", is_unique: true, dependencies: [], params: { method: "uuid4" } }
            ]
        };
        setTables([...tables, newTable]);
        setActiveTableId(newId);
    };

    const removeTable = (id) => {
        if (tables.length <= 1) return;
        const newTables = tables.filter(t => t.id !== id);
        setTables(newTables);
        if (activeTableId === id) setActiveTableId(newTables[0].id);
    };

    const updateTable = (id, updates) => {
        setTables(tables.map(t => t.id === id ? { ...t, ...updates } : t));
    };

    const addField = (newField) => {
        const updatedTable = { ...activeTable, fields: [...activeTable.fields, newField] };
        updateTable(activeTableId, updatedTable);
    };

    const updateField = (updatedField) => {
        const newFields = [...activeTable.fields];
        newFields[editingIndex] = updatedField;
        updateTable(activeTableId, { fields: newFields });
        setEditingIndex(null);
    };

    const removeField = (index) => {
        const newFields = [...activeTable.fields];
        newFields.splice(index, 1);
        updateTable(activeTableId, { fields: newFields });
        if (editingIndex === index) setEditingIndex(null);
    };

    const startEditing = (index) => setEditingIndex(index);
    const cancelEditing = () => setEditingIndex(null);

    return {
        tables,
        setTables,
        activeTableId,
        setActiveTableId,
        activeTable,
        activeFields,
        editingIndex,
        actions: {
            addTable,
            removeTable,
            updateTable,
            addField,
            updateField,
            removeField,
            startEditing,
            cancelEditing
        }
    };
}