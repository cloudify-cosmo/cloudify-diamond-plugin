import os
import time
import string
import random
import cPickle
import unittest
import tempfile

from cloudify.workflows import local


class TestWithBlueprint(unittest.TestCase):
    def setUp(self):
        os.environ['MANAGEMENT_IP'] = '127.0.0.1'
        self.env = None

    def tearDown(self):
        if self.env:
            self.env.execute('uninstall', task_retries=0)

    def test_custom_collectors(self):
        log_path = os.path.join(tempfile.gettempdir(), id_generator())
        inputs = {
            'diamond_config': {
                'prefix': tempfile.mkdtemp(prefix='cloudify-'),
                'interval': 1,
                'collectors': {
                    'TestCollector': {
                        'path': 'collectors/test.py',
                        'config': {
                            'name': 'metric',
                            'value': 42,
                        },
                    },
                },
                'handlers': {
                    'test_handler.TestHandler': {
                        'path': 'handlers/test_handler.py',
                        'config': {
                            'log_path': log_path,
                        }
                    }
                }
            }
        }
        print inputs['diamond_config']['prefix']
        print log_path
        self.env = self._create_env(inputs)
        self.env.execute('install', task_retries=0)

        metric = self.get_metric_instance(log_path)
        collector_config = \
            inputs['diamond_config']['collectors']['TestCollector']['config']

        self.assertEqual(collector_config['name'], metric.getMetricPath())
        self.assertEqual(collector_config['value'], metric.value)
        self.assertEqual(self.env.name, metric.getPathPrefix())
        self.assertEqual('TestCollector', metric.getCollectorPath())
        self.assertEqual(self.env.plan['nodes'][0]['id'],
                         metric.host.split('.')[0])
        self.assertEqual(self.env.plan['node_instances'][0]['id'],
                         metric.host.split('.')[1])

    def _create_env(self, inputs):
        return local.init_env(self._blueprint_path(), inputs=inputs)

    def _blueprint_path(self):
        return self._get_resource_path('blueprint', 'blueprint.yaml')

    def _get_resource_path(self, *args):
        return os.path.join(os.path.dirname(__file__), 'resources', *args)

    def get_metric_instance(self, path, timeout=5):
        end = time.time() + timeout
        while time.time() < end:
            try:
                with open(path) as fh:
                    return cPickle.load(fh)
            except IOError:
                time.sleep(1)
        self.fail()


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))
