from backend.performance import Performance


def test_metrics_do_not_invent_physical_measurements():
    stats=Performance()
    stats.observe({'host_round_trip_us':None,'python_compute_us':5})
    result=stats.snapshot()
    assert result['host_rtt_mean_us'] is None
    assert result['fpga_dropped_packets'] is None
    assert result['python_mean_us']==5
    assert result['uart'] is None


def test_rtt_aggregation_and_bounded_percentile_window():
    stats=Performance()
    for i in range(1,3001):
        stats.observe({'host_round_trip_us':i,'python_compute_us':2})
    result=stats.snapshot()
    assert result['host_rtt_count']==3000
    assert result['host_rtt_mean_us']==1500.5
    assert result['host_rtt_min_us']==1
    assert result['host_rtt_max_us']==3000
    assert result['p95_window_samples']==2048
    assert 2800 < result['host_rtt_p95_us'] < 3000
