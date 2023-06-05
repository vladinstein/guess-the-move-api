from flask import request, jsonify
import io, chess.pgn, math, uuid
from guess_the_move_api.models import Game
from guess_the_move_api import app, db, stockfish

#test5
def calculate_win_chances(eval):
    win_chances = 2 / (1 + math.exp(-0.004 * eval)) - 1
    return win_chances


@app.route('/validate_pgn', methods=['POST'])
def validate_pgn():
    # Check if data is in JSON format
    if not request.is_json:
        return jsonify({"msg": "Missing JSON in request"}), 400
    request_data = request.get_json()
    # Get values from the request
    text_pgn = request_data['pgn']
    text_color = request_data['color']
    if text_color == 'white':
        bool_color = 0
    else:
        bool_color = 1
    # Turn pgn to StringIO object (required by the library)
    pgn = io.StringIO(text_pgn)
    # Parse the game from a pgn string and create a root node.
    game = chess.pgn.read_game(pgn)
    # Check for errors in the pgn and return the name of the first error
    if game.errors:
        error1 = game.errors[0]
        return jsonify({"msg": str(error1)}), 400
    fen = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
    # Add pgn, color and starting fen to the DB 
    game_uuid = str(uuid.uuid4())
    game_db = Game(pgn=text_pgn, color=bool_color, fen=fen, uuid=game_uuid)
    db.session.add(game_db)
    db.session.commit()
    # Create a dict, add ID of the game to it and return as JSON.
    id_dict = {}
    id_dict['id'] = game_db.uuid
    return jsonify(id_dict)

