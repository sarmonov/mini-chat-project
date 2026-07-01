"""RabbitMQ load test — N ta xabarni to'g'ridan-to'g'ri queue'ga publish qiladi.

Ishlatish:
    python loadtest.py                      # 100000 ta xabar -> 'loadtest' queue
    python loadtest.py --count 50000        # boshqa son
    python loadtest.py --queue chat_messages:general   # boshqa queue
    python loadtest.py --persistent         # diskka yoziladigan (sekinroq, realroq)
    python loadtest.py --confirm            # publisher confirms (eng sekin, eng ishonchli)

Standart: alohida 'loadtest' queue'siga, consumer'siz — xabarlar to'planib turadi,
Management UI'da (localhost:15672) ko'rinadi.
"""
import argparse
import asyncio
import json
import time

import aio_pika

RABBITMQ_URL = "amqp://guest:guest@localhost:5672/"


async def run(count: int, queue: str, persistent: bool, confirm: bool, progress_every: int) -> None:
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel(publisher_confirms=confirm)

    # Durable queue e'lon qilamiz (server restartdan keyin ham qoladi)
    await channel.declare_queue(queue, durable=True)

    delivery_mode = (
        aio_pika.DeliveryMode.PERSISTENT if persistent else aio_pika.DeliveryMode.NOT_PERSISTENT
    )

    print(f"Boshlandi: {count:,} ta xabar -> '{queue}' "
          f"(persistent={persistent}, confirm={confirm})")

    start = time.perf_counter()
    last_mark = start

    for i in range(1, count + 1):
        body = json.dumps({
            "type": "message",
            "message_id": i,
            "username": f"loadtester{i % 50}",
            "message": f"Load test xabari #{i}",
            "room": "loadtest",
            "timestamp": time.time(),
        }).encode()

        await channel.default_exchange.publish(
            aio_pika.Message(body=body, delivery_mode=delivery_mode),
            routing_key=queue,
        )

        if i % progress_every == 0:
            now = time.perf_counter()
            rate = progress_every / (now - last_mark)
            print(f"  {i:>8,} / {count:,}  |  {rate:>10,.0f} msg/sek")
            last_mark = now

    elapsed = time.perf_counter() - start
    await connection.close()

    print("-" * 50)
    print(f"TUGADI: {count:,} ta xabar {elapsed:.2f} sekundda")
    print(f"O'rtacha tezlik: {count / elapsed:,.0f} msg/sek")


def main() -> None:
    parser = argparse.ArgumentParser(description="RabbitMQ load test")
    parser.add_argument("--count", type=int, default=100_000, help="Xabarlar soni")
    parser.add_argument("--queue", default="loadtest", help="Queue nomi")
    parser.add_argument("--persistent", action="store_true", help="Diskka yoziladigan xabarlar")
    parser.add_argument("--confirm", action="store_true", help="Publisher confirms (sekin, ishonchli)")
    parser.add_argument("--progress-every", type=int, default=10_000, help="Progress qadami")
    args = parser.parse_args()

    asyncio.run(run(args.count, args.queue, args.persistent, args.confirm, args.progress_every))


if __name__ == "__main__":
    main()
