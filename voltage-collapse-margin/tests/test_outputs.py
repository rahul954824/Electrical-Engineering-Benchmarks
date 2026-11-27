"""Outcome checks (SPEC.md sections 3 and 4; the requirements of instruction.md).

Nodes: test_artifacts (the saved report /root/results/example_report.json of the example case, and the program
file) and test_case[<name>] for every case of tests/truth (the example case and the further cases of spec
section 5), one fresh run of /root/results/tool.py each under the conditions of spec section 4 (uid 10001,
read-only copies of the program and of the case at other paths, a fresh empty working directory that is also HOME
and TMPDIR, whitelisted environment, the two options in a case-dependent order, CALL_SECONDS of wall clock from
process start to exit, exit status 0). CASE_COUNT runs of CALL_SECONDS each fit 1.5 times into
[verifier].timeout_sec of task.toml.

A report is checked in this order (task_check.py holds the three task-specific functions):

  1. contract (task_check.validate): exact key sets, finite JSON numbers, list lengths, bounds and orderings of
     spec section 3; a value at most ROUND_OFF outside a bound or ordering is replaced by the bound;
  2. consistency (task_check.consistency): every reported value that spec section 3 defines through other
     reported values is recomputed from those values and must agree with them;
  3. correctness (task_check.compare): the reported values against the exact values of the case
     (tests/truth/<name>.json, from the independent implementation in tests/truth_source/).

Failure messages quote reported values, values derived from the submission and limits only, never an exact value.
This file is final harness code: nothing in it is task-specific.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import stat
import subprocess

import pytest

from checks import require
import task_check as TC
from truth import TRUTH

HERE = Path(__file__).resolve().parent
PROGRAM_NAME = 'tool.py'
ARTIFACT = Path('/root/results') / PROGRAM_NAME
REPORT_FILE = Path('/root/results/example_report.json')
EXAMPLE = 'example'        # the case shipped as /root/data/example/ (tests/cases/example.<file> is its copy)
SANDBOX = Path('/sandbox')
RUNNER = 'runner'          # uid 10001, created in the Dockerfile
PROGRAM_PATH = '/opt/program-python/bin:/usr/local/bin:/usr/bin:/bin'   # `python` = NumPy/SciPy-only runtime
CALL_SECONDS = TC.CALL_SECONDS   # spec section 4: wall clock from process start to exit
MAX_BYTES = 100_000        # spec section 3: every report and the program at most 100,000 bytes
# Errors of the verifier's own computations at REPORTED values (a failure of the report, never a crash).
COMPUTE_ERRORS = (ValueError, ZeroDivisionError, FloatingPointError, OverflowError, ArithmeticError, IndexError,
                  KeyError)


# ---------------------------------------------------------------------------------------------
# Safe file reading


def strict_pairs(pairs):
    output = {}
    for key, value in pairs:
        require(key not in output, f'duplicate JSON key {key!r}')
        output[key] = value
    return output


def reject_constant(token):
    raise ValueError(f'{token} is not a JSON number')


def read_regular(path, label):
    """Bytes of a regular, non-empty file of at most MAX_BYTES; never opens a FIFO, device or symlink."""
    try:
        before = os.lstat(path)
    except FileNotFoundError:
        raise AssertionError(f'{label}: missing') from None
    require(stat.S_ISREG(before.st_mode), f'{label}: not a regular file (symlink, FIFO, device or directory)')
    require(0 < before.st_size <= MAX_BYTES, f'{label}: must be non-empty and at most {MAX_BYTES} bytes')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise AssertionError(f'{label}: could not be opened as a regular file') from None
    try:
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode) and (st.st_dev, st.st_ino) == (before.st_dev, before.st_ino),
                f'{label}: file changed while being opened')
        chunks, size = [], 0
        while size <= MAX_BYTES:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
    finally:
        os.close(fd)
    data = b''.join(chunks)
    require(0 < len(data) <= MAX_BYTES, f'{label}: must be non-empty and at most {MAX_BYTES} bytes')
    return data


def read_text(path, label):
    """A result file as text: regular file, at most MAX_BYTES, strict UTF-8 without a byte-order mark."""
    data = read_regular(path, label)
    require(not data.startswith(b'\xef\xbb\xbf'),
            f'{label}: starts with a byte-order mark (UTF-8 without one is required)')
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError as error:
        raise AssertionError(f'{label}: not valid UTF-8 ({error})') from None


def read_json(path, label):
    """A result file as strict JSON (no NaN/Infinity, no duplicate keys); the top-level value must be an object."""
    try:
        data = json.loads(read_text(path, label), object_pairs_hook=strict_pairs, parse_constant=reject_constant)
    except (ValueError, RecursionError) as error:
        raise AssertionError(f'{label}: not valid JSON ({str(error)[:200]})') from None
    require(isinstance(data, dict), f'{label}: the top-level JSON value must be an object')
    return data


# ---------------------------------------------------------------------------------------------
# Cases and the three checks of a report


def case_path(name, file_name):
    """tests/cases/<name>.<file_name>: the stored copy of one file of the case directory of `name`."""
    return HERE / 'cases' / f'{name}.{file_name}'


def load_case(name):
    """The parsed case `name` (task_check.parse_case on the texts of its files)."""
    texts = {file_name: case_path(name, file_name).read_text(encoding='utf-8') for file_name in TC.CASE_FILES}
    return TC.parse_case(texts)


def check_report(name, report, where):
    """Contract, then consistency of the derived values, then correctness against the exact values."""
    require(name in TRUTH and TRUTH[name].get('case_id') == name and 'expected' in TRUTH[name],
            f'verifier: no exact values stored for the case {name!r}')
    case = load_case(name)
    values = TC.validate(report, case, where)
    try:
        TC.consistency(values, case, where)
    except COMPUTE_ERRORS as error:
        raise AssertionError(f'{where}: a value defined through other reported values could not be recomputed '
                             f'from them ({type(error).__name__})') from None
    TC.compare(values, TRUTH[name], case, where)


# ---------------------------------------------------------------------------------------------
# Runner


def _drop_privileges() -> None:
    runner = pwd.getpwnam(RUNNER)
    os.setgroups([])
    os.setgid(runner.pw_gid)
    os.setuid(runner.pw_uid)


def _rotated_options(command_tail, name):
    """Present the option/value pairs in a case-dependent order: the spec allows either order."""
    pairs = [command_tail[i:i + 2] for i in range(0, len(command_tail), 2)]
    shift = sum(ord(c) for c in name) % len(pairs)
    pairs = pairs[shift:] + pairs[:shift]
    return [token for pair in pairs for token in pair]


def _live_state(entry):
    """Scheduler state of /proc/<pid> ('Z'/'X' = already dead, waiting to be reaped by PID 1)."""
    return (entry / 'stat').read_text().rsplit(')', 1)[1].split()[0]


def _clear_runner_processes() -> None:
    """Remove program-owned processes in this verifier's private PID namespace."""
    uid = pwd.getpwnam(RUNNER).pw_uid
    for _ in range(5):  # rescan: a forking child may appear during the first pass
        found = False
        for entry in Path('/proc').iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                if entry.stat().st_uid == uid and _live_state(entry) not in ('Z', 'X'):
                    found = True
                    os.kill(int(entry.name), signal.SIGKILL)
            except (ProcessLookupError, FileNotFoundError, PermissionError):
                pass
        if not found:
            break


