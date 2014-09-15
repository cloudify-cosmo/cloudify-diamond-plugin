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
import signal
from shutil import copytree, copy
from tempfile import mkdtemp
from subprocess import call

from configobj import ConfigObj
from cloudify.decorators import operation
from cloudify.utils import get_manager_ip
from cloudify import exceptions

CONFIG_NAME = 'diamond.conf'
PID_NAME = 'diamond.pid'
DEFAULT_COLLECTORS = {
    'CPUCollector': {},
    'MemoryCollector': {},
    'LoadAverageCollector': {},
    'DiskUsageCollector': {}
}

# TODO: get_manager_ip during actual instantiation
DEFAULT_HANDLERS = {
    'cloudify_handler.cloudify.CloudifyHandler': {
        'rmq_server': 'localhost',
        'rmq_port': 5672,
        'rmq_exchange': 'cloudify-monitoring',
        'rmq_user': '',
        'rmq_password': '',
        'rmq_vhost': '/',
        'rmq_exchange_type': 'topic',
        'rmq_durable': False
    }
}

DEFAULT_INTERVAL = 10


@operation
def install(ctx, diamond_config, **kwargs):
    paths = get_paths(diamond_config.get('prefix'))
    ctx.runtime_properties['diamond_pid_file'] = os.path.join(paths['pid'],
                                                              PID_NAME)
    host = '.'.join([ctx.node_name, ctx.node_id])

    # TODO: when handlers and collectors are set,
    # validate at least one and use NonRecoverableError
    handlers = config_handlers(diamond_config.get('handlers'),
                               paths['handlers_config'])
    interval = diamond_config.get('interval', DEFAULT_INTERVAL)
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
                      diamond_config.get('collectors'),
                      paths['collectors_config'],
                      paths['collectors'])

    config_handlers(handlers, paths['handlers_config'])

    try:
        start(paths['config'])
    except OSError as e:
        raise exceptions.NonRecoverableError(
            'Starting diamond failed: {}'.format(e))


@operation
def uninstall(ctx, diamond_config, **kwargs):
    pid_path = ctx.runtime_properties['diamond_pid_file']
    # letting the workflow engine handle this in case of errors
    # so no try/catch
    stop(pid_path)


def start(conf_path):
    cmd = 'diamond --configfile {}'.format(os.path.join(conf_path,
                                                        CONFIG_NAME))
    call(cmd.split())


def stop(pid_path):
    with open(pid_path) as f:
        pid = int(f.read())

    # TODO: test with signal.SIGTERM
    os.kill(pid, signal.SIGKILL)


def config_collectors(ctx, collectors, config_path, collectors_path):
    if collectors is None:
        collectors = DEFAULT_COLLECTORS

    for name, prop in collectors.items():
        if 'path' in prop.keys():
            collector_dir = os.path.join(collectors_path, name)
            os.mkdir(collector_dir)
            collector_file = os.path.join(collector_dir, '{}.py'.format(name))
            ctx.download_resource(prop['path'], collector_file)

        prop.update({'enabled': True})
        config_full_path = os.path.join(config_path, name + '.conf')
        write_config(config_full_path, prop)


def config_handlers(handlers, config_path):
    if handlers is None:
        handlers = DEFAULT_HANDLERS

    for name, props in handlers.items():
        path = os.path.join(config_path, name.split('.')[-1] + '.conf')
        write_config(path, props)

    return handlers.keys()


def write_config(path, properties):
    config = ConfigObj(infile=path)
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
