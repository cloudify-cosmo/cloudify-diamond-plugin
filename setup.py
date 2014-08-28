from setuptools import setup

setup(
    name='cloudify-diamond-plugin',
    version='0.1',
    author='Cloudify',
    packages=['diamond_agent'],
    install_requires=['cloudify-plugins-common==3.0',
                      'diamond',
                      'configobj'],
    tests_require=["nose"],
)