import { Request, Response, NextFunction } from 'express';
import { yandexCalendarService } from '../services/yandexCalendarService';
import { caldavCalendarService } from '../services/caldavCalendarService';
import { calendarAgentService } from '../services/calendarAgentService';
import { AppError, AuthenticatedRequest } from '../types';
import { logger } from '../utils/logger';

class CalendarController {
  /**
   * Обработка OAuth callback для получения токенов
   */
  async handleOAuthCallback(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { code, error } = req.query;

      if (error) {
        logger.error('OAuth authorization error', { error });
        res.status(400).json({
          success: false,
          error: `Authorization failed: ${error}`
        });
        return;
      }

      if (!code || typeof code !== 'string') {
        res.status(400).json({
          success: false,
          error: 'Authorization code not provided'
        });
        return;
      }

      // Обмениваем код на токены
      const tokens = await yandexCalendarService.exchangeCodeForTokens(code);
      
      // Получаем информацию о пользователе
      const userInfo = await yandexCalendarService.getUserInfo(tokens.access_token);
      
      // Сохраняем токены как системные
      await yandexCalendarService.saveSystemTokens(tokens, userInfo.default_email);

      logger.info('System calendar tokens obtained successfully', {
        email: userInfo.default_email
      });

      res.send(`
        <html>
          <body>
            <h2>✅ Календарь успешно подключен!</h2>
            <p>Email: ${userInfo.default_email}</p>
            <p>Токены сохранены. Теперь можно создавать встречи через чат.</p>
            <p>Можете закрыть это окно.</p>
          </body>
        </html>
      `);

    } catch (error) {
      logger.error('OAuth callback error', { error });
      next(new AppError('Failed to process OAuth callback', 500));
    }
  }

  /**
   * Получение URL для авторизации
   */
  async getAuthorizationUrl(req: AuthenticatedRequest, res: Response, next: NextFunction): Promise<void> {
    try {
      const authUrl = yandexCalendarService.getAuthorizationUrl();
      
      res.json({
        success: true,
        data: {
          authUrl,
          instructions: 'Откройте эту ссылку в браузере для авторизации календаря'
        }
      });

    } catch (error) {
      logger.error('Error generating authorization URL', { error });
      next(new AppError('Failed to generate authorization URL', 500));
    }
  }

  /**
   * Тестирование доступа к календарю
   */
  async testCalendarAccess(req: AuthenticatedRequest, res: Response, next: NextFunction): Promise<void> {
    try {
      const testResult = await yandexCalendarService.testCalendarAccess();
      
      res.json({
        success: true,
        data: testResult,
        metadata: {
          timestamp: new Date().toISOString()
        }
      });

    } catch (error) {
      logger.error('Calendar access test failed', { error });
      next(new AppError('Calendar access test failed', 500));
    }
  }

  /**
   * Получение списка календарей
   */
  async getCalendars(req: AuthenticatedRequest, res: Response, next: NextFunction): Promise<void> {
    try {
      const calendars = await yandexCalendarService.getCalendars();
      
      res.json({
        success: true,
        data: calendars,
        metadata: {
          count: calendars.length,
          timestamp: new Date().toISOString()
        }
      });

    } catch (error) {
      logger.error('Error getting calendars', { error });
      next(new AppError('Failed to get calendars', 500));
    }
  }

  /**
   * Создание встречи
   */
  async createMeeting(req: AuthenticatedRequest, res: Response, next: NextFunction): Promise<void> {
    try {
      const { summary, start, end, attendees, description, location } = req.body;

      if (!summary || !start || !end) {
        res.status(400).json({
          success: false,
          error: 'Missing required fields: summary, start, end'
        });
        return;
      }

      const event = await yandexCalendarService.createEvent({
        summary,
        description,
        start: {
          dateTime: start,
          timeZone: 'Europe/Moscow'
        },
        end: {
          dateTime: end,
          timeZone: 'Europe/Moscow'
        },
        attendees: attendees || [],
        location
      });

      logger.info('Meeting created successfully', {
        eventId: event.id,
        summary: event.summary,
        userId: req.user.id
      });

      res.json({
        success: true,
        data: event,
        metadata: {
          timestamp: new Date().toISOString()
        }
      });

    } catch (error) {
      logger.error('Error creating meeting', { error, userId: req.user.id });
      next(new AppError('Failed to create meeting', 500));
    }
  }

  /**
   * Проверка доступности времени
   */
  async checkAvailability(req: AuthenticatedRequest, res: Response, next: NextFunction): Promise<void> {
    try {
      const { emails, timeMin, timeMax } = req.body;

      if (!emails || !Array.isArray(emails) || !timeMin || !timeMax) {
        res.status(400).json({
          success: false,
          error: 'Missing required fields: emails (array), timeMin, timeMax'
        });
        return;
      }

      const availability = await yandexCalendarService.checkAvailability(emails, timeMin, timeMax);
      
      res.json({
        success: true,
        data: availability,
        metadata: {
          timestamp: new Date().toISOString()
        }
      });

    } catch (error) {
      logger.error('Error checking availability', { error });
      next(new AppError('Failed to check availability', 500));
    }
  }

  /**
   * Поиск сотрудников в базе знаний
   */
  async searchEmployees(req: AuthenticatedRequest, res: Response, next: NextFunction): Promise<void> {
    try {
      const { query } = req.query;

      if (!query || typeof query !== 'string') {
        res.status(400).json({
          success: false,
          error: 'Query parameter is required'
        });
        return;
      }

      const employees = await calendarAgentService.searchEmployees(query, req.user.accessLevel);
      
      res.json({
        success: true,
        data: employees,
        metadata: {
          count: employees.length,
          timestamp: new Date().toISOString()
        }
      });

    } catch (error) {
      logger.error('Error searching employees', { error, query: req.query.query });
      next(new AppError('Failed to search employees', 500));
    }
  }

  /**
   * Настройка CalDAV подключения
   */
  async setupCalDAV(req: AuthenticatedRequest, res: Response, next: NextFunction): Promise<void> {
    try {
      const { email, appPassword } = req.body;

      if (!email || !appPassword) {
        res.status(400).json({
          success: false,
          error: 'Missing required fields: email, appPassword'
        });
        return;
      }

      await caldavCalendarService.setupSystemCredentials(email, appPassword);
      
      res.json({
        success: true,
        data: {
          message: 'CalDAV подключение настроено успешно',
          email
        },
        metadata: {
          timestamp: new Date().toISOString()
        }
      });

    } catch (error) {
      logger.error('Error setting up CalDAV', { error });
      next(new AppError('Failed to setup CalDAV connection', 500));
    }
  }

  /**
   * Тестирование CalDAV подключения
   */
  async testCalDAV(req: AuthenticatedRequest, res: Response, next: NextFunction): Promise<void> {
    try {
      const testResult = await caldavCalendarService.testConnection();
      
      res.json({
        success: true,
        data: testResult,
        metadata: {
          timestamp: new Date().toISOString()
        }
      });

    } catch (error) {
      logger.error('CalDAV test failed', { error });
      next(new AppError('CalDAV test failed', 500));
    }
  }

  /**
   * Получение инструкций по настройке CalDAV
   */
  async getCalDAVInstructions(req: AuthenticatedRequest, res: Response, next: NextFunction): Promise<void> {
    try {
      const instructions = caldavCalendarService.getSetupInstructions();
      
      res.json({
        success: true,
        data: {
          instructions,
          setupUrl: '/api/calendar/caldav/setup'
        },
        metadata: {
          timestamp: new Date().toISOString()
        }
      });

    } catch (error) {
      logger.error('Error getting CalDAV instructions', { error });
      next(new AppError('Failed to get CalDAV instructions', 500));
    }
  }

  /**
   * Создание встречи через CalDAV
   */
  async createCalDAVMeeting(req: AuthenticatedRequest, res: Response, next: NextFunction): Promise<void> {
    try {
      const { summary, start, end, attendees, description, location } = req.body;

      if (!summary || !start || !end) {
        res.status(400).json({
          success: false,
          error: 'Missing required fields: summary, start, end'
        });
        return;
      }

      const event = await caldavCalendarService.createEvent({
        summary,
        description,
        start: {
          dateTime: start,
          timeZone: 'Europe/Moscow'
        },
        end: {
          dateTime: end,
          timeZone: 'Europe/Moscow'
        },
        attendees: attendees || [],
        location
      });

      logger.info('CalDAV meeting created successfully', {
        eventId: event.id,
        summary: event.summary,
        userId: req.user.id
      });

      res.json({
        success: true,
        data: event,
        metadata: {
          timestamp: new Date().toISOString()
        }
      });

    } catch (error) {
      logger.error('Error creating CalDAV meeting', { error, userId: req.user.id });
      next(new AppError('Failed to create CalDAV meeting', 500));
    }
  }
}

export const calendarController = new CalendarController();
