#!/usr/bin/env python3

import os
from distutils.core import setup

requirements_dir_path = os.path.split(os.path.abspath(__file__))[0]
requirements_file_path = os.path.join(requirements_dir_path, 'requirements.txt')

with open(requirements_file_path) as f:
    requirements = [r for r in [line.strip() for line in f] if r]

setup(
    name='cc-server',
    version='0.12',
    summary='Curious Containers is an application management service that is able to execute thousands of '
            'short-lived applications in a distributed cluster by employing Docker container engines.',
    description='Curious Containers is an application management service that is able to execute thousands of '
                'short-lived applications in a distributed cluster by employing Docker container engines. In this '
                'context applications are atomic entities taking files and parameters as input and producing new files '
                'as output. They are short-lived in a sense that they calculate something and terminate as soon as all '
                'results have been produced. Curious Containers supports scientific use cases like biomedical analysis '
                'and reproducible research by providing standardized methods for packaging applications and executing '
                'them in a compute environment. Therefore application dependencies are added to a compatible Docker '
                'container image, including all necessary bin, binaries and configurations.',
    author='Christoph Jansen, Michael Witt, Maximilian Beier',
    author_email='Christoph.Jansen@htw-berlin.de',
    url='https://github.com/curious-containers/cc-server',
    packages=[
        'cc_server',
        'cc_server.commons',
        'cc_server.log_service',
        'cc_server.master_service',
        'cc_server.master_service.scheduling_strategies',
        'cc_server.web_service',
    ],
    entry_points={
        'console_scripts': ['cc-server=cc_server:main']
    },
    scripts=[
        'bin/cc-create-user',
        'bin/cc-create-user-non-interactive',
        'bin/cc-drop-db'
    ],
    license='Apache-2.0',
    platforms=['any'],
    install_requires=requirements
)
