import os
from decouple import config

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-this-key')
    SQLALCHEMY_DATABASE_URI = config('DATABASE_URL', default=f'sqlite:///{os.path.join(BASE_DIR, "instance", "database.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'media', 'sabores')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Configurações de sessão
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hora