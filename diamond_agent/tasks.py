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
import platform
import copy as copy_objects
from glob import glob
from time import sleep
from shutil import copytree, copy, rmtree
from tempfile import mkdtemp
from subprocess import call

from psutil import pid_exists, Process
from configobj import ConfigObj

from cloudify import ctx
from cloudify.constants import CLUSTER_SETTINGS_PATH_KEY
from cloudify.decorators import operation
from cloudify import exceptions, utils, constants

CONFIG_NAME = 'diamond.conf'
PID_NAME = 'diamond.pid'
DEFAULT_INTERVAL = 10
DEFAULT_TIMEOUT = 10

DEFAULT_HANDLERS = {
    'cloudify_handler.cloudify.CloudifyHandler': {
        'config': {
            'server': 'localhost',
            'port': constants.BROKER_PORT_SSL,
            'topic_exchange': 'cloudify-monitoring',
            'vhost': '/',
            'user': 'guest',
            'password': 'guest',
        }
    }
}

_PATHS_TO_CLEAN_UP = ['collectors',
                      'handlers',
                      'handlers_config',
                      'collectors_config']


@operation
def install(ctx, diamond_config, **kwargs):
    paths = get_paths(diamond_config.get('prefix'))
    ctx.instance.runtime_properties['diamond_paths'] = paths

    handlers = config_handlers(ctx,
                               diamond_config.get('handlers'),
                               paths['handlers_config'],
                               paths['handlers'])

    interval = diamond_config.get('interval', DEFAULT_INTERVAL)
    create_config(path_prefix=ctx.deployment.id,
                  handlers=handlers,
                  interval=interval,
                  paths=paths)

    copy_content(os.path.join(_prefix(), 'share', 'diamond', 'collectors'),
                 paths['collectors'])
    copy_content(os.path.join(_prefix(), 'etc', 'diamond', 'collectors'),
                 paths['collectors_config'])

    disable_all_collectors(paths['collectors_config'])
    _set_diamond_service(ctx, os.path.join(paths['config'], CONFIG_NAME))


@operation
def uninstall(ctx, **kwargs):
    _unset_diamond_service(ctx)
    paths = ctx.instance.runtime_properties['diamond_paths']
    for path_name in _PATHS_TO_CLEAN_UP:
        delete_path(ctx, paths[path_name])
    delete_path(ctx, os.path.join(paths['config'], CONFIG_NAME))


@operation
def start(ctx, **kwargs):
    paths = ctx.instance.runtime_properties['diamond_paths']
    try:
        start_diamond(paths['config'])
    except OSError as e:
        raise exceptions.NonRecoverableError(
            'Starting diamond failed: {0}'.format(e))


@operation
def stop(ctx, **kwargs):
    conf_path = ctx.instance.runtime_properties['diamond_paths']['config']
    # letting the workflow engine handle this in case of errors
    # so no try/catch
    stop_diamond(conf_path)


@operation
def add_collectors(ctx, collectors_config, **kwargs):
    _ctx = get_host_ctx(ctx)
    paths = _ctx.runtime_properties['diamond_paths']

    enable_collectors(ctx,
                      collectors_config,
                      paths['collectors_config'],
                      paths['collectors'])

    restart_diamond(paths['config'])


@operation
def del_collectors(ctx, collectors_config, **kwargs):
    _ctx = get_host_ctx(ctx)
    paths = _ctx.runtime_properties['diamond_paths']

    disable_collectors(ctx, collectors_config,
                       paths['collectors_config'],
                       paths['collectors'])

    restart_diamond(paths['config'])


def start_diamond(conf_path):
    config_file = os.path.join(conf_path, CONFIG_NAME)
    if not os.path.isfile(config_file):
        raise exceptions.NonRecoverableError("Config file doesn't exists")

    return_code = call(['diamond', '--configfile', config_file])
    if return_code != 0:
        raise exceptions.NonRecoverableError('Diamond agent failed to start')

    for _ in range(DEFAULT_TIMEOUT):
        pid = get_pid(config_file)
        if pid and pid_exists(pid):
            return
        sleep(1)
    raise exceptions.NonRecoverableError('Diamond agent failed to start')


