from setuptools import setup, Extension, find_packages

RELEASE_VERSION = '0.0.4'

setup(
    name='pychatangobot',
    version=RELEASE_VERSION,
    url='https://github.com/dozymoe/PyChatangoBot',
    download_url='https://github.com/dozymoe/PyChatangoBot/tarball/' +\
            RELEASE_VERSION,

    author='Fahri Reza',
    author_email='dozymoe@gmail.com',
    description='asyncio implementation of Chatango bot (ch.py).',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    platforms='any',
    license='MIT',
    install_requires=[
        "aiohttp",
        "bleach",
        "pycircularbuffer",
    ],
    ext_modules=[],
)

print("Visit https://github.com/dozymoe/PyChatangoBot for example run-bot scripts.")
