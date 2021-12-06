import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="lsif-py",
    version="0.0.1",
    author="Eric Fritz",
    author_email="eric@sourcegraph.com",
    description="Python LSIF Indexer",
    entry_points={
        "console_scripts": ["lsif-py=lsif_indexer.indexer:lsif_py"],
    },
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sourcegraph/lsif-py",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=["jedi", "pydantic", "stringcase", "click"],
)
