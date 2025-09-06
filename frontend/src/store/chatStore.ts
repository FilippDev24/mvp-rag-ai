import { create } from 'zustand';
import { ChatStore, ChatMessage } from '../types';
import { apiClient } from '../services/api';

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  loading: false,
  error: null,
  conversationId: null,
  sessions: [],
  sessionsLoading: false,
  currentStatus: null,

  sendMessage: async (message: string) => {
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    };

    // Добавляем сообщение пользователя
    set(state => ({
      messages: [...state.messages, userMessage],
      loading: true,
      error: null,
    }));

    // ID для сообщения ассистента
    const assistantMessageId = (Date.now() + 1).toString();
    let assistantMessageCreated = false;
    let pendingSources: any[] = [];
    let pendingMetrics: any = null;
    let pendingDebug: any = null;
    let currentStatus: string | null = null;

    try {
      console.log('Using streaming method for chat');
      await apiClient.sendMessageStream(
        {
          message,
          conversationId: get().conversationId || undefined,
        },
        // onChunk - создаем сообщение при первом чанке и добавляем текст
        (chunk: string) => {
          if (!assistantMessageCreated) {
            // Создаем сообщение ассистента при первом чанке (убираем "ИИ думает...")
            const assistantMessage: ChatMessage = {
              id: assistantMessageId,
              role: 'assistant',
              content: chunk,
              timestamp: new Date().toISOString(),
              sources: [],
              metadata: {},
            };
            
            set(state => ({
              messages: [...state.messages, assistantMessage],
              loading: false, // Убираем "ИИ думает..."
              currentStatus: null, // Очищаем статус при получении первого чанка
            }));
            
            assistantMessageCreated = true;
          } else {
            // Добавляем текст к существующему сообщению
            set(state => ({
              messages: state.messages.map(msg => 
                msg.id === assistantMessageId 
                  ? { ...msg, content: msg.content + chunk }
                  : msg
              ),
            }));
          }
        },
        // onSources - сохраняем источники для добавления в конце
        (sources: any[]) => {
          pendingSources = sources.map(source => ({
            id: source.chunk?.id || source.chunkId || `source_${Date.now()}`,
            content: source.chunk?.content || source.text || '',
            documentId: source.chunk?.documentId || source.documentId || 'unknown',
            documentTitle: source.document?.title || source.documentTitle || 'Неизвестный документ',
            chunkIndex: source.chunk?.chunkIndex || source.chunkIndex || 0,
            similarity: source.score || source.similarity || 0,
            relevance: source.relevance || source.score || 0,
            accessLevel: source.chunk?.accessLevel || 1,
            charCount: source.chunk?.charCount || source.chunk?.content?.length || 0,
            metadata: source.chunk?.metadata || {},
            createdAt: source.chunk?.createdAt || new Date().toISOString(),
          }));
        },
        // onError - улучшенная обработка ошибок
        (error: string) => {
          console.error('Chat stream error:', error);
          
          // Если сообщение ассистента уже создано, но произошла ошибка
          if (assistantMessageCreated) {
            set(state => ({
              messages: state.messages.map(msg => 
                msg.id === assistantMessageId 
                  ? { 
                      ...msg, 
                      content: msg.content + '\n\n❌ Произошла ошибка при получении ответа. Попробуйте еще раз.' 
                    }
                  : msg
              ),
              error,
              loading: false,
              currentStatus: null // Очищаем статус при ошибке
            }));
          } else {
            // Если сообщение ассистента еще не создано
            set({ error, loading: false, currentStatus: null });
          }
        },
        // onComplete - добавляем источники, метрики и отладочную информацию в конце
        () => {
          set(state => ({
            loading: false, // КРИТИЧНО: Всегда останавливаем загрузку
            currentStatus: null, // Очищаем статус при завершении
            conversationId: (window as any).__currentSessionId || get().conversationId || assistantMessageId,
            messages: state.messages.map(msg => 
              msg.id === assistantMessageId 
                ? { 
                    ...msg, 
                    sources: pendingSources,
                    metadata: { 
                      ...msg.metadata, 
                      performance: pendingMetrics,
                      // ИСПРАВЛЕНИЕ: Сохраняем debug ТОЛЬКО если его еще нет в сообщении
                      debug: msg.metadata?.debug || pendingDebug
                    } 
                  }
                : msg
            ),
          }));
        },
        // onMetrics - применяем метрики сразу при получении
        (metrics: any) => {
          pendingMetrics = metrics;
          
          // Применяем метрики сразу к сообщению ассистента
          if (assistantMessageCreated) {
            set(state => ({
              messages: state.messages.map(msg => 
                msg.id === assistantMessageId 
                  ? { 
                      ...msg, 
                      metadata: { 
                        ...msg.metadata, 
                        performance: metrics,
                        // ИСПРАВЛЕНИЕ: Сохраняем существующую debug информацию при обновлении метрик
                        debug: msg.metadata?.debug || pendingDebug
                      } 
                    }
                  : msg
              ),
            }));
          }
        },
        // onDebug - обрабатываем отладочную информацию (включая календарную)
        (debug: any) => {
          pendingDebug = debug;
          
          // ИСПРАВЛЕНИЕ: Применяем отладочную информацию сразу И сохраняем существующую
          if (assistantMessageCreated) {
            set(state => ({
              messages: state.messages.map(msg => 
                msg.id === assistantMessageId 
                  ? { 
                      ...msg, 
                      metadata: { 
                        ...msg.metadata, 
                        debug: debug, // Заменяем новой debug информацией
                        // Если это календарная отладка, добавляем её отдельно
                        calendarDebug: debug.originalMessage ? debug : msg.metadata?.calendarDebug
                      } 
                    }
                  : msg
              ),
            }));
          }
        },
        // onStatus - обрабатываем статусы (заменяем предыдущий статус)
        (status: { message: string; stage: string }) => {
          currentStatus = status.message;
          
          // Обновляем состояние с текущим статусом
          set(state => ({
            loading: true, // Остаемся в состоянии загрузки
            currentStatus: status.message // Заменяем предыдущий статус
          }));
        }
      );
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to send message';
      set({ error: errorMessage, loading: false });
      throw error;
    }
  },

  clearChat: () => {
    set({
      messages: [],
      conversationId: null,
      error: null,
      loading: false,
    });
  },

  // КРИТИЧНО: Методы для работы с историей сессий
  loadSessions: async () => {
    set({ sessionsLoading: true, error: null });
    
    try {
      const { sessions } = await apiClient.getChatSessions(1, 50);
      set({ sessions, sessionsLoading: false });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load sessions';
      set({ error: errorMessage, sessionsLoading: false });
    }
  },

  loadSessionMessages: async (sessionId: string) => {
    set({ loading: true, error: null });
    
    try {
      const { messages } = await apiClient.getSessionMessages(sessionId, 1, 100);
      
      // Конвертируем сообщения из backend формата в frontend формат
      const formattedMessages: ChatMessage[] = messages.map(msg => ({
        id: msg.id,
        role: msg.role.toLowerCase() as 'user' | 'assistant',
        content: msg.content,
        timestamp: msg.createdAt,
        sources: msg.role === 'ASSISTANT' && msg.metadata?.sources ? 
          msg.metadata.sources.map((source: any) => ({
            id: source.chunkId || `source_${Date.now()}`,
            content: source.text || '',
            documentId: source.documentId || 'unknown',
            documentTitle: source.documentTitle || 'Неизвестный документ',
            chunkIndex: source.chunkIndex || 0,
            similarity: source.score || source.relevance || 0,
            relevance: source.relevance || source.score || 0,
            accessLevel: source.accessLevel || 1,
            charCount: source.charCount || 0,
            metadata: source.metadata || {},
            createdAt: source.createdAt || new Date().toISOString(),
          })) : undefined,
        metadata: msg.role === 'ASSISTANT' ? {
          performance: msg.metadata?.performance || null,
          processingTime: msg.metadata?.processingTime,
          chunksUsed: msg.metadata?.chunksUsed,
          model: msg.metadata?.model,
          // ИСПРАВЛЕНИЕ: Убираем календарную отладку при загрузке сессий - она не несет ценности
          // calendarDebug: msg.metadata?.calendarDebug || null
          debug: msg.metadata?.debug || null // ИСПРАВЛЕНИЕ: Добавляем обычную debug информацию
        } : undefined
      }));

      set({ 
        messages: formattedMessages, 
        conversationId: sessionId,
        loading: false 
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load session messages';
      set({ error: errorMessage, loading: false });
    }
  },

  deleteSession: async (sessionId: string) => {
    try {
      await apiClient.deleteSession(sessionId);
      
      // Обновляем список сессий
      const { sessions } = get();
      const updatedSessions = sessions.filter(session => session.id !== sessionId);
      set({ sessions: updatedSessions });
      
      // Если удаляем текущую сессию, очищаем чат
      if (get().conversationId === sessionId) {
        set({
          messages: [],
          conversationId: null,
        });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete session';
      set({ error: errorMessage });
      throw error;
    }
  },

  // Выбор сессии для загрузки
  selectSession: async (sessionId: string) => {
    await get().loadSessionMessages(sessionId);
  },
}));
