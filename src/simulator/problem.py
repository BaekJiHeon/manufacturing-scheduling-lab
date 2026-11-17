"""Strict FJSP parsing and independent complete-schedule validation."""
from pathlib import Path
from collections import defaultdict
import math
from numbers import Integral


def parse_fjsp(path):
    lines = [line.split() for line in Path(path).read_text().splitlines() if line.strip()]
    if not lines or len(lines[0]) < 2:
        raise ValueError('Missing FJSP header')
    try:
        n, m = map(int, lines[0][:2])
        if len(lines[0]) > 2:
            float(lines[0][2])  # Average flexibility can be fractional.
        if n <= 0 or m <= 0 or len(lines) != n + 1:
            raise ValueError('Invalid job/machine count or job row count')
        jobs = []
        for line in lines[1:]:
            row = list(map(int, line)); count = row[0]; i = 1; job = []
            if count <= 0:
                raise ValueError('Each job needs operations')
            for _ in range(count):
                alternatives = row[i]; i += 1; choices = {}
                if alternatives <= 0:
                    raise ValueError('Operation has no eligible machine')
                for _ in range(alternatives):
                    machine, duration = row[i:i+2]; i += 2
                    if not 1 <= machine <= m or duration <= 0 or machine-1 in choices:
                        raise ValueError('Invalid or duplicate machine/duration')
                    choices[machine-1] = duration
                job.append(choices)
            if i != len(row):
                raise ValueError('Trailing tokens')
            jobs.append(job)
        return jobs, m
    except (IndexError, TypeError) as exc:
        raise ValueError('Truncated or malformed FJSP input') from exc


def verify(jobs, n_machines, rows):
    expected = {(j, o) for j, job in enumerate(jobs) for o in range(len(job))}
    seen = set(); machines = defaultdict(list); operations = {}
    if len(rows) != len(expected):
        raise ValueError('Missing or extra operations')
    for row in rows:
        try:
            j, o, m = (row[k] for k in ('job', 'operation', 'machine'))
            if not all(isinstance(x, Integral) and not isinstance(x, bool) for x in (j,o,m)):
                raise ValueError('Non-integer index')
            if (j,o) not in expected or (j,o) in seen or not 0 <= m < n_machines:
                raise ValueError('Unknown or duplicate operation/machine')
            if m not in jobs[j][o]:
                raise ValueError('Ineligible machine')
            s,e,p = (row[k] for k in ('start','end','duration'))
            if not all(math.isfinite(x) for x in (s,e,p)) or not 0 <= s < e:
                raise ValueError('Invalid timestamps')
            if p != jobs[j][o][m] or not math.isclose(e-s,p,rel_tol=0,abs_tol=1e-9):
                raise ValueError('Interval length differs from processing time')
            seen.add((j,o)); machines[m].append(row); operations[j,o]=row
        except (KeyError, TypeError, IndexError) as exc:
            raise ValueError('Malformed schedule row') from exc
    if seen != expected:
        raise ValueError('Incomplete schedule')
    for rows_on_machine in machines.values():
        ordered = sorted(rows_on_machine, key=lambda x:x['start'])
        if any(a['end'] > b['start'] for a,b in zip(ordered,ordered[1:])):
            raise ValueError('Machine overlap')
    for j,job in enumerate(jobs):
        for o in range(1,len(job)):
            if operations[j,o-1]['end'] > operations[j,o]['start']:
                raise ValueError('Job precedence violation')
    return True


def scheduling_metrics(jobs, machines, rows, due):
    verify(jobs,machines,rows)
    completion = [max(r['end'] for r in rows if r['job']==j) for j in range(len(jobs))]
    makespan=max(completion); tardiness=[max(0,c-d) for c,d in zip(completion,due)]
    busy=sum(r['duration'] for r in rows)
    return dict(makespan=makespan,total_tardiness=sum(tardiness),mean_tardiness=sum(tardiness)/len(jobs),
                on_time_delivery_rate=sum(c<=d for c,d in zip(completion,due))/len(jobs),
                machine_utilization=busy/(machines*makespan),machine_idle_time=machines*makespan-busy,
                constraint_violation_count=0)
