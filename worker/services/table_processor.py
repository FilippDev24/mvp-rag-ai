from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class ProcessedTable:
    """Обработанная таблица с контекстом"""
    title: str
    headers: List[str]
    rows: List[List[str]]
    context_before: str
    context_after: str
    start_pos: int
    end_pos: int
    metadata: Dict[str, Any]

class TableProcessor:
    """
    Универсальный процессор для обработки таблиц любого типа
    """
    
    def __init__(self):
        self.logger = logger
    
    def process_table_in_context(self, table_data: Dict[str, Any], 
                                full_text: str, table_position: int) -> ProcessedTable:
        """
        Обработка таблицы с сохранением контекста
        
        Args:
            table_data: Данные таблицы из DOCX процессора
            full_text: Полный текст документа
            table_position: Позиция таблицы в тексте
            
        Returns:
            Обработанная таблица с контекстом
        """
        try:
            # Извлечение контекста
            context_before, context_after = self._extract_table_context(
                full_text, table_position, table_data['text_representation']
            )
            
            # Определение заголовка таблицы из контекста
            table_title = self._find_table_title(context_before)
            
            # Извлечение заголовков и строк
            headers, data_rows = self._extract_headers_and_rows(table_data)
            
            processed_table = ProcessedTable(
                title=table_title,
                headers=headers,
                rows=data_rows,
                context_before=context_before,
                context_after=context_after,
                start_pos=table_position,
                end_pos=table_position + len(table_data['text_representation']),
                metadata={
                    'row_count': table_data['row_count'],
                    'col_count': table_data['col_count'],
                    'has_headers': len(headers) > 0,
                    'is_large': table_data['row_count'] > 10,
                    'original_data': table_data
                }
            )
            
            self.logger.info(f"Processed table: rows={len(data_rows)}, cols={len(headers)}")
            
            return processed_table
            
        except Exception as e:
            self.logger.error(f"Error processing table: {str(e)}")
            raise e
    
    def _extract_table_context(self, full_text: str, table_position: int, 
                              table_text: str) -> Tuple[str, str]:
        """Извлечение контекста до и после таблицы"""
        # Поиск позиции таблицы в полном тексте
        table_start = full_text.find(table_text)
        if table_start == -1:
            # Если не нашли точное совпадение, ищем по первой строке
            first_line = table_text.split('\n')[0] if table_text else ''
            table_start = full_text.find(first_line)
        
        if table_start == -1:
            return '', ''
        
        table_end = table_start + len(table_text)
        
        # Контекст до таблицы (предыдущие 200 символов)
        context_start = max(0, table_start - 200)
        context_before = full_text[context_start:table_start].strip()
        
        # Контекст после таблицы (следующие 100 символов)
        context_end = min(len(full_text), table_end + 100)
        context_after = full_text[table_end:context_end].strip()
        
        return context_before, context_after
    
    def _find_table_title(self, context_before: str) -> str:
        """Поиск заголовка таблицы в контексте"""
        if not context_before:
            return "Таблица"
        
        # Ищем последнюю непустую строку перед таблицей
        lines = context_before.split('\n')
        
        for line in reversed(lines):
            line = line.strip()
            if line and len(line) > 3 and len(line) < 150:
                # Убираем двоеточие в конце если есть
                return line.rstrip(':').strip()
        
        return "Таблица"
    
    def _extract_headers_and_rows(self, table_data: Dict[str, Any]) -> Tuple[List[str], List[List[str]]]:
        """Извлечение заголовков и строк данных"""
        if not table_data['rows']:
            return [], []
        
        # Первая строка как заголовки
        headers = [cell.strip() for cell in table_data['rows'][0]]
        
        # Остальные строки как данные
        data_rows = []
        for row in table_data['rows'][1:]:
            cleaned_row = [cell.strip() for cell in row]
            # Добавляем только непустые строки
            if any(cell for cell in cleaned_row):
                data_rows.append(cleaned_row)
        
        return headers, data_rows
    
    def create_table_chunks(self, processed_table: ProcessedTable, 
                           doc_id: str, access_level: int) -> List[Dict[str, Any]]:
        """
        Создание чанков для таблицы согласно лучшим мировым практикам:
        1. Построчное чанкинг с сохранением контекста таблицы в метаданных
        2. Каждая строка = отдельный чанк с полным контекстом таблицы
        3. Богатые метаданные для связи строк с таблицей
        
        Args:
            processed_table: Обработанная таблица
            doc_id: ID документа
            access_level: Уровень доступа
            
        Returns:
            Список чанков (по одному на строку таблицы)
        """
        chunks = []
        
        try:
            # НОВЫЙ ПОДХОД: Построчное чанкинг согласно best practices
            chunks = self._create_row_based_chunks(processed_table, doc_id, access_level)
            
            self.logger.info(f"Created {len(chunks)} row-based chunks for table '{processed_table.title}'")
            
        except Exception as e:
            self.logger.error(f"Error creating table chunks: {str(e)}")
            # Fallback - создаем один чанк со всей таблицей
            chunks = [self._create_fallback_chunk(processed_table, doc_id, access_level)]
        
        return chunks
    
    def _create_single_table_chunk(self, processed_table: ProcessedTable, 
                                  doc_id: str, access_level: int) -> List[Dict[str, Any]]:
        """Создание одного чанка для всей таблицы"""
        # Формируем структурированное представление
        text_parts = []
        
        # Контекст перед таблицей
        if processed_table.context_before:
            text_parts.append(f"Контекст: {processed_table.context_before}")
        
        # Заголовок таблицы
        text_parts.append(f"\n{processed_table.title}")
        
        # Заголовки колонок
        if processed_table.headers:
            headers_line = " | ".join(processed_table.headers)
            text_parts.append(f"Заголовки: {headers_line}")
        
        # Строки данных с полным контекстом
        for i, row in enumerate(processed_table.rows, 1):
            if any(cell.strip() for cell in row):  # Только непустые строки
                row_line = " | ".join(row)
                text_parts.append(f"Строка {i}: {row_line}")
        
        # Контекст после таблицы
        if processed_table.context_after:
            text_parts.append(f"\nДалее: {processed_table.context_after}")
        
        full_text = "\n".join(text_parts)
        
        chunk_data = {
            "text": full_text,
            "metadata": {
                "doc_id": doc_id,
                "chunk_index": 0,
                "access_level": access_level,
                "char_start": processed_table.start_pos,
                "char_end": processed_table.end_pos,
                "char_count": len(full_text),
                "total_chunks": 1,
                
                # Метаданные секции
                "section_title": processed_table.title,
                "section_type": "table",
                "section_level": 1,
                "chunk_type": "complete_table",
                "is_complete_section": True,
                
                # Метаданные таблицы
                "table_rows": len(processed_table.rows),
                "table_cols": len(processed_table.headers),
                "has_context": bool(processed_table.context_before or processed_table.context_after)
            },
            "chunk_index": 0
        }
        
        return [chunk_data]
    
    def _create_chunked_table(self, processed_table: ProcessedTable, 
                             doc_id: str, access_level: int) -> List[Dict[str, Any]]:
        """Создание нескольких чанков для большой таблицы"""
        chunks = []
        rows_per_chunk = 8  # Оптимальное количество строк на чанк
        
        # Базовая информация для всех чанков
        base_info = []
        if processed_table.context_before:
            base_info.append(f"Контекст: {processed_table.context_before}")
        
        base_info.append(f"\n{processed_table.title}")
        
        if processed_table.headers:
            headers_line = " | ".join(processed_table.headers)
            base_info.append(f"Заголовки: {headers_line}")
        
        base_text = "\n".join(base_info)
        
        # Разбиваем строки на группы
        total_chunks = (len(processed_table.rows) + rows_per_chunk - 1) // rows_per_chunk
        
        for chunk_idx in range(total_chunks):
            start_row = chunk_idx * rows_per_chunk
            end_row = min(start_row + rows_per_chunk, len(processed_table.rows))
            chunk_rows = processed_table.rows[start_row:end_row]
            
            # Формируем текст чанка
            chunk_parts = [base_text]
            
            # Добавляем строки данных
            for i, row in enumerate(chunk_rows, start_row + 1):
                if any(cell.strip() for cell in row):
                    row_line = " | ".join(row)
                    chunk_parts.append(f"Строка {i}: {row_line}")
            
            # Информация о продолжении
            if chunk_idx < total_chunks - 1:
                chunk_parts.append(f"\n[Продолжение таблицы в следующем чанке]")
            elif processed_table.context_after:
                chunk_parts.append(f"\nДалее: {processed_table.context_after}")
            
            chunk_text = "\n".join(chunk_parts)
            
            chunk_data = {
                "text": chunk_text,
                "metadata": {
                    "doc_id": doc_id,
                    "chunk_index": chunk_idx,
                    "access_level": access_level,
                    "char_start": processed_table.start_pos,
                    "char_end": processed_table.end_pos,
                    "char_count": len(chunk_text),
                    "total_chunks": total_chunks,
                    
                    # Метаданные секции
                    "section_title": f"{processed_table.title} (часть {chunk_idx + 1})",
                    "section_type": "table",
                    "section_level": 1,
                    "chunk_type": "table_part",
                    "is_complete_section": False,
                    
                    # Метаданные таблицы
                    "table_rows": len(processed_table.rows),
                    "table_cols": len(processed_table.headers),
                    "has_context": True,
                    "part_number": chunk_idx + 1,
                    "total_parts": total_chunks,
                    "rows_in_chunk": len(chunk_rows)
                },
                "chunk_index": chunk_idx
            }
            
            chunks.append(chunk_data)
        
        return chunks
    
    def _create_row_based_chunks(self, processed_table: ProcessedTable, 
                                doc_id: str, access_level: int) -> List[Dict[str, Any]]:
        """
        НОВЫЙ ПОДХОД: Построчное чанкинг согласно лучшим мировым практикам
        
        Принципы:
        1. Каждая строка таблицы = отдельный чанк
        2. Каждый чанк содержит полный контекст таблицы (заголовки + контекст)
        3. Богатые метаданные для связи строк с таблицей
        4. Масштабируется на любое количество строк (хоть 100 000)
        """
        chunks = []
        
        # Формируем базовый контекст для всех строк
        context_parts = []
        
        # Контекст документа перед таблицей
        if processed_table.context_before:
            context_parts.append(f"Контекст документа: {processed_table.context_before}")
        
        # Название и описание таблицы
        context_parts.append(f"Таблица: {processed_table.title}")
        
        # Заголовки таблицы (КРИТИЧНО для понимания данных)
        if processed_table.headers:
            headers_text = " | ".join(processed_table.headers)
            context_parts.append(f"Столбцы таблицы: {headers_text}")
        
        base_context = "\n".join(context_parts)
        
        # Создаем чанк для каждой строки данных
        for row_idx, row_data in enumerate(processed_table.rows):
            # Пропускаем пустые строки
            if not any(cell.strip() for cell in row_data):
                continue
            
            # Формируем текст чанка: контекст + конкретная строка
            row_text_parts = [base_context]
            
            # Добавляем данные строки с привязкой к заголовкам
            if processed_table.headers and len(row_data) == len(processed_table.headers):
                # Структурированное представление: заголовок = значение
                row_details = []
                for header, value in zip(processed_table.headers, row_data):
                    if value.strip():  # Только непустые значения
                        row_details.append(f"{header}: {value.strip()}")
                
                if row_details:
                    row_text_parts.append(f"Строка {row_idx + 1}: {' | '.join(row_details)}")
                else:
                    # Fallback если все значения пустые
                    continue
            else:
                # Простое представление если заголовки не совпадают
                row_values = [cell.strip() for cell in row_data if cell.strip()]
                if row_values:
                    row_text_parts.append(f"Строка {row_idx + 1}: {' | '.join(row_values)}")
                else:
                    continue
            
            # Контекст после таблицы (если есть)
            if processed_table.context_after:
                row_text_parts.append(f"Далее в документе: {processed_table.context_after}")
            
            chunk_text = "\n".join(row_text_parts)
            
            # Создаем чанк с богатыми метаданными
            chunk_data = {
                "text": chunk_text,
                "metadata": {
                    "doc_id": doc_id,
                    "chunk_index": row_idx,
                    "access_level": access_level,
                    "char_start": processed_table.start_pos,
                    "char_end": processed_table.end_pos,
                    "char_count": len(chunk_text),
                    "total_chunks": len(processed_table.rows),
                    
                    # Метаданные секции
                    "section_title": processed_table.title,
                    "section_type": "table_row",  # НОВЫЙ ТИП!
                    "section_level": 1,
                    "chunk_type": "table_row",
                    "is_complete_section": False,
                    
                    # БОГАТЫЕ метаданные таблицы (согласно best practices)
                    "table_title": processed_table.title,
                    "table_headers": processed_table.headers,
                    "table_total_rows": len(processed_table.rows),
                    "table_total_cols": len(processed_table.headers),
                    "table_row_index": row_idx + 1,  # Человеко-читаемый индекс
                    "table_row_data": row_data,  # Сырые данные строки
                    "has_table_context": True,
                    
                    # Контекстные метаданные для лучшего поиска
                    "context_before": processed_table.context_before,
                    "context_after": processed_table.context_after,
                    
                    # Метаданные для гибридного поиска (higher weight)
                    "content_type": "structured_data",
                    "search_weight": 2.0  # Таблицы важнее обычного текста
                },
                "chunk_index": row_idx
            }
            
            chunks.append(chunk_data)
        
        return chunks

    def _create_fallback_chunk(self, processed_table: ProcessedTable, 
                              doc_id: str, access_level: int) -> Dict[str, Any]:
        """Создание fallback чанка при ошибках"""
        original_text = processed_table.metadata['original_data']['text_representation']
        
        return {
            "text": f"{processed_table.title}\n{original_text}",
            "metadata": {
                "doc_id": doc_id,
                "chunk_index": 0,
                "access_level": access_level,
                "char_start": processed_table.start_pos,
                "char_end": processed_table.end_pos,
                "char_count": len(original_text),
                "total_chunks": 1,
                "section_title": processed_table.title,
                "section_type": "table",
                "chunk_type": "fallback_table",
                "is_complete_section": True
            },
            "chunk_index": 0
        }
