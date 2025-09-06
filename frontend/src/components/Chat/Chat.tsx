import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { 
  Card, 
  Input, 
  Button, 
  Space, 
  Typography, 
  Avatar, 
  Divider,
  Alert,
  Tag,
  Collapse,
  Empty,
  Spin,
  List,
  Drawer,
  Tooltip,
  Popconfirm
} from 'antd';
import { 
  SendOutlined, 
  UserOutlined, 
  RobotOutlined,
  FileTextOutlined,
  ClearOutlined,
  MessageOutlined,
  HistoryOutlined,
  DeleteOutlined,
  PlusOutlined,
  BugOutlined
} from '@ant-design/icons';
import { ChatMessage, DocumentChunk } from '../../types';
import { useChatStore } from '../../store/chatStore';
import { useAuthStore } from '../../store/authStore';
import { CalendarDebug } from '../CalendarDebug/CalendarDebug';
import dayjs from 'dayjs';

const { TextArea } = Input;
const { Text, Title } = Typography;
const { Panel } = Collapse;

interface ChatProps {
  className?: string;
}

export const Chat: React.FC<ChatProps> = ({ className }) => {
  const [message, setMessage] = useState('');
  const [inputHeight, setInputHeight] = useState(40);
  // ИСПРАВЛЕНИЕ: Убираем состояние debugMode - отладка всегда включена
  const debugMode = true; // Всегда показываем отладочную информацию
  const [calendarDebugInfo, setCalendarDebugInfo] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<any>(null);
  
  const { 
    messages, 
    loading, 
    error, 
    sessions, 
    sessionsLoading, 
    conversationId,
    currentStatus,
    sendMessage, 
    clearChat, 
    loadSessions, 
    selectSession, 
    deleteSession 
  } = useChatStore();
  const { user } = useAuthStore();

  // Автоскролл к последнему сообщению (только когда не идет загрузка)
  useEffect(() => {
    if (!loading) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, loading]);

  // Фокус на input при загрузке
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // КРИТИЧНО: Загрузка истории сессий при входе пользователя
  useEffect(() => {
    if (user) {
      loadSessions();
    }
  }, [user, loadSessions]);

  const handleSend = async () => {
    if (!message.trim() || loading) return;

    const messageToSend = message.trim();
    setMessage('');
    setInputHeight(40);

    try {
      await sendMessage(messageToSend);
    } catch (err) {
      console.error('Error sending message:', err);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClearChat = () => {
    clearChat();
    inputRef.current?.focus();
  };

  const handleSelectSession = async (sessionId: string) => {
    try {
      await selectSession(sessionId);
    } catch (err) {
      console.error('Error selecting session:', err);
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await deleteSession(sessionId);
    } catch (err) {
      console.error('Error deleting session:', err);
    }
  };

  const handleNewChat = () => {
    clearChat();
    inputRef.current?.focus();
  };

  const renderMessage = (msg: ChatMessage) => {
    const isUser = msg.role === 'user';
    
    return (
      <div
        key={msg.id}
        style={{
          display: 'flex',
          justifyContent: isUser ? 'flex-end' : 'flex-start',
          marginBottom: 16,
        }}
      >
        <div
          style={{
            maxWidth: '70%',
            display: 'flex',
            flexDirection: isUser ? 'row-reverse' : 'row',
            alignItems: 'flex-start',
            gap: 8,
          }}
        >
          <Avatar
            icon={isUser ? <UserOutlined /> : <RobotOutlined />}
            style={{
              backgroundColor: isUser ? '#1890ff' : '#52c41a',
              flexShrink: 0,
            }}
          />
          
          <div style={{ flex: 1 }}>
            <Card
              size="small"
              style={{
                backgroundColor: isUser ? '#e6f7ff' : '#f6ffed',
                border: `1px solid ${isUser ? '#91d5ff' : '#b7eb8f'}`,
                borderRadius: '12px',
              }}
              styles={{ body: { padding: '12px 16px' } }}
            >
              <div style={{ wordBreak: 'break-word' }}>
                {isUser ? (
                  <div style={{ whiteSpace: 'pre-wrap' }}>
                    {msg.content}
                  </div>
                ) : (
                  <ReactMarkdown
                    components={{
                      // Стилизация заголовков
                      h1: ({ children }) => (
                        <h1 style={{ fontSize: '18px', fontWeight: 'bold', margin: '12px 0 8px 0', color: '#262626' }}>
                          {children}
                        </h1>
                      ),
                      h2: ({ children }) => (
                        <h2 style={{ fontSize: '16px', fontWeight: 'bold', margin: '10px 0 6px 0', color: '#262626' }}>
                          {children}
                        </h2>
                      ),
                      h3: ({ children }) => (
                        <h3 style={{ fontSize: '14px', fontWeight: 'bold', margin: '8px 0 4px 0', color: '#262626' }}>
                          {children}
                        </h3>
                      ),
                      // Стилизация списков
                      ul: ({ children }) => (
                        <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
                          {children}
                        </ul>
                      ),
                      ol: ({ children }) => (
                        <ol style={{ margin: '8px 0', paddingLeft: '20px' }}>
                          {children}
                        </ol>
                      ),
                      li: ({ children }) => (
                        <li style={{ margin: '2px 0', lineHeight: '1.5' }}>
                          {children}
                        </li>
                      ),
                      // Стилизация параграфов
                      p: ({ children }) => (
                        <p style={{ margin: '8px 0', lineHeight: '1.5' }}>
                          {children}
                        </p>
                      ),
                      // Стилизация жирного текста
                      strong: ({ children }) => (
                        <strong style={{ fontWeight: 'bold', color: '#262626' }}>
                          {children}
                        </strong>
                      ),
                      // Стилизация кода
                      code: ({ children }) => (
                        <code style={{ 
                          backgroundColor: '#f5f5f5', 
                          padding: '2px 4px', 
                          borderRadius: '3px',
                          fontSize: '13px',
                          fontFamily: 'monospace'
                        }}>
                          {children}
                        </code>
                      ),
                      // Стилизация блоков кода
                      pre: ({ children }) => (
                        <pre style={{ 
                          backgroundColor: '#f5f5f5', 
                          padding: '12px', 
                          borderRadius: '6px',
                          overflow: 'auto',
                          fontSize: '13px',
                          fontFamily: 'monospace',
                          margin: '8px 0'
                        }}>
                          {children}
                        </pre>
                      )
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                )}
              </div>
              
              {msg.sources && msg.sources.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <Divider style={{ margin: '8px 0' }} />
                  <Collapse size="small" ghost>
                    <Panel
                      header={
                        <Space size="small">
                          <FileTextOutlined />
                          <Text type="secondary" style={{ fontSize: '12px' }}>
                            Источники ({msg.sources.length})
                          </Text>
                        </Space>
                      }
                      key="sources"
                    >
                      <Space direction="vertical" size="small" style={{ width: '100%' }}>
                        {msg.sources.map((source, index) => (
                          <Card
                            key={source.id}
                            size="small"
                            style={{ backgroundColor: '#fafafa' }}
                          >
                            <Space direction="vertical" size="small" style={{ width: '100%' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <Text strong style={{ fontSize: '12px' }}>
                                  {source.documentTitle}
                                </Text>
                                {(source.relevance || source.similarity) && (
                                  <Tag color="blue" style={{ fontSize: '10px' }}>
                                    {Math.round(((source.relevance || source.similarity) || 0) * 100)}%
                                  </Tag>
                                )}
                              </div>
                              <Text 
                                style={{ 
                                  fontSize: '11px', 
                                  color: '#666',
                                  display: '-webkit-box',
                                  WebkitLineClamp: 3,
                                  WebkitBoxOrient: 'vertical',
                                  overflow: 'hidden'
                                }}
                              >
                                {source.content}
                              </Text>
                            </Space>
                          </Card>
                        ))}
                      </Space>
                    </Panel>
                  </Collapse>
                </div>
              )}

              {/* Метрики производительности */}
              {msg.metadata?.performance && !isUser && (
                <div style={{ marginTop: 12 }}>
                  <Divider style={{ margin: '8px 0' }} />
                  <Collapse size="small" ghost>
                    <Panel
                      header={
                        <Space size="small">
                          <span style={{ fontSize: '12px' }}>⚡</span>
                          <Text type="secondary" style={{ fontSize: '12px' }}>
                            Метрики производительности
                          </Text>
                        </Space>
                      }
                      key="metrics"
                    >
                      <div style={{ 
                        display: 'grid', 
                        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                        gap: '8px',
                        fontSize: '11px'
                      }}>
                        {/* Embedding метрики */}
                        <Card size="small" style={{ backgroundColor: '#f0f8ff' }}>
                          <Text strong style={{ fontSize: '11px', color: '#1890ff' }}>🧠 Эмбеддинги</Text>
                          <div style={{ marginTop: 4 }}>
                            <div>Время: {msg.metadata.performance.embeddingTime}мс</div>
                            <div>Токены: {msg.metadata.performance.embeddingTokensIn}</div>
                            <div>Модель: {msg.metadata.performance.embeddingModel?.split('/').pop()}</div>
                          </div>
                        </Card>

                        {/* Поиск метрики */}
                        <Card size="small" style={{ backgroundColor: '#f6ffed' }}>
                          <Text strong style={{ fontSize: '11px', color: '#52c41a' }}>🔍 Поиск</Text>
                          <div style={{ marginTop: 4 }}>
                            <div>Время: {msg.metadata.performance.searchTime}мс</div>
                            <div>Найдено: {msg.metadata.performance.candidatesFound}</div>
                            <div>Реранжировано: {msg.metadata.performance.candidatesReranked}</div>
                          </div>
                        </Card>

                        {/* LLM метрики */}
                        <Card size="small" style={{ backgroundColor: '#fff7e6' }}>
                          <Text strong style={{ fontSize: '11px', color: '#fa8c16' }}>🤖 LLM</Text>
                          <div style={{ marginTop: 4 }}>
                            <div>Первый токен: {msg.metadata.performance.timeToFirstToken}мс</div>
                            <div>Токены: {msg.metadata.performance.llmTokensIn}→{msg.metadata.performance.llmTokensOut}</div>
                            <div>Скорость: {Math.round(msg.metadata.performance.tokensPerSecond)} т/с</div>
                          </div>
                        </Card>

                        {/* Общие метрики */}
                        <Card size="small" style={{ backgroundColor: '#f9f0ff' }}>
                          <Text strong style={{ fontSize: '11px', color: '#722ed1' }}>⏱️ Общее</Text>
                          <div style={{ marginTop: 4 }}>
                            <div>Весь пайплайн: {msg.metadata.performance.totalPipelineTime}мс</div>
                            <div>Генерация: {msg.metadata.performance.totalGenerationTime}мс</div>
                            <div>Источников: {msg.sources?.length || 0}</div>
                          </div>
                        </Card>
                      </div>
                    </Panel>
                  </Collapse>
                </div>
              )}

              {/* Календарная отладка */}
              {msg.metadata?.calendarDebug && !isUser && (
                <div style={{ marginTop: 12 }}>
                  <Divider style={{ margin: '8px 0' }} />
                  <div style={{ display: 'flex', justifyContent: 'center' }}>
                    <Button
                      type="primary"
                      icon={<span style={{ fontSize: '14px' }}>📅</span>}
                      onClick={() => setCalendarDebugInfo(msg.metadata?.calendarDebug)}
                      size="small"
                      style={{ backgroundColor: '#722ed1', borderColor: '#722ed1' }}
                    >
                      Показать отладку календарного запроса
                    </Button>
                  </div>
                </div>
              )}

              {/* Отладочная информация */}
              {msg.metadata?.debug && !isUser && debugMode && (
                <div style={{ marginTop: 12 }}>
                  <Divider style={{ margin: '8px 0' }} />
                  <Collapse size="small" ghost>
                    <Panel
                      header={
                        <Space size="small">
                          <span style={{ fontSize: '12px' }}>🐛</span>
                          <Text type="secondary" style={{ fontSize: '12px' }}>
                            Отладочная информация
                          </Text>
                        </Space>
                      }
                      key="debug"
                    >
                      <Space direction="vertical" size="small" style={{ width: '100%' }}>
                        {/* System Prompt */}
                        <Card size="small" style={{ backgroundColor: '#fff2e8' }}>
                          <Text strong style={{ fontSize: '11px', color: '#d46b08' }}>📋 System Prompt</Text>
                          <div style={{ marginTop: 4 }}>
                            <pre style={{ 
                              fontSize: '10px', 
                              fontFamily: 'monospace',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-word',
                              maxHeight: '200px',
                              overflow: 'auto',
                              backgroundColor: '#fafafa',
                              padding: '8px',
                              borderRadius: '4px',
                              margin: 0
                            }}>
                              {msg.metadata.debug.systemPrompt}
                            </pre>
                          </div>
                        </Card>

                        {/* Context */}
                        <Card size="small" style={{ backgroundColor: '#f6ffed' }}>
                          <Text strong style={{ fontSize: '11px', color: '#389e0d' }}>📄 Контекст</Text>
                          <div style={{ marginTop: 4 }}>
                            <Text type="secondary" style={{ fontSize: '10px' }}>
                              Длина: {msg.metadata.debug.context?.length || 0} символов
                            </Text>
                            <pre style={{ 
                              fontSize: '10px', 
                              fontFamily: 'monospace',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-word',
                              maxHeight: '300px',
                              overflow: 'auto',
                              backgroundColor: '#fafafa',
                              padding: '8px',
                              borderRadius: '4px',
                              margin: '4px 0 0 0'
                            }}>
                              {msg.metadata.debug.context}
                            </pre>
                          </div>
                        </Card>

                        {/* Full Prompt */}
                        <Card size="small" style={{ backgroundColor: '#f0f8ff' }}>
                          <Text strong style={{ fontSize: '11px', color: '#1890ff' }}>🔤 Полный промпт</Text>
                          <div style={{ marginTop: 4 }}>
                            <Text type="secondary" style={{ fontSize: '10px' }}>
                              Длина: {msg.metadata.debug.fullPrompt?.length || 0} символов
                            </Text>
                            <pre style={{ 
                              fontSize: '10px', 
                              fontFamily: 'monospace',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-word',
                              maxHeight: '400px',
                              overflow: 'auto',
                              backgroundColor: '#fafafa',
                              padding: '8px',
                              borderRadius: '4px',
                              margin: '4px 0 0 0'
                            }}>
                              {msg.metadata.debug.fullPrompt}
                            </pre>
                          </div>
                        </Card>

                        {/* Raw Response */}
                        <Card size="small" style={{ backgroundColor: '#fff1f0' }}>
                          <Text strong style={{ fontSize: '11px', color: '#cf1322' }}>🤖 Сырой ответ ИИ</Text>
                          <div style={{ marginTop: 4 }}>
                            <Text type="secondary" style={{ fontSize: '10px' }}>
                              Длина: {msg.metadata.debug.rawResponse?.length || 0} символов
                            </Text>
                            <pre style={{ 
                              fontSize: '10px', 
                              fontFamily: 'monospace',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-word',
                              maxHeight: '300px',
                              overflow: 'auto',
                              backgroundColor: '#fafafa',
                              padding: '8px',
                              borderRadius: '4px',
                              margin: '4px 0 0 0'
                            }}>
                              {msg.metadata.debug.rawResponse}
                            </pre>
                          </div>
                        </Card>
                      </Space>
                    </Panel>
                  </Collapse>
                </div>
              )}
            </Card>
            
            <div style={{ 
              textAlign: isUser ? 'right' : 'left', 
              marginTop: 4 
            }}>
              <Text type="secondary" style={{ fontSize: '11px' }}>
                {dayjs(msg.timestamp).format('HH:mm')}
              </Text>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div 
      className={className}
      style={{ height: '100%', display: 'flex', gap: '16px' }}
    >
      {/* Левая панель - История чатов */}
      <Card 
        style={{ width: '300px', display: 'flex', flexDirection: 'column' }}
        styles={{ body: { padding: 0, height: '100%', display: 'flex', flexDirection: 'column' } }}
      >
        <div style={{ 
          padding: '16px', 
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <Space>
            <HistoryOutlined style={{ color: '#1890ff' }} />
            <Title level={5} style={{ margin: 0 }}>
              История чатов
            </Title>
          </Space>
          
          <Tooltip title="Новый чат">
            <Button
              type="text"
              icon={<PlusOutlined />}
              onClick={handleNewChat}
              disabled={!user}
            />
          </Tooltip>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
          {sessionsLoading ? (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              <Spin />
              <div style={{ marginTop: 8 }}>
                <Text type="secondary">Загрузка истории...</Text>
              </div>
            </div>
          ) : sessions.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="Нет сохраненных чатов"
              style={{ marginTop: '40px' }}
            />
          ) : (
            <List
              dataSource={sessions}
              renderItem={(session) => (
                <List.Item
                  key={session.id}
                  style={{
                    cursor: 'pointer',
                    backgroundColor: conversationId === session.id ? '#f0f8ff' : 'transparent',
                    borderRadius: '8px',
                    margin: '4px 0',
                    padding: '8px 12px',
                    border: conversationId === session.id ? '1px solid #91d5ff' : '1px solid transparent'
                  }}
                  onClick={() => handleSelectSession(session.id)}
                  actions={[
                    <Popconfirm
                      key="delete"
                      title="Удалить чат?"
                      description="Это действие нельзя отменить"
                      onConfirm={(e) => {
                        e?.stopPropagation();
                        handleDeleteSession(session.id);
                      }}
                      okText="Да"
                      cancelText="Нет"
                    >
                      <Button
                        type="text"
                        size="small"
                        icon={<DeleteOutlined />}
                        onClick={(e) => e.stopPropagation()}
                        danger
                      />
                    </Popconfirm>
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Text 
                        ellipsis={{ tooltip: session.title }}
                        style={{ 
                          fontWeight: conversationId === session.id ? 'bold' : 'normal',
                          fontSize: '14px'
                        }}
                      >
                        {session.title}
                      </Text>
                    }
                    description={
                      <Text type="secondary" style={{ fontSize: '11px' }}>
                        {dayjs(session.updatedAt).format('DD.MM HH:mm')}
                      </Text>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </div>
      </Card>

      {/* Правая панель - Текущий чат */}
      <Card 
        style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
        styles={{ 
          body: { 
            padding: 0, 
            height: '100%', 
            display: 'flex', 
            flexDirection: 'column' 
          }
        }}
      >
        {/* Header */}
        <div style={{ 
          padding: '16px 20px', 
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <Space>
            <MessageOutlined style={{ color: '#1890ff' }} />
            <Title level={4} style={{ margin: 0 }}>
              Чат с ИИ
            </Title>
          </Space>
          
          <Space>
            {/* ИСПРАВЛЕНИЕ: Убираем кнопку переключения отладки - она всегда включена */}
            <Tooltip title="Отладочная информация всегда включена">
              <Button
                type="primary"
                icon={<BugOutlined />}
                size="small"
                disabled
              >
                Отладка
              </Button>
            </Tooltip>
            {messages.length > 0 && (
              <Button
                type="text"
                icon={<ClearOutlined />}
                onClick={handleClearChat}
                disabled={loading}
              >
                Очистить
              </Button>
            )}
          </Space>
        </div>

        {/* Messages */}
        <div style={{ 
          flex: 1, 
          padding: '20px', 
          overflowY: 'auto',
          minHeight: 0
        }}>
          {error && (
            <Alert
              message="Ошибка"
              description={error}
              type="error"
              showIcon
              style={{ marginBottom: 16 }}
              closable
            />
          )}

          {messages.length === 0 && !loading ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <Space direction="vertical" size="small">
                  <Text type="secondary">Начните диалог с ИИ</Text>
                  <Text type="secondary" style={{ fontSize: '12px' }}>
                    Задайте вопрос по загруженным документам
                  </Text>
                </Space>
              }
            />
          ) : (
            <>
              {messages.map(renderMessage)}
              {loading && (
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'flex-start',
                  marginBottom: 16 
                }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                    <Avatar
                      icon={<RobotOutlined />}
                      style={{ backgroundColor: '#52c41a' }}
                    />
                    <Card
                      size="small"
                      style={{
                        backgroundColor: '#f6ffed',
                        border: '1px solid #b7eb8f',
                        borderRadius: '12px',
                      }}
                      styles={{ body: { padding: '12px 16px' } }}
                    >
                      <Space>
                        <Spin size="small" />
                        <Text type="secondary">
                          {currentStatus || 'ИИ думает...'}
                        </Text>
                      </Space>
                    </Card>
                  </div>
                </div>
              )}
            </>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div style={{ 
          padding: '16px 20px', 
          borderTop: '1px solid #f0f0f0',
          backgroundColor: '#fafafa'
        }}>
          <Space.Compact style={{ width: '100%' }}>
            <TextArea
              ref={inputRef}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={
                user 
                  ? "Задайте вопрос по документам..." 
                  : "Войдите в систему для использования чата"
              }
              disabled={!user || loading}
              autoSize={{ minRows: 1, maxRows: 4 }}
              style={{ resize: 'none' }}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              disabled={!message.trim() || !user || loading}
              loading={loading}
              style={{ height: 'auto' }}
            >
              Отправить
            </Button>
          </Space.Compact>
          
          {!user && (
            <Text type="secondary" style={{ fontSize: '12px', marginTop: 8, display: 'block' }}>
            Необходимо войти в систему для использования чата
          </Text>
          )}
        </div>
      </Card>

      {/* Модальное окно календарной отладки */}
      {calendarDebugInfo && (
        <CalendarDebug
          debug={calendarDebugInfo}
          onClose={() => setCalendarDebugInfo(null)}
        />
      )}
    </div>
  );
};

export default Chat;
