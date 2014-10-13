#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

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
