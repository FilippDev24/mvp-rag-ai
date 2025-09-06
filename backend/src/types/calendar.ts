// Типы для календарных операций согласно ТЗ
export interface CalendarEvent {
  id?: string;
  summary: string;
  description?: string;
  start: {
    dateTime: string;
    timeZone: string;
  };
  end: {
    dateTime: string;
    timeZone: string;
  };
  attendees?: CalendarAttendee[];
  organizer?: {
    email: string;
    displayName?: string;
  };
  location?: string;
  status?: 'confirmed' | 'tentative' | 'cancelled';
}

export interface CalendarAttendee {
  email: string;
  displayName?: string;
  responseStatus?: 'needsAction' | 'declined' | 'tentative' | 'accepted';
  optional?: boolean;
}

export interface YandexTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
}

export interface CalendarConnection {
  id: string;
  userId: string;
  email: string;
  accessToken: string;
  refreshToken: string;
  expiresAt: Date;
  isSystemAccount: boolean;
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}

// Типы для парсинга календарных команд
export interface ParsedCalendarCommand {
  action: 'create_meeting' | 'check_availability' | 'cancel_meeting';
  datetime: Date;
  duration?: number; // в минутах
  participants: string[]; // имена участников
  title?: string;
  description?: string;
  location?: string;
}

export interface EmployeeInfo {
  name: string;
  email: string;
  department?: string;
  position?: string;
}

export interface AvailabilitySlot {
  start: Date;
  end: Date;
  available: boolean;
  conflictingEvents?: CalendarEvent[];
}

export interface MeetingCreationResult {
  success: boolean;
  event?: CalendarEvent;
  message: string;
  participants: EmployeeInfo[];
  alternativeTimes?: Date[];
  error?: string;
  debug?: CalendarDebugInfo;
}

// Типы для отладочной информации календарных запросов
export interface CalendarDebugInfo {
  originalMessage: string;
  parsedCommand: {
    participants: string[];
    datetime: string;
    title: string;
    duration: number;
  };
  participantSearchResults: ParticipantSearchDebug[];
  calendarCreation?: {
    startTime: string;
    endTime: string;
    attendees: string[];
    organizerEmail: string;
  };
  processingSteps: ProcessingStep[];
}

export interface ParticipantSearchDebug {
  searchedFor: string;
  ragResults: {
    resultsCount: number;
    contentPreview: string;
    searchQuery: string;
    taskId: string;
  };
  llmExtraction: {
    prompt: string;
    rawResponse: string;
    parsedResult: any;
    success: boolean;
  };
  finalResult: EmployeeInfo | null;
  processingTime: number;
}

export interface ProcessingStep {
  step: string;
  timestamp: string;
  duration: number;
  success: boolean;
  details: any;
  error?: string;
}

// Типы для API ответов Яндекс.Календаря
export interface YandexCalendarListResponse {
  kind: string;
  etag: string;
  items: YandexCalendarItem[];
}

export interface YandexCalendarItem {
  kind: string;
  etag: string;
  id: string;
  summary: string;
  description?: string;
  timeZone: string;
  accessRole: string;
  primary?: boolean;
}

export interface YandexEventListResponse {
  kind: string;
  etag: string;
  summary: string;
  items: YandexEvent[];
  nextPageToken?: string;
}

export interface YandexEvent {
  kind: string;
  etag: string;
  id: string;
  status: string;
  htmlLink: string;
  created: string;
  updated: string;
  summary: string;
  description?: string;
  location?: string;
  creator: {
    email: string;
    displayName?: string;
  };
  organizer: {
    email: string;
    displayName?: string;
  };
  start: {
    dateTime?: string;
    date?: string;
    timeZone?: string;
  };
  end: {
    dateTime?: string;
    date?: string;
    timeZone?: string;
  };
  attendees?: YandexAttendee[];
}

export interface YandexAttendee {
  email: string;
  displayName?: string;
  responseStatus: 'needsAction' | 'declined' | 'tentative' | 'accepted';
  optional?: boolean;
}

// Константы для календарных операций
export const CALENDAR_CONSTANTS = {
  DEFAULT_MEETING_DURATION: 60, // минут
  DEFAULT_TIMEZONE: 'Europe/Moscow',
  MAX_PARTICIPANTS: 50,
  SEARCH_DAYS_AHEAD: 14, // дней для поиска свободного времени
  WORKING_HOURS_START: 9, // 9:00
  WORKING_HOURS_END: 18, // 18:00
  MEETING_BUFFER_MINUTES: 15, // буфер между встречами
} as const;

// Типы для календарных команд в чате
export interface CalendarChatCommand {
  originalMessage: string;
  isCalendarCommand: boolean;
  parsedCommand?: ParsedCalendarCommand;
  confidence: number; // уверенность в том, что это календарная команда (0-1)
}

// Расширение для RAG ответа с календарными данными
export interface CalendarRAGResponse {
  isCalendarResponse: boolean;
  meetingResult?: MeetingCreationResult;
  availabilityInfo?: AvailabilitySlot[];
  suggestedTimes?: Date[];
}
