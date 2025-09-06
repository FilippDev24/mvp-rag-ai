// API Response types
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

// User types
export interface User {
  id: string;
  email: string;
  name: string;
  accessLevel: number;
  createdAt: string;
  updatedAt: string;
}

// Auth types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  user: User;
}

// Document types
export interface Document {
  id: string;
  title: string;
  filename?: string;
  filePath?: string;
  fileType?: string;
  fileSize?: number;
  mimeType?: string;
  accessLevel: number;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'ERROR' | 'pending' | 'processing' | 'completed' | 'failed' | 'error';
  userId?: string;
  uploadedBy?: string;
  createdAt: string;
  updatedAt?: string;
  chunksCount?: number;
  chunkCount?: number;
  processed?: boolean;
  processedAt?: string;
  metadata?: any;
}

export interface DocumentUploadRequest {
  title: string;
  accessLevel: number;
}

// Типы для метрик производительности
export interface PerformanceMetrics {
  embeddingTime: number;
  embeddingTokensIn: number;
  embeddingModel: string;
  searchTime: number;
  rerankTime: number;
  candidatesFound: number;
  candidatesReranked: number;
  llmTokensIn: number;
  llmTokensOut: number;
  timeToFirstToken: number;
  totalGenerationTime: number;
  tokensPerSecond: number;
  totalPipelineTime: number;
  timestamp: string;
}

// Chat types
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: DocumentChunk[];
  metadata?: {
    performance?: PerformanceMetrics;
    processingTime?: number;
    chunksUsed?: number;
    model?: string;
    relevanceFiltered?: boolean;
    filterReason?: string;
    debug?: {
      fullPrompt: string;
      rawResponse: string;
      context: string;
      systemPrompt: string;
    };
    [key: string]: any;
  };
}

export interface DocumentChunk {
  id: string;
  content: string;
  documentId: string;
  documentTitle?: string;
  chunkIndex: number;
  similarity?: number;
  relevance?: number;
  accessLevel: number;
  charCount: number;
  metadata?: any;
  createdAt: string;
  keywords?: ChunkKeywords;
}

// ЭТАП 2: Типы для ключевых слов
export interface ChunkKeywords {
  semantic_keywords: string[];
  technical_keywords: string[];
  all_keywords: string[];
}

export interface DocumentKeywords {
  document_semantic_keywords: string[];
  document_technical_keywords: string[];
  document_all_keywords: string[];
}

export interface ChunkWithOverlap extends DocumentChunk {
  overlapStart?: number;
  overlapEnd?: number;
  hasOverlapWithNext?: boolean;
  hasOverlapWithPrev?: boolean;
}

export interface ChatRequest {
  message: string;
  conversationId?: string;
}

export interface ChatResponse {
  answer: string;
  sources: SearchResult[];
  sessionId: string;
  messageId: string;
  metadata: {
    processingTime: number;
    chunksUsed: number;
    model: string;
    timestamp: string;
    performance?: PerformanceMetrics;
    relevanceFiltered?: boolean;
    filterReason?: string;
    debug?: {
      fullPrompt: string;
      rawResponse: string;
      context: string;
      systemPrompt: string;
    };
  };
}

export interface SearchResult {
  chunk: DocumentChunk;
  document: Document;
  score: number;
  relevance: number;
}

// Store types
export interface AuthStore {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  setUser: (user: User) => void;
}

export interface DocumentStore {
  documents: Document[];
  loading: boolean;
  error: string | null;
  fetchDocuments: () => Promise<void>;
  uploadDocument: (file: File, title: string, accessLevel: number) => Promise<void>;
  deleteDocument: (id: string) => Promise<void>;
}

export interface ChatSession {
  id: string;
  title: string;
  userId: string;
  createdAt: string;
  updatedAt: string;
  messages?: ChatMessage[];
}

export interface ChatStore {
  messages: ChatMessage[];
  loading: boolean;
  error: string | null;
  conversationId: string | null;
  sessions: ChatSession[];
  sessionsLoading: boolean;
  currentStatus: string | null;
  sendMessage: (message: string) => Promise<void>;
  clearChat: () => void;
  loadSessions: () => Promise<void>;
  loadSessionMessages: (sessionId: string) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  selectSession: (sessionId: string) => Promise<void>;
}
