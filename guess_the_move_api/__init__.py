from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from stockfish import Stockfish
from guess_the_move_api.config import Config

stockfish = Stockfish('/home/vladinstein/stockfish_15.1_linux_x64/stockfish-ubuntu-20.04-x86-64')

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

from guess_the_move_api import routes
