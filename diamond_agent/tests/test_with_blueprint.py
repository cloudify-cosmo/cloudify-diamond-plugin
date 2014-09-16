import os
import unittest
from tempfile import mkdtemp
import time
from cloudify.workflows import local


class TestWithBlueprint(unittest.TestCase):
    def setUp(self):
        os.environ['MANAGEMENT_IP'] = '127.0.0.1'

    def tearDown(self):
        self.env.execute('uninstall', task_retries=0)

    def test_custom_collectors(self):
        inputs = {
            'diamond_config': {
                'prefix': mkdtemp(prefix='cloudify-'),
                'interval': 1,
                'collectors': {
                    'TestCollector': {
                        'path': self._get_resource_path(
                            'blueprint', 'collectors', 'test.py'
                        ),
                    },
                },
                'handlers': {
                    'test_handler.TestHandler': {
                        'path': self._get_resource_path(
                            'blueprint', 'handlers', 'test_handler.py'),
                    }
                }
            }
        }
        print inputs['diamond_config']['prefix']
        self.env = self._create_env(inputs)
        self.env.execute('install', task_retries=0)

        self.check()

    def _create_env(self, inputs):
        return local.init_env(self._blueprint_path(), inputs=inputs)

    def _blueprint_path(self):
        return self._get_resource_path('blueprint', 'blueprint.yaml')

    def _get_resource_path(self, *args):
        return os.path.join(os.path.dirname(__file__), 'resources', *args)

    def check(self, timeout=5):
        end = time.time() + timeout
        while time.time() < end:
            try:
                open('/tmp/handler_file')
                return
            except:
                time.sleep(1)
        self.fail()
