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
import tempfile

import mock

from cloudify import state

import diamond_agent.tasks as tasks


class TestHelperFunctions(unittest.TestCase):

    def test_get_paths_with_prefix(self):
        prefix = '/my/mock/prefix'
        self._test(expected_prefix=prefix, get_paths_arg=prefix)

    def test_get_paths_with_env_plugin_workdir(self):
        prefix = '/my/mock/prefix'
        with mock.patch.dict(os.environ, {'CELERY_WORK_DIR': prefix}):
            ctx = mock.MagicMock()
            ctx.plugin = mock.MagicMock()
            ctx.plugin.workdir = prefix
            state.current_ctx.set(ctx)
            try:
                self._test(expected_prefix=prefix)
            finally:
                state.current_ctx.clear()

    def test_get_paths_with_env_fallback_workdir(self):
        prefix = '/my/mock/prefix'
        with mock.patch.dict(os.environ, {'CELERY_WORK_DIR': prefix}):
            state.current_ctx.set(object())
            try:
                self._test(expected_prefix=os.path.join(prefix, 'diamond'))
            finally:
                state.current_ctx.clear()

    def test_get_paths_without_env(self):
        prefix = os.path.join(tempfile.gettempdir(), 'cloudify-monitoring-')
        with mock.patch.dict(os.environ, {'CELERY_WORK_DIR': ''}):
            self._test(expected_prefix=prefix)

    @mock.patch('diamond_agent.tasks.create_paths', return_value=None)
    def _test(self, _, expected_prefix, get_paths_arg=None):
        paths = tasks.get_paths(get_paths_arg)
        self.assertTrue(len(paths) > 0)
        for path in paths.values():
            self.assertTrue(path.startswith(expected_prefix))
