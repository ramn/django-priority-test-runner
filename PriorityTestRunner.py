import itertools
from itertools import groupby
import datetime

#from django.test.runner import DiscoverRunner # new in django 1.4
from django.test.simple import DjangoTestSuiteRunner


class PriorityTestRunner(DjangoTestSuiteRunner):

    unsuccessful_cases_log = '/tmp/priority_test_runner.dat'

    def build_suite(self, test_labels, extra_tests=None, **kwargs):
        parent_cls = super(PriorityTestRunner, self)
        suite = parent_cls.build_suite(test_labels, extra_tests, **kwargs)
        return self.reorder_suite(suite)

    def reorder_suite(self, suite):
        raw_previous_unsuccessful = None
        try:
            with open(self.unsuccessful_cases_log, 'r') as f:
                raw_previous_unsuccessful = f.readlines()
            raw_previous_unsuccessful = [
                    line.strip() for line in raw_previous_unsuccessful
                    if line.strip() != '']
        except IOError as e:
            pass

        def parse_line(line):
            partitioned = line.partition(' ')
            timestamp_str = partitioned[0]
            date = datetime.datetime.utcfromtimestamp(int(timestamp_str))
            case = partitioned[2]
            return (date, case)

        if raw_previous_unsuccessful is None: 
            return suite

        previous_unsuccessful_runs = [
                parse_line(line) for line in raw_previous_unsuccessful]
        previous_unsuccessful_runs.sort(key=lambda x: x[0])

        def cases_from_last_run(previous_unsuccessful_runs):
            by_timestamp = dict(groupby(previous_unsuccessful_runs, key=lambda x: x[0]))
            most_recent_timestamp = None
            if by_timestamp.keys():
                most_recent_timestamp = sorted(by_timestamp.keys())[-1]
            if most_recent_timestamp:
                most_recent_cases_with_ts = list(by_timestamp[most_recent_timestamp])
                return [pair[1].strip() for pair in most_recent_cases_with_ts]
            else:
                return []

        tests_to_execute_by_name = dict((str(test), test) for test in suite._tests)
        tests_to_execute_names = tests_to_execute_by_name.keys()

        prioritized_case_names = [
                case_name
                for case_name in cases_from_last_run(previous_unsuccessful_runs)
                if case_name in tests_to_execute_names]
        remaining_case_names = list(set(tests_to_execute_names) - set(prioritized_case_names))
        all_case_names_ordered = prioritized_case_names + remaining_case_names
        all_cases_ordered = [tests_to_execute_by_name[name] for name in all_case_names_ordered]

        suite._tests = all_cases_ordered
        return suite

    def run_suite(self, suite, **kwargs):
        result = super(PriorityTestRunner, self).run_suite(suite, **kwargs)

        unsuccessful_cases = [pair[0] for pair in itertools.chain(result.failures, result.errors)]
        timestamp_now = datetime.datetime.utcnow().strftime('%s')
        def format_line(case): return '%s %s' % (timestamp_now, case)
        report_lines = [format_line(case) for case in unsuccessful_cases]

        with open(self.unsuccessful_cases_log, 'a') as f:
            for line in report_lines:
                f.write(line + '\n')

        return result
