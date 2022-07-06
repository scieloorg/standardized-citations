#!/usr/bin/env python
from setuptools import setup, find_packages


install_requires = [
    'aiohttp==3.7.3',
    'articlemetaapi==1.26.7',
    'asyncio==3.4.3',
    'lxml==4.9.1',
    'pymongo==3.11.3',
    'xmltodict==0.12.0',
    'xylose==1.35.4',
]

setup(
    name="standardized-citations",
    version='0.1',
    description="The SciELO Standardization Tools",
    author="SciELO",
    author_email="scielo-dev@googlegroups.com",
    license="BSD",
    url="https://github.com/scieloorg/standardized-citations",
    keywords='cited references, normalization, deduplication',
    maintainer_email='rafael.pezzuto@gmail.com',
    packages=find_packages(),
    install_requires=install_requires,
    entry_points="""
    [console_scripts]
    normalize=proc.normalize:main
    crossref=proc.crossref:main
    """
)
