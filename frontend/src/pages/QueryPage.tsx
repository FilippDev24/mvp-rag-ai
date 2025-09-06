import React from 'react';
import { Typography } from 'antd';
import Chat from '../components/Chat/Chat';

const { Title, Text } = Typography;

const QueryPage: React.FC = () => {
  return (
    <div style={{ height: 'calc(100vh - 120px)' }}>
      <div style={{ marginBottom: 16 }}>
        <Title level={2} style={{ margin: 0 }}>
          💬 Чат с ИИ
        </Title>
        <Text type="secondary">
          Задавайте вопросы по загруженным документам
        </Text>
      </div>
      
      <div style={{ height: 'calc(100% - 60px)' }}>
        <Chat />
      </div>
    </div>
  );
};

export default QueryPage;
