import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    SECRET_KEY = 'ECE1779'
    SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://root:19971014Zbwl@database-1.cjap7jvaq7b8.us-east-1.rds.amazonaws.com/ece1779a2'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024
    UPLOAD_EXTENSIONS = ['.jpg', '.png', '.gif', '.jpeg', '.JPEG', '.PNG', '.JPG', '.GIF']
    MAIL_SERVER = 'smtp.googlemail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = 1
    MAIL_USERNAME = 'jianijiahappy@gmail.com'
    MAIL_PASSWORD = 'Jjn123456'
    ADMINS = ['jianijiahappy@gmail.com']
    INSTANCE_ID = 'i-027a3b0141ec3303f'
    ZONE = 'us-east-1f'
    BUCKET_NAME = 'ece1779-a2-s3-images'
