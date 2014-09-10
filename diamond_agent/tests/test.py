#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

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
                'config': {
                    'interval': '10',
                    }
            }
        }
        self.ctx = MockCloudifyContext(**self.config)
        tasks.install(self.ctx)

    def test_install(self):
        tasks.install(self.ctx)
        config_path = os.path.join(self.ctx['diamond_config_path'],
                                   'diamond.conf')
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
                         self.config['properties']['config']['interval'])

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
