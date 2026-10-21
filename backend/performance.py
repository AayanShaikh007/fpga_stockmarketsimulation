"""Measured host counters; never invent inaccessible FPGA-side diagnostics."""
from collections import deque
import math


class Performance:
    def __init__(self):
        self.rtts = deque(maxlen=2048)
        self.rtt_sum = 0
        self.count = 0
        self.minimum = None
        self.maximum = None
        self.python_sum = 0
        self.python_count = 0
        self.feed = dict(feed_samples_received=0,feed_samples_skipped=0,
                         duplicate_feed_events=0,stale_feed_events=0,observer_events_dropped=0)
        self.uart = None

    def observe(self, row):
        rtt = row['host_round_trip_us']
        if rtt is not None:
            self.rtts.append(rtt)
            self.rtt_sum += rtt
            self.count += 1
            self.minimum = rtt if self.minimum is None else min(self.minimum,rtt)
            self.maximum = rtt if self.maximum is None else max(self.maximum,rtt)
        python_us = row['python_compute_us']
        if python_us is not None:
            self.python_sum += python_us
            self.python_count += 1

    def snapshot(self):
        ordered = sorted(self.rtts)
        return dict(self.feed) | {
            'uart': self.uart, 'fpga_dropped_packets': None,
            'fpga_drop_note': 'Not exposed by current wire protocol; timeouts do not prove packet drops',
            'host_rtt_count': self.count,
            'host_rtt_mean_us': self.rtt_sum/self.count if self.count else None,
            'host_rtt_min_us': self.minimum, 'host_rtt_max_us': self.maximum,
            'host_rtt_p95_us': ordered[math.ceil(.95*len(ordered))-1] if ordered else None,
            'p95_window_samples': len(ordered),
            'python_mean_us': self.python_sum/self.python_count if self.python_count else None,
            'engine_timing_kind': 'architectural estimate, not physical measurement',
        }