def stop_diamond(conf_path):
    config_file = os.path.join(conf_path, CONFIG_NAME)
    pid = get_pid(config_file)
    if pid:
        diamond_process = Process(pid)
        diamond_process.terminate()
        diamond_process.wait(timeout=DEFAULT_TIMEOUT)

        if diamond_process.is_running():
            raise exceptions.NonRecoverableError("Diamond couldn't be killed")
    else:
        raise exceptions.NonRecoverableError('Failed reading diamond pid file')


def restart_diamond(conf_dir):
    stop_diamond(conf_dir)
    start_diamond(conf_dir)


def get_pid(config_file):
    config = ConfigObj(infile=config_file, raise_errors=True)
    pid_path = config['server']['pid_file']
    try:
        with open(pid_path) as f:
            return int(f.read())
    except (IOError, ValueError):
        return None


def enable_collectors(ctx, collectors, config_path, collectors_path):
    for name, prop in collectors.items():
        if 'path' in prop.keys():
            collector_dir = os.path.join(collectors_path, name)
            os.mkdir(collector_dir)
            collector_file = os.path.join(collector_dir, '{0}.py'.format(name))
            ctx.download_resource(prop['path'], collector_file)

        config = prop.get('config', {})
        config.update({'enabled': True,
                       'hostname': '{0}.{1}.{2}'.format(get_host_id(ctx),
                                                        ctx.node.name,
                                                        ctx.instance.id)
                       })
        prop['config'] = config
        config_full_path = os.path.join(config_path, '{0}.conf'.format(name))
        write_config(config_full_path, prop.get('config', {}))


def disable_collectors(ctx, collectors, config_path, collectors_path):
    for name, prop in collectors.items():
        config_full_path = os.path.join(config_path, '{0}.conf'.format(name))
        if 'path' in prop.keys():
            collector_dir = os.path.join(collectors_path, name)
            rmtree(collector_dir)
            os.remove(config_full_path)
        else:
            original_collector = os.path.join(_prefix(), 'etc', 'diamond',
                                              'collectors',
                                              '{0}.conf'.format(name))
            copy(original_collector, config_path)
            config_full_path = os.path.join(config_path,
                                            '{0}.conf'.format(name))
            disable_collector(config_full_path)


def config_handlers(ctx, handlers, config_path, handlers_path):
    """
    create handler configuration files.
    copy over handler if path to file was provided.
    return list of active handlers.
    """
    if handlers is None:
        handlers = copy_objects.deepcopy(DEFAULT_HANDLERS)

        # If we do not have a real manager cloudify_agent is expected to be an
        # empty dict. This will be handled by get_broker_credentials.
        cloudify_agent = ctx.bootstrap_context.cloudify_agent

        broker_user, broker_pass, _ = utils.internal.get_broker_credentials(
            cloudify_agent
        )

        config_changes = {
            'server': cloudify_agent.broker_ip,
            'user': broker_user,
            'password': broker_pass,
        }

        handlers['cloudify_handler.cloudify.CloudifyHandler'][
            'config'].update(config_changes)

    elif not handlers:
        raise exceptions.NonRecoverableError('Empty handlers dict')

    for name, prop in handlers.items():
        if 'path' in prop.keys():
            handler_file = os.path.join(handlers_path,
                                        '{0}.py'.format(name.split('.')[-2]))
            ctx.download_resource(prop['path'], handler_file)

        path = os.path.join(config_path, '{0}.conf'.format(
            name.split('.')[-1]))
        write_config(path, prop.get('config', {}))

    return handlers.keys()


def write_config(path, properties):
    """
    write config file to path with properties. if file exists, properties
    will be appended
    """
    config = ConfigObj(infile=path)
    for key, value in properties.items():
        config[key] = value
    config.write()


def disable_all_collectors(path):
    """
    disables all collectors which configs are located at path
    """
    files = glob(os.path.join(path, '*.conf'))
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
        prefix = _calc_workdir()

    paths = {
        'config': os.path.join(prefix, 'etc'),
        'collectors_config': os.path.join(prefix, 'etc', 'collectors'),
        'collectors': os.path.join(prefix, 'collectors'),
        'handlers_config': os.path.join(prefix, 'etc', 'handlers'),
        'handlers': os.path.join(prefix, 'handlers'),
        'pid': os.path.join(prefix, 'var', 'run'),
        'log': os.path.join(prefix, 'var', 'log')
    }
    create_paths(paths)
    return paths


