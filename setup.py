from setuptools import setup

setup(
    name='cloudify-diamond-plugin',
    version='1.3.15',
    author='Cloudify',
    author_email='cosmo-admin@gigaspaces.com',
    description='Cloudify Diamond monitoring plugin',
    packages=['diamond_agent', 'cloudify_handler'],
    package_data={
        'diamond_agent': ['resources/diamond']
    },
    license='LICENSE',
    install_requires=['cloudify-common',
                      'diamond==3.5.0',
                      'ConfigObj==5.0.6',
                      'psutil==2.1.1'],
)
