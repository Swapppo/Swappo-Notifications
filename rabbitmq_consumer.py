"""
RabbitMQ message consumer for async notification processing
"""

import asyncio
import json
import os
from typing import Callable, Optional

import pika
from pika.exceptions import AMQPConnectionError


class NotificationConsumer:
    """RabbitMQ consumer for processing notification events"""

    def __init__(self, message_handler: Callable):
        """
        Initialize RabbitMQ consumer

        Args:
            message_handler: Callback function to handle incoming messages
        """
        self.rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
        self.rabbitmq_port = int(os.getenv("RABBITMQ_PORT", "5672"))
        self.rabbitmq_user = os.getenv("RABBITMQ_USER", "swappo_user")
        self.rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "swappo_pass")
        self.queue_name = "notifications_queue"

        self.message_handler = message_handler
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None

        self._connect()

    def _connect(self):
        """Establish connection to RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(
                self.rabbitmq_user, self.rabbitmq_password
            )

            parameters = pika.ConnectionParameters(
                host=self.rabbitmq_host,
                port=self.rabbitmq_port,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
            )

            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            # Declare queue (idempotent operation)
            self.channel.queue_declare(
                queue=self.queue_name, durable=True  # Persist messages to disk
            )

            # Set QoS to process one message at a time
            self.channel.basic_qos(prefetch_count=1)

            print(
                f"✅ Consumer connected to RabbitMQ at {self.rabbitmq_host}:{self.rabbitmq_port}"
            )

        except AMQPConnectionError as e:
            print(f"❌ Failed to connect to RabbitMQ: {e}")
            self.connection = None
            self.channel = None

    def _on_message(self, ch, method, properties, body):
        """
        Callback function when message is received

        Args:
            ch: Channel
            method: Delivery method
            properties: Message properties
            body: Message body
        """
        try:
            # Parse JSON message
            notification_data = json.loads(body.decode())

            print(
                f"📥 Received notification: {notification_data.get('type', 'unknown')}"
            )

            # Process message using handler
            success = self.message_handler(notification_data)

            if success:
                # Acknowledge message
                ch.basic_ack(delivery_tag=method.delivery_tag)
                print("✅ Notification processed and acknowledged")
            else:
                # Reject and requeue message
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                print("⚠️ Notification processing failed, requeued")

        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in message: {e}")
            # Acknowledge to remove invalid message
            ch.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as e:
            print(f"❌ Error processing message: {type(e).__name__}: {e}")
            # Reject and requeue
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def start_consuming(self):
        """Start consuming messages from queue"""
        try:
            if not self.channel:
                print("❌ No RabbitMQ channel available")
                return

            print(f"👂 Starting to consume messages from '{self.queue_name}' queue...")

            self.channel.basic_consume(
                queue=self.queue_name,
                on_message_callback=self._on_message,
                auto_ack=False,  # Manual acknowledgment
            )

            self.channel.start_consuming()

        except KeyboardInterrupt:
            print("\n⚠️ Consumer interrupted by user")
            self.stop_consuming()
        except Exception as e:
            print(f"❌ Consumer error: {type(e).__name__}: {e}")

    def stop_consuming(self):
        """Stop consuming messages"""
        try:
            if self.channel:
                self.channel.stop_consuming()
                print("✅ Stopped consuming messages")
        except Exception as e:
            print(f"⚠️ Error stopping consumer: {e}")

    def close(self):
        """Close RabbitMQ connection"""
        try:
            self.stop_consuming()

            if self.connection and not self.connection.is_closed:
                self.connection.close()
                print("✅ RabbitMQ connection closed")
        except Exception as e:
            print(f"⚠️ Error closing RabbitMQ connection: {e}")


async def run_consumer_in_background(consumer: NotificationConsumer):
    """Run consumer in background asyncio task"""
    loop = asyncio.get_event_loop()

    # Run blocking consumer in thread pool
    await loop.run_in_executor(None, consumer.start_consuming)
