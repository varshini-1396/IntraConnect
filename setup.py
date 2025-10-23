"""
Setup script for LAN Collaboration System
"""

from setuptools import setup, find_packages

setup(
    name="lan-collaboration-system",
    version="1.0.0",
    description="Multi-user LAN communication application",
    author="Varshini",
    packages=find_packages(),
    install_requires=[
        'opencv-python>=4.8.0',
        'pyaudio>=0.2.13',
        'Pillow>=10.0.0',
        'numpy>=1.24.0',
    ],
    python_requires='>=3.8',
    entry_points={
        'console_scripts': [
            'lan-server=server.server:main',
            'lan-client=client.client:main',
        ],
    },
)