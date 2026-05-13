#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jan Pienkowski <siraben@protonmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import pathlib
import subprocess
import tempfile


ARCHES = {
    "amd64": {
        "as": ["as", "--64"],
        "ld": ["ld", "-melf_x86_64"],
    },
    "x86": {
        "as": ["as", "--32"],
        "ld": ["ld", "-melf_i386"],
    },
    "aarch64": {
        "as": ["aarch64-linux-gnu-as"],
        "ld": ["aarch64-linux-gnu-ld"],
    },
    "riscv32": {
        "as": ["riscv32-linux-gnu-as", "-march=rv32imac", "-mabi=ilp32"],
        "ld": ["riscv32-linux-gnu-ld", "-melf32lriscv"],
    },
    "riscv64": {
        "as": ["riscv64-linux-gnu-as", "-march=rv64imac", "-mabi=lp64"],
        "ld": ["riscv64-linux-gnu-ld", "-melf64lriscv"],
    },
}


def run(command):
    subprocess.run(command, check=True)


def emit_hex(data, width):
    lines = []
    for offset in range(0, len(data), width):
        chunk = data[offset:offset + width]
        lines.append("".join(f"{byte:02X}" for byte in chunk))
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="Compile a GAS source file and emit flat stage0 hex text."
    )
    parser.add_argument("--architecture", required=True, choices=sorted(ARCHES))
    parser.add_argument("--input", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--bytes-per-line", type=int, default=16)
    parser.add_argument(
        "--section",
        help="optional section to extract, for sources that intentionally want only one section",
    )
    parser.add_argument(
        "--whole-elf",
        action="store_true",
        help="emit the complete linked ELF file instead of objcopy output",
    )
    parser.add_argument(
        "--text-address",
        help="link .text at this address before extracting bytes",
    )
    parser.add_argument(
        "--linker-script",
        type=pathlib.Path,
        help="optional GNU ld script to control section placement",
    )
    parser.add_argument(
        "--end-label",
        help="optional hex2 label to append after the emitted bytes",
    )
    parser.add_argument(
        "--start-label",
        help="optional hex2 label to place before the emitted bytes",
    )
    args = parser.parse_args()

    commands = ARCHES[args.architecture]
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        obj = tmp / "input.o"
        elf = tmp / "input"
        raw = tmp / "input.bin"

        run(commands["as"] + [str(args.input), "-o", str(obj)])
        ld = commands["ld"]
        if args.linker_script:
            ld = ld + ["-T", str(args.linker_script)]
        if args.text_address:
            ld = ld + ["-Ttext=" + args.text_address]
        run(ld + [str(obj), "-o", str(elf)])
        if args.whole_elf:
            data = elf.read_bytes()
        else:
            objcopy = ["objcopy", "-O", "binary"]
            if args.section:
                objcopy = objcopy + ["-j", args.section]
            run(objcopy + [str(elf), str(raw)])
            data = raw.read_bytes()

        text = (
            "# SPDX-License-Identifier: GPL-3.0-or-later\n"
            "# Generated from " + str(args.input) + " by tools/gas-to-hex.py\n"
            "# Regenerate inside a Nix/dev shell with GNU binutils on PATH.\n"
            "\n"
        )
        if args.start_label:
            text = ":" + args.start_label + "\n" + text
        text = text + emit_hex(data, args.bytes_per_line)
        if args.end_label:
            text = text + ":" + args.end_label + "\n"
        args.output.write_text(text)


if __name__ == "__main__":
    main()
