import axios, { AxiosInstance, AxiosResponse } from 'axios';
import { 
  ApiResponse, 
  LoginRequest, 
  LoginResponse, 
  User, 
  Document, 
  DocumentUploadRequest,
  DocumentChunk,
  ChatRequest,
  ChatResponse 
} from '../types';

class ApiClient {
  private baseURL = (import.meta as any).env.VITE_API_URL || 'http://localhost:3001/api';
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // ОБЯЗАТЕЛЬНО: Interceptor для токена
    this.client.interceptors.request.use((config) => {
      // Получаем токен из Zustand store или fallback на localStorage
      let token: string | null = null;
      try {
        const authState = JSON.parse(localStorage.getItem('auth-storage') || '{}');
        token = authState.state?.token || localStorage.getItem('token');
      } catch {
        token = localStorage.getItem('token');
      }
      
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // ОБЯЗАТЕЛЬНО: Обработка 401
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          // Используем Zustand store для очистки состояния
          import('../store/authStore').then(({ useAuthStore }) => {
            useAuthStore.getState().logout();
          });
        }
        return Promise.reject(error);
      }
    );
  }

  // Auth endpoints
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response: AxiosResponse<ApiResponse<LoginResponse>> = await this.client.post(
      '/auth/login',
      credentials
    );
    
    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.error || 'Login failed');
    }
    
    return response.data.data;
  }

  async logout(): Promise<void> {
    await this.client.post('/auth/logout');
  }

  async getMe(): Promise<User> {
    const response: AxiosResponse<ApiResponse<User>> = await this.client.get('/auth/me');
    
    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.error || 'Failed to get user info');
    }
    
    return response.data.data;
  }

  // Document endpoints
  async getStats(): Promise<{ documentsCount: number; chunksCount: number; messagesCount: number }> {
    const response: AxiosResponse<ApiResponse<{ documentsCount: number; chunksCount: number; messagesCount: number }>> = await this.client.get('/documents/stats');
    
    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.error || 'Failed to fetch stats');
    }
    
    return response.data.data;
  }

  async getDocuments(): Promise<Document[]> {
    const response: AxiosResponse<ApiResponse<Document[]>> = await this.client.get('/documents');
    
    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.error || 'Failed to fetch documents');
    }
    
    return response.data.data;
  }

  async uploadDocument(file: File, metadata: DocumentUploadRequest): Promise<Document> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', metadata.title);
    formData.append('accessLevel', metadata.accessLevel.toString());

    const response: AxiosResponse<ApiResponse<Document>> = await this.client.post(
      '/documents/upload',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    
    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.error || 'Failed to upload document');
    }
    
    return response.data.data;
  }

  async deleteDocument(id: string): Promise<void> {
    const response: AxiosResponse<ApiResponse> = await this.client.delete(`/documents/${id}`);
    
    if (!response.data.success) {
      throw new Error(response.data.error || 'Failed to delete document');
    }
  }

  async getDocument(id: string): Promise<Document> {
    const response: AxiosResponse<ApiResponse<Document>> = await this.client.get(`/documents/${id}`);
    
    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.error || 'Failed to fetch document');
    }
    
    return response.data.data;
  }

  async getDocumentChunks(
    documentId: string, 
    page: number = 1, 
    limit: number = 50
  ): Promise<{ chunks: DocumentChunk[]; total: number; totalPages: number }> {
    const response: AxiosResponse<ApiResponse<DocumentChunk[]>> = await this.client.get(
      `/documents/${documentId}/chunks?page=${page}&limit=${limit}`
    );
    
    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.error || 'Failed to fetch document chunks');
    }
    
    return {
      chunks: response.data.data,
      total: response.data.metadata?.total || 0,
      totalPages: Math.ceil((response.data.metadata?.total || 0) / limit)
    };
  }

  async updateChunk(
    documentId: string, 
    chunkId: string, 
    content: string, 
    metadata?: any
  ): Promise<DocumentChunk> {
    const response: AxiosResponse<ApiResponse<DocumentChunk>> = await this.client.put(
      `/documents/${documentId}/chunks/${chunkId}`,
      { content, metadata }
    );
    
    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.error || 'Failed to update chunk');
    }
    
    return response.data.data;
  }

  async deleteChunk(documentId: string, chunkId: string): Promise<void> {
    const response: AxiosResponse<ApiResponse> = await this.client.delete(
      `/documents/${documentId}/chunks/${chunkId}`
    );
    
    if (!response.data.success) {
      throw new Error(response.data.error || 'Failed to delete chunk');
    }
  }

  // ЭТАП 2: Извлечение ключевых слов
  async extractKeywords(documentId?: string): Promise<{ taskId: string; message: string }> {
    const endpoint = documentId 
      ? `/documents/${documentId}/extract-keywords`
      : '/documents/extract-keywords';
      
    const response: AxiosResponse<ApiResponse<{ taskId: string; message: string }>> = await this.client.post(endpoint);
    
    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.error || 'Failed to start keyword extraction');
    }
    
    return response.data.data;
  }

  // Chat endpoints
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const response: AxiosResponse<ApiResponse<ChatResponse>> = await this.client.post(
      '/chat/message',
      { message: request.message, sessionId: request.conversationId }
    );
    
    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.error || 'Failed to send message');
    }
    
    return response.data.data;
  }

  // КРИТИЧНО: Методы для работы с историей чата
  async getChatSessions(page: number = 1, limit: number = 20): Promise<{
    sessions: any[];
    total: number;
  }> {
    const response: AxiosResponse<ApiResponse<any[]>> = await this.client.get(
      `/chat/sessions?page=${page}&limit=${limit}`
    );
    
    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.error || 'Failed to fetch chat sessions');
    }
    
    return {
      sessions: response.data.data,
      total: response.data.metadata?.total || 0
    };
  }

  async getSessionMessages(sessionId: string, page: number = 1, limit: number = 50): Promise<{
    messages: any[];
    total: number;
  }> {
    const response: AxiosResponse<ApiResponse<any[]>> = await this.client.get(
      `/chat/sessions/${sessionId}?page=${page}&limit=${limit}`
    );
    
    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.error || 'Failed to fetch session messages');
    }
    
    return {
      messages: response.data.data,
      total: response.data.metadata?.total || 0
    };
  }

  async deleteSession(sessionId: string): Promise<void> {
    const response: AxiosResponse<ApiResponse> = await this.client.delete(
      `/chat/sessions/${sessionId}`
    );
    
    if (!response.data.success) {
      throw new Error(response.data.error || 'Failed to delete session');
    }
  }

  // Streaming chat endpoint
  async sendMessageStream(
    request: ChatRequest,
    onChunk: (chunk: string) => void,
    onSources: (sources: any[]) => void,
    onError: (error: string) => void,
    onComplete: () => void,
    onMetrics?: (metrics: any) => void,
    onDebug?: (debug: any) => void,
    onStatus?: (status: { message: string; stage: string }) => void
  ): Promise<void> {
    // Получаем токен из Zustand store или fallback на localStorage
    let token: string | null = null;
    try {
      const authState = JSON.parse(localStorage.getItem('auth-storage') || '{}');
      token = authState.state?.token || localStorage.getItem('token');
    } catch {
      token = localStorage.getItem('token');
    }
    
    const url = `${this.baseURL}/chat/stream`;
    console.log('🚀 Starting SSE request to:', url);
    console.log('📝 Request payload:', { message: request.message, sessionId: request.conversationId });
    console.log('🔑 Token being used:', token ? `${token.substring(0, 20)}...` : 'NO TOKEN');
    
    try {
      console.log('🌐 Sending fetch request...');
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : '',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({
          message: request.message,
          sessionId: request.conversationId
        }),
        // КРИТИЧНО: Убираем любые тайм-ауты для SSE
        signal: undefined, // Не используем AbortController
      });
      
      console.log('📡 Fetch response received:', {
        status: response.status,
        statusText: response.statusText,
        headers: Object.fromEntries(response.headers.entries()),
        ok: response.ok
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body reader available');
      }

      const decoder = new TextDecoder();
      let buffer = '';
      let currentEvent = '';
      let hasReceivedData = false;

      try {
        let endEventReceived = false;
        let eventCount = 0;
        
        console.log('📡 Starting SSE stream reading loop');
        
        while (true) {
          console.log('🔄 Reading next chunk from stream...');
          const { done, value } = await reader.read();
          
          if (done) {
            console.log('✅ Stream reading done, hasReceivedData:', hasReceivedData, 'endEventReceived:', endEventReceived);
            // ИСПРАВЛЕНИЕ: Если поток завершился естественно, но мы не получили 'end' событие
            if (!endEventReceived && hasReceivedData) {
              console.warn('⚠️ Stream ended without end event, calling onComplete');
              onComplete();
            } else if (!hasReceivedData) {
              console.error('❌ Stream ended without receiving any data');
              throw new Error('Stream ended without receiving any data');
            }
            break;
          }

          hasReceivedData = true;
          const chunk = decoder.decode(value, { stream: true });
          console.log('📦 Received chunk:', chunk.length, 'bytes');
          
          buffer += chunk;
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.trim() === '') {
              // Пустая строка означает конец события
              currentEvent = '';
              continue;
            }
            
          if (line.startsWith('event: ')) {
            currentEvent = line.substring(7).trim();
            eventCount++;
            console.log('🎯 SSE Event received:', currentEvent, '(#' + eventCount + ')');
            continue;
          }
            
            if (line.startsWith('data: ')) {
              try {
                const dataStr = line.substring(6);
                if (dataStr.trim() === '') continue;
                
                const data = JSON.parse(dataStr);
                console.log('📄 Processing data for event:', currentEvent, 'data size:', JSON.stringify(data).length);
                
                if (currentEvent === 'session') {
                  console.log('🆔 Session event:', data.sessionId);
                  // Сохраняем sessionId для последующих запросов
                  if (data.sessionId) {
                    (window as any).__currentSessionId = data.sessionId;
                  }
                } else if (currentEvent === 'status') {
                  console.log('📊 Status event:', data.message, 'stage:', data.stage);
                  // Вызываем отдельный callback для статусов
                  if (onStatus && data.message) {
                    onStatus({ message: data.message, stage: data.stage });
                  }
                } else if (currentEvent === 'sources') {
                  console.log('📚 Sources event:', data.sources?.length || 0, 'sources');
                  onSources(data.sources || []);
                } else if (currentEvent === 'answer') {
                  console.log('💬 Answer chunk:', data.text?.length || 0, 'chars, done:', data.done);
                  if (data.text) {
                    onChunk(data.text);
                  }
                  // НЕ завершаем при done: true, ждем метрики или end событие
                } else if (currentEvent === 'calendar_debug') {
                  console.log('📅 Calendar debug event');
                  // Обработка календарной отладочной информации
                  if (onDebug && data.debug) {
                    onDebug(data.debug);
                  }
                } else if (currentEvent === 'metrics') {
                  console.log('📊 Metrics event');
                  // Обработка метрик производительности
                  if (onMetrics && data.performance) {
                    onMetrics(data.performance);
                  }
                  // Обработка отладочной информации
                  if (onDebug && data.debug) {
                    onDebug(data.debug);
                  }
                } else if (currentEvent === 'debug') {
                  console.log('🐛 Debug event');
                  // Обработка обычной отладочной информации
                  if (onDebug && data) {
                    onDebug(data);
                  }
                } else if (currentEvent === 'error') {
                  console.error('❌ Error event:', data.error);
                  onError(data.error || 'Stream error');
                  return;
                } else if (currentEvent === 'end') {
                  console.log('🏁 End event received, calling onComplete');
                  endEventReceived = true;
                  onComplete();
                  return;
                }
              } catch (parseError) {
                console.warn('⚠️ Failed to parse SSE data:', { line, parseError });
                // Не прерываем поток из-за одной ошибки парсинга
                continue;
              }
            }
          }
        }
        
        console.log('✅ Stream reading completed, total events:', eventCount);
        
      } catch (readerError) {
        console.error('Reader error:', readerError);
        throw new Error(`Stream reading failed: ${readerError instanceof Error ? readerError.message : 'Unknown error'}`);
      } finally {
        // Освобождаем reader
        try {
          reader.releaseLock();
        } catch (releaseError) {
          console.warn('Failed to release reader lock:', releaseError);
        }
      }
      
    } catch (error) {
      console.error('Stream error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Stream failed';
      
      // Проверяем, не является ли это ошибкой сети
      if (errorMessage.includes('fetch')) {
        onError('Ошибка сети. Проверьте подключение к серверу.');
      } else if (errorMessage.includes('HTTP 401')) {
        onError('Ошибка авторизации. Войдите в систему заново.');
      } else if (errorMessage.includes('HTTP 403')) {
        onError('Недостаточно прав доступа.');
      } else if (errorMessage.includes('HTTP 500')) {
        onError('Внутренняя ошибка сервера. Попробуйте позже.');
      } else {
        onError(`Ошибка обработки запроса: ${errorMessage}`);
      }
    }
  }
}

// Singleton instance
export const apiClient = new ApiClient();
export default apiClient;
