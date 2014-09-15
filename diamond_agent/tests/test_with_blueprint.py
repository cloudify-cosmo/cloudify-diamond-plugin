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
                    'TestCollector': {},
                },
                'handlers': {
                    'test_handler.TestHandler': {}
                }
            }
        }
        self.env = self._create_env(inputs)
        self.env.execute('install', task_retries=0)

        self.check()

    def _create_env(self, inputs):
        return local.init_env(self._blueprint_path(), inputs=inputs)

    def _blueprint_path(self):
        return os.path.join(os.path.dirname(__file__),
                            'resources',
                            'blueprint',
                            'blueprint.yaml')

    def check(self, timeout=10):
        end = time.time() + timeout
        while time.time() < end:
            try:
                with open('/tmp/handler_file') as f:
                    f.write('wrote: {}'.format(metric))
                return
            except:
                time.sleep(1)
        self.fail()
