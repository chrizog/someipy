import src.serialization


def test_base_types_len():
    assert 1 == len(src.serialization.Uint8(1))
    assert 2 == len(src.serialization.Uint16(1))
    assert 4 == len(src.serialization.Uint32(1))
    assert 8 == len(src.serialization.Uint64(1))
    
    assert 1 == len(src.serialization.Sint8(-1))
    assert 2 == len(src.serialization.Sint16(-1))
    assert 4 == len(src.serialization.Sint32(-1))
    assert 8 == len(src.serialization.Sint64(-1))

    assert 1 == len(src.serialization.Bool(True))
    assert 4 == len(src.serialization.Float32(1.0))
    assert 8 == len(src.serialization.Float64(1.0))
