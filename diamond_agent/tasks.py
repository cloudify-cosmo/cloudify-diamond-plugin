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

import json
import os
import sys
import platform
from glob import glob
from time import sleep
import copy as copy_objects
from subprocess import call
from tempfile import mkdtemp
from shutil import copytree, copy, rmtree

from configobj import ConfigObj
from psutil import pid_exists, Process, Error

from cloudify import ctx
from cloudify.decorators import operation
from cloudify import exceptions, constants
from cloudify.constants import CLUSTER_SETTINGS_PATH_KEY

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

AGENT_WORK_DIR_KEY = 'AGENT_WORK_DIR'


@operation
def install(**_):
    ctx.logger.warn(
        'Diamond plugin functionality is deprecated in Cloudify 5. '
        'Doing nothing.')


@operation
def uninstall(**_):
    ctx.logger.warn(
        'Diamond plugin functionality is deprecated in Cloudify 5. '
        'Doing nothing.')


@operation
def start(**_):
    ctx.logger.warn(
        'Diamond plugin functionality is deprecated in Cloudify 5. '
        'Doing nothing.')


@operation
def stop(**_):
    ctx.logger.warn(
        'Diamond plugin functionality is deprecated in Cloudify 5. '
        'Doing nothing.')


@operation
def add_collectors(**_):
    ctx.logger.warn(
        'Diamond plugin functionality is deprecated in Cloudify 5. '
        'Doing nothing.')


@operation
def del_collectors(**_):
    ctx.logger.warn(
        'Diamond plugin functionality is deprecated in Cloudify 5. '
        'Doing nothing.')


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
        need_kill = True
        try:
            diamond_process = Process(pid)
            diamond_process.terminate()
            diamond_process.wait(timeout=DEFAULT_TIMEOUT)
            need_kill = diamond_process.is_running()
        except Error:
            pass
        if need_kill:
            call(["sudo", "kill", str(pid)])
            # diamond deletes the pid file, even if killed
            for __ in range(DEFAULT_TIMEOUT):
                pid = get_pid(config_file)
                if not pid:
                    return
                sleep(1)
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
        if 'path' in prop:
            collector_dir = os.path.join(collectors_path, name)
            if os.path.exists(collector_dir):
                ctx.logger.warn(
                    'Collector path {path} already existed, removing.'.format(
                        path=collector_dir,
                    )
                )
                rmtree(collector_dir)
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
        if 'path' in prop:
            collector_dir = os.path.join(collectors_path, name)
            try:
                rmtree(collector_dir)
            except OSError:
                pass
            else:
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

        agent_workdir = _calc_workdir()
        conf_file_path = os.path.join(agent_workdir, 'broker_config.json')
        if os.path.isfile(conf_file_path):
            with open(conf_file_path) as conf_handle:
                agent_config = json.load(conf_handle)

            config_changes = {
                'server': agent_config['broker_hostname'],
                'user': agent_config['broker_username'],
                'password': agent_config['broker_password'],
                'broker_cert_path': agent_config['broker_cert_path'],
                'broker_ssl_enabled': agent_config['broker_ssl_enabled'],
            }

            handlers['cloudify_handler.cloudify.CloudifyHandler'][
                'config'].update(config_changes)
    elif not handlers:
        raise exceptions.NonRecoverableError('Empty handlers dict')

    for name, prop in handlers.items():
        if 'path' in prop:
            handler_file = os.path.join(handlers_path,
                                        '{0}.py'.format(name.split('.')[-2]))
            ctx.download_resource(prop['path'], handler_file)

        path = os.path.join(config_path, '{0}.conf'.format(
            name.split('.')[-1]))
        write_config(path, prop.get('config', {}))

    return list(handlers.keys())


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
    for _, path in paths.items():
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
            'args': "('{0}', 'midnight', 1, 2)".format(
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
            full_dest = os.path.join(dest, item)
            if os.path.exists(full_dest):
                rmtree(full_dest)
            copytree(full_path, full_dest)
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
        prefix = ctx.plugin.prefix
    except TypeError:
        prefix = ''

    try:
        test_suffix = os.path.join('share', 'diamond', 'collectors')
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
    agent_workdir = os.environ.get(AGENT_WORK_DIR_KEY)
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
    agent = _get_agent(ctx)
    return agent.get('name', get_host_id(ctx))


def _get_agent_user(ctx):
    agent = _get_agent(ctx)
    return agent.get('user')


def _get_agent(ctx):
    return ctx.instance.runtime_properties.get(
        'cloudify_agent',
        ctx.instance.runtime_properties.get(
            'agent_config',
            ctx.node.properties.get(
                'agent_config', {})))


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
    workdir = os.environ.get(AGENT_WORK_DIR_KEY, '')
    new_content = new_content.replace('{{ WORK_DIR }}', workdir)
    new_content = new_content.replace(
        '{{ CLUSTER_SETTINGS_PATH }}',
        os.environ.get(CLUSTER_SETTINGS_PATH_KEY, ''),
    )
    new_content = \
        new_content.replace(
            '{{ AGENT_USER }}',
            _get_agent_user(ctx))

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
