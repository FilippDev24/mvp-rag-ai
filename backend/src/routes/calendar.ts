import { Router } from 'express';
import { calendarController } from '../controllers/calendarController';
import { authenticate } from '../middlewares/auth';

const router = Router();

// OAuth callback endpoint для получения токенов
router.get('/oauth/callback', calendarController.handleOAuthCallback);

// Получение URL для авторизации
router.get('/oauth/authorize', authenticate, calendarController.getAuthorizationUrl as any);

// Тестирование доступа к календарю
router.get('/test', authenticate, calendarController.testCalendarAccess as any);

// Получение списка календарей
router.get('/calendars', authenticate, calendarController.getCalendars as any);

// Создание встречи
router.post('/meetings', authenticate, calendarController.createMeeting as any);

// Проверка доступности времени
router.post('/availability', authenticate, calendarController.checkAvailability as any);

// Поиск сотрудников
router.get('/employees/search', authenticate, calendarController.searchEmployees as any);

// CalDAV endpoints
router.get('/caldav/instructions', authenticate, calendarController.getCalDAVInstructions as any);
router.post('/caldav/setup', authenticate, calendarController.setupCalDAV as any);
router.get('/caldav/test', authenticate, calendarController.testCalDAV as any);
router.post('/caldav/meetings', authenticate, calendarController.createCalDAVMeeting as any);

export default router;
