import { Router } from 'express';
import { AuthController, validateLogin } from '../controllers/authController';
import { authenticate, checkAccessLevel } from '../middlewares/auth';
import { logger } from '../config/database';

const router = Router();

// ОБЯЗАТЕЛЬНО: Логируем все обращения к auth endpoints согласно ТЗ
router.use((req, res, next) => {
  logger.info('Auth endpoint accessed', {
    method: req.method,
    path: req.path,
    ip: req.ip,
    userAgent: req.get('User-Agent')
  });
  next();
});

// POST /api/auth/login - Вход в систему
router.post('/login', 
  validateLogin,           // Валидация входных данных
  AuthController.login     // Контроллер логина
);

// POST /api/auth/logout - Выход из системы
router.post('/logout',
  authenticate,            // ОБЯЗАТЕЛЬНО: Проверка JWT
  AuthController.logout    // Контроллер логаута
);

// GET /api/auth/me - Получение информации о текущем пользователе
router.get('/me',
  authenticate,            // ОБЯЗАТЕЛЬНО: Проверка JWT
  AuthController.getCurrentUser
);

// GET /api/auth/validate-token - Проверка валидности токена
router.get('/validate-token',
  AuthController.validateToken
);

// GET /api/auth/check-access/:level - Проверка уровня доступа
router.get('/check-access/:level',
  authenticate,            // ОБЯЗАТЕЛЬНО: Проверка JWT
  (req, res, next) => {
    const level = parseInt(req.params.level);
    if (isNaN(level) || level < 1 || level > 100) {
      return res.status(400).json({
        success: false,
        error: 'Invalid access level. Must be between 1 and 100'
      });
    }
    
    // Вызываем контроллер с нужным уровнем
    AuthController.checkAccessLevel(level)(req, res, next);
  }
);

export default router;
