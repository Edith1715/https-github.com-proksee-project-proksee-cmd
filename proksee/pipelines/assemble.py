"""
Copyright Government of Canada 2022

Written by:

Arnab Saha Mandal
    University of Manitoba
    National Microbiology Laboratory, Public Health Agency of Canada

Eric Marinier
    National Microbiology Laboratory, Public Health Agency of Canada

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

from shutil import rmtree

from proksee import utilities
from proksee.assemble.assembly_database import AssemblyDatabase
from proksee.assemble.assembly_measurer import AssemblyMeasurer
from proksee.contamination_handler import ContaminationHandler
from proksee.evaluate.heuristic_evaluator import HeuristicEvaluator, compare_assemblies
from proksee.input_verification import are_valid_fastq
from proksee.evaluate.ml_assembly_evaluator import MLAssemblyEvaluator
from proksee.platform_identify import PlatformIdentifier, identify_name, Platform
from proksee.reads.read_filterer import ReadFilterer
from proksee.expert_system import ExpertSystem
from proksee.writer.assembly_statistics_writer import AssemblyStatisticsWriter
from proksee.species.species_estimator import SpeciesEstimator
from proksee.assemble.skesa_assembler import SkesaAssembler
from proksee.assemble.spades_assembler import SpadesAssembler
from proksee.assemble.assembly_summary import AssemblySummary


def report_valid_fastq(valid):
    """
    Reports to output whether or not the reads appear to be in a valid FASTQ file format.

    ARGUMENTS
        valid (bool): whether or not the reads appear to be in FASTQ format

    POST
        A statement reporting whether or not the reads appear to be in a valid FASTQ file format will be written to the
        program's output.
    """

    if not valid:
        output = "One or both of the reads are not in FASTQ format."

    else:
        output = "The reads appear to be formatted correctly."

    print(output)


def report_platform(platform):
    """
    Reports the sequencing platform to output.

    ARGUMENTS
        platform (Platform (Enum)): the sequencing platform to report

    POST
        A statement reporting the sequencing platform will be written to output.
    """

    output = "Sequencing Platform: " + str(platform.value)

    print(output)


def report_species(species_list):
    """
    Reports observed species in the reads to output.

    ARGUMENTS
        species_list (List(Species)): the list of species to report

    POST
        The observed species will be reported to output.
    """

    species = species_list[0]
    print("SPECIES: " + str(species))

    if len(species_list) > 1:
        print("\nWARNING: Additional high-confidence species were found in the input data:\n")

        for species in species_list[1:min(5, len(species_list))]:
            print(species)

    if species.name == "Unknown":  # A species could not be determined.
        print("\nWARNING: A species could not be determined with high confidence from the input data.")

    print("")  # Blank line


def report_strategy(strategy):
    """
    Reports the assembly strategy that will be used to output.

    ARGUMENTS
        strategy (AssemblyStrategy): the assembly strategy that will be used for assembling

    POST
        The assembly strategy will be written to output.
    """

    print(strategy.report)

    if not strategy.proceed:
        print("The assembly was unable to proceed.\n")


def report_contamination(evaluation):
    """
    Reports observed contamination to output.

    ARGUMENTS
        evaluation (Evaluation): an evaluation of observed contamination

    POST
        The evaluation of observed contamination will be written to output.
    """

    print(evaluation.report)

    if not evaluation.success:
        print("The assembly was unable to proceed.\n")


def determine_platform(reads, platform_name=None):
    """
    Attempts to determine the sequencing platform used to generate the reads.

    ARGUMENTS:
        reads (Reads): the reads generated by the sequencing platform
        platform_name (string): optional; the name of the sequencing platform

    RETURNS:
        platform (Platform): the estimated sequencing platform
    """

    platform = Platform.UNIDENTIFIABLE

    if platform_name:
        platform = identify_name(platform_name)

        if platform is Platform.UNIDENTIFIABLE:
            print("\nThe platform name '" + str(platform_name) + "' is unrecognized.")
            print("Please see the help message for valid platform names.")

        else:
            print("\nThe platform name '" + str(platform_name) + "' was recognized.")

    if platform is Platform.UNIDENTIFIABLE:
        print("\nAttempting to identify the sequencing platform from the reads.")

        platform_identifier = PlatformIdentifier(reads)
        platform = platform_identifier.identify()

    return platform


def cleanup(output_directory):
    """
    Cleans up temporary files in the output directory.

    ARGUMENTS:
        output_directory (string): the location of the program output

    POST:
        The output directory will have all temporary program files deleted.
    """

    # Temporary FASTA directory used in contamination detection:
    fasta_directory = os.path.join(output_directory, ContaminationHandler.FASTA_DIRECTORY)

    if os.path.isdir(fasta_directory):
        rmtree(fasta_directory)

    # Read filtering logfile (i.e. fastp.log):
    filterer_logfile_path = os.path.join(output_directory, ReadFilterer.LOGFILE_FILENAME)

    if os.path.isfile(filterer_logfile_path):
        os.remove(filterer_logfile_path)

    # Forward and reverse filtered read files:
    fwd_filtered_path = os.path.join(output_directory, ReadFilterer.FWD_FILTERED_FILENAME)
    rev_filtered_path = os.path.join(output_directory, ReadFilterer.REV_FILTERED_FILENAME)

    if os.path.isfile(fwd_filtered_path):
        os.remove(fwd_filtered_path)

    if os.path.isfile(rev_filtered_path):
        os.remove(rev_filtered_path)

    # Species estimation output (i.e. mash.o):
    species_estimation_path = os.path.join(output_directory, SpeciesEstimator.OUTPUT_FILENAME)

    if os.path.isfile(species_estimation_path):
        os.remove(species_estimation_path)

    # Assembly quality measurer temporary files (i.e. quast.out and quast.err)
    assembly_measurer_output_path = os.path.join(output_directory, AssemblyMeasurer.OUTPUT_FILENAME)
    assembly_measurer_error_path = os.path.join(output_directory, AssemblyMeasurer.ERROR_FILENAME)

    if os.path.isfile(assembly_measurer_output_path):
        os.remove(assembly_measurer_output_path)

    if os.path.isfile(assembly_measurer_error_path):
        os.remove(assembly_measurer_error_path)

    # Assembly output directories:
    skesa_directory = os.path.join(output_directory, SkesaAssembler.DIRECTORY_NAME)
    spades_directory = os.path.join(output_directory, SpadesAssembler.DIRECTORY_NAME)

    if os.path.isdir(skesa_directory):
        rmtree(skesa_directory)

    if os.path.isdir(spades_directory):
        rmtree(spades_directory)


def assemble(reads, output_directory, force, database_path, mash_database_path, resource_specification,
             id_mapping_filename, species_name=None, platform_name=None):
    """
    Assembles sequence reads and evaluates the resulting contigs.

    ARGUMENTS:
        reads (Reads): the reads to assemble
        output_directory (string): the location to place all program output and temporary files
        force (bool): whether or not to force the assembly to continue, even when it's evaluated as being poor
        database_path (string): the file path of the sequence assembly statistics database
        mash_database_path (string): the file path of the Mash database
        resource_specification (ResourceSpecification): the resources that sub-programs should use
        id_mapping_filename (string) optional; the name of the NCBI ID to taxonomy mapping database file
        species_name (string): optional; the name of the species being assembled
        platform_name (string): optional; the name of the sequencing platform that generated the reads

    RETURNS:
        contigs_filename (string): the file name of the assembled contigs

    POST:
        The passed reads will be assembled in the output directory if successful, or a message explaning why assembly
        could not continue will be written to standard output.
    """

    # Make output directory:
    if not os.path.isdir(output_directory):
        os.mkdir(output_directory)

    # Validate FASTQ inputs:
    valid_fastq = are_valid_fastq(reads)
    report_valid_fastq(valid_fastq)

    if not valid_fastq and not force:
        return

    platform = determine_platform(reads, platform_name)
    report_platform(platform)

    # Filter reads:
    read_filterer = ReadFilterer(reads, output_directory)
    filtered_reads = read_filterer.filter_reads()
    read_quality = read_filterer.summarize_quality()

    # Species and assembly database:
    assembly_database = AssemblyDatabase(database_path)

    # Estimate species
    filtered_filenames = filtered_reads.get_file_locations()
    species_list = utilities.determine_species(filtered_filenames, assembly_database, output_directory,
                                               mash_database_path, id_mapping_filename, species_name)
    species = species_list[0]
    report_species(species_list)

    # Determine a fast assembly strategy:
    expert = ExpertSystem(platform, species, filtered_reads, output_directory, resource_specification)
    fast_strategy = expert.create_fast_assembly_strategy(read_quality)
    report_strategy(fast_strategy)

    if not fast_strategy.proceed and not force:
        return

    # Perform a fast assembly:
    assembler = fast_strategy.assembler
    output = assembler.assemble()
    print(output)

    # Check for contamination at the contig level:
    contamination_handler = ContaminationHandler(species, assembler.contigs_filename, output_directory,
                                                 mash_database_path, id_mapping_filename)
    evaluation = contamination_handler.estimate_contamination()
    report_contamination(evaluation)

    if not evaluation.success and not force:
        return

    # Measure assembly quality statistics:
    assembly_measurer = AssemblyMeasurer(assembler.contigs_filename, output_directory)
    fast_assembly_quality = assembly_measurer.measure_quality()

    # Machine learning evaluation (fast assembly)
    machine_learning_evaluator = MLAssemblyEvaluator(species)
    evaluation = machine_learning_evaluator.evaluate(fast_assembly_quality)
    print(evaluation.report)

    # Expert assembly:
    expert_strategy = expert.create_expert_assembly_strategy(fast_assembly_quality, assembly_database)
    report_strategy(expert_strategy)

    if not expert_strategy.proceed and not force:
        return

    print("Performing expert assembly.")
    assembler = expert_strategy.assembler
    output = assembler.assemble()
    print(output)

    # Measure assembly quality:
    assembly_measurer = AssemblyMeasurer(assembler.contigs_filename, output_directory)
    expert_assembly_quality = assembly_measurer.measure_quality()

    # Machine learning evaluation (expert assembly)
    machine_learning_evaluation = machine_learning_evaluator.evaluate(expert_assembly_quality)
    print(machine_learning_evaluation.report)

    # Evaluate assembly quality
    heuristic_evaluator = HeuristicEvaluator(species, assembly_database)
    heuristic_evaluation = heuristic_evaluator.evaluate(expert_assembly_quality)
    print(heuristic_evaluation.report)

    # Compare fast and slow assemblies:
    report = compare_assemblies(fast_assembly_quality, expert_assembly_quality)
    print(report)

    # Write CSV assembly statistics summary:
    assembly_statistics_writer = AssemblyStatisticsWriter(output_directory)
    assembly_statistics_writer.write_csv([fast_strategy.assembler.name, expert_strategy.assembler.name],
                                         [fast_assembly_quality, expert_assembly_quality])

    # Write expert assembly information to JSON file:
    assembly_statistics_writer.write_json(platform, species, reads, read_quality, expert_assembly_quality,
                                          heuristic_evaluation, machine_learning_evaluation, assembly_database)

    # Move final assembled contigs to the main level of the output directory and rename it.
    contigs_filename = assembler.get_contigs_filename()
    contigs_new_filename = os.path.join(output_directory, "contigs.fasta")
    os.rename(contigs_filename, contigs_new_filename)  # moves and renames

    # Clean up the output directory:
    cleanup(output_directory)

    print("Complete.\n")
    return AssemblySummary(species, expert_assembly_quality, contigs_new_filename)
