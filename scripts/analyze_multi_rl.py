"""Summarize the complete predeclared comparison without selecting seeds/checkpoints."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from scipy.stats import t
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src.evaluation.campaign import ROOT
from scripts.audit_extended_results import audit

COLORS=['#0072B2','#D55E00','#009E73','#CC79A7']
GROUPS=['fresh_generated_test','external_static','external_dynamic']
LABELS=['Fresh generated (20)','External static (10)','External dynamic (6)']


def interval(values):
    a=np.asarray(values,float);mean=float(a.mean())
    half=float(t.ppf(.975,len(a)-1)*a.std(ddof=1)/np.sqrt(len(a))) if len(a)>1 else float('nan')
    return mean,mean-half,mean+half


def markdown(frame):
    result=['| '+' | '.join(frame.columns)+' |','| '+' | '.join(['---']*len(frame.columns))+' |']
    for row in frame.itertuples(index=False,name=None):
        result.append('| '+' | '.join(f'{v:.3f}' if isinstance(v,(float,np.floating)) else str(v) for v in row)+' |')
    return '\n'.join(result)


def main():
    rid=(ROOT/'reports/latest_multi_rl_run.txt').read_text().strip();folder=ROOT/'results/multi_rl'/rid
    meta=json.loads((folder/'metadata.json').read_text());assert meta['status']=='completed'
    cfg=meta['config'];methods=cfg['methods'];frame=pd.read_csv(folder/'metrics.csv')
    coverage=[]
    def leaves(value):
        for item in value:
            if isinstance(item,list):yield from leaves(item)
            else:yield int(item)
    for method in methods:
        for training_seed in cfg['seeds']:
            bank=set(range(cfg['training_seed_base']+training_seed*1000,cfg['training_seed_base']+training_seed*1000+cfg['training_bank_size']))
            seen=list(leaves(json.loads((folder/f'{method}_seed{training_seed}_training_seeds.json').read_text())))
            assert set(seen)<=bank and not set(seen)&set(cfg['test_seeds']+cfg['validation_seeds'])
            coverage.append(dict(method=method,seed=training_seed,unique_training_instances=len(set(seen)),logged_instance_selections=len(seen),selection_unit='same-instance group prompt' if method.endswith('-Sched') else 'environment reset'))
    (folder/'training_data_audit.json').write_text(json.dumps(dict(disjoint_from_validation_and_test=True,coverage=coverage),indent=2))

    tests=frame[frame.record_type=='test'].copy();rl=tests[tests.method.isin(methods)].copy()
    assert len(rl)==len(methods)*len(cfg['seeds'])*36
    expected={(method,seed,instance) for method in methods for seed in cfg['seeds'] for instance in tests.instance.unique()}
    assert set(zip(rl.method,rl.seed,rl.instance))==expected
    cp=tests[(tests.method=='CP-SAT')&(tests.budget_s==5)][['instance','objective_score']].rename(columns={'objective_score':'cp_score'})
    paired=rl.merge(cp,on='instance',validate='many_to_one')
    ppo=rl[rl.method=='MaskablePPO'][['instance','seed','objective_score']].rename(columns={'objective_score':'ppo_score'})
    paired=paired.merge(ppo,on=['instance','seed'],validate='many_to_one')
    paired['gap_cp_percent']=100*(paired.objective_score/paired.cp_score-1)
    paired['gap_ppo_percent']=100*(paired.objective_score/paired.ppo_score-1)
    seed=paired.groupby(['method','scenario','seed'])[['objective_score','gap_cp_percent','gap_ppo_percent','runtime_ms','mean_inference_ms']].mean().reset_index()
    rows=[]
    for (method,group),part in seed.groupby(['method','scenario']):
        row=dict(method=method,scenario=group)
        for key in ['objective_score','gap_cp_percent','gap_ppo_percent','runtime_ms','mean_inference_ms']:
            a,b,c=interval(part[key]);row.update({key:a,key+'_ci95_low':b,key+'_ci95_high':c})
        instance_means=paired[(paired.method==method)&(paired.scenario==group)].groupby('instance')[['objective_score','cp_score']].mean()
        delta=instance_means.objective_score-instance_means.cp_score
        row.update(wins_cp=int((delta< -1e-8).sum()),ties_cp=int((delta.abs()<=1e-8).sum()),losses_cp=int((delta>1e-8).sum()))
        rows.append(row)
    summary=pd.DataFrame(rows)
    training=frame[frame.record_type=='training_summary'].copy()
    baseline_summary=tests.groupby(['method','scenario','budget_s'],dropna=False).agg(objective_mean=('objective_score','mean'),episode_ms_mean=('runtime_ms','mean'),episodes=('instance','count')).reset_index()
    baseline_summary.to_csv(folder/'all_method_descriptive_summary.csv',index=False)
    train_summary=training.groupby('method').agg(trials=('seed','count'),training_seconds_mean=('training_time_s','mean'),training_seconds_std=('training_time_s','std'),parameters=('parameter_count','first'),unused_transitions_mean=('unused_transitions','mean'),unused_transitions_max=('unused_transitions','max')).reset_index()
    for name,data in [('paired_comparison',paired),('seed_summary',seed),('summary',summary),('training_summary',train_summary)]:data.to_csv(folder/(name+'.csv'),index=False)
    audit(['multi_rl'],'multi_rl_artifact_audit.json')
    audit_report=json.loads((ROOT/'reports/multi_rl_artifact_audit.json').read_text())
    output=ROOT/'figures/publication'/rid;output.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.titlesize':9,'pdf.fonttype':42,'svg.fonttype':'none','savefig.dpi':600})
    figures=[]
    def save(fig,name):
        for extension in ['png','svg','pdf']:fig.savefig(output/(name+'.'+extension),bbox_inches='tight',dpi=600)
        plt.close(fig);figures.append(name)
    validation=frame[frame.record_type=='validation']
    fig,axs=plt.subplots(2,2,figsize=(7.1,5),layout='constrained')
    for ax,method,color in zip(axs.flat,methods,COLORS):
        for training_seed,p in validation[validation.method==method].groupby('seed'):
            ax.plot(p.env_steps,p.objective_score,marker=['o','s','^','D','v'][int(training_seed)],ms=2,lw=.9,alpha=.75,color=color,label=f'Seed {int(training_seed)}')
        ax.set_title(method);ax.set_xlabel('Actual environment transitions');ax.set_ylabel('Validation cost (lower better)');ax.grid(alpha=.2)
    fig.legend(*axs[0,0].get_legend_handles_labels(),loc='outside lower center',ncol=5)
    save(fig,'01_multi_rl_learning_raw')
    fig,axs=plt.subplots(1,3,figsize=(7.1,3),layout='constrained')
    for ax,group,label in zip(axs,GROUPS,LABELS):
        for i,(method,color) in enumerate(zip(methods,COLORS)):
            r=summary[(summary.method==method)&(summary.scenario==group)].iloc[0]
            ax.errorbar(i,r.gap_cp_percent,yerr=[[r.gap_cp_percent-r.gap_cp_percent_ci95_low],[r.gap_cp_percent_ci95_high-r.gap_cp_percent]],fmt='o',color=color,capsize=3)
            vals=seed[(seed.method==method)&(seed.scenario==group)].gap_cp_percent
            ax.scatter(np.arange(5)*.03+i-.06,vals,color=color,s=6,alpha=.4)
        ax.axhline(0,color='gray',lw=.8);ax.set_title(label);ax.set_xticks(range(4),methods,rotation=55,ha='right');ax.grid(axis='y',alpha=.2)
    axs[0].set_ylabel('Cost gap to CP-SAT 5s (%)')
    fig.suptitle('Mean and t 95% CI across 5 training seeds; positive is worse',fontsize=9)
    save(fig,'02_multi_rl_quality')
    fig,axs=plt.subplots(1,3,figsize=(7.1,3),layout='constrained')
    markers=['o','s','^','D']
    for ax,group,label in zip(axs,GROUPS,LABELS):
        for method,color,marker in zip(methods,COLORS,markers):
            p=seed[(seed.method==method)&(seed.scenario==group)]
            ax.scatter(p.runtime_ms.mean(),p.objective_score.mean(),label=method,color=color,marker=marker,s=30)
        for baseline,marker in [('CP-SAT','X'),('SPT','v'),('EDD','<'),('MWKR','>')]:
            p=tests[(tests.method==baseline)&(tests.scenario==group)]
            if baseline=='CP-SAT':p=p[p.budget_s==5]
            ax.scatter(p.runtime_ms.mean(),p.objective_score.mean(),label=baseline+' 5s' if baseline=='CP-SAT' else baseline,color='black',marker=marker,s=22)
        ax.set_xscale('log');ax.set_xlabel('Mean full episode computation (ms)');ax.set_title(label);ax.grid(alpha=.2)
    axs[0].set_ylabel('Mean objective cost (lower better)')
    fig.legend(*axs[0].get_legend_handles_labels(),loc='outside lower center',ncol=4)
    save(fig,'03_multi_rl_quality_latency')
    fig,ax=plt.subplots(figsize=(7.1,3),layout='constrained')
    for j,(method,color,marker) in enumerate(zip(methods,COLORS,markers)):
        p=paired[(paired.method==method)&(paired.scenario=='external_static')].groupby('instance').gap_cp_percent.mean().reindex([f'MK{i:02d}' for i in range(1,11)])
        ax.plot(np.arange(10),p,color=color,marker=marker,ms=3,lw=.8,label=method)
    ax.axhline(0,color='gray',lw=.8);ax.set_xticks(range(10),[f'MK{i:02d}' for i in range(1,11)],rotation=45);ax.set_ylabel('Mean cost gap to CP-SAT 5s (%)');ax.grid(alpha=.2);ax.legend(ncol=2)
    save(fig,'04_multi_rl_external_transfer')
    manifest=dict(run_id=rid,source_metrics_sha256=hashlib.sha256((folder/'metrics.csv').read_bytes()).hexdigest(),generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),figures=figures,dpi=600)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    fresh=summary[summary.scenario=='fresh_generated_test'].sort_values('gap_cp_percent')
    best=fresh.iloc[0]
    group_comparison=summary[summary.method.isin(['GRPO-Sched','GSPO-Sched'])]
    all_overlap=((group_comparison.gap_ppo_percent_ci95_low<=0)&(group_comparison.gap_ppo_percent_ci95_high>=0)).all()
    overlap_text='PPO와 직접 짝지은 GRPO/GSPO 상대차의 모든 시나리오95% 구간은0을 포함했다.' if all_overlap else 'PPO와 직접 짝지은 상대차의 시나리오별95% 구간은 아래 표에서 확인해야 한다.'
    main_conclusion='GRPO·GSPO가 PPO보다 확실히 우수하다는 근거는 부족하다.' if all_overlap else 'PPO와의 차이는 시나리오별로 구분해 해석해야 한다.'
    cp_conclusion='이번 설정에서 CP-SAT을 대체할 근거는 없다.' if (summary.gap_cp_percent_ci95_low>0).all() else 'CP-SAT과의 차이도 시나리오별로 확인해야 한다.'

    report=f'''# 추가 강화학습 비교 결과

실행 `{rid}`. PPO·PQN·GRPO-Sched·GSPO-Sched를 각각 5개 시드, 65,536 환경 전이로 학습했다. 총 20개 실행 / 1,310,720 전이이며 모든 마지막 체크포인트를 평가했다. 36개 평가 조건 × 20개 모델 = 720개 RL 스케줄, 별도로 CP-SAT 1/5초와 휴리스틱 3종 180개를 평가했다.

**{main_conclusion} {cp_conclusion}** 새 생성 문제의 CP-SAT 대비 문제별 상대차 평균은 {best['method']}가 {best['gap_cp_percent']:.2f}%로 가장 작았지만, 원시 비용 평균은 PPO{fresh.loc[fresh.method=='MaskablePPO','objective_score'].iloc[0]:.4f} / GSPO{fresh.loc[fresh.method=='GSPO-Sched','objective_score'].iloc[0]:.4f}였다. 문제별 비율을 평균하는 것과 원시 비용을 평균하는 것은 가중치가 달라 순위가 다를 수 있다. {overlap_text} 이것은 고정 예산 파일럿이며 수렴·일반적 우월성·최신 알고리즘 전체에 대한 결론이 아니다.

## 품질 비교

비용은 `(makespan + mean tardiness)/100`이며 낮을수록 좋다. 각 문제의 CP5 대비 상대차를 시드별로 평균한 뒤, 학습 시드5개에 대한 평균과 t95% 구간을 계산했다. 구간은 독립 공장 표본의 불확실성이 아니다.

{markdown(summary[['method','scenario','objective_score','gap_cp_percent','gap_cp_percent_ci95_low','gap_cp_percent_ci95_high','wins_cp','ties_cp','losses_cp']])}

wins/ties/losses는 문제별 RL 시드 평균과 CP5의 비교다. 외부 정적10개/동적6개는 이전에 확인한 전이 평가이고, 새 생성20개만 이번에 고정한 새로운 평가다.

## 휴리스틱 기준도 함께 확인

단순 SPT(가장 짧은 처리시간 우선)의 시나리오별 평균 비용도 이번 네 RL 구성보다 낮았다. 따라서 CP-SAT 대비 차이만으로 결과를 설명하면 안 된다. 모델 교체만으로 성능 개선이 확보되지 않았으며, 추가 연구에서는 상태 표현·학습 분포·예산의 영향을 따로 검증해야 한다. 아래는 튜닝 없이 고정한 휴리스틱 결과다.

{markdown(baseline_summary[baseline_summary.method.isin(['SPT','EDD','MWKR'])][['method','scenario','objective_mean','episode_ms_mean']])}

## 같은 예산의 PPO 대비

음수면 해당 방법이 이번 PPO보다 평균 비용이 낮다. 같은 학습 시드와 같은 평가 문제끼리 짝지었다.

{markdown(summary[['method','scenario','gap_ppo_percent','gap_ppo_percent_ci95_low','gap_ppo_percent_ci95_high']])}

## 속도와 계산 비용

{markdown(summary[['method','scenario','runtime_ms','mean_inference_ms']])}

runtime_ms는 전체 에피소드 계산, mean_inference_ms는 행동 한 번의 평균이다. PPO/PQN/GRPO/GSPO의 행동 한 번과 CP-SAT의 전체 재계획은 서로 다른 작업 단위다. 사용자 정의 정책과 SB3 정책의 추론 경로·망 크기도 달라, 속도 차이를 알고리즘 자체의 우월성으로 단정하지 않는다. CP·휴리스틱도 같은 호스트에서 다시 실행했다.

{markdown(train_summary)}

학습 시간은 주기적 검증·기록·체크포인트 저장을 포함한다. 그룹 방법에서 마지막 예산 경계에 걸린 미완성 그룹의 전이도 총65,536에 포함했고, 학습에 사용하지 않은 수를 공개했다. 네 방법이 같은128개 학습 문제를 사용하지만 그룹 재표본으로 방문 횟수는 다르다. 이전 PPO 파일럿은 학습 데이터 생성 방식도 달라 직접 통제군으로 쓰지 않았다.

## 최근 알고리즘을 어디까지 구현했는가?

- PQN: [2024 논문 / ICLR2025](https://arxiv.org/abs/2407.04811)의 온라인 Q(lambda), LayerNorm, 병렬 환경, replay/target network 없는 구성을 스케줄링에 맞춰 구현했다. 행동 선택과 bootstrap 모두 합법 행동만 허용한다.
- GRPO-Sched: [DeepSeekMath(2024)](https://arxiv.org/abs/2402.03300)의 동일 문제 그룹 보상 정규화와 행동별 clipped ratio를 스케줄 궤적에 적용했다.
- GSPO-Sched: [GSPO(2025)](https://arxiv.org/abs/2507.18071)의 길이 정규화된 전체 궤적 likelihood ratio와 궤적 단위 clipping을 적용했다.

GRPO/GSPO는 원래 언어모델용 방법의 **스케줄링 적용 실험**이다. 공식 제조 구현이나 LLM 결과 재현으로 표현하면 안 된다. 사전학습 참조 모델이 없어 KL beta=0, entropy .01을 사용했다. PQN은 LayerNorm/ReLU, 정책 방식은 Tanh128×128이고 PPO만 value망이 추가되어, 순수 optimizer만 바꾼 실험도 아니다. 모든 차이와 고정 설정은 multi_rl_protocol.md 및 configs/algorithms/multi_rl.json에 기록했다. 테스트 결과를 본 뒤 튜닝하거나 좋은 시드만 선택하지 않았다.

## 검증과 보관

독립 스케줄 검사: {sum(audit_report['schedule_records_checked'].values())}개 완료 스케줄 및 {audit_report['decision_schedules_checked']}개 중간 계획, 제약 위반 {audit_report['feasibility_violations']}건. 솔버 응답 감사 경고 {len(audit_report['warnings'])}건은 원본과 감사 파일에 보존했다. 20개 체크포인트 모두 재로딩 후 검증 스케줄이 동일했다. 원시 JSON·CSV·DB 모든 셀 대조는 db_validation.json에 있다.

- 원시 결과 및 표: results/multi_rl/{rid}/
- 모델: checkpoints/{rid}/ (Git에는 해시만 기록)
- 그림4종: figures/publication/{rid}/ — PDF/SVG/600dpi PNG, 학습곡선은 원시 측정점
- 대시보드: http://localhost:3000/d/research-multi-rl/manufacturing-rl-7c-ppo-pqn-grpo-gspo-comparison?var-run_id={rid}
'''
    (ROOT/'reports/multi_rl_results.md').write_text(report)
    print(fresh[['method','gap_cp_percent','gap_ppo_percent']].to_string(index=False));print(output)

if __name__=='__main__':main()
