from setuptools import setup

setup(
    name='cloudify-diamond-plugin',
    version='1.1a3',
    author='Cloudify',
    author_email='cosmo-admin@gigaspaces.com',
    packages=['diamond_agent', 'cloudify_handler'],
    install_requires=['cloudify-plugins-common==3.1a3',
                      'diamond==3.4.421',
                      'ConfigObj==5.0.6'],
)