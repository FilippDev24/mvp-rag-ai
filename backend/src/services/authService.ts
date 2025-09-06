import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { prisma, logger } from '../config/database';
import { AppError, CONSTANTS } from '../types';
import type { LoginRequest, LoginResponse, UserWithoutPassword } from '../types';

export class AuthService {
  // ОБЯЗАТЕЛЬНО: Используем BCRYPT_ROUNDS = 12 согласно ТЗ
  private static readonly SALT_ROUNDS = CONSTANTS.BCRYPT_ROUNDS;
  
  // Логин пользователя
  static async login(loginData: LoginRequest): Promise<LoginResponse> {
    const { email, password } = loginData;
    
    try {
      // КРИТИЧНО: Логируем все неудачные попытки аутентификации согласно ТЗ
      logger.info('Login attempt', { email });
      
      // Находим пользователя по email
      const user = await prisma.user.findUnique({
        where: { email: email.toLowerCase() }
      });
      
      if (!user) {
        logger.warn('Login failed: User not found', { email });
        throw new AppError('Invalid email or password', 401);
      }
      
      // Проверяем пароль
      const isPasswordValid = await bcrypt.compare(password, user.passwordHash);
      
      if (!isPasswordValid) {
        logger.warn('Login failed: Invalid password', { 
          email, 
          userId: user.id 
        });
        throw new AppError('Invalid email or password', 401);
      }
      
      // Создаем JWT токен
      const token = this.generateToken(user.id);
      
      // Убираем пароль из ответа
      const userWithoutPassword: UserWithoutPassword = {
        id: user.id,
        email: user.email,
        fullName: user.fullName,
        accessLevel: user.accessLevel,
        role: user.role,
        createdAt: user.createdAt
      };
      
      logger.info('Login successful', {
        userId: user.id,
        email: user.email,
        accessLevel: user.accessLevel,
        role: user.role
      });
      
      return {
        user: userWithoutPassword,
        token,
        expiresIn: CONSTANTS.JWT_EXPIRY
      };
      
    } catch (error) {
      if (error instanceof AppError) {
        throw error;
      }
      
      logger.error('Login service error', { error, email });
      throw new AppError('Login failed', 500);
    }
  }
  
  // Получение информации о текущем пользователе
  static async getCurrentUser(userId: string): Promise<UserWithoutPassword> {
    try {
      const user = await prisma.user.findUnique({
        where: { id: userId }
      });
      
      if (!user) {
        logger.warn('Get current user failed: User not found', { userId });
        throw new AppError('User not found', 404);
      }
      
      // Убираем пароль из ответа
      const userWithoutPassword: UserWithoutPassword = {
        id: user.id,
        email: user.email,
        fullName: user.fullName,
        accessLevel: user.accessLevel,
        role: user.role,
        createdAt: user.createdAt
      };
      
      logger.info('Current user retrieved', {
        userId: user.id,
        email: user.email
      });
      
      return userWithoutPassword;
      
    } catch (error) {
      if (error instanceof AppError) {
        throw error;
      }
      
      logger.error('Get current user service error', { error, userId });
      throw new AppError('Failed to get user information', 500);
    }
  }
  
  // Проверка валидности токена
  static async validateToken(token: string): Promise<UserWithoutPassword | null> {
    try {
      const jwtSecret = process.env.JWT_SECRET;
      if (!jwtSecret) {
        logger.error('JWT_SECRET not configured');
        return null;
      }
      
      const decoded = jwt.verify(token, jwtSecret) as any;
      
      const user = await prisma.user.findUnique({
        where: { id: decoded.id }
      });
      
      if (!user) {
        logger.warn('Token validation failed: User not found', { userId: decoded.id });
        return null;
      }
      
      // Убираем пароль из ответа
      const userWithoutPassword: UserWithoutPassword = {
        id: user.id,
        email: user.email,
        fullName: user.fullName,
        accessLevel: user.accessLevel,
        role: user.role,
        createdAt: user.createdAt
      };
      
      return userWithoutPassword;
      
    } catch (error) {
      logger.debug('Token validation failed', { error });
      return null;
    }
  }
  
  // Генерация JWT токена
  private static generateToken(userId: string): string {
    const jwtSecret = process.env.JWT_SECRET;
    if (!jwtSecret) {
      logger.error('JWT_SECRET not configured');
      throw new AppError('Server configuration error', 500);
    }
    
    const payload = {
      id: userId,
      iat: Math.floor(Date.now() / 1000)
    };
    
    return jwt.sign(payload, jwtSecret, {
      expiresIn: CONSTANTS.JWT_EXPIRY
    });
  }
  
  // Хеширование пароля (для будущего использования при регистрации)
  static async hashPassword(password: string): Promise<string> {
    try {
      return await bcrypt.hash(password, this.SALT_ROUNDS);
    } catch (error) {
      logger.error('Password hashing error', { error });
      throw new AppError('Password processing failed', 500);
    }
  }
  
  // Проверка сложности пароля согласно ТЗ
  static validatePasswordStrength(password: string): { isValid: boolean; errors: string[] } {
    const errors: string[] = [];
    
    if (password.length < 8) {
      errors.push('Password must be at least 8 characters long');
    }
    
    if (!/[a-z]/.test(password)) {
      errors.push('Password must contain at least one lowercase letter');
    }
    
    if (!/[A-Z]/.test(password)) {
      errors.push('Password must contain at least one uppercase letter');
    }
    
    if (!/\d/.test(password)) {
      errors.push('Password must contain at least one digit');
    }
    
    if (!/[@$!%*?&]/.test(password)) {
      errors.push('Password must contain at least one special character (@$!%*?&)');
    }
    
    return {
      isValid: errors.length === 0,
      errors
    };
  }
  
  // Логаут (в данной реализации просто логируем событие)
  static async logout(userId: string): Promise<void> {
    try {
      logger.info('User logged out', { userId });
      
      // В будущем здесь можно добавить:
      // - Добавление токена в blacklist
      // - Очистка refresh токенов
      // - Обновление времени последней активности
      
    } catch (error) {
      logger.error('Logout service error', { error, userId });
      throw new AppError('Logout failed', 500);
    }
  }
}
