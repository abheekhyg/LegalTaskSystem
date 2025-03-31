import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-testing'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///task_manager.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TASKS_PER_PAGE = 10
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY') 