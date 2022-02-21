# Python LSIF Indexer ![](https://img.shields.io/badge/status-development-yellow)

🚨 This implementation is in its infancy and conforms to the [0.4.0 draft of the LSIF spec](https://github.com/Microsoft/language-server-protocol/blob/master/indexFormat/specification.md).

## Language Server Index Format

The purpose of the Language Server Index Format (LSIF) is to define a standard format for language servers and related tools to dump their knowledge about a workspace. The dump is basically a pre-computed set of responses that a language server *would* send back about a particular range of source code.

## Requirements

This package uses [poetry](https://python-poetry.org/docs/) for dependency management and packaging. See docs for installation instructions.

The indexer requires Python 3.x. Poetry will create and manage a virtual environment for you.

## Basic Usage

To run the indexer, simply run the provided shell script wrapper and provide a workspace directory to be indexed.

```
$ poetry run lsif-py lsif_indexer
Indexing file lsif_indexer/analysis.py
Indexing file lsif_indexer/index.py
Indexing file lsif_indexer/__init__.py
Indexing file lsif_indexer/consts.py
Indexing file lsif_indexer/script.py
Indexing file lsif_indexer/emitter.py

Processed in 2834.89ms
```

Verbose logging can be enabled with `-v`. The dump file is `data.lsif` by default, but can be changed via the `-o <filename>` flag.

### Installation on macOS

On macOS, where the system Python on macOS is still 2.7.x, you can install Python 3 via [Homebrew](https://brew.sh/):

```shell
brew install python@3
```

You may need to write `pip3` instead of `pip` to get the correct version.
