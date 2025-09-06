// Импортируем типы из Prisma Client
import { User, Document, Chunk, ChatSession, Message, Role, MessageRole, DocumentStatus } from '@prisma/client';

// Экспортируем типы из Prisma
export { User, Document, Chunk, ChatSession, Message, Role, MessageRole, DocumentStatus };

// КРИТИЧНО: Типы для безопасности согласно ТЗ
export interface AuthenticatedUser extends User {
  // Дополнительные поля для аутентифицированного пользователя
}

export interface UserWithoutPassword extends Omit<User, 'passwordHash'> {}

export interface DocumentWithUser extends Document {
  user: UserWithoutPassword;
}

export interface DocumentWithChunks extends Document {
  chunks: Chunk[];
  user: UserWithoutPassword;
}

export interface ChunkWithDocument extends Chunk {
  document: Document;
}

export interface ChatSessionWithMessages extends ChatSession {
  messages: Message[];
  user: UserWithoutPassword;
}

export interface MessageWithSession extends Message {
  session: ChatSession;
}

// API Response типы согласно ТЗ
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  metadata?: {
    page?: number;
    total?: number;
    timestamp: string;
  };
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  metadata: {
    page: number;
    total: number;
    totalPages: number;
    hasNext: boolean;
    hasPrev: boolean;
    timestamp: string;
  };
}

// Типы для аутентификации
export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  user: UserWithoutPassword;
  token: string;
  expiresIn: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  fullName?: string;
  accessLevel?: number;
}

// Типы для документов
export interface DocumentUploadRequest {
  title: string;
  accessLevel: number;
}

export interface DocumentCreateData {
  title: string;
  filePath: string;
  fileType: string;
  accessLevel: number;
  uploadedBy: string;
  metadata?: any;
}

export interface DocumentUpdateRequest {
  title?: string;
  accessLevel?: number;
  processed?: boolean;
  chunkCount?: number;
  metadata?: any;
}

// Типы для чанков
export interface ChunkCreateData {
  documentId: string;
  chunkIndex: number;
  content: string;
  accessLevel: number;
  charCount: number;
  metadata?: any;
}

export interface ChunkUpdateRequest {
  content?: string;
  accessLevel?: number;
  metadata?: any;
}

// Типы для чата
export interface ChatSessionCreateRequest {
  title?: string;
}

export interface MessageCreateRequest {
  sessionId: string;
  role: MessageRole;
  content: string;
  metadata?: any;
}

// Типы для поиска и RAG
export interface SearchRequest {
  query: string;
  accessLevel?: number;
  limit?: number;
  offset?: number;
}

export interface SearchResult {
  chunk: Chunk;
  document: Document;
  score: number;
  relevance: number;
}

export interface RAGRequest {
  question: string;
  sessionId?: string;
  accessLevel: number;
  context?: any;
}

// Типы для метрик производительности согласно ТЗ
export interface PerformanceMetrics {
  // Embedding метрики
  embeddingTime: number;           // Время генерации эмбеддинга
  embeddingTokensIn: number;       // Токены на входе
  embeddingModel: string;          // Модель эмбеддингов
  
  // RAG метрики  
  searchTime: number;              // Время поиска в ChromaDB
  rerankTime: number;              // Время реранжирования
  candidatesFound: number;         // Найдено кандидатов
  candidatesReranked: number;      // Реранжировано
  
  // LLM метрики
  llmTokensIn: number;            // Токены в промпте
  llmTokensOut: number;           // Токены в ответе
  timeToFirstToken: number;       // Время до первого токена (ms)
  totalGenerationTime: number;    // Общее время генерации (ms)
  tokensPerSecond: number;        // Скорость генерации
  
  // Общие метрики
  totalPipelineTime: number;      // Время всего пайплайна
  timestamp: string;              // Временная метка
}

export interface RAGResponse {
  answer: string;
  sources: SearchResult[];
  sessionId: string;
  messageId: string;
  metadata: {
    processingTime: number;
    chunksUsed: number;
    model: string;
    timestamp: string;
    requestType?: 'CALENDAR' | 'RAG' | 'SIMPLE';
    performance?: PerformanceMetrics;
    relevanceFiltered?: boolean;
    filterReason?: string;
    bestRelevanceScore?: number;
    error?: string;
    debug?: {
      fullPrompt: string;
      rawResponse: string;
      context: string;
      systemPrompt: string;
    };
    calendarDebug?: import('./calendar').CalendarDebugInfo;
  };
}

// Типы для обработки файлов
export interface FileProcessingJob {
  documentId: string;
  filePath: string;
  accessLevel: number;
  userId: string;
}

export interface ProcessingResult {
  success: boolean;
  chunksCreated: number;
  error?: string;
  processingTime: number;
}

// Константы согласно ТЗ
export const CONSTANTS = {
  // Chunking
  CHUNK_SIZE: 1000,
  CHUNK_OVERLAP: 100,
  MIN_CHUNK_SIZE: 200,
  
  // Embedding
  EMBEDDING_MODEL: 'intfloat/multilingual-e5-large',
  EMBEDDING_DIMENSION: 1024,
  
  // Search
  SEARCH_TOP_K: 30,
  RERANK_TOP_K: 10,
  
  // Auth
  JWT_EXPIRY: '7d',
  BCRYPT_ROUNDS: 12,
  
  // Limits
  MAX_FILE_SIZE: 10 * 1024 * 1024,  // 10MB
  MAX_CHUNKS_PER_DOC: 1000,
  
  // Access levels
  ACCESS_LEVEL_MIN: 1,
  ACCESS_LEVEL_MAX: 100,
  ACCESS_LEVEL_DEFAULT: 50
} as const;

// Типы для ошибок согласно ТЗ
export class AppError extends Error {
  statusCode: number;
  isOperational: boolean;
  
  constructor(message: string, statusCode: number) {
    super(message);
    this.statusCode = statusCode;
    this.isOperational = true;
    
    Error.captureStackTrace(this, this.constructor);
  }
}

// Типы для валидации
export interface ValidationError {
  field: string;
  message: string;
  value?: any;
}

export interface ValidationResult {
  isValid: boolean;
  errors: ValidationError[];
}

// Типы для логирования
export interface LogContext {
  userId?: string;
  documentId?: string;
  sessionId?: string;
  requestId?: string;
  ip?: string;
  userAgent?: string;
  [key: string]: any;
}

// Типы для метрик
export interface Metrics {
  documentProcessingTime: number;
  chunkSize: number;
  chunksPerDocument: number;
  searchTime: number;
  responseQuality?: number;
}

// Express Request с пользователем
import { Request } from 'express';

export interface AuthenticatedRequest extends Request {
  user: AuthenticatedUser;
}

// Расширенный ApiResponse с дополнительными полями
export interface ExtendedApiResponse<T = any> extends ApiResponse<T> {
  metadata?: {
    page?: number;
    total?: number;
    totalPages?: number;
    hasNext?: boolean;
    hasPrev?: boolean;
    timestamp: string;
    processingTime?: number;
  };
}
