import unittest
from diamond_agent import tasks
from configobj import ConfigObj
from cloudify.mocks import MockCloudifyContext


class TestDiamondPlugin(unittest.TestCase):
    def test_install(self):
        config = {
            'deployment_id': 'dep',
            'node_name': 'vm',
            'node_id': 'vm_id',
            'properties': {
                'interval': '10',
            }
        }
        ctx = MockCloudifyContext(**config)

        tasks.install(ctx)
        config_path = ctx['diamond_config_path']
        try:
            config_file = ConfigObj(infile=config_path, file_error=True)
        except IOError:
            self.fail('Could not open config file: {}'.format(config_path))
        self.assertEqual(config_file['collectors']['path_prefix'],
                         config['deployment_id'])
        self.assertEqual(config_file['collectors']['hostname'],
                         '.'.join([config['node_name'],config['node_id']]))
        self.assertEqual(config_file['collectors']['interval'],
                         config['properties']['interval'])