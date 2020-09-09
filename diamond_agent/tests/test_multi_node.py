import os
import time
import tempfile

import mock
import testtools

from cloudify.workflows import local

from diamond_agent import tasks
from diamond_agent.tests import IGNORED_LOCAL_WORKFLOW_MODULES


class TestMultiNode(testtools.TestCase):
    def setUp(self):
        super(TestMultiNode, self).setUp()
        os.environ['MANAGEMENT_IP'] = '127.0.0.1'
        self.is_uninstallable = True
        self.env = None
        self._original_get_agent_name = tasks._get_agent_name
        tasks._get_agent_name = mock.MagicMock(return_value='agent_name')

    def tearDown(self):
        super(TestMultiNode, self).tearDown()
        if self.env and self.is_uninstallable:
            self.env.execute('uninstall', task_retries=0)
        tasks._get_agent_name = self._original_get_agent_name

    def test_custom_collectors(self):
        log_path = tempfile.mktemp()
        inputs = {
            'diamond_config': {
                'prefix': tempfile.mkdtemp(prefix='cloudify-'),
                'interval': 1,
                'handlers': {
                    'test_handler.TestHandler': {
                        'path': 'handlers/test_handler.py',
                        'config': {
                            'log_path': log_path,
                        }
                    }
                }
            },
            'collectors_config': {
                'TestCollector': {
                    'path': 'collectors/test.py',
                    'config': {
                        'name': 'metric',
                        'value': 42,
                    },
                },
            },
        }
        self.env = self._create_env(inputs)
        self.env.execute('install', task_retries=0)

    def test_del_collectors(self):
        log_path = tempfile.mktemp()
        inputs = {
            'diamond_config': {
                'prefix': tempfile.mkdtemp(prefix='cloudify-'),
                'interval': 1,
                'handlers': {
                    'test_handler.TestHandler': {
                        'path': 'handlers/test_handler.py',
                        'config': {
                            'log_path': log_path,
                        }
                    }
                }
            },
            'collectors_config': {
                'TestCollector': {
                    'path': 'collectors/test.py',
                    'config': {
                        'name': 'metric',
                        'value': 42,
                    },
                },
                'CPUCollector': {
                    'config': {
                        'some': 'property',
                    },
                },
            },
        }
        self.env = self._create_env(inputs)
        self.is_uninstallable = False
        self.env.execute('install', task_retries=0)

    def _create_env(self, inputs):
        return local.init_env(self._blueprint_path(),
                              inputs=inputs,
                              ignored_modules=IGNORED_LOCAL_WORKFLOW_MODULES)

    def _blueprint_path(self):
        return self._get_resource_path('blueprint', 'multi_node.yaml')

    def _get_resource_path(self, *args):
        return os.path.join(os.path.dirname(__file__), 'resources', *args)


def is_created(path, timeout=5):
    for _ in range(timeout):
        if os.path.isfile(path):
            return True
        time.sleep(1)
    return False


def get_ids(instances, name):
    for instance in instances:
        if instance['name'] == name:
            return instance['host_id'], instance['node_id'], instance['id']
