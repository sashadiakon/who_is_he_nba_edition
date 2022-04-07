import logging
import os
import numpy as np
import pandas as pd
from retry import retry
import editdistance
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Update, ReplyKeyboardMarkup, ForceReply
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler, \
    ConversationHandler

TOKEN = "5203048737:AAHTSnzjm68wVTEMMfVAFxU0OWYzRloGJg4"

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

PORT = int(os.environ.get('PORT', 8443))


ENTRY_TEXT = """Hi, this bot is created for nba fans to play NBA 'Who is he?' game.  
If you don't know this game, type or click /info, if you know - click /play


"""

INFO = """ This game-bot has two types of games:
1) Guessing players by his photo
When you started game(chosen difficulty and type of game),
 you will receive photo of player, you need to send player name or team.
 after you guessed or skipped it, you will receive the next one. 
 In such a way you pass 5 pictures and get your result 
"""
from random import randint

START, DIFFUCULTY, GAME = range(3)

data = pd.read_csv("data/players_2022.csv")
easy = pd.read_csv("data/easy.csv")
mid = pd.read_csv("data/mid.csv")
hard = pd.read_csv("data/hard.csv")

LVLS = ["Easy", "Medium", "Hard"]

N = 5


def random_pl(dt):
    l = dt.shape[0]
    n = randint(0, l)
    return dt.loc[n]["Player"]


def generate_player(level, n=5):
    if level.lower() == "easy":
        return random_pl(easy)
    elif level.lower() == "medium":
        return random_pl(mid)
    elif level.lower() == "hard":
        return random_pl(hard)


@retry(tries=100)
def send_player_img(update, context):
    pl = generate_player(level=context.user_data["lvl"])
    print(pl)
    context.user_data["answer"] = pl
    path = fr"data/img/{pl}.jpg"
    img = open(path, "rb")
    button = [[InlineKeyboardButton("Skip", callback_data = "skip")]]
    reply_markup = InlineKeyboardMarkup(button)
    chat_id = update.effective_message.chat_id
    context.bot.send_photo(chat_id, img, reply_markup = reply_markup)
    img.close()


def start(update: Update, context: CallbackContext):
    user = update.effective_user
    update.message.reply_text(ENTRY_TEXT)


def info(update: Update, context: CallbackContext):
    update.message.reply_text(INFO)


def play(update: Update, context: CallbackContext):
    context.user_data["type"] = update.message.text
    buttons = [[KeyboardButton("Easy")],
               [KeyboardButton("Medium")], [KeyboardButton("Hard")]]
    reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
    update.message.reply_text("Choose difficulty level",
                              reply_markup=reply_markup)
    return DIFFUCULTY


def choose_diff(update: Update, context: CallbackContext):
    lvl = update.message.text
    context.user_data["lvl"] = lvl
    context.user_data["nr"] = 0
    context.user_data["count"] = 0
    type = context.user_data["type"]
    send_player_img(update, context)
    return GAME


def game(update: Update, context: CallbackContext):
    user_answer = update.message.text
    real_answer = context.user_data["answer"]
    eq = user_answer.lower() == real_answer.lower()
    print(f"{context.user_data['count']}//{context.user_data['nr']}")
    if eq or (editdistance.eval(user_answer, real_answer) / len(user_answer) <= 0.25): # If real answer and user are equal or close
        context.user_data["nr"] += 1
        context.user_data["count"] += 1
        count = context.user_data["count"]
        nr = context.user_data["nr"]
        if count < N:
            text = "You are right, go next one" if eq else f"May be you meant {real_answer}"
            update.message.reply_text(text)
            send_player_img(update, context)
        else:
            update.message.reply_text("The game is over. "
                                      f"You got {nr}\\{N} on {context.user_data['lvl']}")
            return ConversationHandler.END
    else:
        update.message.reply_text("Not correct, try one more time or use /skip")


def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data
    if data == "skip":
        skip(update, context)



def skip(update: Update, context: CallbackContext):
    answer = context.user_data["answer"]
    chat_id = update.effective_message.chat_id
    context.bot.send_message(chat_id, f"It was {answer}, go to next player")
    context.user_data["count"] += 1
    if context.user_data["count"] < N:
        send_player_img(update, context)
    else:
        return endgame(update, context)


def endgame(update: Update, context: CallbackContext):
    endtext = "Game is over"
    context.bot.send_message(update.effective_message.chat_id, endtext +
                                 f" You got {context.user_data['nr']}\\{context.user_data['count']} on {context.user_data['lvl']}")
    return ConversationHandler.END


def main():
    APP_NAME = "https://thawing-chamber-87786.herokuapp.com/"
    updater = Updater(TOKEN)

    dp = updater.dispatcher
    play_handler = ConversationHandler(entry_points=[CommandHandler("play", play)],
                                       states={
                                           START: [
                                               MessageHandler(
                                                   Filters.text & ~Filters.command, play
                                               )
                                           ],
                                           DIFFUCULTY: [
                                               MessageHandler(
                                                   Filters.text & ~Filters.command, choose_diff
                                               )
                                           ],
                                           GAME: [
                                               MessageHandler(
                                                   Filters.text & ~Filters.command, game
                                               ),
                                               CommandHandler("skip", skip)
                                           ],
                                       },
                                       fallbacks = [CommandHandler("end", endgame)],
                                       conversation_timeout = 180
                                       )
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("rules", info))
    dp.add_handler(play_handler)
    dp.add_handler(CallbackQueryHandler(button))
    # dp.add_handler(MessageHandler(Filters.text, echo))
    # Start bot 
    updater.start_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=APP_NAME + TOKEN)
    updater.idle()

if __name__ == "__main__":
    main()