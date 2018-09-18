from setuptools import setup, find_packages

setup(
    name='flashtool',
    version='1.0.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
            'libusb1',
    ],
    entry_points={
        'console_scripts': [
            'flashtool = flashtool:main',
        ],
    },
)
