from diamond.handler.rabbitmq_topic import rmqHandler
from format import jsonify
try:
    import pika
except ImportError:
    pika = None


class CloudifyHandler(rmqHandler):
    def process(self, metric):
        if not pika:
            return

        try:
            self.channel.basic_publish(
                exchange=self.topic_exchange,
                routing_key=metric.getPathPrefix(),
                body=jsonify(metric))

        except Exception:  # Rough connection re-try logic.
            self.log.info(
                "Failed publishing to rabbitMQ. Attempting reconnect")
            self._bind()
