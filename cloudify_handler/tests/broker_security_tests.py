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

import ssl
import unittest

from mock import patch, PropertyMock

import cloudify_handler


class TestSecurity(unittest.TestCase):

    @patch('cloudify_handler.cloudify.broker_config')
    @patch('cloudify_handler.cloudify.pika.BlockingConnection')
    @patch('cloudify_handler.cloudify.pika.ConnectionParameters')
    @patch('cloudify_handler.cloudify.pika.PlainCredentials')
    def test_cloudify_handler_uses_supplied_credentials(self,
                                                        mock_creds,
                                                        mock_params,
                                                        mock_conn,
                                                        mock_config):
        username = 'someuser'
        password = 'somepass'

        type(mock_config).broker_ssl_enabled = PropertyMock(
            return_value=False,
        )
        type(mock_config).broker_cert_path = PropertyMock(
            return_value='',
        )

        # We are testing _bind, but this happens implicitly
        cloudify_handler.cloudify.CloudifyHandler(
            config={
                'server': 'localhost',
                'port': '5672',
                'topic_exchange': 'cloudify-monitoring',
                'vhost': '/',
                'user': username,
                'password': password,
            },
        )

        mock_creds.assert_called_once_with(
            username,
            password,
        )

    @patch('cloudify_handler.cloudify.broker_config')
    @patch('cloudify_handler.cloudify.pika.BlockingConnection')
    @patch('cloudify_handler.cloudify.pika.ConnectionParameters')
    @patch('cloudify_handler.cloudify.pika.PlainCredentials')
    def test_cloudify_handler_ssl_configuration(self,
                                                mock_creds,
                                                mock_params,
                                                mock_conn,
                                                mock_config):
        username = 'someuser'
        password = 'somepass'
        cert_path = '/not/real/cert.pem'

        type(mock_config).broker_ssl_enabled = PropertyMock(
            return_value=True,
        )
        type(mock_config).broker_cert_path = PropertyMock(
            return_value=cert_path,
        )

        # We are testing _bind, but this happens implicitly
        cloudify_handler.cloudify.CloudifyHandler(
            config={
                'server': 'localhost',
                'port': '5671',
                'topic_exchange': 'cloudify-monitoring',
                'vhost': '/',
                'user': username,
                'password': password,
            },
        )

        # We don't care about most of the args but there should only have been
        # one call, with ssl disabled
        self.assertEqual(mock_params.call_count, 1)

        _, mock_params_kwargs = mock_params.call_args
        # Check ssl is actually True, as assertTrue accepts Truey values,
        # but pika shouldn't be expected to
        self.assertEqual(
            mock_params_kwargs['ssl'],
            True,
        )
        # Check ssl options are correct
        self.assertEqual(
            mock_params_kwargs['ssl_options'],
            {
                'cert_reqs': ssl.CERT_REQUIRED,
                'ca_certs': cert_path,
            },
        )
        # Check port was passed correctly
        self.assertEqual(
            mock_params_kwargs['port'],
            5671,
        )
