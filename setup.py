from setuptools import setup, find_packages

setup(
    name="tts-generator",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "google-genai>=1.0.0",
        "elevenlabs>=1.0.0",
        "pydub>=0.25.1",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "tts-generator=tts_generator.cli:main",
        ],
    },
    python_requires=">=3.10",
)
