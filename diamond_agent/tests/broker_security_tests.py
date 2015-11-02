########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

import unittest

from mock import Mock, PropertyMock, patch

import diamond_agent


CONFIG_DIR_PATH = '/tmp/not/real'
EXPECTED_CONFIG_FILE_PATH = '/tmp/not/real/CloudifyHandler.conf'


class FakeCloudifyAgent(object):
    def __init__(self, broker_user=None, broker_pass=None):
        """
            Creates a fake agent with or without broker credentials attributes
        """
        # Allow for empty strings in future with an explicit None check
        if broker_user is not None:
            self.broker_user = broker_user
        if broker_pass is not None:
            self.broker_pass = broker_pass


class TestSecurity(unittest.TestCase):

    def _get_fake_ctx(self, broker_user=None, broker_pass=None):
        ctx = Mock()

        fake_agent = FakeCloudifyAgent(broker_user, broker_pass)

        type(ctx.bootstrap_context).cloudify_agent = PropertyMock(
            return_value=fake_agent
        )

        return ctx

    @patch('diamond_agent.tasks.write_config')
    @patch('diamond_agent.tasks.get_manager_ip', return_value='192.0.2.1')
    def test_configure_handlers_uses_default_credentials(self,
                                                         mock_get_manager_ip,
                                                         mock_config_writer):
        ctx = self._get_fake_ctx()

        diamond_agent.tasks.config_handlers(
            ctx=ctx,
            handlers=None,
            config_path=CONFIG_DIR_PATH,
            handlers_path=None,
        )

        # We don't care about most of the args but there should only have been
        # one call, with ssl disabled
        self.assertEqual(mock_config_writer.call_count, 1)

        mock_config_writer_args, _ = mock_config_writer.call_args

        # Check the username and password were the defaults
        self.assertEqual(
            mock_config_writer_args[1]['user'],
            'guest',
        )
        self.assertEqual(
            mock_config_writer_args[1]['password'],
            'guest',
        )

    @patch('diamond_agent.tasks.write_config')
    @patch('diamond_agent.tasks.get_manager_ip', return_value='192.0.2.1')
    def test_configure_handlers_uses_provided_credentials(self,
                                                          mock_get_manager_ip,
                                                          mock_config_writer):
        username = 'bobby'
        password = "tables'); select * from"

        ctx = self._get_fake_ctx(broker_user=username, broker_pass=password)

        diamond_agent.tasks.config_handlers(
            ctx=ctx,
            handlers=None,
            config_path=CONFIG_DIR_PATH,
            handlers_path=None,
        )

        # We don't care about most of the args but there should only have been
        # one call, with ssl disabled
        self.assertEqual(mock_config_writer.call_count, 1)

        mock_config_writer_args, _ = mock_config_writer.call_args

        # Check the username and password were the defaults
        self.assertEqual(
            mock_config_writer_args[1]['user'],
            username,
        )
        self.assertEqual(
            mock_config_writer_args[1]['password'],
            password,
        )
