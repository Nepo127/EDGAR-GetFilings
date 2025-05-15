"""
Setup script for EDGAR Data Extractor
This script creates a simple installation for the EDGAR Data Extractor.
"""

# from setuptools import setup, find_packages
# setup(
#     name="edgar_data_extractor",
#     version="1.0.0",
#     description="Tools for downloading and parsing SEC EDGAR filings",
#     author="Horia & Matilda",
#     packages=find_packages(),  # This will find app_utils, edgar_downloader, and edgar_parser
#     install_requires=[
#         # Core dependencies shared by all packages
#         "requests>=2.25.0",
#         "tomli>=2.0.0; python_version < '3.11'",
        
#         # Parser-specific dependencies
#         "beautifulsoup4>=4.9.0",
#         "lxml>=4.6.0",
#         "pandas>=1.0.0",
#         "chardet>=3.0.0",
#     ],
#     python_requires='>=3.7',
#     entry_points={
#         'console_scripts': [
#             # Command-line tools
#             'edgar-parser=edgar_parser:main',
#             #'edgar-downloader=edgar_downloader:main',
#             #'edgar-tool=main:main',  # The main script entry point
#         ],
#     },
#     classifiers=[
#         "Development Status :: 4 - Beta",
#         "Intended Audience :: Financial and Insurance Industry",
#         "License :: OSI Approved :: MIT License",
#         "Programming Language :: Python :: 3",
#         "Programming Language :: Python :: 3.7",
#         "Programming Language :: Python :: 3.8",
#         "Programming Language :: Python :: 3.9",
#         "Programming Language :: Python :: 3.10",
#         "Programming Language :: Python :: 3.11",
#         "Topic :: Office/Business :: Financial",
#     ],
# )

from setuptools import setup, find_packages

# Debug: Print what packages are found
packages = find_packages()
print(f"Found packages: {packages}")

setup(
    name="edgar_data_extractor",
    version="1.0.0",
    description="Tools for downloading and parsing SEC EDGAR filings",
    author="Horia & Matilda",
    packages=packages,  # Use all discovered packages
    install_requires=[
        # Core dependencies
        "requests>=2.25.0",
        "tomli>=2.0.0; python_version < '3.11'",
        
        # Parser-specific dependencies
        "beautifulsoup4>=4.9.0",
        "lxml>=4.6.0",
        "pandas>=1.0.0",
        "chardet>=3.0.0",
    ],
    python_requires='>=3.7',
    entry_points={
        'console_scripts': [
            # Include both underscore and hyphen versions to be safe
            'edgar_parser=edgar_parser:main',
            'edgar-parser=edgar_parser:main',
        ],
    },
    # Include package data (like config files)
    package_data={
        '': ['*.toml'],  # Include all .toml files
    },
    # Make sure the package is zip_safe=False for reliable imports
    zip_safe=False,
)