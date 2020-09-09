import os
import time
import tempfile
import pickle as cPickle

import mock
from testtools import TestCase

from cloudify.workflows import local
from cloudify.decorators import operation

from diamond_agent import tasks
from diamond_agent.tests import IGNORED_LOCAL_WORKFLOW_MODULES


class TestSingleNode(TestCase):
    def setUp(self):
        super(TestSingleNode, self).setUp()
        os.environ['MANAGEMENT_IP'] = '127.0.0.1'
        self.is_uninstallable = True
        self.env = None
        self._original_get_agent_name = tasks._get_agent_name
        tasks._get_agent_name = mock.MagicMock(return_value='agent_name')
        self.addCleanup(self._unmock_agent_name)

    def tearDown(self):
        super(TestSingleNode, self).tearDown()
        if self.env and self.is_uninstallable:
            self.env.execute('uninstall', task_retries=0)

    # custom handler + custom collector
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

    def test_cloudify_handler_format(self):
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
                            'output_cloudify_format': True,
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

    # custom handler + no collector
    # diamond should run without outputting anything
    def test_no_collectors(self):
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
                        },
                    }
                }
            },
            'collectors_config': {}
        }
        self.env = self._create_env(inputs)
        self.env.execute('install', task_retries=0)

    def test_uninstall_workflow(self):
        inputs = {
            'diamond_config': {
                'prefix': tempfile.mkdtemp(prefix='cloudify-'),
                'interval': 1,
                'handlers': {
                    'diamond.handler.archive.ArchiveHandler': {
                        'config': {
                            'log_file': tempfile.mktemp(),
                        }
                    }
                }
            },
            'collectors_config': {},

        }
        self.is_uninstallable = False
        self.env = self._create_env(inputs)
        self.env.execute('install', task_retries=0)

    def test_no_handlers(self):
        inputs = {
            'diamond_config': {
                'handlers': {},
            },
            'collectors_config': {},

        }
        self.is_uninstallable = False
        self.env = self._create_env(inputs)
        self.env.execute('install', task_retries=0)

    def test_restart_plugin_script(self):
        """A script that restarts diamond doesn't interfere with the plugin.

        If the add_collectors tasks run in parallel with a script that
        also happens to restart diamond, there's a race condition between them
        looking up the process by the PID, making one of them to break.
        """
        blueprint_yaml = self._get_resource_path('blueprint',
                                                 'restart_diamond_script.yaml')
        self.is_uninstallable = False
        local_env = local.init_env(
            blueprint_yaml, ignored_modules=IGNORED_LOCAL_WORKFLOW_MODULES)
        self.addCleanup(local_env.execute, 'uninstall')
        # this needs a threadpool size >1 so that the add_collectors task
        # can run in parallel with the custom restart task
        local_env.execute('install', task_thread_pool_size=5)

    def _mock_get_paths(self, prefix):
        return [
            os.path.join(prefix, 'etc', tasks.CONFIG_NAME),
            os.path.join(prefix, 'etc', 'collectors'),
            os.path.join(prefix, 'collectors'),
            os.path.join(prefix, 'etc', 'handlers'),
            os.path.join(prefix, 'handlers')
        ]

    def _create_env(self, inputs):
        return local.init_env(self._blueprint_path(),
                              inputs=inputs,
                              ignored_modules=IGNORED_LOCAL_WORKFLOW_MODULES)

    def _blueprint_path(self):
        return self._get_resource_path('blueprint', 'single_node.yaml')

    def _get_resource_path(self, *args):
        return os.path.join(os.path.dirname(__file__), 'resources', *args)

    def _unmock_agent_name(self):
        tasks._get_agent_name = self._original_get_agent_name


def collector_in_log(path, collector):
    with open(path, 'r') as fh:
        try:
            while True:
                metric = cPickle.load(fh)
                if metric.path.split('.')[3] == collector:
                    return True
        except EOFError:
            return False


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


def get_pid(config):
    pid_file = os.path.join(config['diamond_config']['prefix'],
                            'var', 'run', 'diamond.pid')

    with open(pid_file, 'r') as pf:
        pid = int(pf.read())

    return pid


@operation
def sleep_and_restart_diamond(ctx):
    """Restart diamond 5 times, with 3 second pauses between restarts.

    This is a task used in the TestSingleNode.test_restart_plugin_script test.
    """
    ctx.logger.info('Foo')