def _tail(path):
    """Quote the last 2000 bytes of a regular file; never follow a planted symlink."""
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return ''
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return ''
        os.lseek(fd, max(0, st.st_size - 2000), os.SEEK_SET)
        return os.read(fd, 2000).decode('utf-8', errors='replace')
    finally:
        os.close(fd)


def _run_as_runner(argv, work_dir, log_dir, limit):
    """Run argv as uid 10001 in work_dir (also HOME and TMPDIR) with the whitelisted environment of spec
    section 4, in its own session; the whole process group is killed at the wall-clock limit and any surviving
    uid-10001 process is killed before and after. Returns (timed_out, returncode, stdout tail, stderr tail)."""
    _clear_runner_processes()
    stdout_path, stderr_path = log_dir / 'stdout', log_dir / 'stderr'
    process = None
    timed_out = False
    returncode = None
    try:
        with stdout_path.open('w') as out, stderr_path.open('w') as err:
            process = subprocess.Popen(
                argv, cwd=work_dir,
                env={'PATH': PROGRAM_PATH, 'HOME': str(work_dir), 'TMPDIR': str(work_dir), 'LANG': 'C.UTF-8',
                     'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'},
                stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                start_new_session=True,
                preexec_fn=_drop_privileges,
            )
            try:
                returncode = process.wait(timeout=limit)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        _clear_runner_processes()
    return timed_out, returncode, _tail(stdout_path), _tail(stderr_path)


