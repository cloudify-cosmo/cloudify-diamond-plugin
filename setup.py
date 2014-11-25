from setuptools import setup

setup(
    name='cloudify-diamond-plugin',
    version='3.1ga',
    author='Cloudify',
    author_email='cosmo-admin@gigaspaces.com',
    packages=['diamond_agent', 'cloudify_handler'],
    install_requires=['cloudify-plugins-common==3.1ga',
                      'diamond==3.5.0',
                      'ConfigObj==5.0.6',
                      'psutil==2.1.1'],
)
