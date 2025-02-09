
# Introduction

Pmole is a library for reproducing data from a single file.
Pmole uses `.cm` file extension to create a "origin" file that will be used to reproduced the compressed data.

# Installation

You can use **pip**:

```bash
pip install git+https://github.com/ramsy0dev/pmole
```

or you can build **from source**:

```bash
git clone https://github.com/ramsy0dev/pmole --depth=1
cd pmole
pip install -e .
```

# Usage

Pmole can be used as a library, as well as a cli tool.

* ## Library

```python
from pmole.algo import LZW

text_data = "Hello World"

lzw = LZW()

compressed_data = lzw.compress(
    data=text_data
)

decompressed_data = lzw.decompress(
    compressed_data=compressed_data
)
```

* ## CLI

Compressing a single file:

```bash
pmole compress --file-path /path/to/file
```

Compressing a directory:

```bash
pmole compress --dir-path /path/to/file
```

Decompressing:

```bash
pmole decompress --pm-file-path /path/to/output.pm
```

# Example

The .pm output file will look something like this:

```
:: .\data\hello_world.txt

-- 72 101 32 115 116 97 114 101 100 32 111 117 116 32 116 104 65537 119 105
-- 110 100 111 119 32 97 65548 65550 65537 115 110 65557 121 32 102 105 101 108 100
-- 46 32 65536 39 65544 98 101 101 110 65538 116 117 99 107 32 65554 65549 65551 32
-- 104 65546 115 65537 102 111 114 32 99 108 111 65595 65549 111 65559 32 109 111 110
-- 65550 65559 65555 65592 105 115 65545 110 108 65567 118 65570 65558 111 102 65590 65537 65546 116
-- 115 105 100 65552 65598 65572 32 119 97 65617 65550 114 65546 103 104 65627 65637 65554 65556
-- 119 65574 84 65551 65542 65637 65639 110 39 65548 109 65585 65645 116 65606 65595 101 65574 73
-- 65548 65638 65617 65609 65539 65620 32 106 117 65539 65646 65569 65571 65544 65553 65612 97 65582 111
-- 99 99 65639 105 65610 97 108 32 98 105 114 65544 65598 65538 109 65693 65694 65685 105
-- 65702 65694 119 65593 32 118 65581 65584 65542 65544 65554 65663 65679 65570 65572 65574 65 65617 65591
-- 99 65610 116 65554 117 65543 65605 65583 65541 65628 65547 65646 65553 65555 65557 44 65592 65634 65555
-- 101 65715 65592 65557 65608 65661 32 65602 110 103 65745 65742 65577 65695 65563 104 97 65586 108
-- 65731 65718 65562 65583 65580 65694 98 65541 65588 110 65631 65633 65646 65593 65677 101 [EOF]
```

And the decompressed data is:

```
He stared out the window at the snowy field. He'd been stuck in the house for close to a month and his only view of the outside world was through the window. There wasn't much to see. It was mostly just the field with an occasional bird or small animal who ventured into the field. As he continued to stare out the window, he wondered how much longer he'd be shackled to the steel bar inside the house
```

every file path starts with `**` while the compressed data of that file starts with `--`, the end of the compressed data is marked by `[EOF]`, that's where the pmole stops adding tokens to the buffer and decompresses it.

# LICENSE

[MIT](https://github.com/ramsy0dev/pmole/blob/main/LICENSE)
