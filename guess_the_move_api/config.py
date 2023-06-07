import json

with open('/etc/guess_the_move_config.json') as config_file:
    config = json.load(config_file)

class Config:
    SQLALCHEMY_DATABASE_URI = config.get('SQLALCHEMY_DATABASE_URI')
    SECRET_KEY = config.get('SECRET_KEY')
    SESSION_PERMANENT = True
    SESSION_TYPE = 'filesystem'
