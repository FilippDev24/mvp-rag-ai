import { Request, Response, NextFunction } from 'express';
import Joi from 'joi';
import { AppError } from '../types';

/**
 * Middleware для валидации данных согласно техническим требованиям
 */
export const validate = (schema: Joi.Schema, source: 'body' | 'query' | 'params' = 'body') => {
  return (req: Request, res: Response, next: NextFunction) => {
    try {
      let dataToValidate;
      
      switch (source) {
        case 'body':
          dataToValidate = req.body;
          break;
        case 'query':
          dataToValidate = req.query;
          break;
        case 'params':
          dataToValidate = req.params;
          break;
        default:
          dataToValidate = req.body;
      }

      const { error, value } = schema.validate(dataToValidate, {
        abortEarly: false,
        stripUnknown: true,
        convert: true
      });

      if (error) {
        const errorMessage = error.details.map(detail => detail.message).join(', ');
        throw new AppError(errorMessage, 400);
      }

      // Обновляем соответствующую часть запроса валидированными данными
      switch (source) {
        case 'body':
          req.body = value;
          break;
        case 'query':
          req.query = value;
          break;
        case 'params':
          req.params = value;
          break;
      }

      next();
    } catch (error) {
      next(error);
    }
  };
};
