import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class DocumentType(Enum):
    """Типы документов для специализированной обработки"""
    ORDER = "order"  # Приказ
    INSTRUCTION = "instruction"  # Инструкция
    CONTRACT = "contract"  # Договор
    REPORT = "report"  # Отчет
    GENERAL = "general"  # Общий документ

@dataclass
class DocumentSection:
    """Секция документа с метаданными"""
    title: str
    content: str
    level: int  # Уровень вложенности (1 - заголовок, 2 - подзаголовок и т.д.)
    section_type: str  # header, paragraph, list_item, table, etc.
    start_pos: int
    end_pos: int
    metadata: Dict[str, Any]

@dataclass
class DocumentMetadata:
    """Извлеченные метаданные документа"""
    document_type: DocumentType
    title: Optional[str] = None
    number: Optional[str] = None
    date: Optional[str] = None
    organization: Optional[str] = None
    signatories: List[str] = None
    legal_info: Dict[str, str] = None
    custom_fields: Dict[str, Any] = None

class DocumentStructureAnalyzer:
    """
    Анализатор структуры документов для семантического chunking
    """
    
    def __init__(self):
        self.logger = logger
        
        # Паттерны для распознавания типов документов
        self.document_patterns = {
            DocumentType.ORDER: [
                r'ПРИКАЗ',
                r'П\s*Р\s*И\s*К\s*А\s*З',
                r'№\s*\d+[-\w]*\s*от',
                r'ПРИКАЗЫВАЮ'
            ],
            DocumentType.INSTRUCTION: [
                r'ИНСТРУКЦИЯ',
                r'ДОЛЖНОСТНАЯ\s+ИНСТРУКЦИЯ',
                r'РЕГЛАМЕНТ'
            ],
            DocumentType.CONTRACT: [
                r'ДОГОВОР',
                r'СОГЛАШЕНИЕ',
                r'КОНТРАКТ'
            ]
        }
        
        # Паттерны для извлечения метаданных
        self.metadata_patterns = {
            'order_number': r'№\s*(\d+[-\w]*)',
            'date': r'«(\d{1,2})»\s+(\w+)\s+(\d{4})\s*г\.?',
            'organization': r'(?:ООО|ОАО|ЗАО|ИП)\s*[«"]?([^«"»\n]+)[«"»]?',
            'inn': r'ИНН\s*(\d{10,12})',
            'ogrn': r'ОГРН\s*(\d{13,15})',
            'kpp': r'КПП\s*(\d{9})',
            'signatory': r'(?:Директор|Генеральный\s+директор|Руководитель)[^\n]*\s+([А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.[А-ЯЁ]\.)',
            'address': r'(?:Юридический\s+адрес|Фактический\s+адрес):\s*([^\n]+)'
        }
        
        # Паттерны для структурных элементов
        self.structure_patterns = {
            'numbered_item': r'^(\d+(?:\.\d+)*)\.\s*(.+)',
            'lettered_item': r'^([а-я])\)\s*(.+)',
            'dash_item': r'^[-–—]\s*(.+)',
            'header': r'^([А-ЯЁ\s]{3,}):?\s*$',
            'subheader': r'^([А-ЯЁ][а-яё\s]+):?\s*$',
            'table_start': r'^\[Заголовки таблицы:',
            'table_row': r'^\[Строка \d+:'
        }
    
    def analyze_document(self, text: str) -> Tuple[DocumentMetadata, List[DocumentSection]]:
        """
        Анализ структуры документа
        
        Args:
            text: Текст документа
            
        Returns:
            Кортеж (метаданные, список секций)
        """
        try:
            # Определение типа документа
            doc_type = self._detect_document_type(text)
            
            # Извлечение метаданных
            metadata = self._extract_metadata(text, doc_type)
            
            # Анализ структуры
            sections = self._analyze_structure(text, doc_type)
            
            self.logger.info(f"Document analyzed: type={doc_type.value}, sections={len(sections)}")
            
            return metadata, sections
            
        except Exception as e:
            self.logger.error(f"Error analyzing document structure: {str(e)}")
            # Возвращаем базовую структуру при ошибке
            return DocumentMetadata(DocumentType.GENERAL), [
                DocumentSection(
                    title="Документ",
                    content=text,
                    level=1,
                    section_type="paragraph",
                    start_pos=0,
                    end_pos=len(text),
                    metadata={}
                )
            ]
    
    def _detect_document_type(self, text: str) -> DocumentType:
        """Определение типа документа по содержимому"""
        text_upper = text.upper()
        
        for doc_type, patterns in self.document_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_upper):
                    self.logger.info(f"Detected document type: {doc_type.value}")
                    return doc_type
        
        return DocumentType.GENERAL
    
    def _extract_metadata(self, text: str, doc_type: DocumentType) -> DocumentMetadata:
        """Извлечение метаданных документа"""
        metadata = DocumentMetadata(document_type=doc_type)
        
        try:
            # Номер документа
            if match := re.search(self.metadata_patterns['order_number'], text):
                metadata.number = match.group(1)
            
            # Дата
            if match := re.search(self.metadata_patterns['date'], text):
                day, month, year = match.groups()
                metadata.date = f"{day} {month} {year}"
            
            # Организация
            if match := re.search(self.metadata_patterns['organization'], text):
                metadata.organization = match.group(1).strip()
            
            # Подписанты
            signatories = []
            for match in re.finditer(self.metadata_patterns['signatory'], text):
                signatories.append(match.group(1).strip())
            metadata.signatories = signatories
            
            # Юридическая информация
            legal_info = {}
            for field in ['inn', 'ogrn', 'kpp']:
                if match := re.search(self.metadata_patterns[field], text):
                    legal_info[field.upper()] = match.group(1)
            
            # Адреса
            addresses = []
            for match in re.finditer(self.metadata_patterns['address'], text):
                addresses.append(match.group(1).strip())
            if addresses:
                legal_info['addresses'] = addresses
            
            metadata.legal_info = legal_info
            
            # Заголовок документа (первая строка после шапки)
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if line and not any(pattern in line.upper() for pattern in ['ООО', 'ИНН', 'АДРЕС', 'ОГРН']):
                    if len(line) > 10 and not re.match(r'^\d+', line):
                        metadata.title = line
                        break
            
            self.logger.info(f"Extracted metadata: number={metadata.number}, date={metadata.date}, org={metadata.organization}")
            
        except Exception as e:
            self.logger.error(f"Error extracting metadata: {str(e)}")
        
        return metadata
    
    def _analyze_structure(self, text: str, doc_type: DocumentType) -> List[DocumentSection]:
        """Анализ структуры документа"""
        sections = []
        lines = text.split('\n')
        current_section = None
        current_content = []
        
        try:
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                if not line_stripped:
                    if current_content:
                        current_content.append('')
                    continue
                
                # Проверка на структурные элементы
                section_info = self._classify_line(line_stripped, doc_type)
                
                if section_info['is_header']:
                    # Сохраняем предыдущую секцию
                    if current_section and current_content:
                        current_section.content = '\n'.join(current_content).strip()
                        sections.append(current_section)
                    
                    # Создаем новую секцию
                    start_pos = sum(len(l) + 1 for l in lines[:i])
                    current_section = DocumentSection(
                        title=section_info['title'],
                        content='',
                        level=section_info['level'],
                        section_type=section_info['type'],
                        start_pos=start_pos,
                        end_pos=start_pos + len(line),
                        metadata=section_info['metadata']
                    )
                    current_content = [line_stripped] if section_info['include_in_content'] else []
                else:
                    # Добавляем к текущей секции
                    if current_content or line_stripped:
                        current_content.append(line_stripped)
            
            # Сохраняем последнюю секцию
            if current_section and current_content:
                current_section.content = '\n'.join(current_content).strip()
                current_section.end_pos = len(text)
                sections.append(current_section)
            
            # Если секций нет, создаем одну общую
            if not sections:
                sections.append(DocumentSection(
                    title="Документ",
                    content=text.strip(),
                    level=1,
                    section_type="paragraph",
                    start_pos=0,
                    end_pos=len(text),
                    metadata={}
                ))
            
            self.logger.info(f"Analyzed structure: {len(sections)} sections")
            
        except Exception as e:
            self.logger.error(f"Error analyzing structure: {str(e)}")
            # Возвращаем базовую структуру при ошибке
            sections = [DocumentSection(
                title="Документ",
                content=text.strip(),
                level=1,
                section_type="paragraph",
                start_pos=0,
                end_pos=len(text),
                metadata={}
            )]
        
        return sections
    
    def _classify_line(self, line: str, doc_type: DocumentType) -> Dict[str, Any]:
        """Классификация строки документа"""
        result = {
            'is_header': False,
            'title': line,
            'level': 1,
            'type': 'paragraph',
            'metadata': {},
            'include_in_content': True
        }
        
        # Нумерованные пункты (1., 1.1., 2.3.6.)
        if match := re.match(self.structure_patterns['numbered_item'], line):
            number, title = match.groups()
            level = len(number.split('.'))
            result.update({
                'is_header': True,
                'title': f"Пункт {number}",
                'level': level,
                'type': 'numbered_item',
                'metadata': {'number': number, 'item_title': title.strip()},
                'include_in_content': True
            })
        
        # Буквенные пункты (а), б), в))
        elif match := re.match(self.structure_patterns['lettered_item'], line):
            letter, title = match.groups()
            result.update({
                'is_header': True,
                'title': f"Подпункт {letter})",
                'level': 3,
                'type': 'lettered_item',
                'metadata': {'letter': letter, 'item_title': title.strip()},
                'include_in_content': True
            })
        
        # Заголовки (ПРИКАЗЫВАЮ:, О внесении дополнений)
        elif re.match(self.structure_patterns['header'], line):
            result.update({
                'is_header': True,
                'title': line,
                'level': 1,
                'type': 'header',
                'metadata': {},
                'include_in_content': True
            })
        
        # Подзаголовки
        elif re.match(self.structure_patterns['subheader'], line) and len(line) < 100:
            result.update({
                'is_header': True,
                'title': line,
                'level': 2,
                'type': 'subheader',
                'metadata': {},
                'include_in_content': True
            })
        
        # Распознавание таблиц
        elif re.match(self.structure_patterns['table_start'], line):
            # Извлекаем заголовок таблицы из контекста
            table_title = "Таблица"
            if ":" in line:
                table_title = line.split(":", 1)[0].replace("[Заголовки таблицы", "").strip()
            
            result.update({
                'is_header': True,
                'title': table_title,
                'level': 1,
                'type': 'table',
                'metadata': {'is_table_start': True},
                'include_in_content': True
            })
        
        # Специальные элементы для приказов
        elif doc_type == DocumentType.ORDER:
            if 'ПРИКАЗЫВАЮ' in line.upper():
                result.update({
                    'is_header': True,
                    'title': 'Распорядительная часть',
                    'level': 1,
                    'type': 'order_directive',
                    'metadata': {},
                    'include_in_content': True
                })
            elif line.startswith('Директор') or line.startswith('Генеральный директор'):
                result.update({
                    'is_header': True,
                    'title': 'Подписи',
                    'level': 1,
                    'type': 'signatures',
                    'metadata': {},
                    'include_in_content': True
                })
        
        return result
    
    def get_optimal_chunk_size(self, section: DocumentSection) -> int:
        """Определение оптимального размера чанка для секции"""
        base_size = 1000
        
        # Адаптивный размер в зависимости от типа секции
        if section.section_type == 'header':
            return min(500, len(section.content) + 100)  # Короткие чанки для заголовков
        elif section.section_type == 'numbered_item':
            # Для пунктов приказов - размер зависит от содержимого
            content_length = len(section.content)
            if content_length < 300:
                return content_length + 50  # Маленькие пункты целиком
            elif content_length < 800:
                return 600  # Средние пункты
            else:
                return base_size  # Большие пункты стандартно
        elif section.section_type == 'signatures':
            return min(300, len(section.content) + 50)  # Короткие чанки для подписей
        elif section.section_type == 'table':
            return min(1500, len(section.content) + 200)  # Большие чанки для таблиц
        else:
            return base_size
    
    def should_keep_together(self, section: DocumentSection) -> bool:
        """Определение, нужно ли держать секцию целиком"""
        # Короткие секции держим целиком
        if len(section.content) < 200:
            return True
        
        # Заголовки и подписи не разбиваем
        if section.section_type in ['header', 'signatures', 'lettered_item']:
            return True
        
        # ТАБЛИЦЫ: НЕ держим целиком - позволяем TableProcessor разбивать построчно
        # Это согласно лучшим мировым практикам RAG для таблиц
        if section.section_type == 'table':
            return False  # Позволяем разбивать таблицы
        
        # Нумерованные пункты до 500 символов держим целиком
        if section.section_type == 'numbered_item' and len(section.content) < 500:
            return True
        
        return False
