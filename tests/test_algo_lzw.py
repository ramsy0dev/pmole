
from pmole.algo import LZW



def test_algo_lzw() -> None:
    """
    Test the LZW algorithm
    """
    text_data = open("./data/test_file_10kb_words.txt", "r", encoding="utf-8").read()

    lzw = LZW()
    data = text_data

    print(data)
    compressed_data = lzw.compress(
        data=data
    )

    decompressed_data = lzw.decompress(
        compressed_data=compressed_data
    )

    # assert text_data == compressed_data
