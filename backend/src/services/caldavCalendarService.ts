import axios from 'axios';
import { CalendarEvent, EmployeeInfo, MeetingCreationResult, CALENDAR_CONSTANTS } from '../types/calendar';
import { AppError } from '../types';
import { logger } from '../utils/logger';
import { randomUUID } from 'crypto';

interface CalDAVCredentials {
  email: string;
  password: string; // Пароль приложения
  caldavUrl: string;
}

class CalDAVCalendarService {
  private readonly yandexCalDAVUrl = 'https://caldav.yandex.ru';
  private systemCredentials: CalDAVCredentials | null = null;

  /**
   * Настройка системных учетных данных для CalDAV
   */
  async setupSystemCredentials(email: string, appPassword: string): Promise<void> {
    this.systemCredentials = {
      email,
      password: appPassword,
      caldavUrl: `${this.yandexCalDAVUrl}/calendars/${email}/`
    };

    // Тестируем подключение
    const testResult = await this.testConnection();
    if (!testResult.success) {
      throw new AppError('Failed to connect to CalDAV server', 500);
    }

    logger.info('CalDAV system credentials configured successfully', { email });
  }

  /**
   * Тестирование подключения к CalDAV серверу
   */
  async testConnection(): Promise<{ success: boolean; error?: string }> {
    if (!this.systemCredentials) {
      return { success: false, error: 'No credentials configured' };
    }

    try {
      const response = await axios({
        method: 'PROPFIND',
        url: this.systemCredentials.caldavUrl,
        headers: {
          'Content-Type': 'application/xml',
          'Depth': '1'
        },
        auth: {
          username: this.systemCredentials.email,
          password: this.systemCredentials.password
        },
        data: `<?xml version="1.0" encoding="utf-8" ?>
          <D:propfind xmlns:D="DAV:">
            <D:prop>
              <D:displayname />
              <D:resourcetype />
            </D:prop>
          </D:propfind>`,
        timeout: 10000
      });

      logger.info('CalDAV connection test successful', {
        status: response.status,
        email: this.systemCredentials.email
      });

      return { success: true };

    } catch (error: any) {
      logger.error('CalDAV connection test failed', {
        error: error.message,
        status: error.response?.status,
        email: this.systemCredentials?.email
      });

      return {
        success: false,
        error: error.response?.status === 401 ? 'Invalid credentials' : error.message
      };
    }
  }

