import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Table, 
  Button, 
  Space, 
  Tag, 
  Popconfirm, 
  Typography, 
  Alert,
  Card,
  Tooltip,
  Badge
} from 'antd';
import { 
  DeleteOutlined, 
  FileTextOutlined, 
  EyeOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  LoadingOutlined,
  BlockOutlined
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { Document } from '../../types';
import { useDocumentStore } from '../../store/documentStore';
import dayjs from 'dayjs';
import 'dayjs/locale/ru';

dayjs.locale('ru');

const { Title, Text } = Typography;

interface DocumentListProps {
  onDocumentSelect?: (document: Document) => void;
}

export const DocumentList: React.FC<DocumentListProps> = ({ 
  onDocumentSelect 
}) => {
  const navigate = useNavigate();
  const { documents, loading, error, fetchDocuments, deleteDocument } = useDocumentStore();
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    fetchDocuments().catch(console.error);
  }, [fetchDocuments]);

  // Отдельный useEffect для автообновления
  useEffect(() => {
    const interval = setInterval(() => {
      const hasProcessingDocs = documents.some(doc => 
        doc.status?.toLowerCase() === 'pending' || 
        doc.status?.toLowerCase() === 'processing'
      );
      
      if (hasProcessingDocs) {
        fetchDocuments().catch(console.error);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [documents, fetchDocuments]);

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await deleteDocument(id);
    } catch (err) {
      console.error('Error deleting document:', err);
    } finally {
      setDeletingId(null);
    }
  };

  const getStatusIcon = (status: Document['status']) => {
    const normalizedStatus = status?.toLowerCase();
    switch (normalizedStatus) {
      case 'pending':
        return <ClockCircleOutlined style={{ color: '#faad14' }} />;
      case 'processing':
        return <LoadingOutlined style={{ color: '#1890ff' }} />;
      case 'completed':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'failed':
      case 'error':
        return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
      default:
        return <ClockCircleOutlined />;
    }
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
        return 'Ожидает';
      case 'processing':
        return 'Обрабатывается';
      case 'completed':
        return 'Готов';
      case 'failed':
      case 'error':
        return 'Ошибка';
      default:
        return 'Неизвестно';
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const columns: ColumnsType<Document> = [
    {
      title: 'Документ',
      dataIndex: 'title',
      key: 'title',
      render: (title: string, record: Document) => (
        <Space>
          <FileTextOutlined style={{ color: '#1890ff' }} />
          <div>
            <div style={{ fontWeight: 500 }}>{title}</div>
            <Text type="secondary" style={{ fontSize: '12px' }}>
              {record.filename || record.metadata?.originalName || 'Неизвестный файл'}
            </Text>
          </div>
        </Space>
      ),
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: Document['status']) => (
        <Tag 
          icon={getStatusIcon(status)} 
          color={getStatusColor(status)}
        >
          {getStatusText(status)}
        </Tag>
      ),
    },
    {
      title: 'Размер',
      dataIndex: 'fileSize',
      key: 'fileSize',
      width: 100,
      render: (size: number, record: Document) => (
        <Text type="secondary">
          {size ? formatFileSize(size) : record.metadata?.size ? formatFileSize(record.metadata.size) : '—'}
        </Text>
      ),
    },
    {
      title: 'Уровень доступа',
      dataIndex: 'accessLevel',
      key: 'accessLevel',
      width: 120,
      render: (level: number) => (
        <Badge 
          count={level} 
          style={{ 
            backgroundColor: level >= 80 ? '#f50' : level >= 50 ? '#faad14' : '#52c41a' 
          }} 
        />
      ),
    },
    {
      title: 'Чанки',
      dataIndex: 'chunksCount',
      key: 'chunksCount',
      width: 80,
      render: (count?: number, record?: Document) => (
        <Text type="secondary">{count || record?.chunkCount || '—'}</Text>
      ),
    },
    {
      title: 'Дата создания',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 150,
      render: (date: string) => (
        <Tooltip title={dayjs(date).format('DD.MM.YYYY HH:mm:ss')}>
          <Text type="secondary">
            {dayjs(date).format('DD.MM.YY')}
          </Text>
        </Tooltip>
      ),
    },
    {
      title: 'Действия',
      key: 'actions',
      width: 160,
      render: (_, record: Document) => (
        <Space size="small">
          {onDocumentSelect && (
            <Tooltip title="Просмотр">
              <Button
                type="text"
                icon={<EyeOutlined />}
                onClick={() => onDocumentSelect(record)}
                disabled={record.status?.toLowerCase() !== 'completed'}
              />
            </Tooltip>
          )}
          <Tooltip title="Чанки">
            <Button
              type="text"
              icon={<BlockOutlined />}
              onClick={() => navigate(`/documents/${record.id}/chunks`)}
              disabled={record.status?.toLowerCase() !== 'completed'}
            />
          </Tooltip>
          <Popconfirm
            title="Удалить документ?"
            description="Это действие нельзя отменить"
            onConfirm={() => handleDelete(record.id)}
            okText="Да"
            cancelText="Нет"
            okType="danger"
          >
            <Tooltip title="Удалить">
              <Button
                type="text"
                danger
                icon={<DeleteOutlined />}
                loading={deletingId === record.id}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  if (error) {
    return (
      <Alert
        message="Ошибка загрузки документов"
        description={error}
        type="error"
        showIcon
        action={
          <Button size="small" onClick={() => fetchDocuments()}>
            Повторить
          </Button>
        }
      />
    );
  }

  return (
    <Card>
      <div style={{ marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          Документы ({documents.length})
        </Title>
        <Text type="secondary">
          Управление загруженными документами
        </Text>
      </div>

      <Table
        columns={columns}
        dataSource={documents}
        rowKey="id"
        loading={loading}
        pagination={{
          pageSize: 10,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total, range) =>
            `${range[0]}-${range[1]} из ${total} документов`,
        }}
        locale={{
          emptyText: (
            <div style={{ padding: '40px 0', textAlign: 'center' }}>
              <FileTextOutlined style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 16 }} />
              <div>
                <Text type="secondary">Документы не найдены</Text>
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  Загрузите первый документ для начала работы
                </Text>
              </div>
            </div>
          ),
        }}
        scroll={{ x: 800 }}
      />
    </Card>
  );
};

export default DocumentList;
