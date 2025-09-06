import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography, Alert, Space } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

const { Title, Text } = Typography;

interface LoginFormValues {
  email: string;
  password: string;
}

const LoginPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const login = useAuthStore(state => state.login);

  const onFinish = async (values: LoginFormValues) => {
    setLoading(true);
    setError(null);

    try {
      await login(values.email, values.password);
      navigate('/');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Ошибка входа';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ 
      minHeight: '100vh', 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
    }}>
      <Card 
        style={{ 
          width: 400, 
          boxShadow: '0 8px 32px rgba(0,0,0,0.1)',
          borderRadius: '12px'
        }}
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div style={{ textAlign: 'center' }}>
            <Title level={2} style={{ marginBottom: 8 }}>
              📚 Knowledge Base
            </Title>
            <Text type="secondary">
              Войдите в систему для доступа к базе знаний
            </Text>
          </div>

          {error && (
            <Alert
              message="Ошибка входа"
              description={error}
              type="error"
              showIcon
              closable
              onClose={() => setError(null)}
            />
          )}

          <Form
            name="login"
            onFinish={onFinish}
            autoComplete="off"
            size="large"
          >
            <Form.Item
              name="email"
              rules={[
                { required: true, message: 'Пожалуйста, введите email!' },
                { type: 'email', message: 'Введите корректный email!' }
              ]}
            >
              <Input
                prefix={<UserOutlined />}
                placeholder="Email"
                autoComplete="email"
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[
                { required: true, message: 'Пожалуйста, введите пароль!' },
                { min: 6, message: 'Пароль должен содержать минимум 6 символов!' }
              ]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="Пароль"
                autoComplete="current-password"
              />
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                style={{ width: '100%', height: '40px' }}
              >
                {loading ? 'Вход...' : 'Войти'}
              </Button>
            </Form.Item>
          </Form>

          <div style={{ textAlign: 'center' }}>
            <Text type="secondary" style={{ fontSize: '12px' }}>
              Тестовые данные: admin@test.com / Admin123!
            </Text>
          </div>
        </Space>
      </Card>
    </div>
  );
};

export default LoginPage;
