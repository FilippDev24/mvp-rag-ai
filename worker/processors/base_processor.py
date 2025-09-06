from abc import ABC, abstractmethod
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class BaseProcessor(ABC):
    """
    Абстрактный базовый класс для обработчиков документов
    """
    
    def __init__(self):
        self.logger = logger
    
    @abstractmethod
    def extract_text(self, file_path: str) -> str:
        """
        Извлечение текста из файла
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Извлеченный текст
        """
        pass
    
    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """
        Получить список поддерживаемых расширений файлов
        
        Returns:
            Список расширений (например, ['.docx', '.doc'])
        """
        pass
    
    def clean_text(self, text: str) -> str:
        """
        Очистка текста от лишних символов и форматирования
        
        Args:
            text: Исходный текст
            
        Returns:
            Очищенный текст
        """
        if not text:
            return ""
        
        # Удаление специальных символов
        text = text.replace('\x00', '')  # Null bytes
        text = text.replace('\ufeff', '')  # BOM
        text = text.replace('\r\n', '\n')  # Нормализация переносов строк
        text = text.replace('\r', '\n')
        
        # Удаление избыточных пробелов, но сохранение структуры
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Удаляем лишние пробелы в начале и конце строки
            cleaned_line = line.strip()
            if cleaned_line:  # Добавляем только непустые строки
                # Удаляем множественные пробелы внутри строки
                cleaned_line = ' '.join(cleaned_line.split())
                cleaned_lines.append(cleaned_line)
        
        # Объединяем строки с переносами
        result = '\n'.join(cleaned_lines)
        
        return result.strip()
    
    def validate_file(self, file_path: str) -> bool:
        """
        Валидация файла перед обработкой
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            True если файл валиден
        """
        import os
        
        if not os.path.exists(file_path):
            self.logger.error(f"File not found: {file_path}")
            return False
        
        if os.path.getsize(file_path) == 0:
            self.logger.error(f"File is empty: {file_path}")
            return False
        
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in self.get_supported_extensions():
            self.logger.error(f"Unsupported file extension: {file_ext}")
            return False
        
        return True
    
    def process_document(self, file_path: str, doc_id: str, access_level: int) -> Dict[str, Any]:
        """
        Основной метод обработки документа
        
        Args:
            file_path: Путь к файлу
            doc_id: ID документа
            access_level: Уровень доступа
            
        Returns:
            Результат обработки
        """
        try:
            # Валидация файла
            if not self.validate_file(file_path):
                raise ValueError(f"File validation failed: {file_path}")
            
            # Извлечение текста
            text = self.extract_text(file_path)
            
            # Очистка текста
            cleaned_text = self.clean_text(text)
            
            if not cleaned_text:
                raise ValueError("No text extracted from document")
            
            self.logger.info(f"Successfully processed document {doc_id}, text length: {len(cleaned_text)}")
            
            return {
                "success": True,
                "doc_id": doc_id,
                "text": cleaned_text,
                "text_length": len(cleaned_text),
                "access_level": access_level
            }
            
        except Exception as e:
            self.logger.error(f"Error processing document {doc_id}: {str(e)}")
            return {
                "success": False,
                "doc_id": doc_id,
                "error": str(e)
            }
