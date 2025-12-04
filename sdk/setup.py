"""
Setup script for runagent-pulse SDK
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="runagent-pulse",
    version="0.1.0",
    author="RunAgent",
    description="Lightweight scheduling service for AI agents",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.31.0",
        "python-dateutil>=2.8.2",
        "croniter>=2.0.1",
        "pytz>=2023.3",
    ],
    extras_require={
        "langgraph": ["langgraph>=0.0.1"],
        "crewai": ["crewai>=0.1.0"],
        "all": ["langgraph>=0.0.1", "crewai>=0.1.0"],
    },
)


