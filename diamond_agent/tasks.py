import os
import sys
from psutil import pid_exists
from subprocess import call
from cloudify.decorators import operation
from configobj import ConfigObj

# TODO: place log in homedir
# TODO: add cloudify handler & configure it
# TODO: paths cannot be unix only

@operation
def install(ctx, **kwargs):
    ctx.runtime_properties['diamond_config_path'] = \
        os.path.join(sys.prefix, 'etc/diamond/diamond.conf')

    ctx.runtime_properties['diamond_col_conf_path'] = \
        os.path.join(sys.prefix, 'etc/diamond/collectors')

    ctx.runtime_properties['diamond_col_path'] = \
        os.path.join(sys.prefix, 'share/diamond/collectors')

    ctx.runtime_properties['diamond_hdl_conf_path'] = \
        os.path.join(sys.prefix, 'etc/diamond/handlers')

    ctx.runtime_properties['diamond_handlers'] = \
        'cloudify_handler.cloudify.CloudifyHandler'

    create_config(ctx)


@operation
def uninstall(ctx, **kwargs):
    pass


@operation
def start(ctx, **kwargs):
    cmd = 'diamond --configfile {}'\
        .format(ctx.runtime_properties['diamond_config_path'])
    try:
        call(cmd.split())
    except OSError:
        ctx.logger.info('Failed starting Diamond')


@operation
def stop(ctx, **kwargs):
    with open ('/tmp/diamond.pid') as f:
        pid = int(f.read())

    try:
        os.kill(pid, 9)
    except OSError:
        ctx.logger.info('Failed stopping Diamond')

@operation
def enable_collector(ctx, collector_name, **kwargs):
    conf_path = os.path.join([ctx.runtime_properties['diamond_col_conf_path'],
                              collector_name + '.conf'])
    try:
        config = ConfigObj(infile=conf_path, file_error=True)
    except IOError:
        ctx.logger.info('Collector {} not found. '
                        'Enable failed'.format(collector_name))
    else:
        config['enabled'] = True
        config.write()


@operation
def disable_collector(ctx, collector_name, **kwargs):
    conf_path = os.path.join([ctx.runtime_properties['diamond_col_conf_path'],
                              collector_name + '.conf'])
    try:
        config = ConfigObj(infile=conf_path, file_error=True)
    except IOError:
        ctx.logger.info('Collector {} not found. '
                        'Disable failed'.format(collector_name))
    else:
        config['enabled'] = False
        config.write()


def create_config(ctx):
    """
    Create config file and write it into config_path
    """
    server_config = {
        'server': {
            'handlers': ctx.runtime_properties['diamond_handlers'],
            'user': '',
            'group': '',
            'pid_file': '/tmp/diamond.pid',
            'collectors_path': ctx.runtime_properties['diamond_col_path'],
            'collectors_config_path':
                    ctx.runtime_properties['diamond_col_conf_path'],
            'handlers_config_path':
                    ctx.runtime_properties['diamond_hdl_conf_path'],
            'handlers_path': '/usr/share/diamond/handlers/',
            'collectors_reload_interval': 3600,
        },
        'handlers': {
            'keys': 'rotated_file',
            'default': {},
        },
        'collectors': {
            'default': {
                'hostname': '.'.join([ctx.node_name, ctx.node_id]),
                'path_prefix': ctx.deployment_id,
                'interval': ctx.properties['interval'],
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
            # 'args': '({}, {}, 1, 7)'.format('/tmp/diamond.log', 'midnight'),
            'args': "('/tmp/diamond.log', 'midnight', 1, 7)",
        },
        'formatter_default': {
            'format': '[%(asctime)s] [%(threadName)s] %(message)s',
            'datefmt': '',
        },
    }
    config = ConfigObj(server_config, indent_type='', list_values=False)
    config.filename = ctx.runtime_properties['diamond_config_path']
    config.write()
