import axios, { AxiosResponse } from 'axios';
import { 
  YandexTokens, 
  CalendarEvent, 
  YandexCalendarListResponse, 
  YandexEventListResponse,
  YandexEvent,
  CALENDAR_CONSTANTS 
} from '../types/calendar';
import { AppError } from '../types';
import { logger } from '../utils/logger';
import fs from 'fs/promises';
import path from 'path';

class YandexCalendarService {
  private readonly baseUrl = 'https://api.calendar.yandex.net/api/v3';
  private readonly oauthUrl = 'https://oauth.yandex.ru';
  private readonly clientId = process.env.YANDEX_CLIENT_ID!;
  private readonly clientSecret = process.env.YANDEX_CLIENT_SECRET!;
  private readonly redirectUri = process.env.YANDEX_REDIRECT_URI!;

  private systemAccessToken: string | null = null;
  private systemRefreshToken: string | null = null;
  private systemEmail: string | null = null;
  private tokenExpiresAt: Date | null = null;

  constructor() {
    // Загружаем системные токены при инициализации
    this.loadSystemTokens();
  }

  /**
   * Получение URL для авторизации
   */
  getAuthorizationUrl(): string {
    const params = new URLSearchParams({
      response_type: 'code',
      client_id: this.clientId,
      redirect_uri: this.redirectUri,
      scope: 'calendar:read calendar:write login:email'
    });

    return `${this.oauthUrl}/authorize?${params.toString()}`;
  }

