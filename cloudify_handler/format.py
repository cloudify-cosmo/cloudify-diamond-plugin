from json import dumps


def jsonify(metric):
    metric_path = metric.path.split('.')

    output = {
        # Node instance id
        'node_id': metric_path[2],

        # Node id
        'node_name': metric_path[1],

        # Deployment id
        'deployment_id': metric_path[0],

        # Metric name (e.g. cpu)
        'name': metric_path[3],

        # Sub-metric name (e.g. avg)
        'path': '_'.join(metric_path[4:]),

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
