# Python LSIF Indexer

🚨 This implementation is in its infancy and conforms to the [0.4.0 draft of the LSIF spec](https://github.com/Microsoft/language-server-protocol/blob/master/indexFormat/specification.md).

## Language Server Index Format

The purpose of the Language Server Index Format (LSIF) is to define a standard format for language servers and related tools to dump their knowledge about a workspace. The dump is basically a pre-computed set of responses that a language server *would* send back about a particular range of source code.

## Quickstart

Simply run the provided shell script wrapper.

```
$ ./lsif-py lsif_indexer
Indexing file lsif_indexer/analysis.py
Indexing file lsif_indexer/index.py
Indexing file lsif_indexer/__init__.py
Indexing file lsif_indexer/consts.py
Indexing file lsif_indexer/script.py
Indexing file lsif_indexer/emitter.py

Processed in 2834.89ms
```

Verbose logging can be enabled with `-v`. The dump file is `data.lsif` by default, but can be changed via the `-o <filename>` flag.
