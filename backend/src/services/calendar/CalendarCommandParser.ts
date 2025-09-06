import { ParsedCalendarCommand, CALENDAR_CONSTANTS } from '../../types/calendar';
import { logger } from '../../utils/logger';
import axios from 'axios';

// Типы для Ollama API ответов
interface OllamaResponse {
  response?: string;
  model?: string;
  created_at?: string;
  done?: boolean;
}

/**
 * Сервис для парсинга календарных команд через LLM
 * НЕ определяет тип команды - только парсит уже классифицированные календарные команды
 */
export class CalendarCommandParser {
  
  /**
   * Парсинг календарной команды с извлечением участников из истории чата
   * Предполагается, что команда УЖЕ классифицирована как календарная в chatService
   */
  async parseCalendarCommand(message: string, chatHistory: any[] = []): Promise<ParsedCalendarCommand> {
    try {
      // Используем московское время для корректного парсинга
      const now = new Date();
      const moscowTime = new Date(now.toLocaleString('en-US', { timeZone: 'Europe/Moscow' }));
      
      const currentDateStr = moscowTime.toISOString().split('T')[0]; // YYYY-MM-DD
      const currentTimeStr = moscowTime.toTimeString().split(' ')[0].substring(0, 5); // HH:MM
      const currentDayName = moscowTime.toLocaleDateString('ru-RU', { weekday: 'long' });
      
      const tomorrow = new Date(moscowTime.getTime() + 24*60*60*1000);
      const tomorrowDate = tomorrow.toISOString().split('T')[0];
      
      // Извлекаем участников из истории чата
      const mentionedPeople = this.extractPeopleFromChatHistory(chatHistory);
      const historyText = this.buildHistoryText(chatHistory, mentionedPeople);
      
      const prompt = `Ты календарный ассистент. Извлеки параметры встречи из сообщения пользователя.

КОНТЕКСТ:
- Сегодня: ${currentDateStr} (${currentDayName})
- Завтра: ${tomorrowDate}
- Текущее время: ${currentTimeStr}
- Часовой пояс: Europe/Moscow (UTC+3)${historyText}

Сообщение: "${message}"

ПРАВИЛА ПАРСИНГА:
1. ВРЕМЯ: Если указано конкретное время (например "16:00", "на 16:00"), используй ЕГО, а не текущее время
2. ДАТА: "завтра" = ${tomorrowDate}, "сегодня" = ${currentDateStr}, правильно считай даты относительно текущей
3. УЧАСТНИКИ: 
   - Извлекай имена людей из текста (например: "с Антоном", "Антон и Руслан" → ["Антон", "Руслан"])
   - "с ними" означает людей из истории чата
   - Если в сообщении "с ними", используй ВСЕХ упомянутых в чате людей
4. ТЕМА: Создай краткое название на основе контекста встречи

КРИТИЧЕСКИ ВАЖНО: 
- Ответь ТОЛЬКО валидным JSON без дополнительного текста
- Используй ТОЛЬКО двойные кавычки для строк
- Массив participants должен содержать только строки с именами

ФОРМАТ ОТВЕТА (СТРОГО):
{
  "title": "название встречи",
  "datetime": "YYYY-MM-DDTHH:MM:00+03:00",
  "participants": ["имя1", "имя2"],
  "duration": 60
}`;

      const response = await axios.post(
        `${process.env.OLLAMA_HOST || 'http://localhost:11434'}/api/generate`,
        {
          model: 'qwen-rag-optimized',
          prompt: prompt,
          stream: false,
          options: {
            temperature: 0.1,
            top_p: 0.9,
            num_predict: 300
          }
        },
        { timeout: 30000 }
      );

      let llmResponse = (response.data as OllamaResponse).response?.trim() || '';
      
      // Очищаем ответ от возможного мусора
      const jsonMatch = llmResponse.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        llmResponse = jsonMatch[0];
      }
      
      try {
        const parsed = JSON.parse(llmResponse);
        
        // Валидация обязательных полей
        if (!parsed.title || !parsed.datetime || !Array.isArray(parsed.participants)) {
          throw new Error('Invalid JSON structure: missing required fields');
        }
        
        // Если участники не найдены, но есть "с ними" - добавляем из истории
        if (parsed.participants.length === 0 && 
            (message.toLowerCase().includes('с ними') || message.toLowerCase().includes('с ним'))) {
          parsed.participants = mentionedPeople;
          logger.info('Added participants from chat history', { participants: mentionedPeople });
        }
        
        // Валидация формата даты
        const parsedDate = new Date(parsed.datetime);
        if (isNaN(parsedDate.getTime())) {
          throw new Error('Invalid datetime format');
        }
        
        const result: ParsedCalendarCommand = {
          action: 'create_meeting',
          datetime: parsedDate,
          participants: parsed.participants.filter((p: any) => typeof p === 'string' && p.trim() !== ''),
          title: parsed.title.trim() || 'Встреча',
          description: parsed.description?.trim(),
          location: parsed.location?.trim(),
          duration: typeof parsed.duration === 'number' && parsed.duration > 0 
            ? parsed.duration 
            : CALENDAR_CONSTANTS.DEFAULT_MEETING_DURATION
        };

        logger.info('LLM parsed calendar command successfully', {
          originalMessage: message.substring(0, 100),
          parsedCommand: {
            title: result.title,
            datetime: result.datetime.toISOString(),
            participants: result.participants,
            duration: result.duration
          }
        });

        return result;

      } catch (parseError) {
        logger.error('Failed to parse LLM response for calendar parsing', { 
          llmResponse: llmResponse.substring(0, 500), 
          parseError: parseError instanceof Error ? parseError.message : parseError,
          message: message.substring(0, 100)
        });
        
        // Fallback к базовому парсингу с участниками из истории
        return this.createFallbackCommand(mentionedPeople);
      }

    } catch (error) {
      logger.error('Error in LLM calendar command parsing', { 
        error: error instanceof Error ? error.message : error,
        message: message.substring(0, 100)
      });
      
      // Fallback к базовому парсингу
      return this.createFallbackCommand([]);
    }
  }

  /**
   * Извлечение упомянутых людей из истории чата
   */
  private extractPeopleFromChatHistory(chatHistory: any[]): string[] {
    const mentionedPeople: string[] = [];
    
    if (chatHistory.length > 0) {
      const recentHistory = chatHistory.slice(-5); // Берем последние 5 сообщений
      
      recentHistory.forEach((msg) => {
        if (msg.role === 'USER') {
          // Ищем имена (слова с заглавной буквы)
          const peopleMatches = msg.content.match(/\b[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)*\b/g);
          if (peopleMatches) {
            mentionedPeople.push(...peopleMatches.filter((name: string) => 
              name.length > 2 && 
              !['Дай', 'Можешь', 'Поставь', 'Встреча', 'Система', 'Почту'].includes(name)
            ));
          }
        }
      });
    }
    
    // Убираем дубликаты
    return [...new Set(mentionedPeople)];
  }

  /**
   * Построение текста истории для промпта
   */
  private buildHistoryText(chatHistory: any[], mentionedPeople: string[]): string {
    let historyText = '';
    
    if (chatHistory.length > 0) {
      const recentHistory = chatHistory.slice(-5);
      historyText = '\n\nИСТОРИЯ ЧАТА (для понимания участников):\n';
      
      recentHistory.forEach((msg) => {
        const role = msg.role === 'USER' ? 'Пользователь' : 'Ассистент';
        const content = msg.role === 'ASSISTANT' 
          ? `[Ответил про: ${msg.content.substring(0, 200)}...]`
          : msg.content;
        historyText += `${role}: ${content}\n`;
      });
      
      if (mentionedPeople.length > 0) {
        historyText += `\nУПОМЯНУТЫЕ В ЧАТЕ ЛЮДИ: ${mentionedPeople.join(', ')}\n`;
      }
    }
    
    return historyText;
  }

  /**
   * Создание fallback команды
   */
  private createFallbackCommand(mentionedPeople: string[]): ParsedCalendarCommand {
    return {
      action: 'create_meeting',
      datetime: new Date(Date.now() + 24 * 60 * 60 * 1000), // завтра
      participants: mentionedPeople,
      title: 'Встреча',
      duration: CALENDAR_CONSTANTS.DEFAULT_MEETING_DURATION
    };
  }
}
