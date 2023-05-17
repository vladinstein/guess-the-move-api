from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from stockfish import Stockfish
from guess_the_move_api.config import Config

stockfish = Stockfish('C:/Users/vladi/Downloads/stockfish_15.1_win_x64_popcnt/stockfish-windows-2022-x86-64-modern')

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

from guess_the_move_api import routes