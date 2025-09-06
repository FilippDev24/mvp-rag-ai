import React, { useEffect, useState } from 'react';
import { Row, Col, Typography, Card, Space, Button } from 'antd';
import { MessageOutlined, FileTextOutlined, RobotOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { apiClient } from '../services/api';
import Chat from '../components/Chat/Chat';

const { Title, Text, Paragraph } = Typography;

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuthStore();
  const [stats, setStats] = useState<{
    documentsCount: number;
    chunksCount: number;
    messagesCount: number;
  } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      loadStats();
    }
  }, [isAuthenticated]);

  const loadStats = async () => {
    try {
      setLoading(true);
      const data = await apiClient.getStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to load stats:', error);
    } finally {
      setLoading(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div style={{ 
        minHeight: '60vh', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center' 
      }}>
        <Card style={{ maxWidth: 600, textAlign: 'center' }}>
          <Space direction="vertical" size="large">
            <RobotOutlined style={{ fontSize: 64, color: '#1890ff' }} />
            <Title level={2}>Добро пожаловать в базу знаний</Title>
            <Paragraph type="secondary">
              Загружайте документы и задавайте вопросы с помощью ИИ
            </Paragraph>
            <Button 
              type="primary" 
              size="large"
              onClick={() => navigate('/login')}
            >
              Войти в систему
            </Button>
          </Space>
        </Card>
      </div>
    );
  }

  return (
    <div style={{ height: 'calc(100vh - 120px)' }}>
      <Row gutter={[16, 16]} style={{ height: '100%' }}>
        {/* Основной чат */}
        <Col xs={24} lg={18} style={{ height: '100%' }}>
          <Chat />
        </Col>

        {/* Правая панель - Статистика */}
        <Col xs={24} lg={6} style={{ height: '100%' }}>
          <Space direction="vertical" size="middle" style={{ width: '100%', height: '100%' }}>
            {/* Статистика */}
            <Card title="Статистика" size="small" loading={loading}>
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <div style={{ textAlign: 'center' }}>
                  <Title level={3} style={{ margin: 0, color: '#1890ff' }}>
                    {stats?.documentsCount ?? '—'}
                  </Title>
                  <Text type="secondary" style={{ fontSize: '14px' }}>
                    Документов в базе
                  </Text>
                </div>
                
                <div style={{ textAlign: 'center' }}>
                  <Title level={3} style={{ margin: 0, color: '#52c41a' }}>
                    {stats?.messagesCount ?? '—'}
                  </Title>
                  <Text type="secondary" style={{ fontSize: '14px' }}>
                    Всего запросов
                  </Text>
                </div>

                <div style={{ textAlign: 'center' }}>
                  <Title level={3} style={{ margin: 0, color: '#722ed1' }}>
                    {stats?.chunksCount ?? '—'}
                  </Title>
                  <Text type="secondary" style={{ fontSize: '14px' }}>
                    Фрагментов текста
                  </Text>
                </div>
              </Space>
            </Card>

            {/* Информация о пользователе */}
            <Card size="small">
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <div style={{ textAlign: 'center' }}>
                  <Text strong>{user?.name}</Text>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <Text type="secondary" style={{ fontSize: '12px' }}>
                    Уровень доступа: {user?.accessLevel}
                  </Text>
                </div>
              </Space>
            </Card>
          </Space>
        </Col>
      </Row>
    </div>
  );
};

export default HomePage;
