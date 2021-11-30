# adapted over https://github.com/pypa/sampleproject/blob/master/setup.py

from setuptools import setup, find_packages
from os import path
import pytimefliplib

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md')) as f:
    long_description = f.read()

with open(path.join(here, 'requirements/requirements-base.in')) as f:
    requirements = f.readlines()

with open(path.join(here, 'requirements/requirements.in')) as f:
    requirements_dev = f.readlines()[1:]

setup(
    name='pytimefliplib',
    version=pytimefliplib.__version__,

    # Description
    description=pytimefliplib.__doc__,
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords='website',

    project_urls={
        'Bug Reports': 'https://github.com/pierre-24/pytimefliplib/issues',
        'Source': 'https://github.com/pierre-24/pytimefliplib/',
    },

    author='Pierre Beaujean',

    # Classifiers
    classifiers=[
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions:
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],

    packages=find_packages(),
    python_requires='>=3.6',

    include_package_data=True,

    # requirements
    install_requires=requirements,

    extras_require={  # Optional
        'dev': requirements_dev,
    },

    entry_points={
        'console_scripts': [
            'timeflip-check = pytimefliplib.scripts.check:main',
            'timeflip-clear-history = pytimefliplib.scripts.clear_history:main',
            'timeflip-discover = pytimefliplib.scripts.discover:main',
            'timeflip-set-name = pytimefliplib.scripts.set_name:main',
            'timeflip-set-passwd = pytimefliplib.scripts.set_password:main'
        ]
    },
)
