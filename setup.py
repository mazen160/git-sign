from setuptools import setup

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="git-sign",
    version="0.1.0",
    description="Re-sign commits on a branch with your GPG/SSH key.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Mazin Ahmed",
    author_email="mazin@mazinahmed.net",
    url="https://github.com/mazen160/git-sign",
    scripts=["git-sign.py"],
    python_requires=">=3.7",
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Version Control :: Git",
    ],
)