  /**
   * Получение правильного пути календаря Яндекса
   */
  private async getCalendarPath(): Promise<string> {
    try {
      const response = await axios({
        method: 'PROPFIND',
        url: `${this.yandexCalDAVUrl}/calendars/${this.systemCredentials!.email}/`,
        headers: {
          'Content-Type': 'application/xml',
          'Depth': '1'
        },
        auth: {
          username: this.systemCredentials!.email,
          password: this.systemCredentials!.password
        },
        data: `<?xml version="1.0" encoding="utf-8" ?>
          <D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:prop>
              <D:resourcetype />
              <D:href />
            </D:prop>
          </D:propfind>`,
        timeout: 10000
      });

      // Парсим ответ и ищем календарь типа events-XXXXXX
      const responseText = response.data;
      logger.info('PROPFIND response for calendar discovery', { 
        responseText: responseText.substring(0, 1000) 
      });

      // Ищем путь календаря с числовым ID
      const match = responseText.match(/\/calendars\/[^\/]+\/(events-\d+)\//);
      
      if (match) {
        const calendarPath = match[1]; // Вернет 'events-XXXXXX'
        logger.info('Found Yandex calendar path', { calendarPath });
        return calendarPath;
      }
      
      throw new Error('Calendar collection not found in PROPFIND response');

    } catch (error: any) {
      logger.error('Failed to discover calendar path', { 
        error: error.message,
        status: error.response?.status 
      });
      throw new AppError('Failed to discover calendar path', 500);
    }
  }

  /**
   * Создание события в календаре через CalDAV
   */
  async createEvent(event: CalendarEvent): Promise<CalendarEvent> {
    if (!this.systemCredentials) {
      throw new AppError('CalDAV credentials not configured', 500);
    }

    try {
      // ИСПРАВЛЕНИЕ: Используем timestamp + UUID для гарантированной уникальности
      // Яндекс.Календарь хранит все UUID навсегда и не позволяет переиспользовать
      const eventId = `${Date.now()}-${randomUUID()}`;
      
      // ИСПРАВЛЕНИЕ: Получаем правильный путь календаря через PROPFIND
      const calendarPath = await this.getCalendarPath(); // получаем 'events-XXXXXX'
      
      // ИСПРАВЛЕНИЕ: Используем правильный путь с числовым ID календаря
      const eventUrl = `${this.yandexCalDAVUrl}/calendars/${this.systemCredentials.email}/${calendarPath}/${eventId}.ics`;

      // Создаем iCalendar данные
      const icalData = this.createICalendarData(event, eventId);

      logger.info('Attempting to create CalDAV event', {
        eventId,
        eventUrl,
        calendarPath,
        summary: event.summary,
        email: this.systemCredentials.email
      });

      // ИСПРАВЛЕНИЕ: Retry логика для надёжности
      let lastError: any;
      const maxRetries = 3;
      
      for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
          logger.info('CalDAV event creation attempt', {
            attempt,
            maxRetries,
            eventId,
            eventUrl
          });

          const response = await axios({
            method: 'PUT',
            url: eventUrl,
            headers: {
              'Content-Type': 'text/calendar; charset=utf-8',
              'If-None-Match': '*' // Важно для создания нового события
            },
            auth: {
              username: this.systemCredentials.email,
              password: this.systemCredentials.password
            },
            data: icalData,
            timeout: 60000, // ИСПРАВЛЕНИЕ: Увеличиваем таймаут до 60 секунд для Yandex CalDAV
            validateStatus: (status) => {
              // Принимаем 200, 201, 204 как успешные
              return status >= 200 && status < 300;
            }
          });

          logger.info('CalDAV event created successfully', {
            eventId,
            summary: event.summary,
            status: response.status,
            eventUrl,
            calendarPath,
            attempt
          });

          return {
            ...event,
            id: eventId
          };

        } catch (attemptError: any) {
          lastError = attemptError;
          
          logger.warn('CalDAV event creation attempt failed', {
            attempt,
            maxRetries,
            error: attemptError.message,
            status: attemptError.response?.status,
            statusText: attemptError.response?.statusText
          });

          // Если это последняя попытка или критическая ошибка - не ретраим
          if (attempt === maxRetries || 
              attemptError.response?.status === 401 || 
              attemptError.response?.status === 404) {
            break;
          }

          // Ждем перед следующей попыткой (экспоненциальная задержка)
          const delay = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
          logger.info('Waiting before retry', { delay, attempt });
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }

      // Если все попытки неудачны - выбрасываем последнюю ошибку
      throw lastError;

    } catch (error: any) {
      logger.error('Failed to create CalDAV event', {
        error: error.message,
        status: error.response?.status,
        statusText: error.response?.statusText,
        responseData: error.response?.data,
        event: { summary: event.summary },
        url: error.config?.url,
        service: 'knowledge-base-backend',
        timestamp: new Date().toISOString()
      });

      // ИСПРАВЛЕНИЕ: Правильная обработка ошибок без fallback на mock
      if (error.response?.status === 409) {
        throw new AppError('Calendar collection not found or event conflict', 409);
      }
      
      if (error.response?.status === 401) {
        throw new AppError('CalDAV authentication failed', 401);
      }
      
      if (error.response?.status === 404) {
        throw new AppError('Calendar not found', 404);
      }
      
      if (error.response?.status === 405) {
        throw new AppError('Method not allowed - check CalDAV configuration', 405);
      }
      
      if (error.response?.status === 504) {
        throw new AppError('Yandex CalDAV server timeout - try again later', 504);
      }

      throw new AppError('Failed to create calendar event via CalDAV', 500);
    }
  }


  /**
   * УПРОЩЕННОЕ создание iCalendar данных для Yandex CalDAV с участниками
   */
  private createICalendarData(event: CalendarEvent, eventId: string): string {
    const now = new Date();
    const startDate = new Date(event.start.dateTime);
    const endDate = new Date(event.end.dateTime);

    // УПРОЩЕННОЕ форматирование дат для Yandex
    const formatDate = (date: Date): string => {
      return date.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
    };

    // КРИТИЧНО: Добавляем участников в упрощенном формате
    const attendeesLines: string[] = [];
    if (event.attendees && event.attendees.length > 0) {
      event.attendees.forEach(attendee => {
        attendeesLines.push(`ATTENDEE:mailto:${attendee.email}`);
      });
    }

    // МИНИМАЛЬНЫЙ набор полей для Яндекса + участники
    const icalLines = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//Knowledge Base//EN',
      'BEGIN:VEVENT',
      `UID:${eventId}`,
      `DTSTAMP:${formatDate(now)}`,
      `DTSTART:${formatDate(startDate)}`,
      `DTEND:${formatDate(endDate)}`,
      `SUMMARY:${event.summary || 'Встреча'}`,
      `ORGANIZER:mailto:${this.systemCredentials?.email}`,
      ...attendeesLines, // Добавляем участников
      'STATUS:CONFIRMED',
      'END:VEVENT',
      'END:VCALENDAR'
    ];