  /**
   * Обмен кода авторизации на токены
   */
  async exchangeCodeForTokens(code: string): Promise<YandexTokens> {
    try {
      const response: AxiosResponse<YandexTokens> = await axios.post(
        `${this.oauthUrl}/token`,
        {
          grant_type: 'authorization_code',
          code,
          client_id: this.clientId,
          client_secret: this.clientSecret,
          redirect_uri: this.redirectUri
        },
        {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          }
        }
      );

      logger.info('Successfully exchanged code for tokens');
      return response.data;

    } catch (error: any) {
      logger.error('Failed to exchange code for tokens', { 
        error: error.response?.data || error.message 
      });
      throw new AppError('Failed to exchange authorization code for tokens', 500);
    }
  }

  /**
   * Получение информации о пользователе
   */
  async getUserInfo(accessToken: string): Promise<{ default_email: string; real_name?: string }> {
    try {
      const response = await axios.get('https://login.yandex.ru/info', {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      });

      return response.data;

    } catch (error: any) {
      logger.error('Failed to get user info', { error: error.response?.data || error.message });
      throw new AppError('Failed to get user information', 500);
    }
  }

  /**
   * Сохранение системных токенов
   */
  async saveSystemTokens(tokens: YandexTokens, email: string): Promise<void> {
    try {
      this.systemAccessToken = tokens.access_token;
      this.systemRefreshToken = tokens.refresh_token;
      this.systemEmail = email;
      this.tokenExpiresAt = new Date(Date.now() + tokens.expires_in * 1000);

      // Сохраняем в .env файл
      const envPath = path.join(process.cwd(), '.env');
      let envContent = await fs.readFile(envPath, 'utf-8');

      // Обновляем переменные окружения
      envContent = this.updateEnvVariable(envContent, 'SYSTEM_CALENDAR_EMAIL', email);
      envContent = this.updateEnvVariable(envContent, 'SYSTEM_CALENDAR_ACCESS_TOKEN', tokens.access_token);
      envContent = this.updateEnvVariable(envContent, 'SYSTEM_CALENDAR_REFRESH_TOKEN', tokens.refresh_token);

      await fs.writeFile(envPath, envContent);

      // Обновляем process.env
      process.env.SYSTEM_CALENDAR_EMAIL = email;
      process.env.SYSTEM_CALENDAR_ACCESS_TOKEN = tokens.access_token;
      process.env.SYSTEM_CALENDAR_REFRESH_TOKEN = tokens.refresh_token;

      logger.info('System tokens saved successfully', { email });

    } catch (error) {
      logger.error('Failed to save system tokens', { error });
      throw new AppError('Failed to save system tokens', 500);
    }
  }

  /**
   * Загрузка системных токенов из переменных окружения
   */
  private loadSystemTokens(): void {
    this.systemAccessToken = process.env.SYSTEM_CALENDAR_ACCESS_TOKEN || null;
    this.systemRefreshToken = process.env.SYSTEM_CALENDAR_REFRESH_TOKEN || null;
    this.systemEmail = process.env.SYSTEM_CALENDAR_EMAIL || null;

    if (this.systemAccessToken) {
      logger.info('System calendar tokens loaded', { email: this.systemEmail });
    } else {
      logger.warn('No system calendar tokens found in environment variables');
    }
  }

  /**
   * Обновление переменной в .env файле
   */
  private updateEnvVariable(envContent: string, key: string, value: string): string {
    const regex = new RegExp(`^${key}=.*$`, 'm');
    const newLine = `${key}=${value}`;
    
    if (regex.test(envContent)) {
      return envContent.replace(regex, newLine);
    } else {
      return envContent + `\n${newLine}`;
    }
  }

  /**
   * Обновление токенов через refresh_token
   */
  async refreshTokens(): Promise<void> {
    if (!this.systemRefreshToken) {
      throw new AppError('No refresh token available', 401);
    }

    try {
      const response: AxiosResponse<YandexTokens> = await axios.post(
        `${this.oauthUrl}/token`,
        {
          grant_type: 'refresh_token',
          refresh_token: this.systemRefreshToken,
          client_id: this.clientId,
          client_secret: this.clientSecret
        }
      );

      await this.saveSystemTokens(response.data, this.systemEmail!);
      logger.info('Tokens refreshed successfully');

    } catch (error: any) {
      logger.error('Failed to refresh tokens', { error: error.response?.data || error.message });
      throw new AppError('Failed to refresh access token', 401);
    }
  }

  /**
   * Получение валидного access token (с автообновлением)
   */
  private async getValidAccessToken(): Promise<string> {
    if (!this.systemAccessToken) {
      throw new AppError('No system access token available. Please authorize first.', 401);
    }

    // Проверяем, не истек ли токен (с запасом в 5 минут)
    if (this.tokenExpiresAt && this.tokenExpiresAt.getTime() - Date.now() < 5 * 60 * 1000) {
      await this.refreshTokens();
    }

    return this.systemAccessToken;
  }

  /**
   * Тестирование доступа к календарю
   */
  async testCalendarAccess(): Promise<{ success: boolean; email?: string; calendarsCount?: number }> {
    try {
      const accessToken = await this.getValidAccessToken();
      
      const response = await axios.get(`${this.baseUrl}/calendars`, {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        }
      });

      const calendars = response.data.items || [];
      
      return {
        success: true,
        email: this.systemEmail || undefined,
        calendarsCount: calendars.length
      };

    } catch (error: any) {
      logger.error('Calendar access test failed', { error: error.response?.data || error.message });
      return {
        success: false
      };
    }
  }

  /**
   * Получение списка календарей
   */
  async getCalendars(): Promise<any[]> {
    try {
      const accessToken = await this.getValidAccessToken();
      
      const response: AxiosResponse<YandexCalendarListResponse> = await axios.get(
        `${this.baseUrl}/calendars`,
        {
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
          }
        }
      );

      return response.data.items || [];

    } catch (error: any) {
      logger.error('Failed to get calendars', { error: error.response?.data || error.message });
      throw new AppError('Failed to get calendars', 500);
    }
  }

  /**
   * Создание события в календаре
   */
  async createEvent(event: CalendarEvent): Promise<CalendarEvent> {
    try {
      const accessToken = await this.getValidAccessToken();
      
      // Преобразуем в формат Яндекс.Календаря
      const yandexEvent = {
        summary: event.summary,
        description: event.description,
        location: event.location,
        start: {
          dateTime: event.start.dateTime,
          timeZone: event.start.timeZone
        },
        end: {
          dateTime: event.end.dateTime,
          timeZone: event.end.timeZone
        },
        attendees: event.attendees?.map(attendee => ({
          email: attendee.email,
          displayName: attendee.displayName
        })) || []
      };

      const response = await axios.post(
        `${this.baseUrl}/calendars/primary/events`,
        yandexEvent,
        {
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
          }
        }
      );

      const createdEvent = response.data;
      
      logger.info('Event created successfully', {
        eventId: createdEvent.id,
        summary: createdEvent.summary,
        attendeesCount: event.attendees?.length || 0
      });

      return this.convertYandexEventToCalendarEvent(createdEvent);

    } catch (error: any) {
      logger.error('Failed to create event', { 
        error: error.response?.data || error.message,
        event: { summary: event.summary, attendees: event.attendees?.length }
      });
      throw new AppError('Failed to create calendar event', 500);
    }
  }

  /**
   * Проверка доступности времени (заглушка - Яндекс.Календарь не поддерживает FreeBusy API)
   */
  async checkAvailability(emails: string[], timeMin: string, timeMax: string): Promise<any> {
    logger.warn('Availability check not supported by Yandex Calendar API', { emails, timeMin, timeMax });
    
    // Возвращаем заглушку - все свободны
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
      note: 'Yandex Calendar does not support FreeBusy API. All participants assumed available.'
    };
  }

  /**
   * Получение событий календаря
   */
  async getEvents(timeMin?: string, timeMax?: string): Promise<CalendarEvent[]> {
    try {
      const accessToken = await this.getValidAccessToken();
      
      const params = new URLSearchParams();
      if (timeMin) params.append('timeMin', timeMin);
      if (timeMax) params.append('timeMax', timeMax);
      params.append('maxResults', '250');
      params.append('singleEvents', 'true');
      params.append('orderBy', 'startTime');

      const response: AxiosResponse<YandexEventListResponse> = await axios.get(
        `${this.baseUrl}/calendars/primary/events?${params.toString()}`,
        {
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
          }
        }
      );

      const events = response.data.items || [];
      return events.map(event => this.convertYandexEventToCalendarEvent(event));

    } catch (error: any) {
      logger.error('Failed to get events', { error: error.response?.data || error.message });
      throw new AppError('Failed to get calendar events', 500);
    }
  }

  /**
   * Конвертация события Яндекс.Календаря в наш формат
   */
  private convertYandexEventToCalendarEvent(yandexEvent: YandexEvent): CalendarEvent {
    return {
      id: yandexEvent.id,
      summary: yandexEvent.summary,
      description: yandexEvent.description,
      location: yandexEvent.location,
      start: {
        dateTime: yandexEvent.start.dateTime || yandexEvent.start.date || '',
        timeZone: yandexEvent.start.timeZone || CALENDAR_CONSTANTS.DEFAULT_TIMEZONE
      },
      end: {
        dateTime: yandexEvent.end.dateTime || yandexEvent.end.date || '',
        timeZone: yandexEvent.end.timeZone || CALENDAR_CONSTANTS.DEFAULT_TIMEZONE
      },
      attendees: yandexEvent.attendees?.map(attendee => ({
        email: attendee.email,
        displayName: attendee.displayName,
        responseStatus: attendee.responseStatus,
        optional: attendee.optional
      })),
      organizer: {
        email: yandexEvent.organizer.email,
        displayName: yandexEvent.organizer.displayName
      },
      status: yandexEvent.status === 'confirmed' ? 'confirmed' : 
              yandexEvent.status === 'tentative' ? 'tentative' : 'cancelled'
    };
  }
}

export const yandexCalendarService = new YandexCalendarService();
