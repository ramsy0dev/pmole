from pmole.algo import LZW


def test_algo_lzw() -> None:
    """
    Test the LZW algorithm
    """
    text_data = "hello there 123 world fire [cold] @cold im cold" \
        "world on fire i love love 123 not love hello hello there" \
            "world fire cold cold im cold 123 world on fire i love love not love hello"

    lzw = LZW()

    compressed_data = lzw.compress(
        data=text_data
    )

    decompressed_data = lzw.decompress(
        compressed_data=compressed_data
    )

    assert decompressed_data == text_data
