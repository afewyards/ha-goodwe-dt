from goodwe_dt_lib.recovery import RecoveryPolicy, RecoveryState

def test_starts_awake():
    p = RecoveryPolicy()
    assert p.state == RecoveryState.AWAKE
    assert p.should_wake is False

def test_transient_failures_stay_awake_fast_cadence():
    p = RecoveryPolicy(asleep_after=3, awake_interval=30, asleep_interval=300)
    assert p.on_failure(1) == 30
    assert p.state == RecoveryState.AWAKE
    assert p.on_failure(2) == 30
    assert p.should_wake is False

def test_third_failure_goes_asleep():
    p = RecoveryPolicy(asleep_after=3, awake_interval=30, asleep_interval=300)
    assert p.on_failure(3) == 300
    assert p.state == RecoveryState.ASLEEP
    assert p.should_wake is True

def test_stays_asleep_with_more_failures():
    p = RecoveryPolicy()
    p.on_failure(3); p.on_failure(7)
    assert p.state == RecoveryState.ASLEEP
    assert p.should_wake is True

def test_success_returns_to_awake():
    p = RecoveryPolicy(awake_interval=30)
    p.on_failure(5)                 # asleep
    assert p.on_success() == 30     # morning revive
    assert p.state == RecoveryState.AWAKE
    assert p.should_wake is False

def test_custom_intervals():
    p = RecoveryPolicy(asleep_after=2, awake_interval=10, asleep_interval=120)
    assert p.on_failure(2) == 120 and p.state == RecoveryState.ASLEEP
