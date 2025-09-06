import { CalendarAgent } from './calendar/CalendarAgent';
import { MeetingCreationResult } from '../types/calendar';
import { logger } from '../utils/logger';

/**
 * Обертка для обратной совместимости со старым API календарного агента
 * Использует новый декомпозированный CalendarAgent
 */
class CalendarAgentService {
  private calendarAgent: CalendarAgent;

  constructor() {
    this.calendarAgent = new CalendarAgent();
  }

  /**
   * Основной метод обработки календарной команды
   * Обертка для нового CalendarAgent
   */
  async processCalendarCommand(
    message: string, 
    organizerEmail: string, 
    accessLevel: number,
    chatHistory: any[] = []
  ): Promise<MeetingCreationResult> {
    logger.info('CalendarAgentService: delegating to new CalendarAgent', {
      message: message.substring(0, 100),
      organizerEmail,
      accessLevel
    });

    return await this.calendarAgent.processCalendarCommand(
      message,
      organizerEmail,
      accessLevel,
      chatHistory
    );
  }

  /**
   * Обработка календарной команды с детальной отладочной информацией
   * Обертка для нового CalendarAgent
   */
  async processCalendarCommandWithDebug(
    message: string, 
    organizerEmail: string, 
    accessLevel: number,
    chatHistory: any[] = []
  ): Promise<MeetingCreationResult> {
    logger.info('CalendarAgentService: delegating to new CalendarAgent with debug', {
      message: message.substring(0, 100),
      organizerEmail,
      accessLevel
    });

    return await this.calendarAgent.processCalendarCommandWithDebug(
      message,
      organizerEmail,
      accessLevel,
      chatHistory
    );
  }
}

export const calendarAgentService = new CalendarAgentService();
