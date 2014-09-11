import os
import unittest
from tempfile import mkdtemp
from time import sleep
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
                    'ExampleCollector': {},
                },
                'handlers': {
                    'diamond.handler.archive.ArchiveHandler': {
                        'log_file': '/tmp/diamond.log'
                    }
                }
            }
        }
        self.env = self._create_env(inputs)
        self.env.execute('install', task_retries=0)
        sleep(20)
        self.assertTrue(True)

    def _create_env(self, inputs):
        return local.Environment(self._blueprint_path(), inputs=inputs)

    def _blueprint_path(self):
        return os.path.join(os.path.dirname(__file__),
                            'resources', 'blueprint.yaml')
