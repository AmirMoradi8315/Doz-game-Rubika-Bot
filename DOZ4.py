# AUTHOR : OT
# حق خرید و فروش و نسخه برداری از سورس محفوظ است.

SESSION = "Name" #نام سشن ربات

admins = ["u0DBv4C0d32c78d5db399aab2842fbab"]
# گوید آدمینای ربات برای ارسال دستور

#=============================
#دست به چیزی نزنید !
from pyrubi import Client
from pyrubi.types import Message
import time
import random
import json
import os
from datetime import datetime, timedelta

bot = Client(session=SESSION)

games = {}
banned_users = set()
stats_file = "doz_game_stats.json"

COLOR_EMOJIS = {
    1: '🔴', 2: '🟠', 3: '🟡', 4: '🟢', 5: '🔵', 6: '🟣', 7: '⚫️', 8: '🟤'
}

def load_stats():
    if os.path.exists(stats_file):
        with open(stats_file, 'r') as f:
            return json.load(f)
    return {"daily": {}, "total": {}, "games_started": 0, "games_cancelled": 0, "last_reset": time.time()}

def save_stats(stats):
    with open(stats_file, 'w') as f:
        json.dump(stats, f)

stats = load_stats()

def reset_daily_stats():
    current_time = time.time()
    if current_time - stats["last_reset"] >= 86400:  # 12 hours
        stats["daily"] = {}
        stats["games_cancelled"] = 0
        stats["games_started"] = 0
        stats["last_reset"] = current_time
        save_stats(stats)

def update_stats(winner):
    reset_daily_stats()
    stats["daily"][winner] = stats["daily"].get(winner, 0) + 1
    stats["total"][winner] = stats["total"].get(winner, 0) + 1
    save_stats(stats)

def create_board():
    return [[' ' for _ in range(7)] for _ in range(6)]

def board_to_text(board, player_colors):
    symbols = {' ': '⚪', 'X': player_colors['X'], 'O': player_colors['O']}
    rows = [''.join(symbols[cell] for cell in row) for row in board]
    rows.append('1⃣2⃣3⃣4⃣5⃣6⃣7⃣')
    return '\n'.join(rows)

def check_win(board, player):
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
    for row in range(6):
        for col in range(7):
            if board[row][col] == player:
                for dr, dc in directions:
                    if all(0 <= row + i*dr < 6 and 0 <= col + i*dc < 7 and 
                           board[row + i*dr][col + i*dc] == player for i in range(4)):
                        return True
    return False

def is_full(board):
    return all(cell != ' ' for row in board for cell in row)

def make_move(board, col, player):
    for row in range(5, -1, -1):
        if board[row][col] == ' ':
            board[row][col] = player
            return True
    return False

def send_board_text(message: Message, board, game):
    current_player = game['player_colors'][game['current_player']]
    player_name = game['player_names'].get(game['current_player'], 'Unknown Player')
    text = f"نوبت {player_name} {current_player}\n{board_to_text(board, game['player_colors'])}"
    
    if 'last_message' in game:
        bot.delete_messages(message.object_guid, [game['last_message']])
    
    new_message = message.reply(text)
    game['last_message'] = new_message["message_update"]["message_id"]

def calculate_score(board, player):
    score = 0
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
    for row in range(6):
        for col in range(7):
            if board[row][col] == player:
                for dr, dc in directions:
                    count = sum(1 for i in range(4) 
                                if 0 <= row + i*dr < 6 and 0 <= col + i*dc < 7 
                                and board[row + i*dr][col + i*dc] == player)
                    if count == 3:
                        score += 1
                    elif count >= 4:
                        score += 2
    return score

def get_game_difficulty_message(filled_cells):
    fill_percentage = (filled_cells / 42) * 100
    if fill_percentage < 25:
        return "بازی راحتی بود 😂"
    elif fill_percentage < 50:
        return "بازی مهیجی بود 😍"
    elif fill_percentage < 75:
        return "بازی سختی بود 🧐"
    else:
        return "بازی نفس‌گیری بود 😟"

