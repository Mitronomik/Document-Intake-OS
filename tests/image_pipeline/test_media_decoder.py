from document_intake.image_pipeline.media_decoder import dhash64, dhash64_hamming_distance


def test_dhash64_vectors_and_distance():
    ascending = bytes([0,1,2,3,4,5,6,7,8] * 8)
    descending = bytes([8,7,6,5,4,3,2,1,0] * 8)
    alternating = bytes(([0,1,2,3,4,5,6,7,8] + [8,7,6,5,4,3,2,1,0]) * 4)
    assert dhash64(ascending) == "0000000000000000"
    assert dhash64(descending) == "ffffffffffffffff"
    assert dhash64(alternating) == "00ff00ff00ff00ff"
    assert dhash64_hamming_distance("0000000000000000", "ffffffffffffffff") == 64
    assert dhash64_hamming_distance("0000000000000000", "00ff00ff00ff00ff") == 32
    assert dhash64_hamming_distance("0000000000000000", "0000000000000001") == 1
