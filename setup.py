#!/usr/bin/env python3

import pathlib

import setuptools


HERE = pathlib.Path(__file__).resolve().parent
with open(HERE / 'src/caterpillar/version.py') as fp:
    exec(fp.read())

setuptools.setup(
    name='caterpillar-hls',
    version=__version__,
    description='Hardened HLS merger',
    long_description='See https://github.com/zmwangx/caterpillar#readme.',
    url='https://github.com/zmwangx/caterpillar',
    author='Zhiming Wang',
    author_email='zmwangx@gmail.com',
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Multimedia :: Video',
        'Topic :: Multimedia :: Video :: Conversion',
    ],
    keywords='HLS streaming m3u8 concatenate merge',
    package_dir={'': 'src'},
    packages=['caterpillar'],
    install_requires=['appdirs', 'chardet', 'click', 'm3u8', 'peewee', 'requests'],
    extras_require={
        'dev': ['flake8', 'mypy', 'pylint', 'pytest', 'tox'],
    },
    entry_points={
        'console_scripts': [
            'caterpillar=caterpillar.caterpillar:main',
        ],
    },
)
