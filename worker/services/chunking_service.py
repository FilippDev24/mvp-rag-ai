import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from services.document_analyzer import DocumentStructureAnalyzer, DocumentSection, DocumentType
from services.table_processor import TableProcessor
import logging

logger = logging.getLogger(__name__)

class ChunkingConfig:
    """Конфигурация для чанкинга согласно требованиям"""
    # Базовые размеры
    SIZE = 1000
    OVERLAP = 100
    MIN_SIZE = 200
    
    # Адаптивные размеры для разных типов контента
    HEADER_SIZE = 500
    NUMBERED_ITEM_SIZE = 600
    SIGNATURES_SIZE = 300
    TABLE_SIZE = 1500
    
    # ВАЖНО: Не обрезать посреди слова
    RESPECT_SENTENCE_BOUNDARY = True
    RESPECT_SEMANTIC_BOUNDARY = True

class TextChunk:
    """Класс для представления чанка текста с расширенными метаданными"""
    
    def __init__(self, text: str, start: int, end: int, index: int, 
                 section_info: Optional[Dict[str, Any]] = None):
        self.text = text
        self.start = start
        self.end = end
        self.index = index
        self.section_info = section_info or {}

class SemanticChunkingService:
    """
    Улучшенный сервис для семантического и адаптивного chunking
    """
    
    def __init__(self):
        self.config = ChunkingConfig()
        self.logger = logger
        self.analyzer = DocumentStructureAnalyzer()
        self.table_processor = TableProcessor()
    
    def create_chunks(self, text: str, doc_id: str, access_level: int, 
                     document_sections: Optional[List[DocumentSection]] = None,
                     document_metadata: Optional[Dict[str, Any]] = None,
                     structured_data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Семантическое создание чанков с учетом структуры документа
        
        Args:
            text: Очищенный текст документа
            doc_id: ID документа
            access_level: Уровень доступа
            document_sections: Предварительно проанализированные секции
            document_metadata: Метаданные документа
            
        Returns:
            Список чанков с расширенными метаданными
        """
        try:
            # Если секции не переданы, анализируем структуру
            if not document_sections:
                doc_metadata, document_sections = self.analyzer.analyze_document(text)
                if not document_metadata:
                    document_metadata = {
                        "type": doc_metadata.document_type.value,
                        "title": doc_metadata.title,
                        "number": doc_metadata.number,
                        "date": doc_metadata.date,
                        "organization": doc_metadata.organization
                    }
            
            # Если есть структурированные данные (таблицы), обрабатываем их отдельно
            if structured_data and structured_data.get('tables'):
                chunks = self._create_chunks_with_tables(
                    document_sections, text, document_metadata, structured_data, doc_id, access_level
                )
            else:
                # Семантическое разбиение по секциям
                chunks = self._create_semantic_chunks(document_sections, text, document_metadata)
            
            # Создание метаданных для КАЖДОГО чанка
            chunk_data = []
            for i, chunk in enumerate(chunks):
                metadata = {
                    "doc_id": doc_id,
                    "chunk_index": i,
                    "access_level": access_level,  # КРИТИЧНО!
                    "char_start": chunk.start,
                    "char_end": chunk.end,
                    "created_at": datetime.now().isoformat(),
                    "char_count": len(chunk.text),
                    "overlap_prev": self._calculate_overlap_prev(chunk, chunks, i),
                    "overlap_next": self._calculate_overlap_next(chunk, chunks, i),
                    "total_chunks": len(chunks),
                    
                    # Семантические метаданные
                    "section_title": chunk.section_info.get("section_title", ""),
                    "section_type": chunk.section_info.get("section_type", "paragraph"),
                    "section_level": chunk.section_info.get("section_level", 1),
                    "chunk_type": chunk.section_info.get("chunk_type", "content"),
                    "is_complete_section": chunk.section_info.get("is_complete_section", False),
                    
                    # Метаданные документа (обеспечиваем, что все значения - строки)
                    "document_type": str(document_metadata.get("type", "general")) if document_metadata else "general",
                    "document_title": str(document_metadata.get("title", "")) if document_metadata and document_metadata.get("title") else "",
                    "document_number": str(document_metadata.get("number", "")) if document_metadata and document_metadata.get("number") else "",
                    "document_date": str(document_metadata.get("date", "")) if document_metadata and document_metadata.get("date") else "",
                    "document_organization": str(document_metadata.get("organization", "")) if document_metadata and document_metadata.get("organization") else ""
                }
                
                chunk_data.append({
                    "text": chunk.text,
                    "metadata": metadata,
                    "chunk_index": i
                })
            
            self.logger.info(f"Created {len(chunk_data)} semantic chunks for document {doc_id}")
            
            return chunk_data
            
        except Exception as e:
            self.logger.error(f"Error creating semantic chunks for document {doc_id}: {str(e)}")
            # Fallback к базовому chunking
            return self._create_basic_chunks(text, doc_id, access_level)
    
    def _create_semantic_chunks(self, sections: List[DocumentSection], 
                               full_text: str, document_metadata: Optional[Dict[str, Any]]) -> List[TextChunk]:
        """Создание чанков на основе семантических секций"""
        chunks = []
        chunk_index = 0
        
        for section in sections:
            section_chunks = self._process_section(section, chunk_index, document_metadata)
            chunks.extend(section_chunks)
            chunk_index += len(section_chunks)
        
        return chunks
    
    def _process_section(self, section: DocumentSection, start_index: int, 
                        document_metadata: Optional[Dict[str, Any]]) -> List[TextChunk]:
        """Обработка отдельной секции документа"""
        chunks = []
        
        # Определяем оптимальный размер чанка для секции
        optimal_size = self.analyzer.get_optimal_chunk_size(section)
        
        # Проверяем, нужно ли держать секцию целиком
        if self.analyzer.should_keep_together(section):
            # Создаем один чанк для всей секции
            section_info = {
                "section_title": section.title,
                "section_type": section.section_type,
                "section_level": section.level,
                "chunk_type": "complete_section",
                "is_complete_section": True,
                **section.metadata
            }
            
            chunk = TextChunk(
                text=section.content,
                start=section.start_pos,
                end=section.end_pos,
                index=start_index,
                section_info=section_info
            )
            chunks.append(chunk)
        else:
            # Разбиваем секцию на несколько чанков
            section_chunks = self._split_section_into_chunks(
                section, optimal_size, start_index
            )
            chunks.extend(section_chunks)
        
        return chunks
    
    def _split_section_into_chunks(self, section: DocumentSection, 
                                  chunk_size: int, start_index: int) -> List[TextChunk]:
        """Разбивка большой секции на чанки с сохранением контекста"""
        chunks = []
        text = section.content
        
        if len(text) <= chunk_size:
            # Секция помещается в один чанк
            section_info = {
                "section_title": section.title,
                "section_type": section.section_type,
                "section_level": section.level,
                "chunk_type": "complete_section",
                "is_complete_section": True,
                **section.metadata
            }
            
            chunk = TextChunk(
                text=text,
                start=section.start_pos,
                end=section.end_pos,
                index=start_index,
                section_info=section_info
            )
            chunks.append(chunk)
            return chunks
        
        # Разбиваем секцию на части
        current_pos = 0
        chunk_index = start_index
        part_number = 1
        
        while current_pos < len(text):
            # Определяем конец чанка
            end_pos = min(current_pos + chunk_size, len(text))
            
            # Ищем семантическую границу
            if end_pos < len(text):
                end_pos = self._find_semantic_boundary(text, end_pos, section.section_type)
            
            # Извлекаем текст чанка
            chunk_text = text[current_pos:end_pos].strip()
            
            if chunk_text and len(chunk_text) >= self.config.MIN_SIZE:
                # Добавляем контекст секции к чанку
                if part_number == 1:
                    # Первый чанк секции - добавляем заголовок
                    contextual_text = f"[{section.title}]\n{chunk_text}"
                else:
                    # Последующие чанки - добавляем краткий контекст
                    contextual_text = f"[{section.title} (продолжение)]\n{chunk_text}"
                
                section_info = {
                    "section_title": section.title,
                    "section_type": section.section_type,
                    "section_level": section.level,
                    "chunk_type": "section_part",
                    "is_complete_section": False,
                    "part_number": part_number,
                    "total_parts": None,  # Будет вычислено позже
                    **section.metadata
                }
                
                chunk = TextChunk(
                    text=contextual_text,
                    start=section.start_pos + current_pos,
                    end=section.start_pos + end_pos,
                    index=chunk_index,
                    section_info=section_info
                )
                chunks.append(chunk)
                chunk_index += 1
                part_number += 1
            
            # Переход к следующему чанку с перекрытием
            if end_pos >= len(text):
                break
            
            current_pos = max(current_pos + 1, end_pos - self.config.OVERLAP)
        
        # Обновляем информацию о количестве частей
        for chunk in chunks:
            if chunk.section_info.get("chunk_type") == "section_part":
                chunk.section_info["total_parts"] = len(chunks)
        
        return chunks
    
    def _find_semantic_boundary(self, text: str, position: int, section_type: str) -> int:
        """Поиск семантической границы с учетом типа секции"""
        search_range = min(150, position)
        
        # Для разных типов секций используем разные стратегии
        if section_type == "numbered_item":
            # Для нумерованных пунктов ищем конец пункта или подпункта
            for i in range(position, max(0, position - search_range), -1):
                if i > 0 and text[i-1:i+1] == '.\n':
                    # Проверяем, что следующая строка начинается с номера
                    next_line_start = i + 1
                    while next_line_start < len(text) and text[next_line_start].isspace():
                        next_line_start += 1
                    
                    if next_line_start < len(text):
                        next_line = text[next_line_start:next_line_start + 10]
                        if re.match(r'^\d+\.', next_line):
                            return i + 1
        
        # Общий поиск границ предложений
        return self._find_sentence_boundary(text, position)
    
    def _find_sentence_boundary(self, text: str, position: int) -> int:
        """Поиск границы предложения (улучшенная версия)"""
        search_range = min(100, position)
        
        # Ищем назад от позиции
        for i in range(position, max(0, position - search_range), -1):
            char = text[i]
            
            # Границы предложений
            if char in '.!?':
                # Проверяем, что это не сокращение
                if i + 1 < len(text) and text[i + 1].isspace():
                    # Дополнительная проверка на сокращения
                    if not self._is_abbreviation(text, i):
                        return i + 1
            
            # Границы абзацев
            elif char == '\n':
                # Проверяем, что это не просто перенос строки внутри предложения
                if i + 1 < len(text) and (text[i + 1].isupper() or text[i + 1].isdigit()):
                    return i + 1
        
        # Если не нашли границу предложения, ищем границу слова
        for i in range(position, max(0, position - search_range), -1):
            if text[i].isspace():
                return i
        
        return position
    
    def _is_abbreviation(self, text: str, position: int) -> bool:
        """Проверка, является ли точка частью сокращения"""
        if position < 2:
            return False
        
        # Список распространенных сокращений
        abbreviations = ['т.д', 'т.п', 'и.о', 'г.', 'см.', 'стр.', 'п.', 'пп.']
        
        # Проверяем контекст вокруг точки
        start = max(0, position - 5)
        end = min(len(text), position + 3)
        context = text[start:end].lower()
        
        for abbr in abbreviations:
            if abbr in context:
                return True
        
        return False
    
    def _create_basic_chunks(self, text: str, doc_id: str, access_level: int) -> List[Dict[str, Any]]:
        """Fallback к базовому chunking при ошибках"""
        try:
            chunks = self._split_text_into_chunks(text)
            
            chunk_data = []
            for i, chunk in enumerate(chunks):
                metadata = {
                    "doc_id": doc_id,
                    "chunk_index": i,
                    "access_level": access_level,
                    "char_start": chunk.start,
                    "char_end": chunk.end,
                    "created_at": datetime.now().isoformat(),
                    "char_count": len(chunk.text),
                    "total_chunks": len(chunks),
                    "chunk_type": "basic",
                    "is_complete_section": False
                }
                
                chunk_data.append({
                    "text": chunk.text,
                    "metadata": metadata,
                    "chunk_index": i
                })
            
            return chunk_data
            
        except Exception as e:
            self.logger.error(f"Error in basic chunking: {str(e)}")
            raise e
    
    def _split_text_into_chunks(self, text: str) -> List[TextChunk]:
        """Базовая разбивка текста на чанки (для совместимости)"""
        if len(text) <= self.config.SIZE:
            return [TextChunk(text, 0, len(text), 0)]
        
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            end = min(start + self.config.SIZE, len(text))
            
            if end < len(text) and self.config.RESPECT_SENTENCE_BOUNDARY:
                end = self._find_sentence_boundary(text, end)
            
            chunk_text = text[start:end].strip()
            
            if len(chunk_text) >= self.config.MIN_SIZE or chunk_index == 0:
                chunks.append(TextChunk(chunk_text, start, end, chunk_index))
                chunk_index += 1
            
            if end >= len(text):
                break
                
            start = max(start + 1, end - self.config.OVERLAP)
        
        return chunks
    
    def _calculate_overlap_prev(self, chunk: TextChunk, chunks: List[TextChunk], index: int) -> int:
        """Вычисление перекрытия с предыдущим чанком"""
        if index == 0:
            return 0
        
        prev_chunk = chunks[index - 1]
        overlap_start = max(chunk.start, prev_chunk.start)
        overlap_end = min(chunk.end, prev_chunk.end)
        
        return max(0, overlap_end - overlap_start)
    
    def _calculate_overlap_next(self, chunk: TextChunk, chunks: List[TextChunk], index: int) -> int:
        """Вычисление перекрытия со следующим чанком"""
        if index >= len(chunks) - 1:
            return 0
        return 0  # Будет вычислено для следующего чанка
    
    def _create_chunks_with_tables(self, sections: List[DocumentSection], 
                                  full_text: str, document_metadata: Optional[Dict[str, Any]],
                                  structured_data: Dict[str, Any], doc_id: str, access_level: int) -> List[TextChunk]:
        """Создание чанков с учетом таблиц из структурированных данных"""
        chunks = []
        chunk_index = 0
        
        # Получаем таблицы из структурированных данных
        tables = structured_data.get('tables', [])
        
        # Создаем карту позиций таблиц в тексте
        table_positions = {}
        for i, table in enumerate(tables):
            table_text = table.get('text_representation', '')
            if table_text:
                pos = full_text.find(table_text)
                if pos != -1:
                    table_positions[pos] = {'index': i, 'table': table}
        
        # Обрабатываем секции, заменяя таблицы на специальные чанки
        for section in sections:
            # Проверяем, содержит ли секция таблицы
            section_tables = self._find_tables_in_section(section, table_positions)
            
            if section_tables:
                # Секция содержит таблицы - обрабатываем специально
                section_chunks = self._process_section_with_tables(
                    section, section_tables, chunk_index, document_metadata, doc_id, access_level
                )
            else:
                # Обычная секция без таблиц
                section_chunks = self._process_section(section, chunk_index, document_metadata)
            
            chunks.extend(section_chunks)
            chunk_index += len(section_chunks)
        
        return chunks
    
    def _find_tables_in_section(self, section: DocumentSection, 
                               table_positions: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Поиск таблиц в секции"""
        section_tables = []
        
        for pos, table_info in table_positions.items():
            # Проверяем, попадает ли таблица в диапазон секции
            if section.start_pos <= pos <= section.end_pos:
                section_tables.append({
                    'position': pos,
                    'relative_position': pos - section.start_pos,
                    **table_info
                })
        
        # Сортируем по позиции
        section_tables.sort(key=lambda x: x['position'])
        return section_tables
    
    def _process_section_with_tables(self, section: DocumentSection, 
                                   section_tables: List[Dict[str, Any]], 
                                   start_index: int, document_metadata: Optional[Dict[str, Any]],
                                   doc_id: str, access_level: int) -> List[TextChunk]:
        """Обработка секции, содержащей таблицы"""
        chunks = []
        current_pos = 0
        chunk_index = start_index
        
        for table_info in section_tables:
            table = table_info['table']
            table_pos = table_info['relative_position']
            
            # Добавляем текст до таблицы как обычный чанк
            if table_pos > current_pos:
                text_before = section.content[current_pos:table_pos].strip()
                if text_before and len(text_before) >= self.config.MIN_SIZE:
                    section_info = {
                        "section_title": section.title,
                        "section_type": section.section_type,
                        "section_level": section.level,
                        "chunk_type": "text_before_table",
                        "is_complete_section": False,
                        **section.metadata
                    }
                    
                    chunk = TextChunk(
                        text=text_before,
                        start=section.start_pos + current_pos,
                        end=section.start_pos + table_pos,
                        index=chunk_index,
                        section_info=section_info
                    )
                    chunks.append(chunk)
                    chunk_index += 1
            
            # Обрабатываем таблицу с помощью table_processor
            try:
                processed_table = self.table_processor.process_table_in_context(
                    table, section.content, table_pos
                )
                
                # Создаем чанки для таблицы
                table_chunks_data = self.table_processor.create_table_chunks(
                    processed_table, doc_id, access_level
                )
                
                # Конвертируем в TextChunk объекты
                for table_chunk_data in table_chunks_data:
                    table_chunk = TextChunk(
                        text=table_chunk_data['text'],
                        start=section.start_pos + table_pos,
                        end=section.start_pos + table_pos + len(table.get('text_representation', '')),
                        index=chunk_index,
                        section_info=table_chunk_data['metadata']
                    )
                    chunks.append(table_chunk)
                    chunk_index += 1
                
                self.logger.info(f"Processed table in section '{section.title}': {len(table_chunks_data)} chunks")
                
            except Exception as e:
                self.logger.error(f"Error processing table in section: {str(e)}")
                # Fallback - добавляем таблицу как обычный текст
                table_text = table.get('text_representation', '')
                if table_text:
                    section_info = {
                        "section_title": f"Таблица в {section.title}",
                        "section_type": "table",
                        "section_level": section.level,
                        "chunk_type": "fallback_table",
                        "is_complete_section": True,
                        **section.metadata
                    }
                    
                    chunk = TextChunk(
                        text=table_text,
                        start=section.start_pos + table_pos,
                        end=section.start_pos + table_pos + len(table_text),
                        index=chunk_index,
                        section_info=section_info
                    )
                    chunks.append(chunk)
                    chunk_index += 1
            
            # Обновляем текущую позицию
            table_text_len = len(table.get('text_representation', ''))
            current_pos = table_pos + table_text_len
        
        # Добавляем оставшийся текст после последней таблицы
        if current_pos < len(section.content):
            text_after = section.content[current_pos:].strip()
            if text_after and len(text_after) >= self.config.MIN_SIZE:
                section_info = {
                    "section_title": section.title,
                    "section_type": section.section_type,
                    "section_level": section.level,
                    "chunk_type": "text_after_table",
                    "is_complete_section": False,
                    **section.metadata
                }
                
                chunk = TextChunk(
                    text=text_after,
                    start=section.start_pos + current_pos,
                    end=section.end_pos,
                    index=chunk_index,
                    section_info=section_info
                )
                chunks.append(chunk)
        
        return chunks

    def get_chunking_stats(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Получение расширенной статистики по чанкам"""
        if not chunks:
            return {}
        
        chunk_sizes = [len(chunk["text"]) for chunk in chunks]
        
        # Статистика по типам чанков
        chunk_types = {}
        section_types = {}
        complete_sections = 0
        
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            
            chunk_type = metadata.get("chunk_type", "unknown")
            chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
            
            section_type = metadata.get("section_type", "unknown")
            section_types[section_type] = section_types.get(section_type, 0) + 1
            
            if metadata.get("is_complete_section", False):
                complete_sections += 1
        
        return {
            "total_chunks": len(chunks),
            "avg_chunk_size": sum(chunk_sizes) / len(chunk_sizes),
            "min_chunk_size": min(chunk_sizes),
            "max_chunk_size": max(chunk_sizes),
            "total_characters": sum(chunk_sizes),
            "chunk_types": chunk_types,
            "section_types": section_types,
            "complete_sections": complete_sections,
            "partial_sections": len(chunks) - complete_sections
        }

# Для обратной совместимости
ChunkingService = SemanticChunkingService
