import { Request, Response } from 'express';
import { logger } from '../config/database';
import { AppError, ExtendedApiResponse, RAGRequest, RAGResponse, AuthenticatedRequest } from '../types';
import { chatService } from '../services/chatService';
import Joi from 'joi';

// ОБЯЗАТЕЛЬНО: Валидация входных данных согласно ТЗ
const messageSchema = Joi.object({
  message: Joi.string().min(1).max(2000).required(),
  sessionId: Joi.string().uuid().optional()
});

export class ChatController {
  /**
   * POST /api/chat/message
   * Основной endpoint для RAG запросов согласно требованиям
   */
  async sendMessage(req: AuthenticatedRequest, res: Response): Promise<void> {
    const startTime = Date.now();
    
    try {
      // ОБЯЗАТЕЛЬНО: Валидация данных
      const { error, value } = messageSchema.validate(req.body);
      if (error) {
        throw new AppError(error.details[0].message, 400);
      }

      const { message, sessionId } = value;
      const user = req.user;

      logger.info('Chat message request received', {
        userId: user.id,
        messageLength: message.length,
        sessionId,
        accessLevel: user.accessLevel
      });

      // КРИТИЧНО: Проверка уровня доступа согласно ТЗ
      if (user.accessLevel < 1) {
        throw new AppError('Insufficient access level for chat', 403);
      }

      // Подготовка RAG запроса
      const ragRequest: RAGRequest = {
        question: message,
        sessionId,
        accessLevel: user.accessLevel,
        context: {
          userId: user.id,
          userEmail: user.email
        }
      };

      // Обработка через RAG pipeline
      const ragResponse = await chatService.processRAGQuery(ragRequest);

      // Сохранение сообщений в БД
      const savedSession = await chatService.saveMessageToSession(
        user.id,
        ragRequest,
        ragResponse
      );

      const processingTime = Date.now() - startTime;

      // ОБЯЗАТЕЛЬНО: Единый формат ответа согласно ТЗ
      const response: ExtendedApiResponse<RAGResponse> = {
        success: true,
        data: {
          ...ragResponse,
          sessionId: savedSession.sessionId,
          messageId: savedSession.messageId
        },
        metadata: {
          timestamp: new Date().toISOString(),
          processingTime
        }
      };

      logger.info('Chat message processed successfully', {
        userId: user.id,
        sessionId: savedSession.sessionId,
        messageId: savedSession.messageId,
        processingTime,
        sourcesCount: ragResponse.sources.length
      });

      res.status(200).json(response);

    } catch (error) {
      const processingTime = Date.now() - startTime;
      
      logger.error('Chat message processing failed', {
        error,
        userId: req.user?.id,
        processingTime
      });

      if (error instanceof AppError) {
        res.status(error.statusCode).json({
          success: false,
          error: error.message,
          metadata: {
            timestamp: new Date().toISOString(),
            processingTime
          }
        });
      } else {
        res.status(500).json({
          success: false,
          error: 'Internal server error',
          metadata: {
            timestamp: new Date().toISOString(),
            processingTime
          }
        });
      }
    }
  }

  /**
   * POST /api/chat/stream
   * Streaming endpoint для RAG ответов
   */
  async streamMessage(req: AuthenticatedRequest, res: Response): Promise<void> {
    try {
      // ОБЯЗАТЕЛЬНО: Валидация данных
      const { error, value } = messageSchema.validate(req.body);
      if (error) {
        throw new AppError(error.details[0].message, 400);
      }

      const { message, sessionId } = value;
      const user = req.user;

      logger.info('Chat stream request received', {
        userId: user.id,
        messageLength: message.length,
        sessionId,
        accessLevel: user.accessLevel
      });

      // КРИТИЧНО: Проверка уровня доступа
      if (user.accessLevel < 1) {
        throw new AppError('Insufficient access level for chat', 403);
      }

      // Настройка SSE headers
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, Cache-Control, Accept',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS'
      });

      // Подготовка RAG запроса
      const ragRequest: RAGRequest = {
        question: message,
        sessionId,
        accessLevel: user.accessLevel,
        context: {
          userId: user.id,
          userEmail: user.email
        }
      };