def report_player(game, reporter, reported):
    report_time = time.time()
    game['report'] = {
        'reporter': reporter,
        'reported': reported,
        'time': report_time
    }
    reporter_name = game['player_names'][reporter]
    reported_name = game['player_names'][reported]
    message = f"""
    بازیکن {reported_name}
    گزارش شما مبنی بر این میباشد که در بازی اتلاف وقت ایجاد کرده اید!
    به مدت ۳ دقیقه وقت دارین بازی را ادامه دهید در غیر این صورت شما بازنده محسوب میشوید و امتیازات شما به بازیکن {reporter_name} تعلق میگیرد‌.
    """
    return message

def check_report_timeout(game):
    if 'report' in game:
        current_time = time.time()
        if current_time - game['report']['time'] > 180:  # 3 minutes = 180 seconds
            return True
    return False

def get_winning_moves(board, player):
    winning_moves = []
    for col in range(7):
        if make_move(board, col, player):
            if check_win(board, player):
                winning_moves.append(col)
            board[next(row for row in range(6) if board[row][col] != ' ')][col] = ' '
    return winning_moves

def get_best_moves(board, player):
    opponent = 'O' if player == 'X' else 'X'
    
    # Check for winning moves
    winning_moves = get_winning_moves(board, player)
    if winning_moves:
        return winning_moves

    # Block opponent's winning moves
    blocking_moves = get_winning_moves(board, opponent)
    if blocking_moves:
        return blocking_moves

    # Find moves that create opportunities
    good_moves = []
    for col in range(7):
        if make_move(board, col, player):
            score = calculate_score(board, player)
            good_moves.append((col, score))
            board[next(row for row in range(6) if board[row][col] != ' ')][col] = ' '
    
    if good_moves:
        max_score = max(score for _, score in good_moves)
        return [col for col, score in good_moves if score == max_score]

    # If no good moves, return all valid moves
    return [col for col in range(7) if board[0][col] == ' ']

def get_color_selection_message():
    return """
بازی شروع شد.
کاربر‌ گرامی لطفا رنگ‌ مهره ی خود را به سلیقه ی خود انتخاب کنید.

1 - 🔴 قرمز 
2 - 🟠 نارنجی
3 - 🟡 زرد
4 - 🟢 سبز
5 - 🔵 آبی
6 - 🟣 بنفش 
7 - ⚫️ مشکی
8 - 🟤 قهوه‌ای
"""

def get_game_stats():
    reset_daily_stats()
    daily_stats = sorted(stats["daily"].items(), key=lambda x: x[1], reverse=True)[:5]
    total_stats = sorted(stats["total"].items(), key=lambda x: x[1], reverse=True)[:20]
    
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    
    daily_text = "• آمار بازیکنان برتر DOZ GAME\n\n"
    daily_text += f"• تاریخ : {date_str}\n• ساعت : {time_str}\n\n"
    
    medals = ["🥇", "🥈", "🥉", "🤓", "🥺"]
    for i, (player, wins) in enumerate(daily_stats):
        daily_text += f"- نفر {i+1} {medals[i]}\n[{wins} برد | {player}]\n"
    
    daily_text += f"\n♡ بازی های انجام شده : {stats['games_started']}\n"
    daily_text += f"♡ بازی های لغو شده : {stats['games_cancelled']}\n"
    daily_text += f"♡ افراد بن شده : {len(banned_users)}"
    
    total_text = "آمار کل نفرات برتر DOZ GAME\n\n"
    total_text += f"• تاریخ : {date_str}\n• ساعت : {time_str}\n\n"
    
    for i, (player, wins) in enumerate(total_stats, 1):
        total_text += f"نفر {i} {player} با {wins} برد\n"
    
    return daily_text, total_text

