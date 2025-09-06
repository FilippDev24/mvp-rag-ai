import React from 'react';
import { Menu } from 'antd';
import { HomeOutlined, FileTextOutlined } from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

const Navigation: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    {
      key: '/',
      icon: <HomeOutlined />,
      label: 'Главная',
    },
    {
      key: '/documents',
      icon: <FileTextOutlined />,
      label: 'Документы',
    },
  ];

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  return (
    <Menu
      mode="horizontal"
      selectedKeys={[location.pathname]}
      style={{ border: 'none', flex: 1 }}
      items={menuItems}
      onClick={handleMenuClick}
    />
  );
};

export default Navigation;
