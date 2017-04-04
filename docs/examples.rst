.. highlight:: yaml

.. _example:

Example
=======

The following example shows the configuration options of the plugin.::

    node_types:
      my_type:
        derived_from: cloudify.nodes.WebServer
        properties:
          collectors_config: {}

    node_templates:
      vm:
        type: cloudify.nodes.Compute
        interfaces:
          cloudify.interfaces.monitoring_agent:
            install:
              implementation: diamond.diamond_agent.tasks.install
              inputs:
                diamond_config:
                  interval: 10
            start: diamond.diamond_agent.tasks.start
            stop: diamond.diamond_agent.tasks.stop
            uninstall: diamond.diamond_agent.tasks.uninstall

      app:
        type: my_type
        properties:
          collectors_config:
            CPUCollector: {}
            DiskUsageCollector:
              config:
                devices: x?vd[a-z]+[0-9]*$
            MemoryCollector: {}
            NetworkCollector: {}
            ExampleCollector:
              path: collectors/example.py
              config:
                  key: value
        interfaces:
          cloudify.interfaces.monitoring:
            start:
              implementation: diamond.diamond_agent.tasks.add_collectors
              inputs:
                collectors_config: { get_propery: [SELF, collectors_config] }
            stop:
              implementation: diamond.diamond_agent.tasks.del_collectors
              inputs:
                collectors_config: { get_propery: [SELF, collectors_config] }
        relationships:
          - type: cloudify.relationships.contained_in
             target: node
