import json
from typing import List, Dict, Any
from .base_processor import BaseProcessor
import logging

logger = logging.getLogger(__name__)

class JsonProcessor(BaseProcessor):
    """
    Обработчик для JSON файлов
    """
    
    def get_supported_extensions(self) -> List[str]:
        return ['.json']
    
    def extract_text(self, file_path: str) -> str:
        """
        Извлечение текста из JSON файла
        
        Args:
            file_path: Путь к JSON файлу
            
        Returns:
            Извлеченный текст в структурированном формате
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as jsonfile:
                data = json.load(jsonfile)
            
            # Преобразование JSON в читаемый текст
            text_parts = []
            self._extract_from_json(data, text_parts, prefix="")
            
            if not text_parts:
                raise ValueError("JSON файл пуст или не содержит текстовых данных")
            
            full_text = '\n'.join(text_parts)
            
            self.logger.info(f"Extracted {len(full_text)} characters from JSON: {file_path}")
            
            return full_text
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON format in {file_path}: {str(e)}")
            raise ValueError(f"Некорректный формат JSON: {str(e)}")
            
        except UnicodeDecodeError:
            # Попытка с другой кодировкой
            try:
                return self._extract_with_encoding(file_path, 'cp1251')
            except:
                return self._extract_with_encoding(file_path, 'latin1')
                
        except Exception as e:
            self.logger.error(f"Error extracting text from JSON {file_path}: {str(e)}")
            raise e
    
    def _extract_from_json(self, data: Any, text_parts: List[str], prefix: str = "", max_depth: int = 10) -> None:
        """
        Рекурсивное извлечение текста из JSON структуры
        
        Args:
            data: JSON данные
            text_parts: Список для накопления текстовых частей
            prefix: Префикс для текущего уровня
            max_depth: Максимальная глубина рекурсии
        """
        if max_depth <= 0:
            text_parts.append(f"{prefix}: [слишком глубокая вложенность]")
            return
        
        if isinstance(data, dict):
            for key, value in data.items():
                new_prefix = f"{prefix}.{key}" if prefix else key
                
                if isinstance(value, (dict, list)):
                    self._extract_from_json(value, text_parts, new_prefix, max_depth - 1)
                else:
                    # Преобразование значения в строку
                    str_value = self._value_to_string(value)
                    if str_value:  # Только непустые значения
                        text_parts.append(f"{new_prefix}: {str_value}")
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_prefix = f"{prefix}[{i}]" if prefix else f"элемент_{i}"
                
                if isinstance(item, (dict, list)):
                    self._extract_from_json(item, text_parts, new_prefix, max_depth - 1)
                else:
                    str_value = self._value_to_string(item)
                    if str_value:
                        text_parts.append(f"{new_prefix}: {str_value}")
        
        else:
            # Простое значение
            str_value = self._value_to_string(data)
            if str_value:
                text_parts.append(f"{prefix}: {str_value}" if prefix else str_value)
    
    def _value_to_string(self, value: Any) -> str:
        """
        Преобразование значения в строку
        
        Args:
            value: Значение для преобразования
            
        Returns:
            Строковое представление
        """
        if value is None:
            return ""
        elif isinstance(value, bool):
            return "да" if value else "нет"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            return value.strip()
        else:
            return str(value)
    
    def _extract_with_encoding(self, file_path: str, encoding: str) -> str:
        """
        Извлечение текста с указанной кодировкой
        
        Args:
            file_path: Путь к файлу
            encoding: Кодировка
            
        Returns:
            Извлеченный текст
        """
        with open(file_path, 'r', encoding=encoding) as jsonfile:
            data = json.load(jsonfile)
        
        text_parts = []
        self._extract_from_json(data, text_parts, prefix="")
        
        full_text = '\n'.join(text_parts)
        
        self.logger.info(f"Extracted {len(full_text)} characters from JSON with {encoding}: {file_path}")
        
        return full_text
