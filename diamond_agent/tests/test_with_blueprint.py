
import os
import unittest

from cloudify.workflows import local


class TestWithBlueprint(unittest.TestCase):

    def setUp(self):
        os.environ['MANAGEMENT_IP'] = 'localhost'
        self.env = local.Environment(self._blueprint_path())

    def test_with_blueprint(self):
        self.env.execute('uninstall', task_retries=0)

    def _blueprint_path(self):
        return os.path.join(os.path.dirname(__file__),
                            'resources', 'blueprint.yaml')
