from guess_the_move_api import db

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pgn = db.Column(db.Text, nullable=False)
    color = db.Column(db.Boolean, nullable=False)
    fen = db.Column(db.String(100), nullable=False)
    blunder = db.Column(db.Integer, default=0)
    mistake = db.Column(db.Integer, default=0)
    inaccuracy = db.Column(db.Integer, default=0)
    difference = db.Column(db.Float, default=0)

    def __repr__(self):
        return f"User '{self.id}'"
    