import os
import sys
import glob
from subprocess import call
from cloudify.decorators import operation
from cloudify.utils import get_manager_ip
from configobj import ConfigObj

# TODO: place log in homedir
# TODO: paths cannot be unix only
# TODO: check if kill cannot be signal 9
# TODO: add possibility to configure default collectors from BP

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
    disable_all_collectors(ctx.runtime_properties['diamond_col_conf_path'])
    enable_collectors(ctx.runtime_properties['diamond_col_conf_path'],
                      ['CPUCollector', 'MemoryCollector',
                       'LoadAverageCollector', 'DiskUsageCollector'])

    config_cloudify_handler(
        os.path.join(ctx.runtime_properties['diamond_hdl_conf_path'],
                     'CloudifyHandler.con'))


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


def enable_collector(path, collector):
    conf_path = os.path.join(path, collector + '.conf')
    config = ConfigObj(infile=conf_path, file_error=True)
    config['enabled'] = True
    config.write()


def disable_collector(path, collector):
    conf_path = os.path.join(path, collector + '.conf')
    config = ConfigObj(infile=conf_path, file_error=True)
    config['enabled'] = False
    config.write()


def enable_collectors(path, collectors):
    for collector in collectors:
        enable_collector(path, collector)


def disable_all_collectors(path):
    files = glob.glob(os.path.join(path, '*.conf'))
    for f in files:
        collector = os.path.splitext(os.path.basename(f))[0]
        disable_collector(path, collector)


def config_cloudify_handler(config_path):
    handler_config = {
        'rmq_server': get_manager_ip(),
        'rmq_port': 5672,
        'rmq_exchange': 'diamond',
        'rmq_user': '',
        'rmq_password': '',
        'rmq_vhost': '',
        'rmq_exchange_type': 'fanout',
        'rmq_durable': False
    }
    config = ConfigObj(handler_config)
    config.filename = config_path
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
