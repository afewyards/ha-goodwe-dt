import enum


class RecoveryState(enum.Enum):
    AWAKE = "awake"
    ASLEEP = "asleep"


class RecoveryPolicy:
    def __init__(self, asleep_after: int = 3, awake_interval: int = 30, asleep_interval: int = 300):
        self.asleep_after = asleep_after
        self.awake_interval = awake_interval
        self.asleep_interval = asleep_interval
        self.state = RecoveryState.AWAKE

    def on_success(self) -> int:
        """Call after a successful read. Returns the next poll interval (seconds)."""
        self.state = RecoveryState.AWAKE
        return self.awake_interval

    def on_failure(self, consecutive_failures: int) -> int:
        """Call after a failed read with the transport's consecutive-failure count.
        Returns the next poll interval (seconds). Enters ASLEEP once failures reach
        asleep_after (transient failures below that keep the fast cadence so a quick
        recovery is detected promptly)."""
        if consecutive_failures >= self.asleep_after:
            self.state = RecoveryState.ASLEEP
            return self.asleep_interval
        return self.awake_interval

    @property
    def should_wake(self) -> bool:
        """True when asleep -> the coordinator should send a wake probe before the next read."""
        return self.state == RecoveryState.ASLEEP
