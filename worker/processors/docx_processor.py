from typing import List, Dict, Any, Tuple
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from .base_processor import BaseProcessor
from services.document_analyzer import DocumentStructureAnalyzer, DocumentMetadata, DocumentSection
from services.chunking_service import SemanticChunkingService
import logging

logger = logging.getLogger(__name__)

class DocxProcessor(BaseProcessor):
    """
    Улучшенный обработчик для DOCX документов с поддержкой структурного анализа
    """
    
    def __init__(self):
        super().__init__()
        self.analyzer = DocumentStructureAnalyzer()
    
    def get_supported_extensions(self) -> List[str]:
        return ['.docx']
    
    def extract_text(self, file_path: str) -> str:
        """
        Извлечение текста из DOCX файла (базовый метод для совместимости)
        
        Args:
            file_path: Путь к DOCX файлу
            
        Returns:
            Извлеченный текст
        """
        try:
            structured_data = self.extract_structured_content(file_path)
            return structured_data['full_text']
            
        except Exception as e:
            self.logger.error(f"Error extracting text from DOCX {file_path}: {str(e)}")
            raise e
    
    def extract_structured_content(self, file_path: str) -> Dict[str, Any]:
        """
        Извлечение структурированного содержимого из DOCX файла
        
        Args:
            file_path: Путь к DOCX файлу
            
        Returns:
            Словарь с полным текстом, таблицами и метаданными
        """
        try:
            doc = Document(file_path)
            
            # Извлечение основного содержимого
            content_parts = []
            tables_data = []
            document_properties = {}
            
            # Извлечение свойств документа
            if hasattr(doc.core_properties, 'title') and doc.core_properties.title:
                document_properties['title'] = doc.core_properties.title
            if hasattr(doc.core_properties, 'author') and doc.core_properties.author:
                document_properties['author'] = doc.core_properties.author
            if hasattr(doc.core_properties, 'created') and doc.core_properties.created:
                document_properties['created'] = doc.core_properties.created.isoformat()
            if hasattr(doc.core_properties, 'modified') and doc.core_properties.modified:
                document_properties['modified'] = doc.core_properties.modified.isoformat()
            
            # Обработка элементов документа в порядке их появления
            for element in doc.element.body:
                if element.tag.endswith('p'):  # Параграф
                    paragraph = Paragraph(element, doc)
                    if paragraph.text.strip():
                        # Анализ стиля параграфа
                        style_info = self._analyze_paragraph_style(paragraph)
                        content_parts.append({
                            'type': 'paragraph',
                            'text': paragraph.text.strip(),
                            'style': style_info
                        })
                
                elif element.tag.endswith('tbl'):  # Таблица
                    table = Table(element, doc)
                    table_data = self._extract_table_data(table)
                    if table_data['rows']:
                        tables_data.append(table_data)
                        # Добавляем таблицу в основной текст
                        content_parts.append({
                            'type': 'table',
                            'text': table_data['text_representation'],
                            'table_data': table_data
                        })
            
            # Формирование полного текста
            full_text_parts = []
            for part in content_parts:
                full_text_parts.append(part['text'])
            
            full_text = '\n'.join(full_text_parts)
            
            self.logger.info(f"Extracted structured content from DOCX: {len(full_text)} chars, {len(tables_data)} tables")
            
            return {
                'full_text': full_text,
                'content_parts': content_parts,
                'tables': tables_data,
                'document_properties': document_properties,
                'text_length': len(full_text)
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting structured content from DOCX {file_path}: {str(e)}")
            raise e
    
    def _analyze_paragraph_style(self, paragraph: Paragraph) -> Dict[str, Any]:
        """Анализ стиля параграфа"""
        style_info = {
            'style_name': None,
            'is_heading': False,
            'heading_level': None,
            'is_bold': False,
            'is_italic': False,
            'alignment': None
        }
        
        try:
            # Название стиля
            if paragraph.style and paragraph.style.name:
                style_info['style_name'] = paragraph.style.name
                
                # Определение заголовков
                if 'heading' in paragraph.style.name.lower():
                    style_info['is_heading'] = True
                    # Извлечение уровня заголовка
                    import re
                    level_match = re.search(r'(\d+)', paragraph.style.name)
                    if level_match:
                        style_info['heading_level'] = int(level_match.group(1))
            
            # Анализ форматирования первого run
            if paragraph.runs:
                first_run = paragraph.runs[0]
                if first_run.bold:
                    style_info['is_bold'] = True
                if first_run.italic:
                    style_info['is_italic'] = True
            
            # Выравнивание
            if paragraph.alignment:
                style_info['alignment'] = str(paragraph.alignment)
                
        except Exception as e:
            self.logger.debug(f"Error analyzing paragraph style: {str(e)}")
        
        return style_info
    
    def _extract_table_data(self, table: Table) -> Dict[str, Any]:
        """
        Извлечение данных из таблицы согласно лучшим мировым практикам RAG
        
        Принципы:
        1. Прямой доступ к структуре таблицы через XML (преимущество Word над PDF)
        2. Сохранение структурированных данных для построчного чанкинга
        3. Извлечение контекста вокруг таблицы
        4. Подготовка данных для TableProcessor
        """
        table_data = {
            'rows': [],
            'headers': [],
            'text_representation': '',
            'row_count': len(table.rows),
            'col_count': 0,
            'structured_rows': [],  # НОВОЕ: структурированные данные
            'has_merged_cells': False,  # НОВОЕ: информация о объединенных ячейках
            'table_style': None  # НОВОЕ: стиль таблицы
        }
        
        try:
            if not table.rows:
                return table_data
            
            # Определение количества колонок
            table_data['col_count'] = len(table.rows[0].cells) if table.rows else 0
            
            # Анализ стиля таблицы (если доступен)
            if hasattr(table, 'style') and table.style:
                table_data['table_style'] = table.style.name
            
            # Извлечение данных по строкам с улучшенной обработкой
            text_parts = []
            headers_extracted = False
            
            for row_idx, row in enumerate(table.rows):
                row_data = []
                row_text_parts = []
                structured_row = {}
                
                for cell_idx, cell in enumerate(row.cells):
                    # Улучшенное извлечение текста из ячейки
                    cell_text = self._extract_cell_text(cell)
                    row_data.append(cell_text)
                    
                    if cell_text:
                        row_text_parts.append(cell_text)
                    
                    # Проверка на объединенные ячейки
                    if self._is_merged_cell(cell):
                        table_data['has_merged_cells'] = True
                
                table_data['rows'].append(row_data)
                
                # Определение заголовков (первая непустая строка)
                if not headers_extracted and any(cell.strip() for cell in row_data):
                    table_data['headers'] = row_data
                    headers_extracted = True
                    
                    # Создаем структурированную строку для заголовков
                    for idx, header in enumerate(row_data):
                        if header.strip():
                            structured_row[f"col_{idx}"] = header.strip()
                    
                    text_parts.append(f"[Заголовки таблицы: {' | '.join(row_text_parts)}]")
                else:
                    # Создаем структурированную строку данных
                    if table_data['headers']:
                        for idx, (header, value) in enumerate(zip(table_data['headers'], row_data)):
                            if header.strip() and value.strip():
                                structured_row[header.strip()] = value.strip()
                    else:
                        # Fallback если заголовки не определены
                        for idx, value in enumerate(row_data):
                            if value.strip():
                                structured_row[f"col_{idx}"] = value.strip()
                    
                    if row_text_parts:  # Только непустые строки
                        text_parts.append(f"[Строка {row_idx}: {' | '.join(row_text_parts)}]")
                
                # Сохраняем структурированную строку
                if structured_row:
                    table_data['structured_rows'].append(structured_row)
            
            # Создание текстового представления таблицы
            if text_parts:
                table_data['text_representation'] = '\n'.join(text_parts)
            
            self.logger.debug(f"Extracted table: {table_data['row_count']}x{table_data['col_count']}, "
                            f"structured_rows={len(table_data['structured_rows'])}, "
                            f"has_merged_cells={table_data['has_merged_cells']}")
            
        except Exception as e:
            self.logger.error(f"Error extracting table data: {str(e)}")
        
        return table_data
    
    def _extract_cell_text(self, cell) -> str:
        """
        Улучшенное извлечение текста из ячейки таблицы
        
        Обрабатывает:
        - Множественные параграфы в ячейке
        - Переносы строк
        - Специальные символы
        """
        try:
            # Извлекаем текст из всех параграфов в ячейке
            cell_texts = []
            for paragraph in cell.paragraphs:
                para_text = paragraph.text.strip()
                if para_text:
                    cell_texts.append(para_text)
            
            # Объединяем с пробелами, убираем лишние пробелы
            full_text = ' '.join(cell_texts)
            
            # Очистка от лишних пробелов и специальных символов
            import re
            full_text = re.sub(r'\s+', ' ', full_text)  # Множественные пробелы в один
            full_text = full_text.replace('\x0b', ' ')  # Вертикальные табы
            full_text = full_text.replace('\x0c', ' ')  # Разрывы страниц
            
            return full_text.strip()
            
        except Exception as e:
            self.logger.debug(f"Error extracting cell text: {str(e)}")
            return cell.text.strip() if hasattr(cell, 'text') else ''
    
    def _is_merged_cell(self, cell) -> bool:
        """
        Проверка, является ли ячейка объединенной
        
        Это важно для правильной обработки сложных таблиц
        """
        try:
            # Проверяем через XML элементы
            tc_element = cell._element
            
            # Ищем элементы объединения
            gridSpan = tc_element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}gridSpan')
            vMerge = tc_element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}vMerge')
            
            return gridSpan is not None or vMerge is not None
            
        except Exception as e:
            self.logger.debug(f"Error checking merged cell: {str(e)}")
            return False
    
    def process_document(self, file_path: str, doc_id: str, access_level: int) -> Dict[str, Any]:
        """
        Расширенная обработка документа с структурным анализом
        
        Args:
            file_path: Путь к файлу
            doc_id: ID документа
            access_level: Уровень доступа
            
        Returns:
            Результат обработки с дополнительными метаданными
        """
        try:
            # Валидация файла
            if not self.validate_file(file_path):
                raise ValueError(f"File validation failed: {file_path}")
            
            # Извлечение структурированного содержимого
            structured_data = self.extract_structured_content(file_path)
            full_text = structured_data['full_text']
            
            if not full_text:
                raise ValueError("No text extracted from document")
            
            # Структурный анализ документа
            document_metadata, document_sections = self.analyzer.analyze_document(full_text)
            
            self.logger.info(f"Successfully processed DOCX document {doc_id}: "
                           f"text_length={len(full_text)}, "
                           f"sections={len(document_sections)}, "
                           f"type={document_metadata.document_type.value}, "
                           f"tables={len(structured_data['tables'])}")
            
            return {
                "success": True,
                "doc_id": doc_id,
                "text": full_text,
                "text_length": len(full_text),
                "access_level": access_level,
                "structured_data": structured_data,
                "document_metadata": {
                    "type": document_metadata.document_type.value,
                    "title": document_metadata.title,
                    "number": document_metadata.number,
                    "date": document_metadata.date,
                    "organization": document_metadata.organization,
                    "signatories": document_metadata.signatories or [],
                    "legal_info": document_metadata.legal_info or {},
                    "document_properties": structured_data['document_properties']
                },
                "document_sections": [
                    {
                        "title": section.title,
                        "content": section.content,
                        "level": section.level,
                        "section_type": section.section_type,
                        "start_pos": section.start_pos,
                        "end_pos": section.end_pos,
                        "metadata": section.metadata
                    }
                    for section in document_sections
                ],
                "tables_count": len(structured_data['tables']),
                "content_parts_count": len(structured_data['content_parts'])
            }
            
        except Exception as e:
            self.logger.error(f"Error processing DOCX document {doc_id}: {str(e)}")
            return {
                "success": False,
                "doc_id": doc_id,
                "error": str(e)
            }
