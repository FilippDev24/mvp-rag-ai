import { Router, Request, Response } from 'express';
import { chatController } from '../controllers/chatController';
import { authenticate } from '../middlewares/auth';
import { validate } from '../middlewares/validation';
import { AuthenticatedRequest } from '../types';
import Joi from 'joi';

const router = Router();

// ОБЯЗАТЕЛЬНО: Валидация схем согласно ТЗ
const messageSchema = Joi.object({
  message: Joi.string().min(1).max(2000).required(),
  sessionId: Joi.string().uuid().optional()
});

// T1.6: Валидация для batch запросов
const batchMessageSchema = Joi.object({
  messages: Joi.array().items(Joi.string().min(1).max(2000)).min(1).max(10).required(),
  sessionId: Joi.string().uuid().optional(),
  options: Joi.object({
    vectorWeight: Joi.number().min(0).max(1).default(0.7),
    bm25Weight: Joi.number().min(0).max(1).default(0.3),
    topK: Joi.number().integer().min(1).max(100).default(30),
    rerankTopK: Joi.number().integer().min(1).max(50).default(10)
  }).optional()
});

const sessionParamsSchema = Joi.object({
  sessionId: Joi.string().uuid().required()
});

const paginationSchema = Joi.object({
  page: Joi.number().integer().min(1).default(1),
  limit: Joi.number().integer().min(1).max(100).default(20)
});

/**
 * POST /api/chat/message
 * Основной endpoint для RAG запросов согласно требованиям
 * 
 * ОБЯЗАТЕЛЬНЫЕ middleware согласно ТЗ:
 * 1. authenticate - проверка JWT
 * 2. validate - валидация данных
 */
router.post('/message',
  authenticate,                           // 1. Проверка JWT
  validate(messageSchema),                // 2. Валидация данных
  (req: Request, res: Response) => chatController.sendMessage(req as AuthenticatedRequest, res)
);

/**
 * POST /api/chat/stream
 * Streaming endpoint для RAG ответов
 */
router.post('/stream',
  authenticate,                           // 1. Проверка JWT
  validate(messageSchema),                // 2. Валидация данных
  (req: Request, res: Response) => chatController.streamMessage(req as AuthenticatedRequest, res)
);

/**
 * POST /api/chat/batch
 * T1.6: Batch endpoint для множественных запросов
 */
router.post('/batch',
  authenticate,                           // 1. Проверка JWT
  validate(batchMessageSchema),           // 2. Валидация данных
  (req: Request, res: Response) => chatController.batchMessage(req as AuthenticatedRequest, res)
);

/**
 * GET /api/chat/sessions
 * Получение списка сессий пользователя
 */
router.get('/sessions',
  authenticate,                           // 1. Проверка JWT
  validate(paginationSchema, 'query'),    // 2. Валидация query параметров
  (req: Request, res: Response) => chatController.getSessions(req as AuthenticatedRequest, res)
);

/**
 * GET /api/chat/sessions/:sessionId
 * Получение сообщений сессии
 */
router.get('/sessions/:sessionId',
  authenticate,                           // 1. Проверка JWT
  validate(sessionParamsSchema, 'params'), // 2. Валидация параметров
  validate(paginationSchema, 'query'),    // 3. Валидация query параметров
  (req: Request, res: Response) => chatController.getSessionMessages(req as AuthenticatedRequest, res)
);

/**
 * DELETE /api/chat/sessions/:sessionId
 * Удаление сессии
 */
router.delete('/sessions/:sessionId',
  authenticate,                           // 1. Проверка JWT
  validate(sessionParamsSchema, 'params'), // 2. Валидация параметров
  (req: Request, res: Response) => chatController.deleteSession(req as AuthenticatedRequest, res)
);

export default router;
