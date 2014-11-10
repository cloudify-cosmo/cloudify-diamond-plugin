from setuptools import setup

setup(
    name='cloudify-diamond-plugin',
    version='1.1rc2',
    author='Cloudify',
    author_email='cosmo-admin@gigaspaces.com',
    packages=['diamond_agent', 'cloudify_handler'],
    install_requires=['cloudify-plugins-common==3.1rc2',
                      'diamond==3.5.0',
                      'ConfigObj==5.0.6',
                      'psutil==2.1.1'],
)