@app.route('/evaluate_move', methods=['POST'])
def evaluate_move():
    # Get the values from the request
    request_data = request.get_json()
    game_id = request_data['game_id']
    user_move = request_data['user_move']
    # Query the DB to get a game with this ID
    game_db = Game.query.filter_by(uuid=game_id).first()
    # If that game doesn't exist, send an error message 
    if game_db == None:
        return jsonify({"msg": 'Game Not Found'}), 400
    # If that game has already finished, send an error response
    if game_db.fen == 'Game Finished':
        return jsonify({"msg": 'Game Finished'}), 400
    # Turn pgn to StringIO object (required by the library)
    pgn = io.StringIO(game_db.pgn)
    # Parse the game from a pgn string and create a root node.
    game = chess.pgn.read_game(pgn)
    # Create a board object
    board = game.board()
    # Set the board to the current fen position
    board.set_fen(game_db.fen)
    # Get the number of half-moves from the beginning of the game
    x = board.ply()
    # Reset the board to the start
    board.reset()
    i = 0
    # Move 1 step up the node tree (pgn) and make one move on the board 
    # (first move is done no matter what)
    node = game.next()
    board.push(node.move)
    if x == 0 and game_db.color == 1:
            # If the color is black, make one more step up the node tree and make one more move on the board.
            # (If playing for black this is done no matter what)
            node = node.next()
            board.push(node.move)
    # Go to the exact place on the node tree (determined by fen) if it's not the first move. 
    # Make moves accordingly.
    for i in range (x-1):
        node = node.next()
        board.push(node.move)
        i += 1
    # Set eval_user to None to check later on if the user evaluation was different.    
    eval_user = None
    # Set position for the Stockfish and get evaluation of the pro.
    stockfish.set_fen_position(board.fen())
    eval_pro = stockfish.get_evaluation()
    # If player's move is different, evaluate it.
    if user_move != node.move.uci():
        # Undo the last move on the board (pro)
        board.pop()
        move = chess.Move.from_uci(user_move)
        # Check if the move is in legal moves.
        if move in board.legal_moves:
            # Make a move with the variation (user)
            # Can replace with push_uci or even push_san
            board.push(move)
        else:
            # Return an error if not
            return jsonify({"msg": 'Illegal move'}), 400
        # Move one node back and create a variation.
        node = node.parent
        node = node.add_variation(chess.Move.from_uci(user_move))
        # Create a pgn string with a variation.
        exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
        pgn_string = game.accept(exporter)
        # Update pgn in the database to include a new variation
        game_db.pgn = pgn_string
        db.session.commit()
        # Set the postion for the Stockfish with the user move and evaluate it.
        stockfish.set_fen_position(board.fen())
        eval_user = stockfish.get_evaluation()
        # Calculate winning chances after user's move.
        win_chances = calculate_win_chances(eval_user['value'])
        # Calculate the difference between the pro move and the user move
        difference = eval_pro['value'] - eval_user['value']
        # If the color is black, change - to + and the other way around.
        # So that when the difference is positive it means the pro's move is better and vice versa. 
        if game_db.color == 1:
            difference = - difference
    else:
        # If user's move is same as pro's move, set difference to 0 and calculate win
        # chanses after pro's move.
        difference = 0
        win_chances = calculate_win_chances(eval_pro['value'])
    # Update the centipawn difference value in the DB.
    if x == 0:
        game_db.difference = difference
    else:
        game_db.difference = (game_db.difference + difference) / 2
    # Move 1 node back on the pgn tree and undo 1 move on the board (in case there was a variation) 
    node = node.parent
    board.pop()
    # Set Stockfish to previous position, evaluate it and calculate previous move's winning chances
    stockfish.set_fen_position(board.fen())
    eval_prev = stockfish.get_evaluation()
    win_chances_prev = calculate_win_chances(eval_prev['value'])
    # Blunder count is the difference between winning chances for current and previous moves.
    blunder_count = win_chances_prev - win_chances
    # If the color is black, change - to + and the other way around to keep it same for both players.
    blunder = mistake = inaccuracy = False
    if game_db.color == 1:
        blunder_count = - blunder_count
    # Check if it's a blunder/mistake/inaccuracy, update the variable and increment the value in the DB if needed.
    if blunder_count >= 0.3:
        blunder = True
        game_db.blunder += 1
        db.session.commit()
    elif blunder_count >= 0.2:
        mistake = True
        game_db.mistake += 1
        db.session.commit()
    elif blunder_count >= 0.1:
        inaccuracy = True
        game_db.inaccuracy += 1
        db.session.commit()
    # Move 3 steps forward and make 3 half-moves on the board to get to the next move's position
    i = 0
    game_end = False
    for i in range (3):
        node = node.next()
        # If that was the last move of this side, set game_end variable to True and stop the loop
        if node == None:
            game_end = True
            break
        board.push(node.move)
        i += 1
    # Check if the game has ended
    if game_end:
        # If the game has ended, store "Game Finished" instead of the fen
        game_db.fen = 'Game Finished'
    else:
        # Otherwise get the fen required for the next move and add it to the DB.   
        game_db.fen = board.fen()
    db.session.commit()
    # Create evaluation dictionary, turn it to JSON and send it back.
    eval_dict = {}
    eval_dict['pgn'] = game_db.pgn
    eval_dict['eval_user'] = eval_user['value']
    eval_dict['eval_pro'] = eval_pro['value']
    eval_dict['game_end'] = game_end
    eval_dict['current_difference'] = difference
    eval_dict['avg_difference'] = game_db.difference
    eval_dict['win_chances'] = win_chances
    eval_dict['blunder_count'] = blunder_count
    eval_dict['blunder'] = blunder
    eval_dict['mistake'] = mistake
    eval_dict['inaccuracy'] = inaccuracy
    return jsonify(eval_dict)

@app.route('/report_card', methods=['POST'])
def report_card():
    # Remove all the new line charcters from the pgn string
    # pgn_string = pgn_string.replace("\n", "")
    # Get the values from the request
    request_data = request.get_json()
    game_id = request_data['game_id']
    # Query the DB to get a game with this ID
    game_db = Game.query.filter_by(uuid=game_id).first()
    # If that game doesn't exist, send an error message 
    if game_db == None:
        return jsonify({"msg": 'Game Not Found'}), 400
    if game_db.fen != 'Game Finished':
        return jsonify({"msg": 'Game Not Finished'}), 400
    report_dict = {}
    report_dict['pgn'] = game_db.pgn
    report_dict['inaccuracies'] = game_db.inaccuracy
    report_dict['mistakes'] = game_db.mistake
    report_dict['blunders'] = game_db.blunder
    report_dict['avg_difference'] = game_db.difference
    return jsonify(report_dict)