      // Streaming обработка
      await chatService.processStreamingRAGQuery(ragRequest, res);

    } catch (error) {
      logger.error('Chat streaming failed', {
        error,
        userId: req.user?.id
      });

      if (!res.headersSent) {
        res.status(500).json({
          success: false,
          error: error instanceof AppError ? error.message : 'Internal server error',
          metadata: {
            timestamp: new Date().toISOString()
          }
        });
      }
    }
  }

  /**
   * GET /api/chat/sessions
   * Получение списка сессий пользователя
   */
  async getSessions(req: AuthenticatedRequest, res: Response): Promise<void> {
    try {
      const user = req.user;
      const page = parseInt(req.query.page as string) || 1;
      const limit = parseInt(req.query.limit as string) || 20;

      logger.info('Get chat sessions request', {
        userId: user.id,
        page,
        limit
      });

      const sessions = await chatService.getUserSessions(user.id, page, limit);

      const response: ExtendedApiResponse = {
        success: true,
        data: sessions.sessions,
        metadata: {
          page,
          total: sessions.total,
          totalPages: Math.ceil(sessions.total / limit),
          hasNext: page < Math.ceil(sessions.total / limit),
          hasPrev: page > 1,
          timestamp: new Date().toISOString()
        }
      };

      res.status(200).json(response);

    } catch (error) {
      logger.error('Get sessions failed', {
        error,
        userId: req.user?.id
      });

      res.status(500).json({
        success: false,
        error: 'Failed to get sessions',
        metadata: {
          timestamp: new Date().toISOString()
        }
      });
    }
  }

  /**
   * GET /api/chat/sessions/:sessionId
   * Получение сообщений сессии
   */
  async getSessionMessages(req: AuthenticatedRequest, res: Response): Promise<void> {
    try {
      const user = req.user;
      const { sessionId } = req.params;
      const page = parseInt(req.query.page as string) || 1;
      const limit = parseInt(req.query.limit as string) || 50;

      // Валидация UUID
      if (!sessionId.match(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i)) {
        throw new AppError('Invalid session ID format', 400);
      }

      logger.info('Get session messages request', {
        userId: user.id,
        sessionId,
        page,
        limit
      });

      const messages = await chatService.getSessionMessages(user.id, sessionId, page, limit);

      const response: ExtendedApiResponse = {
        success: true,
        data: messages.messages,
        metadata: {
          page,
          total: messages.total,
          totalPages: Math.ceil(messages.total / limit),
          hasNext: page < Math.ceil(messages.total / limit),
          hasPrev: page > 1,
          timestamp: new Date().toISOString()
        }
      };

      res.status(200).json(response);

    } catch (error) {
      logger.error('Get session messages failed', {
        error,
        userId: req.user?.id,
        sessionId: req.params.sessionId
      });

      if (error instanceof AppError) {
        res.status(error.statusCode).json({
          success: false,
          error: error.message,
          metadata: {
            timestamp: new Date().toISOString()
          }
        });
      } else {
        res.status(500).json({
          success: false,
          error: 'Failed to get session messages',
          metadata: {
            timestamp: new Date().toISOString()
          }
        });
      }
    }
  }

  /**
   * DELETE /api/chat/sessions/:sessionId
   * Удаление сессии
   */
  async deleteSession(req: AuthenticatedRequest, res: Response): Promise<void> {
    try {
      const user = req.user;
      const { sessionId } = req.params;

      // Валидация UUID
      if (!sessionId.match(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i)) {
        throw new AppError('Invalid session ID format', 400);
      }

      logger.info('Delete session request', {
        userId: user.id,
        sessionId
      });

      await chatService.deleteSession(user.id, sessionId);

      const response: ExtendedApiResponse = {
        success: true,
        data: { sessionId },
        metadata: {
          timestamp: new Date().toISOString()
        }
      };

      res.status(200).json(response);

    } catch (error) {
      logger.error('Delete session failed', {
        error,
        userId: req.user?.id,
        sessionId: req.params.sessionId
      });

      if (error instanceof AppError) {
        res.status(error.statusCode).json({
          success: false,
          error: error.message,
          metadata: {
            timestamp: new Date().toISOString()
          }
        });
      } else {
        res.status(500).json({
          success: false,
          error: 'Failed to delete session',
          metadata: {
            timestamp: new Date().toISOString()
          }
        });
      }
    }
  }

  /**
   * POST /api/chat/batch
   * T1.6: Batch endpoint для множественных запросов
   */
  async batchMessage(req: AuthenticatedRequest, res: Response): Promise<void> {
    const startTime = Date.now();
    
    try {
      const { messages, sessionId, options = {} } = req.body;
      const user = req.user;

      logger.info('Batch chat request received', {
        userId: user.id,
        messagesCount: messages.length,
        sessionId,
        accessLevel: user.accessLevel
      });

      // КРИТИЧНО: Проверка уровня доступа согласно ТЗ
      if (user.accessLevel < 1) {
        throw new AppError('Insufficient access level for chat', 403);
      }

      // T1.6: Используем SearchService для batch поиска
      const { SearchService } = await import('../services/searchService');
      const batchResult = await SearchService.batchHybridSearch(
        messages,
        user.accessLevel,
        options
      );

      const processingTime = Date.now() - startTime;

      // ОБЯЗАТЕЛЬНО: Единый формат ответа согласно ТЗ
      const response: ExtendedApiResponse = {
        success: true,
        data: {
          ...batchResult,
          batchSize: messages.length
        },
        metadata: {
          timestamp: new Date().toISOString(),
          processingTime
        }
      };

      logger.info('Batch chat processed successfully', {
        userId: user.id,
        messagesCount: messages.length,
        processingTime,
        cacheHits: batchResult.cache_hits || 0
      });

      res.status(200).json(response);

    } catch (error) {
      const processingTime = Date.now() - startTime;
      
      logger.error('Batch chat processing failed', {
        error,
        userId: req.user?.id,
        processingTime
      });

      if (error instanceof AppError) {
        res.status(error.statusCode).json({
          success: false,
          error: error.message,
          metadata: {
            timestamp: new Date().toISOString(),
            processingTime
          }
        });
      } else {
        res.status(500).json({
          success: false,
          error: 'Internal server error',
          metadata: {
            timestamp: new Date().toISOString(),
            processingTime
          }
        });
      }
    }
  }
}

export const chatController = new ChatController();
