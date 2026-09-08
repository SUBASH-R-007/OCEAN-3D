import pytest
from scripts.analyze_evaluation import summarize
from scripts.load_acceptance import percentile


def test_practice_and_unscored_results_cannot_establish_user_benefit():
    trials=[dict(participant='P01',task_id='profile-evidence',condition=c,score=s,elapsed_seconds=t) for c,s,t in [('ocean3d',1,90),('usual-workflow',1,120),('developer-practice',1,1)]]
    trials.append(dict(participant='P02',task_id='profile-evidence',condition='ocean3d',score=None,elapsed_seconds=1))
    result=summarize([dict(schema='ocean3d-evaluation-session-1',trials=trials)])
    assert result['paired_tasks']==1 and result['participants']==1
    assert result['median_time_difference_seconds']==-30 and result['excluded_practice_or_unscored']==2
    with pytest.raises(ValueError,match='Duplicate'):summarize([dict(schema='ocean3d-evaluation-session-1',trials=trials+[trials[0]])])
    empty=summarize([dict(schema='ocean3d-evaluation-session-1',trials=trials[2:])])
    assert empty['median_time_difference_seconds'] is None and empty['paired_tasks']==0


def test_latency_percentiles_are_interpolated_without_inventing_missing_measurements():
    assert percentile([],0.95) is None
    assert percentile([1,2,3,4],0.5)==2.5
    assert percentile([1],0.95)==1
