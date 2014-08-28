import os
import sys
from cloudify.decorators import operation
from configobj import ConfigObj

# how do I run diamond? who executes it?
# how do we make diamond run on reboot?
# how do i restart diamond process? and make sure only one instance is running?

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

    ctx.runtime_properties['diamond_handlers'] = 'Cloudify'

    create_config(ctx, path=ctx.runtime_properties['diamond_config_path'])


@operation
def uninstall(ctx, **kwargs):
    pass


@operation
def start(ctx, **kwargw):
    pass


@operation
def stop(ctx, **kwargs):
    pass


@operation
def enable_collector(ctx, collector_name, **kwargs):
    conf_path = os.path.join([ctx.runtime_properties['diamond_col_conf_path'],
                              collector_name + '.conf'])
    try:
        config = ConfigObj(infile=conf_path, file_error=True)
    except IOError:
        ctx.logger('Collector {} not found. '
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
        ctx.logger('Collector {} not found. '
                   'Disable failed'.format(collector_name))
    else:
        config['enabled'] = False
        config.write()


def create_config(ctx, path):
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
            'keys': 'rotated files',
            'default': {},
        },
        'collectors': {
            'hostname': '.'.join([ctx.node_name, ctx.node_id]),
            'path_prefix': ctx.deployment_id,
            'interval': ctx.properties['interval'],
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
            'args': "('/tmp/diamond.log', 'midnight', 1, 7)"
        }
    }
    config = ConfigObj(server_config)
    config.filename = path
    config.write()
