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

from json import dumps


def jsonify(metric):
    node_name, node_id = metric.host.split('.')

    output = {
        # Node instance id
        'node_id': node_id,

        # Node id
        'node_name': node_name,

        # Deployment id
        'deployment_id': metric.getPathPrefix(),

        # Metric name (e.g. cpu)
        'name': metric.getCollectorPath(),

        # Sub-metric name (e.g. avg)
        'path': metric.getMetricPath().replace('.', '_'),

        # The actual metric value
        'metric': float(metric.value),

        # Metric unit
        'unit': '',

        # Metric type (gauge, counter, etc...)
        'type': metric.metric_type,

        # Fixed stub for riemann
        'host': 'host',

        # The full metric name (
        # e.g. deployment_id.node_id.node_instance_id.metric)
        'service': metric.path,

        # epoch timestamp of the metric
        'time': metric.timestamp,
    }
    return dumps(output)