def bot_move(board, difficulty):
    if difficulty == 1:  # Easy
        return random_move(board)
    elif difficulty == 2:  # Medium
        return medium_move(board)
    elif difficulty == 3:  # Hard
        return hard_move(board)
    elif difficulty == 4:  # Very Hard
        return very_hard_move(board)

def random_move(board):
    valid_moves = [col for col in range(7) if board[0][col] == ' ']
    return random.choice(valid_moves)

def medium_move(board):
    # Check for immediate winning move
    winning_move = get_winning_move(board, 'O')
    if winning_move is not None:
        return winning_move
    
    # Block opponent's winning move
    blocking_move = get_winning_move(board, 'X')
    if blocking_move is not None:
        return blocking_move
    
    # If no immediate threat or winning move, make a random move
    return random_move(board)

def hard_move(board):
    best_score = float('-inf')
    best_move = None
    for col in range(7):
        if board[0][col] == ' ':
            temp_board = [row[:] for row in board]
            make_move(temp_board, col, 'O')
            score = minimax(temp_board, 3, False)
            if score > best_score:
                best_score = score
                best_move = col
    return best_move if best_move is not None else random_move(board)

def very_hard_move(board):
    # For simplicity, we'll use the same algorithm as hard, but with greater depth
    best_score = float('-inf')
    best_move = None
    for col in range(7):
        if board[0][col] == ' ':
            temp_board = [row[:] for row in board]
            make_move(temp_board, col, 'O')
            score = minimax(temp_board, 5, False)
            if score > best_score:
                best_score = score
                best_move = col
    return best_move if best_move is not None else random_move(board)

def minimax(board, depth, is_maximizing):
    if depth == 0 or is_terminal(board):
        return evaluate(board)
    
    if is_maximizing:
        best_score = float('-inf')
        for col in range(7):
            if board[0][col] == ' ':
                temp_board = [row[:] for row in board]
                make_move(temp_board, col, 'O')
                score = minimax(temp_board, depth - 1, False)
                best_score = max(score, best_score)
        return best_score
    else:
        best_score = float('inf')
        for col in range(7):
            if board[0][col] == ' ':
                temp_board = [row[:] for row in board]
                make_move(temp_board, col, 'X')
                score = minimax(temp_board, depth - 1, True)
                best_score = min(score, best_score)
        return best_score

def is_terminal(board):
    return check_win(board, 'X') or check_win(board, 'O') or is_full(board)

def evaluate(board):
    if check_win(board, 'O'):
        return 1000
    elif check_win(board, 'X'):
        return -1000
    else:
        return 0

def get_winning_move(board, player):
    for col in range(7):
        if board[0][col] == ' ':
            temp_board = [row[:] for row in board]
            make_move(temp_board, col, player)
            if check_win(temp_board, player):
                return col
    return None

