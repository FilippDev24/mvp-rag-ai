import React, { useState } from 'react';
import { Row, Col, Typography, Button, Modal, message, Descriptions, Tag, Space } from 'antd';
import { PlusOutlined, FileTextOutlined, CalendarOutlined, UserOutlined, LockOutlined } from '@ant-design/icons';
import DocumentUpload from '../components/DocumentUpload/DocumentUpload';
import DocumentList from '../components/DocumentList/DocumentList';
import { Document } from '../types';
import dayjs from 'dayjs';

const { Title, Text } = Typography;

const DocumentsPage: React.FC = () => {
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [documentViewVisible, setDocumentViewVisible] = useState(false);

  const handleUploadSuccess = (document: Document) => {
    message.success(`Документ "${document.title}" успешно загружен!`);
    setUploadModalVisible(false);
  };

  const handleUploadError = (error: string) => {
    message.error(`Ошибка загрузки: ${error}`);
  };

  const handleDocumentSelect = (document: Document) => {
    setSelectedDocument(document);
    setDocumentViewVisible(true);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getStatusColor = (status: Document['status']) => {
    const normalizedStatus = status?.toLowerCase();
    switch (normalizedStatus) {
      case 'pending':
        return 'warning';
      case 'processing':
        return 'processing';
      case 'completed':
        return 'success';
      case 'failed':
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };

  const getStatusText = (status: Document['status']) => {
    const normalizedStatus = status?.toLowerCase();
    switch (normalizedStatus) {
      case 'pending':
        return 'Ожидает обработки';
      case 'processing':
        return 'Обрабатывается';
      case 'completed':
        return 'Готов к использованию';
      case 'failed':
      case 'error':
        return 'Ошибка обработки';
      default:
        return 'Неизвестный статус';
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: 8
        }}>
          <Title level={2} style={{ margin: 0 }}>
            📄 Управление документами
          </Title>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setUploadModalVisible(true)}
          >
            Загрузить документ
          </Button>
        </div>
        <Text type="secondary">
          Загружайте и управляйте документами для работы с ИИ
        </Text>
      </div>

      <Row gutter={[24, 24]}>
        <Col span={24}>
          <DocumentList onDocumentSelect={handleDocumentSelect} />
        </Col>
      </Row>

      <Modal
        title="Загрузка документа"
        open={uploadModalVisible}
        onCancel={() => setUploadModalVisible(false)}
        footer={null}
        width={700}
        destroyOnHidden
      >
        <DocumentUpload
          onSuccess={handleUploadSuccess}
          onError={handleUploadError}
        />
      </Modal>

      <Modal
        title={
          <Space>
            <FileTextOutlined />
            Информация о документе
          </Space>
        }
        open={documentViewVisible}
        onCancel={() => {
          setDocumentViewVisible(false);
          setSelectedDocument(null);
        }}
        footer={[
          <Button key="close" onClick={() => {
            setDocumentViewVisible(false);
            setSelectedDocument(null);
          }}>
            Закрыть
          </Button>
        ]}
        width={800}
      >
        {selectedDocument && (
          <div>
            <Descriptions
              title={selectedDocument.title}
              bordered
              column={2}
              size="small"
            >
              <Descriptions.Item label="Статус" span={2}>
                <Tag color={getStatusColor(selectedDocument.status)}>
                  {getStatusText(selectedDocument.status)}
                </Tag>
              </Descriptions.Item>
              
              <Descriptions.Item label="Имя файла">
                {selectedDocument.filename || selectedDocument.metadata?.originalName || 'Неизвестно'}
              </Descriptions.Item>
              
              <Descriptions.Item label="Размер файла">
                {selectedDocument.fileSize 
                  ? formatFileSize(selectedDocument.fileSize)
                  : selectedDocument.metadata?.size 
                    ? formatFileSize(selectedDocument.metadata.size)
                    : 'Неизвестно'
                }
              </Descriptions.Item>
              
              <Descriptions.Item label="Тип файла">
                {selectedDocument.mimeType || selectedDocument.metadata?.mimeType || 'Неизвестно'}
              </Descriptions.Item>
              
              <Descriptions.Item label="Уровень доступа">
                <Tag color={selectedDocument.accessLevel >= 80 ? 'red' : selectedDocument.accessLevel >= 50 ? 'orange' : 'green'}>
                  <LockOutlined /> {selectedDocument.accessLevel}
                </Tag>
              </Descriptions.Item>
              
              <Descriptions.Item label="Количество чанков">
                {selectedDocument.chunkCount || selectedDocument.chunksCount || '—'}
              </Descriptions.Item>
              
              <Descriptions.Item label="ID документа">
                <Text code copyable>{selectedDocument.id}</Text>
              </Descriptions.Item>
              
              <Descriptions.Item label="Дата создания">
                <Space>
                  <CalendarOutlined />
                  {dayjs(selectedDocument.createdAt).format('DD.MM.YYYY HH:mm:ss')}
                </Space>
              </Descriptions.Item>
              
              <Descriptions.Item label="Дата обновления">
                <Space>
                  <CalendarOutlined />
                  {selectedDocument.updatedAt 
                    ? dayjs(selectedDocument.updatedAt).format('DD.MM.YYYY HH:mm:ss')
                    : 'Не обновлялся'
                  }
                </Space>
              </Descriptions.Item>
              
              {selectedDocument.metadata && Object.keys(selectedDocument.metadata).length > 0 && (
                <Descriptions.Item label="Метаданные" span={2}>
                  <Text code style={{ whiteSpace: 'pre-wrap' }}>
                    {JSON.stringify(selectedDocument.metadata, null, 2)}
                  </Text>
                </Descriptions.Item>
              )}
            </Descriptions>
            
            {selectedDocument.status?.toLowerCase() === 'completed' && (
              <div style={{ marginTop: 16, textAlign: 'center' }}>
                <Space>
                  <Button 
                    type="primary" 
                    onClick={() => {
                      setDocumentViewVisible(false);
                      setSelectedDocument(null);
                      window.location.href = `/documents/${selectedDocument.id}/chunks`;
                    }}
                  >
                    Просмотреть чанки
                  </Button>
                  <Button 
                    onClick={() => {
                      setDocumentViewVisible(false);
                      setSelectedDocument(null);
                      window.location.href = `/query?doc=${selectedDocument.id}`;
                    }}
                  >
                    Задать вопрос по документу
                  </Button>
                </Space>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default DocumentsPage;
