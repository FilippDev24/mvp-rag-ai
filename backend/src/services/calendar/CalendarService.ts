import { EmployeeInfo, MeetingCreationResult, CALENDAR_CONSTANTS } from '../../types/calendar';
import { caldavCalendarService } from '../caldavCalendarService';
import { logger } from '../../utils/logger';

/**
 * Минимальный сервис для работы с календарем
 * Пока только создает встречи через CalDAV
 */
export class CalendarService {

  /**
   * Создание встречи с участниками
   */
  async createMeeting(
    title: string,
    startTime: Date,
    endTime: Date,
    participants: EmployeeInfo[],
    organizerEmail: string,
    description?: string,
    location?: string
  ): Promise<MeetingCreationResult> {
    try {
      logger.info('Creating meeting', {
        title,
        startTime: startTime.toISOString(),
        endTime: endTime.toISOString(),
        participants: participants.map(p => p.email),
        organizer: organizerEmail
      });

      // Создание события через CalDAV
      const aiDescription = description 
        ? `${description}\n\n🤖 Встреча создана ИИ-ассистентом`
        : '🤖 Встреча создана ИИ-ассистентом';

      const event = await caldavCalendarService.createEvent({
        summary: title,
        description: aiDescription,
        location: location,
        start: {
          dateTime: startTime.toISOString(),
          timeZone: CALENDAR_CONSTANTS.DEFAULT_TIMEZONE
        },
        end: {
          dateTime: endTime.toISOString(),
          timeZone: CALENDAR_CONSTANTS.DEFAULT_TIMEZONE
        },
        attendees: [
          { email: organizerEmail }, // Организатор
          ...participants.map(p => ({ 
            email: p.email, 
            displayName: p.name 
          }))
        ]
      });

      logger.info('CalDAV event created successfully', {
        eventId: event.id,
        title: event.summary
      });

      const participantNames = participants.map(p => p.name).join(', ');
      const timeStr = startTime.toLocaleString('ru-RU', {
        timeZone: 'Europe/Moscow',
        day: 'numeric',
        month: 'long',
        hour: '2-digit',
        minute: '2-digit'
      });

      // Формируем сообщение в зависимости от результата
      let successMessage = '';
      if (event.id?.startsWith('fallback-')) {
        successMessage = `⚠️ Встреча "${title}" запланирована на ${timeStr}. Календарное приглашение не отправлено (проблемы с календарем), но встреча зафиксирована в системе.`;
        if (participantNames) {
          successMessage += ` Участники: ${participantNames}`;
        }
      } else {
        successMessage = `✅ Встреча "${title}" создана на ${timeStr}.`;
        if (participantNames) {
          successMessage += ` Приглашения отправлены: ${participantNames}`;
        }
      }

      return {
        success: true,
        event,
        message: successMessage,
        participants: participants
      };

    } catch (error) {
      logger.error('Error creating meeting', { error, title });
      
      return {
        success: false,
        message: 'Ошибка при создании встречи. Попробуйте еще раз.',
        participants: [],
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }
}
