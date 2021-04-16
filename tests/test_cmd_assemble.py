"""
Copyright Government of Canada 2021

Written by: Eric Marinier, National Microbiology Laboratory,
            Public Health Agency of Canada

Licensed under the Apache License, Version 2.0 (the "License"); you may not use
this work except in compliance with the License. You may obtain a copy of the
License at:

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import os

from pathlib import Path

from proksee.reads import Reads
from proksee.commands.cmd_assemble import assemble

INPUT_DIR = os.path.join(Path(__file__).parent.absolute(), "data")
OUTPUT_DIR = os.path.join(Path(__file__).parent.absolute(), "output")


class TestCmdAssemble:

    def test_simple_assemble(self):
        """
        Tests the cmd_assemble.py's main control flow: .assemble(...).
        This test uses data with a small file size, that is insufficient to test the accuracy of the assembly.
        Instead, this data and test will be used to test the correctness of the program control flow.
        """

        forward_filename = os.path.join(INPUT_DIR, "NA12878_fwd.fastq")
        reverse_filename = None
        reads = Reads(forward_filename, reverse_filename)

        force = True

        # Files being tracked:
        assembly_statistics_file = os.path.join(OUTPUT_DIR, "assembly_statistics.csv")
        contigs_file = os.path.join(OUTPUT_DIR, "contigs.fasta")
        quast_file = os.path.join(OUTPUT_DIR, "quast", "report.txt")
        refseq_masher_file = os.path.join(OUTPUT_DIR, "refseq_masher.o")

        # Remove previous files if they exist:
        if os.path.isfile(assembly_statistics_file):
            os.remove(assembly_statistics_file)

        if os.path.isfile(contigs_file):
            os.remove(contigs_file)

        if os.path.isfile(quast_file):
            os.remove(quast_file)

        if os.path.isfile(refseq_masher_file):
            os.remove(refseq_masher_file)

        assemble(reads, OUTPUT_DIR, force, species_name=None, platform_name=None)

        # Check that expected files were created:
        assert os.path.isfile(assembly_statistics_file)
        assert os.path.isfile(contigs_file)
        assert os.path.isfile(quast_file)
        assert os.path.isfile(refseq_masher_file)
