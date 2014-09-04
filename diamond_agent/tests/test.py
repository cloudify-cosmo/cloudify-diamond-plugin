import os
import unittest
from time import sleep
from psutil import pid_exists
from diamond_agent import tasks
from configobj import ConfigObj
from cloudify.mocks import MockCloudifyContext


class TestDiamondPlugin(unittest.TestCase):
    def setUp(self):
        os.environ['MANAGEMENT_IP'] = '127.0.0.1'
        self.config = {
            'deployment_id': 'dep',
            'node_name': 'vm',
            'node_id': 'vm_id',
            'properties': {
                'interval': '10',
            }
        }
        self.ctx = MockCloudifyContext(**self.config)
        tasks.install(self.ctx)

    def test_install(self):
        tasks.install(self.ctx)
        config_path = self.ctx['diamond_config_path']
        try:
            config_file = ConfigObj(infile=config_path, file_error=True)
        except IOError:
            self.fail('Could not open config file: {}'.format(config_path))
        self.assertEqual(config_file['collectors']['default']['path_prefix'],
                         self.config['deployment_id'])
        self.assertEqual(config_file['collectors']['default']['hostname'],
                         '.'.join([self.config['node_name'],
                                   self.config['node_id']]))
        self.assertEqual(config_file['collectors']['default']['interval'],
                         self.config['properties']['interval'])

    def test_start_stop(self):
        tasks.start(self.ctx)
        sleep(3)
        with open('/tmp/diamond.pid', 'r') as f:
            pid = int(f.readline())

        if not pid_exists(pid):
            self.fail('diamond agent doesn\'t run')
        else:
            tasks.stop(self.ctx)
            sleep(2)

        if pid_exists(pid):
            self.fail('diamond agent didn\'t stop')
