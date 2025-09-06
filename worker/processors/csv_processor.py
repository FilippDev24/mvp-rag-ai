import csv
import json
from typing import List
from .base_processor import BaseProcessor
import logging

logger = logging.getLogger(__name__)

class CsvProcessor(BaseProcessor):
    """
    Обработчик для CSV файлов
    """
    
    def get_supported_extensions(self) -> List[str]:
        return ['.csv']
    
    def extract_text(self, file_path: str) -> str:
        """
        Извлечение текста из CSV файла
        
        Args:
            file_path: Путь к CSV файлу
            
        Returns:
            Извлеченный текст в структурированном формате
        """
        try:
            text_parts = []
            
            with open(file_path, 'r', encoding='utf-8', newline='') as csvfile:
                # Попытка автоматического определения диалекта
                sample = csvfile.read(1024)
                csvfile.seek(0)
                
                try:
                    dialect = csv.Sniffer().sniff(sample)
                except csv.Error:
                    # Использование стандартного диалекта если не удалось определить
                    dialect = csv.excel
                
                reader = csv.DictReader(csvfile, dialect=dialect)
                
                # Добавление заголовков
                if reader.fieldnames:
                    headers = "Заголовки: " + ", ".join(reader.fieldnames)
                    text_parts.append(headers)
                
                # Обработка строк
                row_count = 0
                for row_num, row in enumerate(reader, 1):
                    if row_count >= 1000:  # Ограничение для больших файлов
                        text_parts.append(f"... (файл содержит больше строк, показаны первые {row_count})")
                        break
                    
                    # Фильтрация пустых значений
                    non_empty_values = {k: v for k, v in row.items() if v and v.strip()}
                    
                    if non_empty_values:
                        row_text = f"Строка {row_num}: " + "; ".join([f"{k}: {v}" for k, v in non_empty_values.items()])
                        text_parts.append(row_text)
                        row_count += 1
            
            if not text_parts:
                raise ValueError("CSV файл пуст или не содержит данных")
            
            full_text = '\n'.join(text_parts)
            
            self.logger.info(f"Extracted {len(full_text)} characters from CSV: {file_path}, processed {row_count} rows")
            
            return full_text
            
        except UnicodeDecodeError:
            # Попытка с другой кодировкой
            try:
                return self._extract_with_encoding(file_path, 'cp1251')
            except:
                return self._extract_with_encoding(file_path, 'latin1')
                
        except Exception as e:
            self.logger.error(f"Error extracting text from CSV {file_path}: {str(e)}")
            raise e
    
    def _extract_with_encoding(self, file_path: str, encoding: str) -> str:
        """
        Извлечение текста с указанной кодировкой
        
        Args:
            file_path: Путь к файлу
            encoding: Кодировка
            
        Returns:
            Извлеченный текст
        """
        text_parts = []
        
        with open(file_path, 'r', encoding=encoding, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Добавление заголовков
            if reader.fieldnames:
                headers = "Заголовки: " + ", ".join(reader.fieldnames)
                text_parts.append(headers)
            
            # Обработка строк
            row_count = 0
            for row_num, row in enumerate(reader, 1):
                if row_count >= 1000:
                    text_parts.append(f"... (файл содержит больше строк, показаны первые {row_count})")
                    break
                
                non_empty_values = {k: v for k, v in row.items() if v and v.strip()}
                
                if non_empty_values:
                    row_text = f"Строка {row_num}: " + "; ".join([f"{k}: {v}" for k, v in non_empty_values.items()])
                    text_parts.append(row_text)
                    row_count += 1
        
        full_text = '\n'.join(text_parts)
        
        self.logger.info(f"Extracted {len(full_text)} characters from CSV with {encoding}: {file_path}")
        
        return full_text
