import { 
  ParsedCalendarCommand, 
  EmployeeInfo, 
  MeetingCreationResult, 
  CALENDAR_CONSTANTS,
  CalendarDebugInfo,
  ParticipantSearchDebug,
  ProcessingStep
} from '../../types/calendar';
import { CalendarCommandParser } from './CalendarCommandParser';
import { EmployeeSearchService } from './EmployeeSearchService';
import { CalendarService } from './CalendarService';
import { logger } from '../../utils/logger';

/**
 * Главный календарный агент - оркестратор всех календарных операций
 * Координирует работу парсера команд, поиска сотрудников и создания встреч
 */
export class CalendarAgent {
  private commandParser: CalendarCommandParser;
  private employeeSearchService: EmployeeSearchService;
  private calendarService: CalendarService;

  constructor() {
    this.commandParser = new CalendarCommandParser();
    this.employeeSearchService = new EmployeeSearchService();
    this.calendarService = new CalendarService();
  }

  /**
   * Основной метод обработки календарной команды
   * Предполагается, что команда УЖЕ классифицирована как календарная в chatService
   */
  async processCalendarCommand(
    message: string, 
    organizerEmail: string, 
    accessLevel: number,
    chatHistory: any[] = []
  ): Promise<MeetingCreationResult> {
    try {
      logger.info('Processing calendar command', {
        message: message.substring(0, 100),
        organizerEmail,
        accessLevel,
        historyLength: chatHistory.length
      });

      // 1. Парсим календарную команду
      const parsedCommand = await this.commandParser.parseCalendarCommand(message, chatHistory);
      
      logger.info('Calendar command parsed', {
        title: parsedCommand.title,
        datetime: parsedCommand.datetime.toISOString(),
        participants: parsedCommand.participants,
        duration: parsedCommand.duration
      });

      // 2. Ищем участников в базе знаний
      const allParticipants: EmployeeInfo[] = [];
      for (const participantName of parsedCommand.participants) {
        const searchResult = await this.employeeSearchService.searchEmployees(participantName, accessLevel);
        allParticipants.push(...searchResult.employees);
      }

      logger.info('Participants search completed', {
        searchedParticipants: parsedCommand.participants,
        foundParticipants: allParticipants.length,
        participants: allParticipants.map(p => ({ name: p.name, email: p.email }))
      });

      // 3. Проверяем, найдены ли участники
      if (allParticipants.length === 0 && parsedCommand.participants.length > 0) {
        return {
          success: false,
          message: `Не найдены участники: ${parsedCommand.participants.join(', ')}`,
          participants: [],
          error: 'Participants not found'
        };
      }

      // 4. Создаем встречу
      const startTime = new Date(parsedCommand.datetime);
      const duration = parsedCommand.duration || CALENDAR_CONSTANTS.DEFAULT_MEETING_DURATION;
      const endTime = new Date(startTime.getTime() + (duration as number) * 60 * 1000);

      const result = await this.calendarService.createMeeting(
        parsedCommand.title || 'Встреча',
        startTime,
        endTime,
        allParticipants,
        organizerEmail,
        parsedCommand.description,
        parsedCommand.location
      );

      logger.info('Calendar command processing completed', {
        success: result.success,
        participantsCount: allParticipants.length,
        message: result.message
      });

      return result;

    } catch (error) {
      logger.error('Error processing calendar command', { error, message });
      
      return {
        success: false,
        message: 'Ошибка при обработке календарной команды. Попробуйте еще раз.',
        participants: [],
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  /**
   * Обработка календарной команды с детальной отладочной информацией
   */
  async processCalendarCommandWithDebug(
    message: string, 
    organizerEmail: string, 
    accessLevel: number,
    chatHistory: any[] = []
  ): Promise<MeetingCreationResult> {
    const processingStartTime = Date.now();
    const processingSteps: ProcessingStep[] = [];
    
    try {
      logger.info('Processing calendar command with debug', {
        message: message.substring(0, 100),
        organizerEmail,
        accessLevel,
        historyLength: chatHistory.length
      });

      // Шаг 1: Парсинг календарной команды
      const parsingStart = Date.now();
      const parsedCommand = await this.commandParser.parseCalendarCommand(message, chatHistory);
      processingSteps.push({
        step: 'Calendar Command Parsing',
        timestamp: new Date().toISOString(),
        duration: Date.now() - parsingStart,
        success: true,
        details: {
          parsedCommand: {
            title: parsedCommand.title,
            datetime: parsedCommand.datetime.toISOString(),
            participants: parsedCommand.participants,
            duration: parsedCommand.duration
          }
        }
      });

      // Шаг 2: Поиск участников с детальной отладкой
      const participantSearchResults: ParticipantSearchDebug[] = [];
      const allParticipants: EmployeeInfo[] = [];
      
      for (const participantName of parsedCommand.participants) {
        const searchStart = Date.now();
        const searchResult = await this.employeeSearchService.searchEmployees(participantName, accessLevel, true);
        
        const debugResult: ParticipantSearchDebug = {
          searchedFor: participantName,
          ragResults: {
            resultsCount: searchResult.debug?.ragResultsCount || 0,
            contentPreview: searchResult.debug?.llmResponse?.substring(0, 500) || '',
            searchQuery: searchResult.debug?.searchQuery || participantName,
            taskId: `search_${Date.now()}`
          },
          llmExtraction: {
            prompt: searchResult.debug?.llmPrompt || '',
            rawResponse: searchResult.debug?.llmResponse || '',
            parsedResult: searchResult.employees,
            success: searchResult.employees.length > 0
          },
          finalResult: searchResult.employees[0] || null,
          processingTime: Date.now() - searchStart
        };
        
        participantSearchResults.push(debugResult);
        allParticipants.push(...searchResult.employees);
        
        processingSteps.push({
          step: `Participant Search: ${participantName}`,
          timestamp: new Date().toISOString(),
          duration: debugResult.processingTime,
          success: searchResult.employees.length > 0,
          details: {
            searchedFor: participantName,
            found: searchResult.employees.length > 0,
            result: searchResult.employees[0] || null
          }
        });
      }

      // Шаг 3: Создание встречи
      const meetingStart = Date.now();
      const startTime = new Date(parsedCommand.datetime);
      const duration = parsedCommand.duration || CALENDAR_CONSTANTS.DEFAULT_MEETING_DURATION;
      const endTime = new Date(startTime.getTime() + (duration as number) * 60 * 1000);

      const result = await this.calendarService.createMeeting(
        parsedCommand.title || 'Встреча',
        startTime,
        endTime,
        allParticipants,
        organizerEmail,
        parsedCommand.description,
        parsedCommand.location
      );
      
      processingSteps.push({
        step: 'Meeting Creation',
        timestamp: new Date().toISOString(),
        duration: Date.now() - meetingStart,
        success: result.success,
        details: {
          participantsCount: allParticipants.length,
          meetingTitle: parsedCommand.title,
          meetingTime: parsedCommand.datetime.toISOString()
        },
        error: result.error
      });

      // Добавляем debug информацию к результату
      result.debug = {
        originalMessage: message,
        parsedCommand: {
          participants: parsedCommand.participants,
          datetime: parsedCommand.datetime.toISOString(),
          title: parsedCommand.title || 'Встреча',
          duration: parsedCommand.duration || CALENDAR_CONSTANTS.DEFAULT_MEETING_DURATION
        },
        participantSearchResults,
        calendarCreation: result.success ? {
          startTime: parsedCommand.datetime.toISOString(),
          endTime: endTime.toISOString(),
          attendees: allParticipants.map(p => p.email),
          organizerEmail
        } : undefined,
        processingSteps
      };

      logger.info('Calendar command processed with debug info', {
        message: message.substring(0, 100),
        totalProcessingTime: Date.now() - processingStartTime,
        participantsFound: allParticipants.length,
        success: result.success
      });

      return result;

    } catch (error) {
      processingSteps.push({
        step: 'Error Handling',
        timestamp: new Date().toISOString(),
        duration: Date.now() - processingStartTime,
        success: false,
        details: {},
        error: error instanceof Error ? error.message : 'Unknown error'
      });

      logger.error('Error processing calendar command with debug', { error, message });
      
      return {
        success: false,
        message: 'Ошибка при обработке календарной команды',
        participants: [],
        error: error instanceof Error ? error.message : 'Unknown error',
        debug: {
          originalMessage: message,
          parsedCommand: {
            participants: [],
            datetime: '',
            title: '',
            duration: 0
          },
          participantSearchResults: [],
          processingSteps
        }
      };
    }
  }
}
