import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';
import { prisma, logger } from '../config/database';
import { AppError } from '../types';
import type { AuthenticatedUser } from '../types';

// Расширяем Request интерфейс для добавления user
declare global {
  namespace Express {
    interface Request {
      user?: AuthenticatedUser;
    }
  }
}

// ОБЯЗАТЕЛЬНО: Проверка JWT токена согласно ТЗ
export const authenticate = async (req: Request, res: Response, next: NextFunction): Promise<void> => {
  try {
    // Получаем токен из заголовка Authorization
    const authHeader = req.headers.authorization;
    const token = authHeader?.replace('Bearer ', '');
    
    if (!token) {
      logger.warn('Authentication failed: No token provided', {
        ip: req.ip,
        userAgent: req.get('User-Agent'),
        path: req.path
      });
      throw new AppError('Unauthorized: No token provided', 401);
    }
    
    // Проверяем JWT токен
    const jwtSecret = process.env.JWT_SECRET;
    if (!jwtSecret) {
      logger.error('JWT_SECRET not configured');
      throw new AppError('Server configuration error', 500);
    }
    
    let decoded: any;
    try {
      decoded = jwt.verify(token, jwtSecret);
    } catch (jwtError) {
      logger.warn('Authentication failed: Invalid token', {
        error: jwtError,
        ip: req.ip,
        userAgent: req.get('User-Agent'),
        path: req.path
      });
      throw new AppError('Unauthorized: Invalid token', 401);
    }
    
    // КРИТИЧНО: Проверяем существование пользователя в БД
    const user = await prisma.user.findUnique({
      where: { id: decoded.id }
    });
    
    if (!user) {
      logger.warn('Authentication failed: User not found', {
        userId: decoded.id,
        ip: req.ip,
        userAgent: req.get('User-Agent'),
        path: req.path
      });
      throw new AppError('Unauthorized: User not found', 401);
    }
    
    // Добавляем пользователя в request
    req.user = user as AuthenticatedUser;
    
    logger.info('User authenticated successfully', {
      userId: user.id,
      email: user.email,
      accessLevel: user.accessLevel,
      path: req.path
    });
    
    next();
    
  } catch (error) {
    if (error instanceof AppError) {
      res.status(error.statusCode).json({
        success: false,
        error: error.message
      });
    } else {
      logger.error('Authentication middleware error', { error });
      res.status(500).json({
        success: false,
        error: 'Internal server error'
      });
    }
  }
};

// КРИТИЧНО: Проверка уровня доступа согласно ТЗ
export const checkAccessLevel = (requiredLevel: number) => {
  return (req: Request, res: Response, next: NextFunction): void => {
    try {
      if (!req.user) {
        logger.error('Access level check called without authentication');
        throw new AppError('Authentication required', 401);
      }
      
      if (req.user.accessLevel < requiredLevel) {
        logger.warn('Access denied: Insufficient access level', {
          userId: req.user.id,
          userAccessLevel: req.user.accessLevel,
          requiredLevel,
          path: req.path
        });
        throw new AppError('Forbidden: Insufficient access level', 403);
      }
      
      logger.info('Access level check passed', {
        userId: req.user.id,
        userAccessLevel: req.user.accessLevel,
        requiredLevel,
        path: req.path
      });
      
      next();
      
    } catch (error) {
      if (error instanceof AppError) {
        res.status(error.statusCode).json({
          success: false,
          error: error.message
        });
      } else {
        logger.error('Access level middleware error', { error });
        res.status(500).json({
          success: false,
          error: 'Internal server error'
        });
      }
    }
  };
};

// Проверка роли администратора
export const requireAdmin = (req: Request, res: Response, next: NextFunction): void => {
  try {
    if (!req.user) {
      throw new AppError('Authentication required', 401);
    }
    
    if (req.user.role !== 'ADMIN') {
      logger.warn('Admin access denied', {
        userId: req.user.id,
        userRole: req.user.role,
        path: req.path
      });
      throw new AppError('Forbidden: Admin access required', 403);
    }
    
    logger.info('Admin access granted', {
      userId: req.user.id,
      path: req.path
    });
    
    next();
    
  } catch (error) {
    if (error instanceof AppError) {
      res.status(error.statusCode).json({
        success: false,
        error: error.message
      });
    } else {
      logger.error('Admin middleware error', { error });
      res.status(500).json({
        success: false,
        error: 'Internal server error'
      });
    }
  }
};

// Опциональная аутентификация (не требует токен, но если есть - проверяет)
export const optionalAuth = async (req: Request, res: Response, next: NextFunction): Promise<void> => {
  try {
    const authHeader = req.headers.authorization;
    const token = authHeader?.replace('Bearer ', '');
    
    if (!token) {
      // Токена нет - продолжаем без аутентификации
      next();
      return;
    }
    
    // Токен есть - проверяем его
    const jwtSecret = process.env.JWT_SECRET;
    if (!jwtSecret) {
      next();
      return;
    }
    
    try {
      const decoded = jwt.verify(token, jwtSecret) as any;
      const user = await prisma.user.findUnique({
        where: { id: decoded.id }
      });
      
      if (user) {
        req.user = user as AuthenticatedUser;
        logger.info('Optional authentication successful', {
          userId: user.id,
          path: req.path
        });
      }
    } catch (jwtError) {
      // Игнорируем ошибки JWT при опциональной аутентификации
      logger.debug('Optional authentication failed', { error: jwtError });
    }
    
    next();
    
  } catch (error) {
    logger.error('Optional auth middleware error', { error });
    next(); // Продолжаем выполнение даже при ошибке
  }
};
