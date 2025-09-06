import { Request, Response, NextFunction } from 'express';
import { AppError } from '../types';
import { logger } from '../config/database';
import type { ApiResponse } from '../types';

// ОБЯЗАТЕЛЬНО: Глобальный обработчик ошибок согласно ТЗ
export const errorHandler = (
  err: Error | AppError,
  req: Request,
  res: Response,
  next: NextFunction
): void => {
  // Логируем все ошибки согласно ТЗ
  const logContext = {
    error: {
      message: err.message,
      stack: err.stack,
      name: err.name
    },
    request: {
      method: req.method,
      url: req.url,
      path: req.path,
      ip: req.ip,
      userAgent: req.get('User-Agent'),
      userId: req.user?.id,
      body: req.method !== 'GET' ? req.body : undefined
    }
  };

  // Определяем статус код и сообщение
  let statusCode = 500;
  let message = 'Internal server error';
  let isOperational = false;

  if (err instanceof AppError) {
    statusCode = err.statusCode;
    message = err.message;
    isOperational = err.isOperational;
    
    // Логируем операционные ошибки как warning, остальные как error
    if (isOperational && statusCode < 500) {
      logger.warn('Operational error occurred', logContext);
    } else {
      logger.error('Application error occurred', logContext);
    }
  } else {
    // Неожиданные ошибки всегда логируем как error
    logger.error('Unexpected error occurred', logContext);
  }

  // ОБЯЗАТЕЛЬНО: Единый формат ответа об ошибке согласно ТЗ
  const response: ApiResponse = {
    success: false,
    error: message,
    ...(process.env.NODE_ENV === 'development' && {
      stack: err.stack,
      details: {
        name: err.name,
        isOperational,
        statusCode
      }
    })
  };

  res.status(statusCode).json(response);
};

// Обработчик для несуществующих роутов
export const notFoundHandler = (req: Request, res: Response): void => {
  logger.warn('Route not found', {
    method: req.method,
    url: req.url,
    ip: req.ip,
    userAgent: req.get('User-Agent')
  });

  const response: ApiResponse = {
    success: false,
    error: `Route ${req.method} ${req.url} not found`
  };

  res.status(404).json(response);
};

// Обработчик для неперехваченных исключений
export const uncaughtExceptionHandler = (err: Error): void => {
  logger.error('Uncaught Exception', {
    error: {
      message: err.message,
      stack: err.stack,
      name: err.name
    }
  });

  // Graceful shutdown
  process.exit(1);
};

// Обработчик для неперехваченных Promise rejections
export const unhandledRejectionHandler = (reason: any, promise: Promise<any>): void => {
  logger.error('Unhandled Rejection', {
    reason,
    promise: promise.toString()
  });

  // Graceful shutdown
  process.exit(1);
};

// Rate limiting error handler
export const rateLimitHandler = (req: Request, res: Response): void => {
  logger.warn('Rate limit exceeded', {
    ip: req.ip,
    userAgent: req.get('User-Agent'),
    path: req.path,
    userId: req.user?.id
  });

  const response: ApiResponse = {
    success: false,
    error: 'Too many requests, please try again later'
  };

  res.status(429).json(response);
};

// Validation error handler
export const validationErrorHandler = (
  field: string,
  message: string,
  req: Request,
  res: Response
): void => {
  logger.warn('Validation error', {
    field,
    message,
    body: req.body,
    ip: req.ip,
    userId: req.user?.id
  });

  const response: ApiResponse = {
    success: false,
    error: message,
    ...(process.env.NODE_ENV === 'development' && {
      field
    })
  };

  res.status(400).json(response);
};
