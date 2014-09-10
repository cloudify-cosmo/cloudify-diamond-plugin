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
import sys
import glob
from shutil import copytree, copy
from tempfile import mkdtemp
from subprocess import call
from cloudify.decorators import operation
from cloudify.utils import get_manager_ip
from configobj import ConfigObj

CONFIG_NAME = 'diamond.conf'
PID_NAME = 'diamond.pid'
DEFAULT_COLLECTORS = {
    'CPUCollector': {},
    'MemoryCollector': {},
    'LoadAverageCollector': {},
    'DiskUsageCollector': {}
}


@operation
def install(ctx, diamond_config, **kwargs):
    paths = get_paths(diamond_config.get('prefix'))
    ctx.runtime_properties['diamond_config'] = paths['config']
    host = '.'.join([ctx.node_name, ctx.node_id])
    # TODO: handlers needs to be customizable as collectors
    handlers = 'cloudify_handler.cloudify.CloudifyHandler'
    interval = diamond_config.get('interval', 10)
    create_config(hostname=host,
                  path_prefix=ctx.deployment_id,
                  handlers=handlers,
                  interval=interval,
                  paths=paths)

    copy_content(os.path.join(sys.prefix, 'share', 'diamond', 'collectors'),
                 paths['collectors'])
    copy_content(os.path.join(sys.prefix, 'etc', 'diamond', 'collectors'),
                 paths['collectors_config'])

    disable_all_collectors(paths['collectors_config'])
    config_collectors(ctx,
                      diamond_config.get('collectors', {}),
                      paths['collectors_config'],
                      paths['collectors'])

    config_cloudify_handler(
        os.path.join(paths['handlers_config'], 'CloudifyHandler.conf'))

    try:
        start(paths['config'])
    except OSError as e:
        ctx.logger.info('Starting diamond failed: {}'.format(e))


@operation
def uninstall(ctx, **kwargs):
    path = os.path.join(ctx.runtime_properties['diamond_config'], CONFIG_NAME)
    try:
        config = ConfigObj(infile=path, file_error=True)
        pid = config['server']['pid_file']
        stop(pid)
    except (OSError, IOError) as e:
        ctx.logger.info('Stoppign diamond failed: {}'.format(e))


def start(conf_path):
    cmd = 'diamond --configfile {}'.format(os.path.join(conf_path,
                                                        CONFIG_NAME))
    call(cmd.split())


def stop(pid_path):
    with open(pid_path) as f:
        pid = int(f.read())
    os.kill(pid, 9)


def config_collectors(ctx, collectors, config_path, collectors_path):
    if not collectors:
        collectors = DEFAULT_COLLECTORS

    for name, prop in collectors.items():
        if 'path' in prop.keys():
            ctx.download_resource(prop['path'],
                                  os.path.join(collectors_path, name))
        prop.update({'enabled': True})
        config_collector(name, config_path, prop)


def config_collector(name, path, properties):
    full_path = os.path.join(path, name + '.conf')
    config = ConfigObj(infile=full_path)
    for key, value in properties.items():
        config[key] = value
    config.write()


def disable_all_collectors(path):
    """
    disables all collectors which configs are located at path
    """
    files = glob.glob(os.path.join(path, '*.conf'))
    for path in files:
        disable_collector(path)


def disable_collector(path):
    """
    disables single collector
    """
    config = ConfigObj(infile=path, file_error=True)
    config['enabled'] = False
    config.write()


def get_paths(prefix):
    """
    creates folder structure and returns dict with full paths
    """
    if prefix is None:
        prefix = mkdtemp(prefix='cloudify-')
    paths = {
        'config': os.path.join(prefix, 'etc'),
        'collectors_config': os.path.join(prefix, 'etc', 'collectors'),
        'collectors': os.path.join(prefix, 'collectors'),
        'handlers_config': os.path.join(prefix, 'etc', 'handlers'),
        'handlers': os.path.join(prefix, 'handlers'),
        'pid': os.path.join(prefix, 'var', 'run'),
        'log': os.path.join(prefix, 'var', 'log')
    }
    for path in paths.values():
        if not os.path.exists(path):
            os.makedirs(path)
    return paths


def config_cloudify_handler(config_path):
    handler_config = {
        'rmq_server': get_manager_ip(),
        'rmq_port': 5672,
        'rmq_exchange': 'cloudify-monitoring',
        'rmq_user': '',
        'rmq_password': '',
        'rmq_vhost': '/',
        'rmq_exchange_type': 'topic',
        'rmq_durable': False
    }
    config = ConfigObj(handler_config, write_empty_values=True)
    config.filename = config_path
    config.write()


def create_config(hostname, path_prefix, handlers, interval, paths):
    """
    Creates main diamond configuration file
    """
    server_config = {
        'server': {
            'handlers': handlers,
            'user': '',
            'group': '',
            'pid_file': os.path.join(paths['pid'], PID_NAME),
            'collectors_path': paths['collectors'],
            'collectors_config_path': paths['collectors_config'],
            'handlers_config_path': paths['handlers_config'],
            'handlers_path': paths['handlers'],
            'collectors_reload_interval': 3600,
        },
        'handlers': {
            'keys': 'rotated_file',
            'default': {},
        },
        'collectors': {
            'default': {
                'hostname': hostname,
                'path_prefix': path_prefix,
                'interval': interval,
            },
        },
        'loggers': {
            'keys': 'root',
        },
        'formatters': {
            'keys': 'default',
        },
        'logger_root': {
            'level': 'INFO',
            'handlers': 'rotated_file',
            'propagate': 1,
        },
        'handler_rotated_file': {
            'class': 'handlers.TimedRotatingFileHandler',
            'level': 'DEBUG',
            'formatter': 'default',
            'args': "('{}', 'midnight', 1, 7)".format(
                os.path.join(paths['log'], 'diamond.log')),
        },
        'formatter_default': {
            'format': '[%(asctime)s] [%(threadName)s] %(message)s',
            'datefmt': '',
        },
    }
    config = ConfigObj(server_config,
                       indent_type='',
                       list_values=False,
                       write_empty_values=True)
    config.filename = os.path.join(paths['config'], CONFIG_NAME)
    config.write()


def copy_content(src, dest):
    for item in os.listdir(src):
        full_path = os.path.join(src, item)
        if os.path.isdir(full_path):
            copytree(full_path, os.path.join(dest, item))
        else:
            copy(full_path, dest)
