import React, { useState, useEffect } from 'react';
import { 
  Upload, 
  Button, 
  Form, 
  Input, 
  InputNumber, 
  Modal, 
  Alert, 
  Progress,
  Typography,
  Space
} from 'antd';
import { UploadOutlined, FileTextOutlined } from '@ant-design/icons';
import type { UploadFile, UploadProps } from 'antd/es/upload/interface';
import { Document } from '../../types';

const { Title, Text } = Typography;

interface DocumentUploadProps {
  onSuccess: (doc: Document) => void;
  onError: (error: string) => void;
}

interface UploadFormValues {
  title: string;
  accessLevel: number;
}

export const DocumentUpload: React.FC<DocumentUploadProps> = ({ 
  onSuccess, 
  onError 
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploadProgress, setUploadProgress] = useState(0);

  // ОБЯЗАТЕЛЬНО: cleanup в useEffect
  useEffect(() => {
    return () => {
      // Очистка файлов при размонтировании
      setFileList([]);
      setError(null);
      setUploadProgress(0);
    };
  }, []);

  const handleUpload = async (values: UploadFormValues) => {
    if (fileList.length === 0) {
      setError('Пожалуйста, выберите файл для загрузки');
      return;
    }

    const file = fileList[0].originFileObj;
    if (!file) {
      setError('Ошибка при получении файла');
      return;
    }

    setLoading(true);
    setError(null);
    setUploadProgress(0);

    try {
      // Симуляция прогресса загрузки
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return prev;
          }
          return prev + 10;
        });
      }, 200);

      // Импортируем store динамически, чтобы избежать циклических зависимостей
      const { useDocumentStore } = await import('../../store/documentStore');
      const uploadDocument = useDocumentStore.getState().uploadDocument;
      
      await uploadDocument(file, values.title, values.accessLevel);
      
      clearInterval(progressInterval);
      setUploadProgress(100);
      
      // Успешная загрузка
      setTimeout(() => {
        setFileList([]);
        form.resetFields();
        setUploadProgress(0);
        setLoading(false);
        
        // Создаем mock документ для onSuccess (реальный документ будет в store)
        const mockDoc: Document = {
          id: Date.now().toString(),
          title: values.title,
          filename: file.name,
          fileSize: file.size,
          mimeType: file.type,
          accessLevel: values.accessLevel,
          status: 'pending',
          userId: 'current-user',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };
        
        onSuccess(mockDoc);
      }, 500);
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Ошибка загрузки файла';
      setError(errorMessage);
      setLoading(false);
      setUploadProgress(0);
      onError(errorMessage);
    }
  };

  const uploadProps: UploadProps = {
    fileList,
    beforeUpload: (file) => {
      // Проверка типа файла
      const allowedTypes = [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword',
        'text/plain',
        'text/csv',
        'application/json'
      ];
      
      if (!allowedTypes.includes(file.type)) {
        setError('Поддерживаются только файлы: PDF, DOCX, DOC, TXT, CSV, JSON');
        return false;
      }

      // Проверка размера файла (10MB)
      const maxSize = 10 * 1024 * 1024;
      if (file.size > maxSize) {
        setError('Размер файла не должен превышать 10MB');
        return false;
      }

      setError(null);
      return false; // Предотвращаем автоматическую загрузку
    },
    onChange: ({ fileList: newFileList }) => {
      const newFile = newFileList.slice(-1); // Оставляем только последний файл
      setFileList(newFile);
      
      // Автоматически заполняем название документа из имени файла
      if (newFile.length > 0 && newFile[0].name) {
        // Убираем расширение из имени файла
        const fileName = newFile[0].name;
        const nameWithoutExtension = fileName.substring(0, fileName.lastIndexOf('.')) || fileName;
        
        // Заполняем поле title только если оно пустое
        const currentTitle = form.getFieldValue('title');
        if (!currentTitle || currentTitle.trim() === '') {
          form.setFieldsValue({
            title: nameWithoutExtension
          });
        }
      }
    },
    onRemove: () => {
      setFileList([]);
      setError(null);
    },
    maxCount: 1,
    accept: '.pdf,.docx,.doc,.txt,.csv,.json',
  };

  return (
    <div style={{ maxWidth: 600, margin: '0 auto' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div style={{ textAlign: 'center' }}>
          <FileTextOutlined style={{ fontSize: 48, color: '#1890ff', marginBottom: 16 }} />
          <Title level={3}>Загрузка документа</Title>
          <Text type="secondary">
            Поддерживаются файлы: PDF, DOCX, DOC, TXT, CSV, JSON (до 10MB)
          </Text>
        </div>

        {error && (
          <Alert
            message="Ошибка"
            description={error}
            type="error"
            showIcon
            closable
            onClose={() => setError(null)}
          />
        )}

        <Form
          form={form}
          layout="vertical"
          onFinish={handleUpload}
          initialValues={{
            accessLevel: 50
          }}
        >
          <Form.Item
            name="title"
            label="Название документа"
            rules={[
              { required: true, message: 'Пожалуйста, введите название документа!' },
              { min: 3, message: 'Название должно содержать минимум 3 символа!' },
              { max: 255, message: 'Название не должно превышать 255 символов!' }
            ]}
            extra="Название автоматически заполнится из имени файла"
          >
            <Input 
              placeholder="Название заполнится автоматически при выборе файла"
              size="large"
            />
          </Form.Item>

          <Form.Item
            name="accessLevel"
            label="Уровень доступа"
            rules={[
              { required: true, message: 'Пожалуйста, укажите уровень доступа!' },
              { type: 'number', min: 1, max: 100, message: 'Уровень доступа должен быть от 1 до 100!' }
            ]}
          >
            <InputNumber
              min={1}
              max={100}
              style={{ width: '100%' }}
              size="large"
              placeholder="Уровень доступа (1-100)"
            />
          </Form.Item>

          <Form.Item
            label="Файл"
            required
          >
            <Upload.Dragger {...uploadProps} style={{ padding: '20px' }}>
              <p className="ant-upload-drag-icon">
                <UploadOutlined style={{ fontSize: 48, color: '#1890ff' }} />
              </p>
              <p className="ant-upload-text">
                Нажмите или перетащите файл в эту область
              </p>
              <p className="ant-upload-hint">
                Поддерживается загрузка одного файла за раз
              </p>
            </Upload.Dragger>
          </Form.Item>

          {loading && uploadProgress > 0 && (
            <Form.Item>
              <Progress 
                percent={uploadProgress} 
                status={uploadProgress === 100 ? 'success' : 'active'}
                strokeColor={{
                  '0%': '#108ee9',
                  '100%': '#87d068',
                }}
              />
            </Form.Item>
          )}

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              disabled={fileList.length === 0}
              size="large"
              style={{ width: '100%' }}
            >
              {loading ? 'Загрузка...' : 'Загрузить документ'}
            </Button>
          </Form.Item>
        </Form>
      </Space>
    </div>
  );
};

export default DocumentUpload;
