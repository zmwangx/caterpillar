#!/usr/bin/env python3

import pathlib

import setuptools


HERE = pathlib.Path(__file__).resolve().parent
with HERE.joinpath("src/caterpillar/version.py").open(encoding="utf-8") as fp:
    exec(fp.read())
with HERE.joinpath("README.md").open(encoding="utf-8") as fp:
    long_description = fp.read()

setuptools.setup(
    name="caterpillar-hls",
    version=__version__,
    description="Hardened HLS merger",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/zmwangx/caterpillar",
    author="Zhiming Wang",
    author_email="zmwangx@gmail.com",
    python_requires=">=3.6",
    license="MIT",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Multimedia :: Video",
        "Topic :: Multimedia :: Video :: Conversion",
    ],
    keywords="HLS streaming m3u8 concatenate merge",
    package_dir={"": "src"},
    packages=["caterpillar"],
    install_requires=["xdgappdirs>=1.4.4.3", "click", "m3u8", "peewee", "requests"],
    extras_require={"dev": ["black", "flake8", "mypy", "pylint", "pytest", "tox"]},
    entry_points={"console_scripts": ["caterpillar=caterpillar.caterpillar:main"]},
)
