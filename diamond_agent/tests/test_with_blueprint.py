import os
import time
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
        log_path = os.path.join(tempfile.gettempdir(), str(time.time()))
        inputs = {
            'diamond_config': {
                'prefix': tempfile.mkdtemp(prefix='cloudify-'),
                'interval': 1,
                'collectors': {
                    'TestCollector': {
                        'path': 'collectors/test.py',
                        'config': {},
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

        self.check(log_path)

    def _create_env(self, inputs):
        return local.init_env(self._blueprint_path(), inputs=inputs)

    def _blueprint_path(self):
        return self._get_resource_path('blueprint', 'blueprint.yaml')

    def _get_resource_path(self, *args):
        return os.path.join(os.path.dirname(__file__), 'resources', *args)

    def check(self, path, timeout=5):
        end = time.time() + timeout
        while time.time() < end:
            try:
                open(path)
                return
            except:
                time.sleep(1)
        self.fail()
