import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import { ConfigProvider, Layout, Menu, Button, Avatar, Dropdown, Space, Typography } from 'antd';
import { 
  HomeOutlined, 
  FileTextOutlined, 
  UserOutlined,
  LogoutOutlined,
  SettingOutlined
} from '@ant-design/icons';
import ruRU from 'antd/locale/ru_RU';

// Pages
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import DocumentsPage from './pages/DocumentsPage';

// Components
import ProtectedRoute from './components/ProtectedRoute';
import { ChunkPreview } from './components/ChunkPreview/ChunkPreview';
import Navigation from './components/Navigation';

// Store
import { useAuthStore } from './store/authStore';

const { Header, Content } = Layout;
const { Text } = Typography;

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  const { user, isAuthenticated, logout } = useAuthStore();

  // Убираем дублирующую инициализацию - Zustand persist уже делает это

  const handleLogout = () => {
    logout();
  };

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: 'Профиль',
      disabled: true,
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: 'Настройки',
      disabled: true,
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Выйти',
      onClick: handleLogout,
    },
  ];

  return (
    <ConfigProvider locale={ruRU}>
      <QueryClientProvider client={queryClient}>
        <Router>
          <Layout style={{ minHeight: '100vh' }}>
            {isAuthenticated && (
              <Header style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between',
                background: '#fff',
                borderBottom: '1px solid #f0f0f0',
                padding: '0 24px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <div style={{ 
                    fontSize: '20px', 
                    fontWeight: 'bold', 
                    marginRight: '32px',
                    color: '#1890ff'
                  }}>
                    📚 Knowledge Base
                  </div>
                  
                  <Navigation />
                </div>

                <Space>
                  <Text type="secondary">
                    Уровень доступа: {user?.accessLevel}
                  </Text>
                  <Dropdown
                    menu={{ items: userMenuItems }}
                    placement="bottomRight"
                    trigger={['click']}
                  >
                    <Button type="text" style={{ height: 'auto', padding: '4px 8px' }}>
                      <Space>
                        <Avatar 
                          size="small" 
                          icon={<UserOutlined />} 
                          style={{ backgroundColor: '#1890ff' }}
                        />
                        <span>{user?.name}</span>
                      </Space>
                    </Button>
                  </Dropdown>
                </Space>
              </Header>
            )}

            <Content style={{ 
              padding: isAuthenticated ? '24px' : '0',
              background: '#f5f5f5'
            }}>
              <Routes>
                <Route path="/login" element={
                  isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />
                } />
                
                <Route path="/" element={
                  <ProtectedRoute>
                    <HomePage />
                  </ProtectedRoute>
                } />
                
                <Route path="/documents" element={
                  <ProtectedRoute>
                    <DocumentsPage />
                  </ProtectedRoute>
                } />
                
                
                <Route path="/documents/:documentId/chunks" element={
                  <ProtectedRoute>
                    <ChunkPreview />
                  </ProtectedRoute>
                } />
                
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Content>
          </Layout>
        </Router>
      </QueryClientProvider>
    </ConfigProvider>
  );
}

export default App;
