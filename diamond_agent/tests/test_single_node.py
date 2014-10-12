import os
import time
import json
import cPickle
import unittest
import tempfile

import psutil

from cloudify.workflows import local


class TestSingleNode(unittest.TestCase):
    def setUp(self):
        os.environ['MANAGEMENT_IP'] = '127.0.0.1'
        self.is_uninstallable = True
        self.env = None

    def tearDown(self):
        if self.env:
            try:
                self.env.execute('uninstall', task_retries=0)
            except RuntimeError as e:
                if self.is_uninstallable:
                    raise e

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
        print log_path
        if not is_created(log_path):
            self.fail('file {} expected, but not found!'.format(log_path))

        with open(log_path, 'r') as fh:
            metric = cPickle.load(fh)
        metric_path = metric.path.split('.')

        collector_config = \
            inputs['collectors_config']['TestCollector']['config']
        self.assertEqual(collector_config['name'], metric_path[4])
        self.assertEqual(collector_config['value'], metric.value)
        self.assertEqual(self.env.name, metric_path[0])
        self.assertEqual('TestCollector', metric_path[3])

        node_instances = self.env.storage.get_node_instances()
        node_id, node_instance_id = get_ids(node_instances, 'node')

        self.assertEqual(node_id, metric_path[1])
        self.assertEqual(node_instance_id, metric_path[2])

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
        if not is_created(log_path):
            self.fail('file {} expected, but not found!'.format(log_path))

        with open(log_path, 'r') as fh:
            metric = json.loads(cPickle.load(fh))

        collector_config = \
            inputs['collectors_config']['TestCollector']['config']
        self.assertEqual(collector_config['name'], metric['path'])
        self.assertEqual(collector_config['value'], metric['metric'])
        self.assertEqual(self.env.name, metric['deployment_id'])
        self.assertEqual('TestCollector', metric['name'])

        node_instances = self.env.storage.get_node_instances()
        node_id, node_instance_id = get_ids(node_instances, 'node')

        self.assertEqual(node_id, metric['node_name'])
        self.assertEqual(node_instance_id, metric['node_id'])

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

        pid = get_pid(inputs)

        if not psutil.pid_exists(pid):
            self.fail('Diamond failed to start with empty collector list')

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
        pid_file = os.path.join(inputs['diamond_config']['prefix'],
                                'var', 'run', 'diamond.pid')
        with open(pid_file, 'r') as pf:
            pid = int(pf.read())

        if psutil.pid_exists(pid):
            self.env.execute('uninstall', task_retries=0)
            time.sleep(5)
        else:
            self.fail('diamond process not running')
        self.assertFalse(psutil.pid_exists(pid))

    def test_no_handlers(self):
        inputs = {
            'diamond_config': {
                'handlers': {},
            },
            'collectors_config': {},

        }
        self.is_uninstallable = False
        self.env = self._create_env(inputs)
        with self.assertRaisesRegexp(RuntimeError, 'Empty handlers dict'):
            self.env.execute('install', task_retries=0)

    def _create_env(self, inputs):
        return local.init_env(self._blueprint_path(),
                              inputs=inputs,
                              ignored_modules=['worker_installer.tasks',
                                               'plugin_installer.tasks'])

    def _blueprint_path(self):
        return self._get_resource_path('blueprint', 'single_node.yaml')

    def _get_resource_path(self, *args):
        return os.path.join(os.path.dirname(__file__), 'resources', *args)


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
            return instance['node_id'], instance['id']


def get_pid(config):
    pid_file = os.path.join(config['diamond_config']['prefix'],
                            'var', 'run', 'diamond.pid')

    with open(pid_file, 'r') as pf:
        pid = int(pf.read())

    return pid
