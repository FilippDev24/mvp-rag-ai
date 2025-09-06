import { Request, Response, NextFunction } from 'express';
import Joi from 'joi';
import { AuthService } from '../services/authService';
import { AppError } from '../types';
import { logger } from '../config/database';
import type { LoginRequest, ApiResponse, LoginResponse, UserWithoutPassword } from '../types';

// Схемы валидации согласно ТЗ
const loginSchema = Joi.object({
  email: Joi.string().email().required().messages({
    'string.email': 'Please provide a valid email address',
    'any.required': 'Email is required'
  }),
  password: Joi.string().min(1).required().messages({
    'any.required': 'Password is required',
    'string.min': 'Password cannot be empty'
  })
});

export class AuthController {
  // POST /api/auth/login
  static async login(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      // ОБЯЗАТЕЛЬНО: Валидация входных данных согласно ТЗ
      const { error, value } = loginSchema.validate(req.body);
      if (error) {
        logger.warn('Login validation failed', {
          error: error.details[0].message,
          ip: req.ip,
          userAgent: req.get('User-Agent')
        });
        throw new AppError(error.details[0].message, 400);
      }
      
      const loginData: LoginRequest = value;
      
      // Выполняем логин
      const result: LoginResponse = await AuthService.login(loginData);
      
      // ОБЯЗАТЕЛЬНО: Единый формат ответа согласно ТЗ
      const response: ApiResponse<LoginResponse> = {
        success: true,
        data: result,
        metadata: {
          timestamp: new Date().toISOString()
        }
      };
      
      logger.info('Login endpoint success', {
        userId: result.user.id,
        email: result.user.email,
        ip: req.ip,
        userAgent: req.get('User-Agent')
      });
      
      res.status(200).json(response);
      
    } catch (error) {
      next(error);
    }
  }
  
  // GET /api/auth/me
  static async getCurrentUser(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      if (!req.user) {
        throw new AppError('Authentication required', 401);
      }
      
      // Получаем актуальную информацию о пользователе из БД
      const user: UserWithoutPassword = await AuthService.getCurrentUser(req.user.id);
      
      const response: ApiResponse<UserWithoutPassword> = {
        success: true,
        data: user,
        metadata: {
          timestamp: new Date().toISOString()
        }
      };
      
      logger.info('Get current user endpoint success', {
        userId: user.id,
        email: user.email,
        ip: req.ip
      });
      
      res.status(200).json(response);
      
    } catch (error) {
      next(error);
    }
  }
  
  // POST /api/auth/logout
  static async logout(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      if (!req.user) {
        throw new AppError('Authentication required', 401);
      }
      
      // Выполняем логаут
      await AuthService.logout(req.user.id);
      
      const response: ApiResponse<{ message: string }> = {
        success: true,
        data: {
          message: 'Logged out successfully'
        },
        metadata: {
          timestamp: new Date().toISOString()
        }
      };
      
      logger.info('Logout endpoint success', {
        userId: req.user.id,
        ip: req.ip,
        userAgent: req.get('User-Agent')
      });
      
      res.status(200).json(response);
      
    } catch (error) {
      next(error);
    }
  }
  
  // GET /api/auth/validate-token (дополнительный endpoint для проверки токена)
  static async validateToken(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const authHeader = req.headers.authorization;
      const token = authHeader?.replace('Bearer ', '');
      
      if (!token) {
        throw new AppError('Token is required', 400);
      }
      
      const user = await AuthService.validateToken(token);
      
      if (!user) {
        throw new AppError('Invalid or expired token', 401);
      }
      
      const response: ApiResponse<{ valid: boolean; user: UserWithoutPassword }> = {
        success: true,
        data: {
          valid: true,
          user
        },
        metadata: {
          timestamp: new Date().toISOString()
        }
      };
      
      logger.info('Token validation endpoint success', {
        userId: user.id,
        ip: req.ip
      });
      
      res.status(200).json(response);
      
    } catch (error) {
      next(error);
    }
  }
  
  // GET /api/auth/check-access/:level (проверка уровня доступа)
  static checkAccessLevel(requiredLevel: number) {
    return async (req: Request, res: Response, next: NextFunction): Promise<void> => {
      try {
        if (!req.user) {
          throw new AppError('Authentication required', 401);
        }
        
        const hasAccess = req.user.accessLevel >= requiredLevel;
        
        const response: ApiResponse<{ 
          hasAccess: boolean; 
          userLevel: number; 
          requiredLevel: number 
        }> = {
          success: true,
          data: {
            hasAccess,
            userLevel: req.user.accessLevel,
            requiredLevel
          },
          metadata: {
            timestamp: new Date().toISOString()
          }
        };
        
        logger.info('Access level check endpoint', {
          userId: req.user.id,
          userLevel: req.user.accessLevel,
          requiredLevel,
          hasAccess,
          ip: req.ip
        });
        
        res.status(200).json(response);
        
      } catch (error) {
        next(error);
      }
    };
  }
}

// Middleware для валидации входных данных
export const validateLogin = (req: Request, res: Response, next: NextFunction): void => {
  const { error } = loginSchema.validate(req.body);
  if (error) {
    logger.warn('Login validation middleware failed', {
      error: error.details[0].message,
      body: req.body,
      ip: req.ip
    });
    
    const response: ApiResponse = {
      success: false,
      error: error.details[0].message
    };
    
    res.status(400).json(response);
    return;
  }
  
  next();
};
