import React, { useEffect, useRef, useState } from 'react';
import { Button, Empty, ConfigProvider, Table, Input, Form, Checkbox, InputRef } from 'antd';
import type { ColumnsType } from 'antd/es/table';

// Define the data type for the table rows
interface DataType {
    key: string;
    value: string | number | boolean | null;
}

// Define the props for the EditableTable component
interface EditableTableProps {
    initialData: Record<string, string | number | boolean | null>;
    onUpdate: (updatedData: Record<string, string | number | boolean | null>) => void;
    metadata: Record<string, { type: string }>; // Metadata with property types
}

// Helper to convert values based on type
const convertToType = (value: any, type: string) => {
    switch (type) {
        case 'int64':
        case 'int32':
            return parseInt(value, 10);
        case 'float64':
            return parseFloat(value);
        case 'bool':
            return value === true || value === 'true';
        case 'string':
            return String(value);
        default:
            return value;
    }
};

const EditableTable: React.FC<EditableTableProps> = ({ initialData, onUpdate, metadata }) => {
    const [dataSource, setDataSource] = useState<DataType[]>(
        Object.entries(initialData).map(([key, value]) => ({ key, value }))
    );
    const [editingKey, setEditingKey] = useState<string>('');
    const [form] = Form.useForm();
    const inputRef = useRef<InputRef>(null); // Ref to manage focus
    const updatedValuesRef = useRef<Record<string, string | number | boolean | null>>({});

    // Function to check if the current row is being edited
    const isEditing = (record: DataType) => record.key === editingKey;

    // Function to toggle editing on a row
    const edit = (record: DataType) => {
        form.setFieldsValue({ value: record.value ?? '' });
        setEditingKey(record.key);
    };

    // Function to handle when the value of a non-boolean field is changed
    const handleValueChange = async (key: string) => {
        try {
            const row = await form.validateFields();
            const newData = [...dataSource];
            const index = newData.findIndex((item) => key === item.key);

            if (index > -1) {
                const item = newData[index];
                const valueType = metadata[key]?.type || 'string';
                const updatedValue = row.value === '' ? null : convertToType(row.value, valueType); // Set to null if empty

                newData.splice(index, 1, { ...item, value: updatedValue });
                setDataSource(newData);
                setEditingKey('');

                // Store the updated value in the ref
                updatedValuesRef.current[key] = updatedValue;

                // Notify the parent component of only the updated value
                onUpdate({ [key]: updatedValue });
            }
        } catch (errInfo) {
            console.log('Validation Failed:', errInfo);
        }
    };

    // Toggle the checkbox for boolean values directly in the table cell
    const handleCheckboxChange = (key: string, checked: boolean) => {
        const newData = [...dataSource];
        const index = newData.findIndex((item) => key === item.key);
        if (index > -1) {
            newData[index].value = checked; // Update the boolean value
            setDataSource(newData);

            // Store the updated value in the ref
            updatedValuesRef.current[key] = checked;

            // Notify the parent component of only the updated value
            onUpdate({ [key]: checked });
        }
    };

    // Auto-focus on the input when entering edit mode
    useEffect(() => {
        if (editingKey) {
            inputRef.current?.focus(); // Focus the input field when editing starts
        }
    }, [editingKey]);

    // Define columns for the table
    const columns: ColumnsType<DataType> = [
        {
            title: 'Key',
            dataIndex: 'key',
            width: '30%',
            key: 'key',
        },
        {
            title: 'Value',
            dataIndex: 'value',
            width: '50%',
            key: 'value',
            render: (_, record: DataType) => {
                const valueType = metadata[record.key]?.type || 'string';

                // Always display the checkbox for boolean values
                if (valueType === 'bool') {
                    return (
                        <Checkbox
                            checked={record.value === true}
                            onChange={(e) => handleCheckboxChange(record.key, e.target.checked)}
                        />
                    );
                }

                // Inline editing for other types (string, number)
                const editable = isEditing(record);
                return editable ? (
                    <Form.Item
                        name="value"
                        style={{ margin: 0 }}
                    >
                        <Input
                            ref={inputRef} // Attach input ref to control focus
                            onPressEnter={() => handleValueChange(record.key)} // Save on pressing Enter
                            onBlur={() => handleValueChange(record.key)} // Save on losing focus
                        />
                    </Form.Item>
                ) : (
                    <div onClick={() => edit(record)} style={{ cursor: 'pointer' }}>
                        {record.value != null && String(record.value).trim() !== ''
                            ? String(record.value)
                            : <span style={{ color: 'gray' }}>Click to edit</span>}
                    </div>
                );
            },
        },
    ];

    return (
        <ConfigProvider
            renderEmpty={() => (
                <Empty description="No Data">
                </Empty>
            )}
        >
            <Form form={form} component={false}>
                <Table
                    bordered
                    dataSource={dataSource}
                    columns={columns}
                    rowClassName="editable-row"
                    pagination={false}
                    scroll={{ y: 400 }}
                />
            </Form>
        </ConfigProvider>
    );
};

export default EditableTable;