def create_paths(paths):
    for path in paths.values():
        if not os.path.exists(path):
            os.makedirs(path)


def create_config(path_prefix,
                  handlers,
                  interval,
                  paths):
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
                'hostname': None,
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
            'args': "('{0}', 'midnight', 1, 7)".format(
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
    """
    copy content of src folder into dest dir. content can be files
    or folders
    """
    for item in os.listdir(src):
        full_path = os.path.join(src, item)
        if os.path.isdir(full_path):
            copytree(full_path, os.path.join(dest, item))
        else:
            copy(full_path, dest)


def get_host_ctx(ctx):
    """
    helper method ..
    """
    host_id = get_host_id(ctx)
    host_node_instance = ctx._endpoint.get_node_instance(host_id)
    return host_node_instance


def get_host_id(ctx):
    ctx.instance._get_node_instance_if_needed()
    return ctx.instance._node_instance.host_id


def delete_path(ctx, path):
    try:
        if os.path.isdir(path):
            rmtree(path)
        else:
            os.remove(path)
    except OSError as e:
        if e.errno == os.errno.ENOENT:
            ctx.logger.info("Couldn't delete path: "
                            "{0}, already doesn't exist".format(path))
        else:
            raise


def _prefix():
    try:
        test_suffix = os.path.join('share', 'diamond', 'collectors')
        prefix = ctx.plugin.prefix
        if os.path.exists(os.path.join(prefix, test_suffix)):
            return prefix
        else:
            # This happens if diamond plugin is installed in the agent package.
            # In this case, the plugin.prefix dir will exist but will be empty.
            return sys.prefix
    except AttributeError:
        # Support older versions of cloudify-plugins-common
        return sys.prefix


def _calc_workdir():
    # Used to check if we are inside an agent environment
    agent_workdir = os.environ.get(constants.AGENT_WORK_DIR_KEY)
    if agent_workdir:
        try:
            workdir = ctx.plugin.workdir
        except AttributeError:
            # Support older versions of cloudify-plugins-common
            workdir = os.path.join(agent_workdir, 'diamond')
    else:  # Used by tests
        workdir = mkdtemp(prefix='cloudify-monitoring-')
    return workdir


def _get_agent_name(ctx):
    return ctx.instance.runtime_properties['cloudify_agent']['name']


def _get_service_name(ctx):
    return 'diamond_{0}'.format(_get_agent_name(ctx))


def _get_service_file_path(ctx):
    return os.path.join('/etc/init.d', _get_service_name(ctx))


def _set_diamond_service(ctx, config_file):
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    source = os.path.join(curr_dir, 'resources', 'diamond')
    target = _get_service_file_path(ctx)
    service_name = _get_service_name(ctx)
    diamond_path = '{0}/env/bin/diamond'.format(curr_dir.split('/env/', 1)[0])

    with open(source, 'r') as t:
        old_content = t.read()
    new_content = old_content.replace(
        '{{ CMD }}',
        '{0} --configfile {1}'.format(diamond_path, config_file))
    workdir = os.environ.get(constants.AGENT_WORK_DIR_KEY, '')
    new_content = new_content.replace('{{ WORK_DIR }}', workdir)
    new_content = new_content.replace(
        '{{ CLUSTER_SETTINGS_PATH }}',
        os.environ.get(CLUSTER_SETTINGS_PATH_KEY, ''),
    )
    with open(source, 'w') as t:
        t.write(new_content)

    call(['sudo', 'mv', source, target])
    call(['sudo', 'chmod', '555', target])
    with open(source, 'w') as t:
        t.write(old_content)

    if 'centos' in platform.platform().lower():
        call(['sudo', 'chkconfig', '--add', service_name])
    else:
        call(['sudo', 'update-rc.d', '-f', service_name, 'remove'])
        call(['sudo', 'update-rc.d', service_name, 'defaults'])
        call(['sudo', 'update-rc.d', service_name, 'enable'])


def _unset_diamond_service(ctx):
    service_name = _get_service_name(ctx)
    service_file_path = _get_service_file_path(ctx)
    if 'centos' in platform.platform().lower():
        call(['sudo', 'chkconfig', '--del', service_name])
    else:
        call(['sudo', 'update-rc.d', '-f', service_name, 'remove'])
    call(['sudo', 'rm', '-rf', service_file_path])
