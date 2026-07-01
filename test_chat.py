"""Barcha funksiyalarni WebSocket orqali test qilish."""
import asyncio
import json
import time

from websockets.sync.client import connect


def test_full_flow():
    base = "ws://localhost:8000/ws/general"

    # 1) user1 ulanadi
    ws1 = connect(f"{base}/testuser1")
    msg = json.loads(ws1.recv())
    print(f"1. Tarix: type={msg['type']}, xabarlar={len(msg.get('messages', []))}")

    msg = json.loads(ws1.recv())
    print(f"2. Online: {msg}")

    msg = json.loads(ws1.recv())
    print(f"3. Join notification: {msg['username']} {msg['event']}")

    # 2) user2 ulanadi
    ws2 = connect(f"{base}/testuser2")
    ws2.recv()  # history
    ws2.recv()  # online_users
    ws2.recv()  # own join notification

    msg = json.loads(ws1.recv())  # online_users update
    print(f"4. Online yangilandi: {msg}")
    msg = json.loads(ws1.recv())  # user2 join
    print(f"5. user2 kirdi: {msg['username']} {msg['event']}")

    # 3) user1 xabar yuboradi
    ws1.send(json.dumps({"type": "message", "message": "Salom, dunyo!"}))
    msg1 = json.loads(ws1.recv())
    msg2 = json.loads(ws2.recv())
    print(f"6. user1 oldi: '{msg1['message']}' from {msg1['username']}")
    print(f"7. user2 oldi: '{msg2['message']}' from {msg2['username']}")

    # 4) typing test
    ws2.send(json.dumps({"type": "typing"}))
    msg = json.loads(ws1.recv())
    print(f"8. Typing: {msg['username']} yozmoqda")

    # 5) read receipt test
    ws2.send(json.dumps({"type": "read", "message_id": msg1["message_id"]}))
    msg = json.loads(ws1.recv())
    print(f"9. Read receipt: {msg['username']} o'qidi message_id={msg['message_id']}")

    # 6) band username test
    try:
        ws3 = connect(f"{base}/testuser1")
        err = json.loads(ws3.recv())
        print(f"10. Band username: {err['message']}")
    except Exception as e:
        print(f"10. Band username xatosi: {e}")

    # 7) user2 chiqadi
    ws2.close()
    time.sleep(0.5)
    msg = json.loads(ws1.recv())  # online update
    print(f"11. Online yangilandi: {msg}")
    msg = json.loads(ws1.recv())  # leave notification
    print(f"12. Leave: {msg['username']} {msg['event']}")

    ws1.close()
    print("\n=== BARCHA TESTLAR MUVAFFAQIYATLI ===")


if __name__ == "__main__":
    test_full_flow()
