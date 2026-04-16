from setuptools import find_packages, setup


setup(
    name="videotransdub",
    version="0.2.0",
    description="Production-grade headless video translation/dubbing pipeline",
    package_dir={"": "src"},
    packages=find_packages("src"),
    install_requires=[
        "pydantic>=2,<3",
        "PyYAML>=6,<7",
    ],
    extras_require={
        "asr": [
            "faster-whisper>=1.0.0",
            "ctranslate2>=4.0.0",
        ],
        "tts": [
            "edge-tts>=6.1.0",
        ],
        "inpaint": [
            "opencv-python-headless>=4.8.0",
        ],
        "ui": [
            "streamlit>=1.30.0",
            "psutil>=5.9.0",
        ],
        "qwen": [
            "dashscope>=1.20.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "videotransdub=videotransdub.cli:main",
            "videotransdub-ui=videotransdub.launch:main",
        ],
    },
)
