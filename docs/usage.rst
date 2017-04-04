.. highlight:: yaml

Usage
=====

Interfaces
----------

Two interfaces are involved in setting up a monitoring agent on a machine:

* ``cloudify.interfaces.monitoring_agent`` - The interface in charge of installing, starting stopping and uninstalling the agent.
* ``cloudify.interfaces.monitoring`` - The interface in charge of configuring the monitoring agent.

The :ref:`example` shows how the Diamond plugin maps to these interfaces.

.. _global_config:

Global config
-------------

The Diamond agent has a number of configuration sections, some of which are global while other are relevant to specific components.
It is possible to pass a `global config <https://github.com/BrightcoveOS/Diamond/blob/v3.5/conf/diamond.conf.example>`_ setting via the ``install`` operation::

    interfaces:
      cloudify.interfaces.monitoring_agent:
        install:
          implementation: diamond.diamond_agent.tasks.install
          inputs:
            diamond_config:
              interval: 10

In the above example we set the
`global poll interval <https://github.com/BrightcoveOS/Diamond/blob/v3.5/conf/diamond.conf.example#L176>`_
to 10 seconds
(each collector will be polled for data every 10 seconds).

Handler
.......

The Handler's job in Diamond is to output the collected data to different destinations.
By default,
the Diamond plugin will setup a custom handler which will output the collected metrics to Cloudify's manager.

It is possible to set an alternative handler in case you want to output data to a different destination::

    interfaces:
      cloudify.interfaces.monitoring_agent:
        install:
          implementation: diamond.diamond_agent.tasks.install
          inputs:
            diamond_config:
              handlers:
                diamond.handler.graphite.GraphiteHandler:
                  host: graphite.example.com
                  port: 2003
                  timeout: 15

In the example above we configured a `handler for Graphite <https://github.com/BrightcoveOS/Diamond/wiki/handler-GraphiteHandler>`_.

.. note::
    If you wish to add your own handler but maintain Cloudify's default handler, see `this <https://github.com/cloudify-cosmo/cloudify-diamond-plugin/blob/1.2/diamond_agent/tasks.py#L38>`_.


Collectors config
-----------------

Collectors are Diamond's data fetchers. Diamond comes with a large number of `built-in collectors <https://github.com/BrightcoveOS/Diamond/wiki/Collectors>`_.

Collectors are added using the ``install`` operation of the ``cloudify.interfaces.monitoring`` interface::

    interfaces:
      cloudify.interfaces.monitoring:
        start:
          implementation: diamond.diamond_agent.tasks.add_collectors
          inputs:
            collectors_config:
              CPUCollector: {}
              DiskUsageCollector:
                config:
                  devices: x?vd[a-z]+[0-9]*$
              MemoryCollector: {}
              NetworkCollector: {}

In the example above we configure 4 collectors:

* A `CPUCollector <https://github.com/BrightcoveOS/Diamond/wiki/collectors-CPUCollector>`_,
* A `DiskUsageCollector <https://github.com/BrightcoveOS/Diamond/wiki/collectors-DiskUsageCollector>`_,
* A `MemoryCollector <https://github.com/BrightcoveOS/Diamond/wiki/collectors-MemoryCollector>`_ and
* A `NetworkCollector <https://github.com/BrightcoveOS/Diamond/wiki/collectors-NetworkCollector>`_.

It is also possible to add a collector-specific configuration
via the ``config`` dictionary (as with ``DiskUsageCollector``).
If ``config`` is not provided,
the collector will use its default settings.

.. admonition:: Default config values
    :class: note

    Config values are left with their default values unless explicitly overridden.

Custom Collectors & Handlers
----------------------------

Collectors & Handlers are essentially Python modules
that implement specific Diamond interfaces.

It is possible to create your own collectors or handlers
and configure them in Diamond.
The example below shows how to upload a custom collector::

    collectors_config:
      ExampleCollector:
        path: collectors/example.py
        config:
          key: value

``path`` points to the location of your custom collector
(relative location to the blueprint's directory).
``ExampleCollector`` is the name of the main class inside
``example.py`` that extends ``diamond.collector.Collector``.

Providing a custom handler is done in a similar manner::

    diamond_config:
      handlers:
        example_handler.ExampleHandler:
          path: handlers/example_handler.py
          config:
            key: value

where ``example_handler`` is the name of the file and ``ExampleHandler`` is the name of the class that extends ``diamond.handler.Handler``.

Note that handlers are configured as part of the :ref:`global_config`.

.. note::
    Diamond's wide range of collectors,
    handlers and extensibility possibilities comes with a price -
    It's not always promised that you'll have all the required
    dependencies built into your instance.

    For example,
    you might find yourself trying to use the ``MongoDBCollector`` collector
    which imports the `pymongo <http://api.mongodb.org/python/current/>`_
    module internally.
    Since ``pymongo`` is not a part of the Python standard library,
    this will fail unless you will install it separately.
    See the
    `nodecellar example <https://github.com/cloudify-cosmo/cloudify-nodecellar-example>`_
    for more information.
