from setuptools import setup

setup(
    name='cloudify-diamond-plugin',
    version='1.3.2',
    author='Cloudify',
    author_email='cosmo-admin@gigaspaces.com',
    description='Cloudify Diamond monitoring plugin',
    packages=['diamond_agent', 'cloudify_handler'],
    license='LICENSE',
    install_requires=['cloudify-plugins-common>=3.3.1',
                      'diamond==3.5.0',
                      'ConfigObj==5.0.6',
                      'psutil==2.1.1'],
)