def _fresh_sandbox():
    """/sandbox/{bin,data,log,work} recreated: bin and data root-owned read-only, log root-only, work owned by
    uid 10001 and empty."""
    for sub in ('bin', 'data', 'log', 'work'):
        if os.path.lexists(SANDBOX / sub):
            shutil.rmtree(SANDBOX / sub)
    runner = pwd.getpwnam(RUNNER)
    (SANDBOX / 'bin').mkdir(mode=0o755)
    (SANDBOX / 'data').mkdir(mode=0o755)
    (SANDBOX / 'log').mkdir(mode=0o700)
    work_dir = SANDBOX / 'work'
    work_dir.mkdir(mode=0o700)
    os.chown(work_dir, runner.pw_uid, runner.pw_gid)
    require(not any(work_dir.iterdir()), 'a fresh run must start in an empty working directory')
    return work_dir


_PROBE_CODE = """
import importlib.util, os, sys
problems = []
for name in ('numpy', 'scipy'):
    mod = __import__(name)
    if mod.__version__ != {'numpy': '1.26.4', 'scipy': '1.11.4'}[name]:
        problems.append(name + ' ' + mod.__version__)
if sys.version_info[:2] != (3, 11):
    problems.append('python ' + sys.version)
if importlib.util.find_spec('pytest') is not None:
    problems.append('pytest importable')
for path in ('/tests', '/tests/truth', '/tests/cases', '/root', '/root/results', '/root/data', '/logs/verifier',
             '/sandbox/log'):
    try:
        os.listdir(path)
        problems.append(path + ' readable')
    except OSError:
        pass
try:
    open('/sandbox/bin/tool.py', 'a').close()
    problems.append('program copy writable')
except OSError:
    pass
print('; '.join(problems))
sys.exit(1 if problems else 0)
"""
_PROBED = []


def _probe_runtime():
    """Once per session: the program runtime offers Python 3.11 with NumPy 1.26.4 and SciPy 1.11.4 and no
    pytest, and uid 10001 reads neither /tests nor /root (fail closed: no program is run otherwise)."""
    if _PROBED:
        return
    work_dir = _fresh_sandbox()
    program = SANDBOX / 'bin' / PROGRAM_NAME
    program.write_bytes(b'# probe\n')
    program.chmod(0o444)
    (SANDBOX / 'bin').chmod(0o555)
    timed_out, returncode, out, err = _run_as_runner(['python', '-I', '-c', _PROBE_CODE], work_dir,
                                                     SANDBOX / 'log', 60)
    require(not timed_out and returncode == 0,
            f'verifier: the program runtime does not meet spec section 4 ({out.strip()!r}; {err.strip()[-300:]!r})')
    _PROBED.append(True)


