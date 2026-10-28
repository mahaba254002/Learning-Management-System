"""Institution-defined numeric grading; Decimal arithmetic, explicit missing data."""
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN, ROUND_DOWN
from typing import Literal
from pydantic import Field, model_validator
from app.schemas.academic import Input


class FinalBand(Input):
    minimum: float = Field(ge=0,le=100,allow_inf_nan=False)
    label: str = Field(min_length=1,max_length=30)
    points: float | None = Field(default=None,ge=0,le=100,allow_inf_nan=False)


class GradingRules(Input):
    enabled: bool = False
    name: str = Field(default='Institution grading policy',min_length=1,max_length=100)
    aggregation: Literal['POINTS','CATEGORY_WEIGHTS'] = 'CATEGORY_WEIGHTS'
    weights: dict[Literal['ASSIGNMENT','COURSEWORK','EXAM'],float] = Field(default_factory=lambda:dict(ASSIGNMENT=0,COURSEWORK=0,EXAM=0))
    within_category: Literal['POINTS','MEAN_PERCENT'] = 'POINTS'
    pass_percentage: float = Field(default=50,ge=0,le=100,allow_inf_nan=False)
    percentage_places: int = Field(default=2,ge=0,le=4)
    rounding: Literal['HALF_UP','HALF_EVEN','DOWN'] = 'HALF_UP'
    grade_basis: Literal['RAW','ROUNDED'] = 'RAW'
    bands: list[FinalBand] = Field(default_factory=list,max_length=20)
    gpa_enabled: bool = False
    gpa_scheme: str = Field(default='Institution GPA',min_length=1,max_length=80)
    gpa_scale: float = Field(default=4,gt=0,le=100,allow_inf_nan=False)
    gpa_places: int = Field(default=2,ge=0,le=4)
    repeats: Literal['ALL','LATEST','BEST'] = 'ALL'

    @model_validator(mode='after')
    def valid_policy(self):
        import math
        if set(self.weights)!={'ASSIGNMENT','COURSEWORK','EXAM'} or any(not math.isfinite(v) or v<0 or v>100 for v in self.weights.values()):
            raise ValueError('Enter all three category weights between 0 and 100')
        if self.enabled:
            if self.aggregation=='CATEGORY_WEIGHTS' and sum(Decimal(str(v)) for v in self.weights.values())!=100:
                raise ValueError('Enabled category weights must total exactly 100%')
            if not self.bands or min(b.minimum for b in self.bands)!=0 or len({b.minimum for b in self.bands})!=len(self.bands) or len({b.label for b in self.bands})!=len(self.bands):
                raise ValueError('Final grade bands need distinct labels and minimum percentages, including zero')
        if self.gpa_enabled:
            if not self.enabled: raise ValueError('Enable final grading before GPA')
            if any(b.points is None or b.points>self.gpa_scale for b in self.bands): raise ValueError('Every final grade band needs points within the GPA scale')
            ordered=sorted(self.bands,key=lambda b:b.minimum)
            if any(a.points>b.points for a,b in zip(ordered,ordered[1:])): raise ValueError('Grade points cannot decrease as marks increase')
        return self


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),default=str).encode()).hexdigest()


def rounded(value,places,mode):
    return value.quantize(Decimal(1).scaleb(-places),rounding={'HALF_UP':ROUND_HALF_UP,'HALF_EVEN':ROUND_HALF_EVEN,'DOWN':ROUND_DOWN}[mode])


def calculate(policy, assessments):
    """Assessments contain numeric published work only; all expected positive-weight marks are required."""
    policy=GradingRules.model_validate(policy).model_dump()
    issues=[]; buckets={}; contributions=[]
    if not policy['enabled']: return dict(ready=False,issues=['Final grading is not enabled.'],result=None)
    for work in assessments:
        weight=Decimal(str(policy['weights'][work['kind']])) if policy['aggregation']=='CATEGORY_WEIGHTS' else Decimal(100)
        if not weight: continue
        buckets.setdefault(work['kind'],[]).append(work)
        if not work['released']: issues.append(f"{work['title']}: results are withheld.")
        elif work['score'] is None: issues.append(f"{work['title']}: mark is missing.")
    if policy['aggregation']=='CATEGORY_WEIGHTS':
        for kind,weight in policy['weights'].items():
            if weight and not buckets.get(kind): issues.append(f'{kind}: no published numeric assessment for its configured weight.')
    if not buckets: issues.append('No contributing numeric assessments.')
    if issues: return dict(ready=False,issues=issues,result=None)
    if policy['aggregation']=='POINTS':
        works=[w for rows in buckets.values() for w in rows]
        raw=sum(Decimal(str(w['score'])) for w in works)/sum(Decimal(str(w['maximum'])) for w in works)*100
    else:
        raw=Decimal(0)
        for kind,works in sorted(buckets.items()):
            if policy['within_category']=='POINTS': percentage=sum(Decimal(str(w['score'])) for w in works)/sum(Decimal(str(w['maximum'])) for w in works)*100
            else: percentage=sum(Decimal(str(w['score']))/Decimal(str(w['maximum']))*100 for w in works)/len(works)
            weight=Decimal(str(policy['weights'][kind])); contribution=percentage*weight/100;raw+=contribution
            contributions.append(dict(category=kind,weight=str(weight),percentage=str(rounded(percentage,4,policy['rounding'])),contribution=str(rounded(contribution,4,policy['rounding'])),assessments=len(works)))
    display=rounded(raw,policy['percentage_places'],policy['rounding'])
    basis=display if policy['grade_basis']=='ROUNDED' else raw
    band=next(b for b in sorted(policy['bands'],key=lambda b:b['minimum'],reverse=True) if basis>=Decimal(str(b['minimum'])))
    return dict(ready=True,issues=[],result=dict(percentage=str(display),raw_percentage=str(raw),grade=band['label'],
        points=str(band['points']) if policy['gpa_enabled'] else None,passed=basis>=Decimal(str(policy['pass_percentage'])),contributions=contributions,
        policy=policy,policy_fingerprint=digest(policy)))


def gpa(attempts):
    """Separate incompatible schemes. All failures count; exemptions and term sub-results do not."""
    schemes={}
    for attempt in attempts:
        result=attempt['result'];policy=result['policy']
        if not policy['gpa_enabled'] or attempt.get('exempt'): continue
        identity={k:policy[k] for k in ['gpa_scheme','gpa_scale','gpa_places','repeats','rounding']}
        key=digest(identity);entry=schemes.setdefault(key,dict(**identity,attempts=[]))
        entry['attempts'].append(attempt)
    output=[]
    for entry in schemes.values():
        selected={}
        for attempt in sorted(entry.pop('attempts'),key=lambda a:a['order']):
            key=attempt['course_key']
            if entry['repeats']=='ALL': key=attempt['id']
            if entry['repeats']!='BEST' or key not in selected or Decimal(attempt['result']['points'])>=Decimal(selected[key]['result']['points']): selected[key]=attempt
        credits=sum(Decimal(a['result']['credits']) for a in selected.values())
        quality=sum(Decimal(a['result']['credits'])*Decimal(a['result']['points']) for a in selected.values())
        output.append(dict(scheme=entry['gpa_scheme'],scale=entry['gpa_scale'],repeat_rule=entry['repeats'],
            gpa=str(rounded(quality/credits,entry['gpa_places'],entry['rounding'])) if credits else None,
            attempted_credits=str(credits),quality_points=str(quality),included_attempts=len(selected)))
    return output