@bot.on_message(filters=["Group"])
def handle_message(message: Message):
    chat_id = message.object_guid
    
    if message.text == "/start":
        message.reply("به بازی چهار در خط خوش آمدید! برای شروع بازی، دستور شروع را ارسال کنید.")
        return

    if message.text == "شروع":
        if chat_id in games:
            print("یک بازی در حال انجام است. لطفاً صبر کنید تا بازی فعلی تمام شود.")
        elif message.author_guid in banned_users:
            message.reply("شما از بازی محروم شده‌اید و نمی‌توانید بازی را شروع کنید.")
        else:
            games[chat_id] = {
                'board': create_board(),
                'current_player': 'X',
                'players': {'X': message.author_guid, 'O': None},
                'player_names': {'X': message.author_title, 'O': None},
                'player_colors': {'X': None, 'O': None},
                'scores': {'X': 0, 'O': 0},
                'help_count': {'X': 2, 'O': 2},
                'color_selection_stage': 'X',
                'waiting_for_second_player': False,
                'start_time': time.time(),
                'bot_game': False,
                'bot_difficulty': None
            }
            stats['games_started'] += 1
            save_stats(stats)
            message.reply(get_color_selection_message())
        return

    if message.text == "ورود":
        if chat_id not in games:
            message.reply("هیچ بازی در حال انتظاری وجود ندارد. برای شروع یک بازی جدید، دستور شروع را ارسال کنید.")
        elif games[chat_id]['bot_game']:
            message.reply("این بازی با ربات در حال انجام است و نمی‌توانید به آن ملحق شوید.")
        elif games[chat_id]['players']['O'] is not None:
            print("این بازی قبلاً پر شده است. لطفاً صبر کنید تا بازی فعلی تمام شود.")
        elif games[chat_id]['players']['X'] == message.author_guid:
            message.reply("شما نمی‌توانید به عنوان هر دو بازیکن بازی کنید!")
        elif not games[chat_id]['waiting_for_second_player']:
            message.reply("لطفاً صبر کنید تا بازیکن اول رنگ مهره خود را انتخاب کند.")
        elif message.author_guid in banned_users:
            message.reply("شما از بازی محروم شده‌اید و نمی‌توانید به بازی ملحق شوید.")
        else:
            games[chat_id]['players']['O'] = message.author_guid
            games[chat_id]['player_names']['O'] = message.author_title
            games[chat_id]['color_selection_stage'] = 'O'
            message.reply(get_color_selection_message())
        return

    if message.text == "bot game":
        if chat_id not in games:
            message.reply("ابتدا بازی را با دستور 'شروع' آغاز کنید.")
        elif games[chat_id]['players']['X'] != message.author_guid:
            message.reply("فقط بازیکن اول می‌تواند درخواست بازی با ربات کند.")
        elif games[chat_id]['players']['O'] is not None:
            message.reply("بازی با دو بازیکن در حال انجام است. نمی‌توانید به بازی با ربات تغییر دهید.")
        else:
            games[chat_id]['bot_game'] = True
            message.reply("""
لطفاً سطح بازی را انتخاب کنید:

1 - آسان 
2 - متوسط
3 - سخت
4 - خیلی سخت
            """)
        return

    if chat_id in games and games[chat_id]['bot_game'] and games[chat_id]['bot_difficulty'] is None:
        if message.text in ['1', '2', '3', '4']:
            games[chat_id]['bot_difficulty'] = int(message.text)
            games[chat_id]['players']['O'] = 'bot'
            games[chat_id]['player_names']['O'] = 'ربات'
            games[chat_id]['player_colors']['X'] = None
            message.reply("""سطح بازی ربات تنظیم شد. لطفاً رنگ مهره خود را انتخاب کنید:

1 - 🔴 قرمز 
2 - 🟠 نارنجی
3 - 🟡 زرد
4 - 🟢 سبز
5 - 🔵 آبی
6 - 🟣 بنفش 
7 - ⚫️ مشکی
8 - 🟤 قهوه‌ای""")
            games[chat_id]['color_selection_stage'] = 'X'
        else:
            print("لطفاً یک عدد بین 1 تا 4 را برای انتخاب سطح بازی وارد کنید.")
        return

    if message.text == "اتمام" and message.author_guid in admins:
        if chat_id in games:
            del games[chat_id]
            stats['games_cancelled'] += 1
            save_stats(stats)
            message.reply("بازی به اتمام رسید.")
        else:
            message.reply("هیچ بازی در حال انجام نیست.")
        return 

    if message.text == "آمار بازی" and message.author_guid in admins:
        daily_stats, _ = get_game_stats()
        message.reply(daily_stats)
        return

    if message.text == "آمار کل بازی" and message.author_guid in admins:
        _, total_stats = get_game_stats()
        message.reply(total_stats)
        return

    if message.text.startswith("ban game") and message.author_guid in admins:
        if message.reply_message_id:
            banned_user = bot.get_messages(chat_id, message.reply_message_id)["messages"][0]["author_object_guid"]
            banned_users.add(banned_user)
            message.reply("کاربر مورد نظر از بازی محروم شد.")
        else:
            message.reply("لطفاً این دستور را روی پیام کاربر مورد نظر ریپلای کنید.")
        return

    if message.text.startswith("unban game") and message.author_guid in admins:
        if message.reply_message_id:
            unbanned_user = bot.get_messages(chat_id, message.reply_message_id)["messages"][0]["author_object_guid"]
            if unbanned_user in banned_users:
                banned_users.remove(unbanned_user)
                message.reply("محرومیت کاربر مورد نظر برداشته شد.")
            else:
                message.reply("این کاربر در لیست محرومین نبود.")
        else:
            message.reply("لطفاً این دستور را روی پیام کاربر مورد نظر ریپلای کنید.")
        return

    if chat_id not in games:
        return

    game = games[chat_id]

    if 'color_selection_stage' in game:
        if message.author_guid != game['players'][game['color_selection_stage']]:
            return

        if message.text.isdigit() and 1 <= int(message.text) <= 8:
            color_choice = int(message.text)
            if COLOR_EMOJIS[color_choice] in game['player_colors'].values():
                message.reply("این رنگ قبلاً انتخاب شده است. لطفاً رنگ دیگری را انتخاب کنید.")
                return

            game['player_colors'][game['color_selection_stage']] = COLOR_EMOJIS[color_choice]

            if game['color_selection_stage'] == 'X':
                if game['bot_game']:
                    # Bot automatically selects a different color
                    available_colors = set(COLOR_EMOJIS.values()) - {game['player_colors']['X']}
                    game['player_colors']['O'] = random.choice(list(available_colors))
                    del game['color_selection_stage']
                    del game['waiting_for_second_player']
                    message.reply("بازی با ربات شروع شد! نوبت شماست. برای انجام حرکت، شماره ستون (1-7) را ارسال کنید.")
                    send_board_text(message, game['board'], game)
                else:
                    game['color_selection_stage'] = 'O'
                    game['waiting_for_second_player'] = True
                    message.reply("رنگ مهره شما ثبت شد. منتظر ورود بازیکن دوم هستیم. بازیکن دوم می‌تواند با ارسال کلمه 'ورود' به بازی ملحق شود.")
            else:
                del game['color_selection_stage']
                del game['waiting_for_second_player']
                message.reply("بازی شروع شد! نوبت بازیکن اول است. برای انجام حرکت، شماره ستون (1-7) را ارسال کنید.")
                send_board_text(message, game['board'], game)
        else:
            print("لطفاً یک عدد بین 1 تا 8 را برای انتخاب رنگ وارد کنید.")
        return

    if message.author_guid != game['players'].get('X') and message.author_guid != game['players'].get('O'):
        return

    if message.text == "انصراف":
        winner = 'O' if game['current_player'] == 'X' else 'X'
        loser = game['current_player']
        game['scores'][winner] += game['scores'][loser]
        game['scores'][loser] = 0
        winner_name = game['player_names'][winner]
        loser_name = game['player_names'][loser]
        end_message = f"بازی به پایان رسید. {winner_name} برنده شد و امتیازات {loser_name} به ایشان منتقل شد."
        end_message += f"\n\n{board_to_text(game['board'], game['player_colors'])}"
        end_message += f"\n\nامتیازات:\n{game['player_colors']['X']} {game['player_names']['X']}: {game['scores']['X']}\n{game['player_colors']['O']} {game['player_names']['O']}: {game['scores']['O']}"
        game_duration = int((time.time() - game['start_time']) / 60)  # Convert to minutes
        end_message += f"\n\nمدت زمان بازی: {game_duration} دقیقه"
        message.reply(end_message)
        update_stats(winner_name)
        del games[chat_id]
        return

    if message.text == "گزارش بازیکن":
        if game['bot_game']:
            message.reply("در بازی با ربات نمی‌توانید گزارش بازیکن ثبت کنید.")
            return
        current_player = 'X' if game['players']['X'] == message.author_guid else 'O'
        other_player = 'O' if current_player == 'X' else 'X'
        
        if current_player != game['current_player']:
            report_message = report_player(game, current_player, other_player)
            message.reply(report_message)
        else:
            message.reply("فقط بازیکنی که نوبتش نیست می‌تواند گزارش بازیکن را ثبت کند.")
        return

    if message.text == "کمک":
        if message.author_guid != game['players'].get(game['current_player']):
            message.reply("الان نوبت شما نیست!")
            return
        
        if game['help_count'][game['current_player']] > 0:
            best_moves = get_best_moves(game['board'], game['current_player'])
            if best_moves:
                help_message = f"ستون‌های پیشنهادی برای حرکت بعدی: {', '.join(str(move + 1) for move in best_moves)}"
            else:
                help_message = "متاسفانه شما هیچگونه احتمال برد در بازی را ندارید!"
            
            game['help_count'][game['current_player']] -= 1
            remaining_helps = game['help_count'][game['current_player']]
            help_message += f"\n\nتعداد کمک‌های باقی‌مانده: {remaining_helps}"
            
            message.reply(help_message)
        else:
            message.reply("شما دیگر کمکی باقی ندارید!")
        return

    if check_report_timeout(game):
        winner = game['report']['reporter']
        loser = game['report']['reported']
        game['scores'][winner] += game['scores'][loser]
        game['scores'][loser] = 0
        winner_name = game['player_names'][winner]
        loser_name = game['player_names'][loser]
        end_message = f"بازی به پایان رسید. {winner_name} برنده شد و امتیازات {loser_name} به ایشان منتقل شد."
        end_message += f"\n\n{board_to_text(game['board'], game['player_colors'])}"
        end_message += f"\n\nامتیازات:\n{game['player_colors']['X']} {game['player_names']['X']}: {game['scores']['X']}\n{game['player_colors']['O']} {game['player_names']['O']}: {game['scores']['O']}"
        game_duration = int((time.time() - game['start_time']) / 60)  # Convert to minutes
        end_message += f"\n\nمدت زمان بازی: {game_duration} دقیقه"
        message.reply(end_message)
        update_stats(winner_name)
        del games[chat_id]
        return

    if message.text.isdigit() and 1 <= int(message.text) <= 7:
        if message.author_guid != game['players'].get(game['current_player']):
            message.reply("الان نوبت شما نیست!")
            return

        col = int(message.text) - 1
        if not make_move(game['board'], col, game['current_player']):
            message.reply("این ستون پر است. لطفاً ستون دیگری را انتخاب کنید.")
            return

        if 'report' in game:
            del game['report']  # Remove the report if the player makes a move

        current_score = calculate_score(game['board'], game['current_player'])
        game['scores'][game['current_player']] += current_score

        if check_win(game['board'], game['current_player']):
            winner = game['current_player']
            loser = 'O' if winner == 'X' else 'X'
            game['scores'][winner] += 10  # Bonus for winning
            if game['scores'][winner] <= game['scores'][loser]:
                game['scores'][winner] = game['scores'][loser] + 1  # Ensure winner has higher score
            
            winner_symbol = game['player_colors'][winner]
            winner_name = game['player_names'][winner]
            filled_cells = sum(cell != ' ' for row in game['board'] for cell in row)
            difficulty_message = get_game_difficulty_message(filled_cells)
            text_win = f"بازیکن {winner_symbol} ({winner_name}) برنده شد!\n\n{board_to_text(game['board'], game['player_colors'])}\n\nامتیازات:\n{game['player_colors']['X']} {game['player_names']['X']}: {game['scores']['X']}\n{game['player_colors']['O']} {game['player_names']['O']}: {game['scores']['O']}\n\n{difficulty_message}"
            game_duration = int((time.time() - game['start_time']) / 60)  # Convert to minutes
            text_win += f"\n\nمدت زمان بازی: {game_duration} دقیقه"
            
            if 'last_message' in game:
                bot.delete_messages(message.object_guid, [game['last_message']])
            
            message.reply(text_win)
            update_stats(winner_name)
            del games[chat_id]
        elif is_full(game['board']):
            filled_cells = sum(cell != ' ' for row in game['board'] for cell in row)
            difficulty_message = get_game_difficulty_message(filled_cells)
            text_draw = f"بازی مساوی شد!\n\n{board_to_text(game['board'], game['player_colors'])}\n\nامتیازات:\n{game['player_colors']['X']} {game['player_names']['X']}: {game['scores']['X']}\n{game['player_colors']['O']} {game['player_names']['O']}: {game['scores']['O']}\n\n{difficulty_message}"
            game_duration = int((time.time() - game['start_time']) / 60)  # Convert to minutes
            text_draw += f"\n\nمدت زمان بازی: {game_duration} دقیقه"
            
            if 'last_message' in game:
                bot.delete_messages(message.object_guid, [game['last_message']])
            
            message.reply(text_draw)
            del games[chat_id]
        else:
            game['current_player'] = 'O' if game['current_player'] == 'X' else 'X'
            send_board_text(message, game['board'], game)

            if game['bot_game'] and game['current_player'] == 'O':
                time.sleep(random.uniform(3, 4))  # Bot waits for 3-4 seconds before making a move
                bot_col = bot_move(game['board'], game['bot_difficulty'])
                make_move(game['board'], bot_col, 'O')
                
                if check_win(game['board'], 'O'):
                    winner = 'O'
                    loser = 'X'
                    game['scores'][winner] += 10  # Bonus for winning
                    if game['scores'][winner] <= game['scores'][loser]:
                        game['scores'][winner] = game['scores'][loser] + 1  # Ensure winner has higher score
                    
                    winner_symbol = game['player_colors'][winner]
                    winner_name = game['player_names'][winner]
                    filled_cells = sum(cell != ' ' for row in game['board'] for cell in row)
                    difficulty_message = get_game_difficulty_message(filled_cells)
                    text_win = f"بازیکن {winner_symbol} ({winner_name}) برنده شد!\n\n{board_to_text(game['board'], game['player_colors'])}\n\nامتیازات:\n{game['player_colors']['X']} {game['player_names']['X']}: {game['scores']['X']}\n{game['player_colors']['O']} {game['player_names']['O']}: {game['scores']['O']}\n\n{difficulty_message}"
                    game_duration = int((time.time() - game['start_time']) / 60)  # Convert to minutes
                    text_win += f"\n\nمدت زمان بازی: {game_duration} دقیقه"
                    
                    if 'last_message' in game:
                        bot.delete_messages(message.object_guid, [game['last_message']])
                    
                    message.reply(text_win)
                    update_stats(winner_name)
                    del games[chat_id]
                elif is_full(game['board']):
                    filled_cells = sum(cell != ' ' for row in game['board'] for cell in row)
                    difficulty_message = get_game_difficulty_message(filled_cells)
                    text_draw = f"بازی مساوی شد!\n\n{board_to_text(game['board'], game['player_colors'])}\n\nامتیازات:\n{game['player_colors']['X']} {game['player_names']['X']}: {game['scores']['X']}\n{game['player_colors']['O']} {game['player_names']['O']}: {game['scores']['O']}\n\n{difficulty_message}"
                    game_duration = int((time.time() - game['start_time']) / 60)  # Convert to minutes
                    text_draw += f"\n\nمدت زمان بازی: {game_duration} دقیقه"
                    
                    if 'last_message' in game:
                        bot.delete_messages(message.object_guid, [game['last_message']])
                    
                    message.reply(text_draw)
                    del games[chat_id]
                else:
                    game['current_player'] = 'X'
                    send_board_text(message, game['board'], game)

bot.run()