    const icalData = icalLines.join('\r\n');

    logger.info('Created simplified iCalendar data with attendees', {
      eventId,
      summary: event.summary,
      startDate: formatDate(startDate),
      endDate: formatDate(endDate),
      attendeesCount: event.attendees?.length || 0,
      attendeesEmails: event.attendees?.map(a => a.email) || [],
      dataLength: icalData.length
    });

    return icalData;
  }

  /**
   * Экранирование текста для iCalendar формата
   */
  private escapeICalText(text: string): string {
    return text
      .replace(/\\/g, '\\\\')
      .replace(/;/g, '\\;')
      .replace(/,/g, '\\,')
      .replace(/\n/g, '\\n')
      .replace(/\r/g, '');
  }

  /**
   * Получение событий календаря
   */
  async getEvents(startDate?: Date, endDate?: Date): Promise<CalendarEvent[]> {
    if (!this.systemCredentials) {
      throw new AppError('CalDAV credentials not configured', 500);
    }

    try {
      const start = startDate || new Date();
      const end = endDate || new Date(Date.now() + 30 * 24 * 60 * 60 * 1000); // 30 дней

      const reportData = `<?xml version="1.0" encoding="utf-8" ?>
        <C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
          <D:prop>
            <D:getetag />
            <C:calendar-data />
          </D:prop>
          <C:filter>
            <C:comp-filter name="VCALENDAR">
              <C:comp-filter name="VEVENT">
                <C:time-range start="${start.toISOString().replace(/[-:]/g, '').split('.')[0]}Z"
                              end="${end.toISOString().replace(/[-:]/g, '').split('.')[0]}Z"/>
              </C:comp-filter>
            </C:comp-filter>
          </C:filter>
        </C:calendar-query>`;

      const response = await axios({
        method: 'REPORT',
        url: this.systemCredentials.caldavUrl,
        headers: {
          'Content-Type': 'application/xml',
          'Depth': '1'
        },
        auth: {
          username: this.systemCredentials.email,
          password: this.systemCredentials.password
        },
        data: reportData,
        timeout: 10000
      });

      // Парсим ответ и извлекаем события
      // Это упрощенная версия - в реальности нужен полноценный парсер iCalendar
      const events: CalendarEvent[] = [];
      
      logger.info('CalDAV events retrieved', {
        status: response.status,
        eventsCount: events.length
      });

      return events;

    } catch (error: any) {
      logger.error('Failed to get CalDAV events', {
        error: error.message,
        status: error.response?.status
      });

      throw new AppError('Failed to get calendar events via CalDAV', 500);
    }
  }

  /**
   * Проверка доступности времени (упрощенная версия)
   */
  async checkAvailability(emails: string[], timeMin: string, timeMax: string): Promise<any> {
    // Для CalDAV это более сложная операция, требующая доступа к календарям каждого участника
    // Пока возвращаем заглушку
    logger.info('CalDAV availability check requested', { emails, timeMin, timeMax });
    
    return {
      calendars: emails.reduce((acc, email) => {
        acc[email] = {
          busy: [],
          errors: []
        };
        return acc;
      }, {} as any),
      timeMin,
      timeMax,
      note: 'CalDAV availability check - simplified implementation'
    };
  }

  /**
   * Получение инструкций для настройки CalDAV
   */
  getSetupInstructions(): string {
    return `
Для настройки CalDAV доступа к Яндекс.Календарю:

1. Войдите в Яндекс.Паспорт: https://passport.yandex.ru/
2. Перейдите в раздел "Безопасность"
3. Найдите "Пароли приложений"
4. Создайте новый пароль приложения для "Календарь"
5. Используйте этот пароль для настройки CalDAV

CalDAV URL для Яндекса: https://caldav.yandex.ru/calendars/[email]/
Имя пользователя: ваш email
Пароль: пароль приложения (НЕ основной пароль)
    `;
  }
}

export const caldavCalendarService = new CalDAVCalendarService();
