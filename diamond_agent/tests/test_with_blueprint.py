import os
import time
import cPickle
import unittest
import tempfile

import psutil

from cloudify.workflows import local


class TestWithBlueprint(unittest.TestCase):
    def setUp(self):
        os.environ['MANAGEMENT_IP'] = '127.0.0.1'
        self.env = None

    def tearDown(self):
        pass
        # if self.env:
        #     self.env.execute('uninstall', task_retries=0)

    def test_custom_collectors(self):
        log_path = tempfile.mktemp()
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
        self.env = self._create_env(inputs)
        self.env.execute('install', task_retries=0)

        if not is_created(log_path):
            self.fail('file {} expected, but not found!'.format(log_path))

        with open(log_path, 'r') as fh:
            metric = cPickle.load(fh)

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

    def test_default_collectors(self):
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
            }
        }
        self.env = self._create_env(inputs)
        self.env.execute('install', task_retries=0)

        if not is_created(log_path):
            self.fail('file {} expected, but not found!'.format(log_path))

        default_collectors = 'cpu memory loadavg iostat'.split()
        for _ in range(5):
            for collector in default_collectors:
                if not collector_in_log(log_path, collector):
                    time.sleep(1)
                    break
            else:
                break
        else:
            self.fail('default collector not found')

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
            }
        }
        self.env = self._create_env(inputs)
        self.env.execute('install', task_retries=0)
        pid_file = os.path.join(inputs['diamond_config']['prefix'],
                                'var', 'run', 'diamond.pid')
        with open(pid_file, 'r') as pf:
            pid = int(pf.read())

        if psutil.pid_exists(pid):
            self.env.execute('uninstall', task_retries=0)
            time.sleep(3)
        else:
            self.fail('diamond process not running')
        self.assertFalse(psutil.pid_exists(pid))

    def _create_env(self, inputs):
        return local.init_env(self._blueprint_path(), inputs=inputs)

    def _blueprint_path(self):
        return self._get_resource_path('blueprint', 'blueprint.yaml')

    def _get_resource_path(self, *args):
        return os.path.join(os.path.dirname(__file__), 'resources', *args)


def collector_in_log(path, collector):
    with open(path, 'r') as fh:
        try:
            while True:
                metric = cPickle.load(fh)
                if metric.getCollectorPath() == collector:
                    return True
        except EOFError:
            return False


def is_created(path, timeout=5):
    for _ in range(timeout):
        if os.path.isfile(path):
            return True
        time.sleep(1)
    return False
