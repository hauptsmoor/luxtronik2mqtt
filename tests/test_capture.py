"""The dump-capture command against a simulated Controller."""

import fixtures
import pytest
from peers import closed_port, simulated_controller

from luxtronik2mqtt.capture import main
from luxtronik2mqtt.controller import Dump

# IPv4 addresses as the CFI sends them: big-endian, as a signed 32-bit register.
IP_172_16_5_20 = -1408236268
IP_172_16_5_255 = -1408236033
IP_172_16_5_1 = -1408236287
IP_10_1_0_20 = 167837716
IP_10_1_1_255 = 167838207
IP_10_1_0_1 = 167837697
MASK_255_255_255_0 = -256
MASK_255_255_254_0 = -512
IP_192_0_2_10 = -1073741302
IP_192_0_2_255 = -1073741057
IP_192_0_2_1 = -1073741311


def capture(dump: Dump, capsys: pytest.CaptureFixture[str]) -> Dump:
    with simulated_controller(dump) as simulated:
        assert main(["127.0.0.1", "--cfi-port", str(simulated.cfi_port), "--shi-port", str(simulated.shi_port)]) == 0
        assert simulated.writes == []
    return Dump.from_json(capsys.readouterr().out)


def test_capture_of_a_real_controller_holds_every_cfi_and_shi_register(capsys: pytest.CaptureFixture[str]) -> None:
    # The fixture's network details are placeholders already, so capturing it changes nothing.
    assert capture(fixtures.load(), capsys) == fixtures.load()


def test_capture_fails_without_output_when_the_cfi_doesnt_answer(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["127.0.0.1", "--cfi-port", str(closed_port()), "--shi-port", str(closed_port())]) == 1

    output = capsys.readouterr()
    assert output.out == ""
    assert "CFI at 127.0.0.1" in output.err


def test_capture_replaces_the_network_details_by_placeholders(capsys: pytest.CaptureFixture[str]) -> None:
    calculations = list(range(260))
    # ID_WEB_AdresseIP_akt, ID_WEB_SubNetMask_akt, ID_WEB_Add_Broadcast, ID_WEB_Add_StdGateway
    calculations[91:95] = [IP_172_16_5_20, MASK_255_255_255_0, IP_172_16_5_255, IP_172_16_5_1]
    dump = Dump(cfi={"parameters": [7, 8], "calculations": calculations, "visibilities": [1, 0]}, shi=None)

    captured = capture(dump, capsys)

    expected = list(range(260))
    expected[91:95] = [IP_192_0_2_10, MASK_255_255_255_0, IP_192_0_2_255, IP_192_0_2_1]
    assert captured == Dump(cfi={"parameters": [7, 8], "calculations": expected, "visibilities": [1, 0]}, shi=None)


def test_capture_replaces_copies_of_the_addresses_in_the_parameters(capsys: pytest.CaptureFixture[str]) -> None:
    calculations = list(range(260))
    calculations[91:95] = [IP_10_1_0_20, MASK_255_255_254_0, IP_10_1_1_255, IP_10_1_0_1]
    # Laid out as on V3.92.1: ID_AdresseIP_akt and its neighbours, and an unknown field holding the gateway.
    parameters = [5, IP_10_1_0_20, MASK_255_255_254_0, IP_10_1_1_255, IP_10_1_0_1, 0, IP_10_1_0_1]
    dump = Dump(cfi={"parameters": parameters, "calculations": calculations, "visibilities": [1, 0]}, shi=None)

    captured = capture(dump, capsys)

    # A mask is too common a value to match: -512 might as well be a temperature of -51.2.
    assert captured.cfi["parameters"] == [
        5,
        IP_192_0_2_10,
        MASK_255_255_254_0,
        IP_192_0_2_255,
        IP_192_0_2_1,
        0,
        IP_192_0_2_1,
    ]


def test_capture_leaves_other_registers_alone_when_the_controller_has_no_address(
    capsys: pytest.CaptureFixture[str],
) -> None:
    calculations = list(range(260))
    calculations[91:95] = [0, 0, 0, 0]  # 0.0.0.0 everywhere, as without a DHCP lease
    parameters = [0, 1, 0]
    dump = Dump(cfi={"parameters": parameters, "calculations": calculations, "visibilities": [1, 0]}, shi=None)

    captured = capture(dump, capsys)

    assert captured.cfi["parameters"] == [0, 1, 0]
    assert captured.cfi["calculations"][90:96] == [
        90,
        IP_192_0_2_10,
        MASK_255_255_255_0,
        IP_192_0_2_255,
        IP_192_0_2_1,
        95,
    ]