def _invoke(name, program_source=ARTIFACT, limit=CALL_SECONDS):
    """One isolated, time-bounded run of the program on the case `name` (tests/cases/<name>.<file>).

    The program file is checked (regular, non-empty, <= 100,000 bytes, UTF-8 without BOM) and copied into a
    root-owned read-only directory (/sandbox/bin); the case files are copied under their spec names into a
    root-owned read-only directory (/sandbox/data/case); the program runs as uid 10001 with the empty,
    uid-10001-owned /sandbox/work as its current directory, HOME and TMPDIR (the only writable location), the
    output path inside it, stdin empty, stdout and stderr to root-only files, the environment PATH, HOME, TMPDIR,
    LANG and the three thread variables, in its own session; the whole process group is killed at the wall-clock
    limit and any surviving uid-10001 process is killed before and after the run.
    """
    source = read_regular(program_source, PROGRAM_NAME)
    require(not source.startswith(b'\xef\xbb\xbf'), f'{PROGRAM_NAME}: starts with a byte-order mark')
    try:
        source.decode('utf-8')
    except UnicodeDecodeError as error:
        raise AssertionError(f'{PROGRAM_NAME}: not valid UTF-8 ({error})') from None
    _probe_runtime()
    work_dir = _fresh_sandbox()
    program = SANDBOX / 'bin' / PROGRAM_NAME
    program.write_bytes(source)
    program.chmod(0o444)
    (SANDBOX / 'bin').chmod(0o555)
    case_dir = SANDBOX / 'data' / 'case'
    case_dir.mkdir(mode=0o755)
    for file_name in TC.CASE_FILES:
        shutil.copyfile(case_path(name, file_name), case_dir / file_name)
        (case_dir / file_name).chmod(0o444)
    case_dir.chmod(0o555)
    (SANDBOX / 'data').chmod(0o555)
    output_path = work_dir / 'report.json'
    command_tail = ['--data', str(case_dir), '--output', str(output_path)]
    timed_out, returncode, out, err = _run_as_runner(['python', str(program), *_rotated_options(command_tail, name)],
                                                     work_dir, SANDBOX / 'log', limit)
    require(not timed_out, f'{name}: the program exceeded the {limit} s wall-clock limit')
    require(returncode == 0, f'{name}: the program exited with status {returncode}; stdout={out!r}; stderr={err!r}')
    require(os.path.lexists(output_path), f'{name}: the program did not write its output file')
    return read_json(output_path, f'{name}: report')


# ---------------------------------------------------------------------------------------------
# Nodes


def test_artifacts():
    """The saved report of the example case and the program file.

    /root/results/tool.py must be a regular, non-empty file of at most 100,000 bytes, UTF-8 without a byte-order
    mark (it is run by test_case). /root/results/example_report.json must be a regular, non-empty file of at most
    100,000 bytes holding strict UTF-8 JSON without a byte-order mark (no NaN or Infinity, no duplicate keys, an
    object at the top level), must satisfy the contract of spec section 3 and must meet the requirements of
    instruction.md for the example case (tests/cases/example.*, the copy of /root/data/example/) against
    tests/truth/example.json.
    """
    read_text(ARTIFACT, PROGRAM_NAME)
    report = read_json(REPORT_FILE, 'example_report.json')
    check_report(EXAMPLE, report, 'example_report.json')


@pytest.mark.parametrize('name', sorted(TRUTH))
def test_case(name, record_property):
    """One fresh run of the program on one case (the example case or one of the further cases).

    The program runs once under the execution contract of spec section 4 (uid 10001, read-only copies of the
    program and of the case, a fresh empty working directory that is also HOME and TMPDIR, the two options in a
    case-dependent order, whitelisted environment, CALL_SECONDS of wall clock from process start to exit, exit
    status 0); its report (regular file, at most 100,000 bytes, strict UTF-8 JSON without a byte-order mark) must
    satisfy the contract of spec section 3 and meet the requirements of instruction.md for that case against
    tests/truth/<name>.json.
    """
    report = _invoke(name)
    record_property('report', report)
    check_report(name, report, f'{name}: report')
