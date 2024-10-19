import React, { useState } from 'react';
import { Modal, Form, Input, Button, FloatButton, ConfigProvider, theme } from 'antd';
import { SettingOutlined } from '@ant-design/icons';
import { useAppDispatch, useAppSelector } from '@/common';
import { setAgentSettings } from '@/store/reducers/global';

interface FormValues {
    greeting: string;
    prompt: string;
}

const FormModal: React.FC = () => {
    const [isModalVisible, setIsModalVisible] = useState(false);
    const [form] = Form.useForm<FormValues>();
    const dispatch = useAppDispatch();
    const agentSettings = useAppSelector(state => state.global.agentSettings);

    const showModal = () => {
        form.setFieldsValue(agentSettings);
        setIsModalVisible(true);
    };

    const handleOk = async () => {
        try {
            const values = await form.validateFields();
            console.log('Form Values:', values);
            // Handle the form submission logic here
            dispatch(setAgentSettings(values));
            setIsModalVisible(false);
            form.resetFields();
        } catch (errorInfo) {
            console.log('Validate Failed:', errorInfo);
        }
    };

    const handleCancel = () => {
        setIsModalVisible(false);
    };

    return (
        <>
            <ConfigProvider
                theme={
                    {
                        algorithm: theme.darkAlgorithm,
                        components: {
                            Modal: {
                                contentBg: "#272A2F",
                                headerBg: "#272A2F",
                                footerBg: "#272A2F",
                            }
                        }
                    }
                }>
                <FloatButton type="primary" icon={<SettingOutlined></SettingOutlined>} onClick={showModal}>
                </FloatButton>
                <Modal
                    title="Settings"
                    visible={isModalVisible}
                    onOk={handleOk}
                    onCancel={handleCancel}
                    okText="OK"
                    cancelText="Cancel"
                >
                    <Form
                        form={form}
                        layout="vertical"
                        name="form_in_modal"
                    >
                        <Form.Item
                            name="greeting"
                            label="Greeting"
                        >
                            <Input.TextArea rows={2} placeholder="Enter the greeting, leave it blank if you want to use default one." />
                        </Form.Item>

                        <Form.Item
                            name="prompt"
                            label="Prompt"
                        >
                            <Input.TextArea rows={4} placeholder="Enter the prompt, leave it blank if you want to use default one." />
                        </Form.Item>
                    </Form>
                </Modal>
            </ConfigProvider>
        </>
    );
};

export default FormModal;
