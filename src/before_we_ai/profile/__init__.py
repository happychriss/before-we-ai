"""Measurement: column profiles and the candidate matrix.

Profiles are statistics, the matrix is measured value overlap — neither
is a judgment. Judgment (promotion, rejection) belongs to probes and
humans; the matrix therefore also *contains* chance overlaps, on purpose.
"""

from before_we_ai.profile.candidates import MAX_CANDIDATE_PAIRS, build_matrix, write_matrix
from before_we_ai.profile.columns import profile_view

__all__ = ["MAX_CANDIDATE_PAIRS", "build_matrix", "profile_view", "write_matrix"]
