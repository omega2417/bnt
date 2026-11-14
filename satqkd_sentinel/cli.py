"""Offline simulation, evaluation and self-contained HTML reporting."""
import argparse
import base64
import html
import importlib.metadata
import json
from pathlib import Path
import platform

import joblib
import numpy as np
import pandas as pd
from . import __version__
from .linkmodel import Link, slant_range
from .telemetry import generate_dataset
from .features import extract_features, FEATURE_NAMES
from .models import predict, predict_proba
from .evaluation import full_evaluation, summary_table
from .finitekey import asymptotic_vs_finite
from .geo import coverage_stats, contact_plan


def positive_int(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError('value must be a positive integer')
    return value


def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def versions():
    result = {'python': platform.python_version(), 'satqkd-sentinel': __version__}
    for name in ('numpy','scipy','pandas','matplotlib','scikit-learn','joblib'):
        result[name] = importlib.metadata.version(name)
    return result


def run_demo(output, n_train=30, n_test=20, seed=42, full=False):
    """Run the real pipeline and export portable artifacts; no web services."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    link = Link()
    methods = ('gradient_boosting','random_forest','logistic_regression') if full else ('random_forest',)
    print(f'Simulating {n_train} training and {n_test} test passes; methods: {", ".join(methods)}', flush=True)
    ev = full_evaluation(link, n_train, n_test, seed, methods=methods, importance_repeats=2)
    selected = ev['best_method']
    model = ev['classifiers'][selected]['model']
    metrics = ev['classifiers'][selected]['metrics']
    table = summary_table(ev)
    table.to_csv(output/'metrics.csv', index=False)
    ev['test_df'].to_csv(output/'telemetry.csv', index=False)
    predictions = ev['test_df'][['pass_id','t_s','label','key_bits']].copy()
    predictions['prediction'] = metrics['y_pred']
    predictions.to_csv(output/'predictions.csv', index=False)
    joblib.dump({'version':__version__, 'sklearn_version':importlib.metadata.version('scikit-learn'), 'feature_names':FEATURE_NAMES, 'model':model}, output/'model.joblib')

    link_rows = []
    for degree in (20,30,40,60,90):
        elevation = np.radians(degree)
        distance = slant_range(elevation,500e3)
        rate,qber = link.rate(link.eta(distance,elevation))
        link_rows.append(dict(elevation_deg=degree,range_km=float(distance/1000),loss_db=float(link.loss_db(distance,elevation)),rate_bps=float(rate),qber=float(qber)))
    finite = asymptotic_vs_finite(link)
    coverage = []
    for n in (3,4,6):
        c = coverage_stats(n)
        coverage.append(dict(nodes=n,coverage_pct=100*c['share1'],dual_coverage_pct=100*c['share2']))
    pd.DataFrame(link_rows).to_csv(output/'link_budget.csv',index=False)
    pd.DataFrame(finite).to_csv(output/'finite_key.csv',index=False)
    pd.DataFrame(coverage).to_csv(output/'geo_coverage.csv',index=False)
    summary = dict(version=__version__,seed=seed,mode='full' if full else 'quick',
        data_origin='synthetic simulation',security_status='illustrative model; not a composable security proof',
        selected_method=selected,selection_basis=ev['selection_basis'],
        train_passes=int(ev['train_df'].pass_id.nunique()),test_passes=int(ev['test_df'].pass_id.nunique()),
        validation_passes=int(ev['validation_df'].pass_id.nunique()),
        test_windows=len(ev['test_df']),macro_f1=float(metrics['macro_f1']),accuracy=float(metrics['accuracy']),
        block_policies=ev['block_policies'],novelty_detectors=ev['novelty_detectors'],
        link_budget=link_rows,finite_key=finite,coverage=coverage,environment=versions())
    save_json(output/'summary.json',summary)

    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    figures=[]
    fig,axes=plt.subplots(1,2,figsize=(11,4.2),layout='constrained')
    degrees=[r['elevation_deg'] for r in link_rows]
    axes[0].plot(degrees,[r['rate_bps']/1000 for r in link_rows],color='#2563eb',marker='o')
    axes[0].set(xlabel='Maximum elevation (deg)',ylabel='Asymptotic rate (kbit/s)',title='LEO link at 500 km')
    x=np.arange(len(finite))
    axes[1].bar(x-.18,[r['K_inf_bits']/1e6 for r in finite],.36,label='Asymptotic')
    axes[1].bar(x+.18,[r['K_fin_bits']/1e6 for r in finite],.36,label='Finite-size estimate')
    axes[1].set(xticks=x,xticklabels=[r['eps_max_deg'] for r in finite],xlabel='Maximum elevation (deg)',ylabel='Key estimate (Mbit)',title='One pass; different intensity allocation')
    axes[1].legend(fontsize=8)
    for ax in axes: ax.grid(axis='y',alpha=.2)
    figures.append(('Канал зв’язку та оцінка обсягу ключа','link_and_key.png',fig))

    fig,ax=plt.subplots(figsize=(10,8),layout='constrained')
    cm=metrics['confusion_matrix']; labels=metrics['labels']
    image=ax.imshow(cm,cmap='Blues')
    ax.set(xticks=range(len(labels)),yticks=range(len(labels)),xticklabels=labels,yticklabels=labels,xlabel='Predicted state',ylabel='True simulated state',title='Independent test passes')
    plt.setp(ax.get_xticklabels(),rotation=45,ha='right',fontsize=8)
    plt.setp(ax.get_yticklabels(),fontsize=8)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j,i,str(cm[i,j]),ha='center',va='center',fontsize=8,color='white' if cm[i,j]>cm.max()/2 else '#172554')
    fig.colorbar(image,ax=ax,shrink=.75)
    figures.append(('Розпізнавання станів на окремій тестовій вибірці','confusion_matrix.png',fig))

    cp=contact_plan(4,[(48.46,35.05)],hours=24,dt=30)
    fig,ax=plt.subplots(figsize=(11,3.4),layout='constrained')
    ax.plot(cp['t']/3600,cp['geo'].sum(axis=0),label='Visible GEO nodes',color='#2563eb')
    ax.fill_between(cp['t']/3600,0,cp['site'][0].astype(int),color='#f59e0b',alpha=.6,label='Ground contact: Dnipro')
    ax.set(xlabel='Time (hours)',ylabel='Count / contact flag',title='24-hour relay contact plan',ylim=(0,4.5))
    ax.legend(loc='upper right');ax.grid(alpha=.2)
    figures.append(('Видимість ретранслятора протягом доби','contact_plan.png',fig))
    sections=[]
    for title,name,fig in figures:
        fig.savefig(output/name,dpi=150)
        plt.close(fig)
        data=base64.b64encode((output/name).read_bytes()).decode('ascii')
        sections.append(f'<section><h2>{title}</h2><img alt="{title}" src="data:image/png;base64,{data}"></section>')
    page=f'''<!doctype html><html lang="uk"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SatQKD-Sentinel — звіт моделювання</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f1f5f9;color:#172554;font:16px/1.6 system-ui,sans-serif}}main{{max-width:1140px;margin:auto;padding:32px 20px}}header,section{{background:white;padding:24px 28px;border-radius:16px;margin-bottom:20px}}h1{{line-height:1.15;font-size:36px;margin:8px 0}}h2{{font-size:21px}}.eyebrow{{color:#2563eb;letter-spacing:.1em;font-weight:700}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}.card{{background:#eff6ff;padding:16px;border-radius:12px}}.card b{{display:block;font-size:30px}}img{{display:block;width:100%;height:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #e2e8f0}}.scroll{{overflow:auto}}.note{{color:#475569}}code{{overflow-wrap:anywhere}}@media print{{body{{background:white}}section{{break-inside:avoid}}}}
</style><main><header><div class="eyebrow">SATQKD-SENTINEL · {__version__}</div><h1>Моделювання супутникової QKD-мережі</h1><p>Відтворюваний запуск: seed {seed}. Навчання, вибір моделі й тестування виконано на окремих прольотах.</p><div class="cards"><div class="card">Macro F1<b>{metrics['macro_f1']:.3f}</b></div><div class="card">Точність<b>{metrics['accuracy']:.1%}</b></div><div class="card">Тестових вікон<b>{len(ev['test_df']):,}</b></div><div class="card">Тестових прольотів<b>{n_test}</b></div></div><p class="note">Синтетичні дані; показники описують цей симулятор. Оцінка finite-key є спрощеною моделлю, не доведеною межею криптографічної безпеки. Класифікатор не авторизує використання реальних ключів.</p></header>
<section><h2>Результати класифікації</h2><p>Модель: <strong>{html.escape(selected)}</strong>. Вибір за окремою валідаційною вибіркою.</p><div class="scroll">{table[['method','macro_f1','accuracy']].round(4).to_html(index=False,border=0)}</div></section>
{''.join(sections)}<section><h2>Покриття GEO</h2>{pd.DataFrame(coverage).round(2).to_html(index=False,border=0)}<h2>Як повторити</h2><p><code>python run.py demo --seed {seed} --train {n_train} --test {n_test}{' --full' if full else ''}</code></p><p>Цей HTML містить усі зображення й відкривається без інтернету. CSV, JSON та модель збережено поряд.</p><p class="note">Модель каналу: 500 км, апертури 0.1 / 0.6 м, 1550 нм. Asymptotic використовує всі імпульси як signal; finite-size — signal/decoy 50/25/25, тому різниця включає обидва ефекти.</p></section></main></html>'''
    (output/'report.html').write_text(page,encoding='utf-8')
    print(f"Macro F1={metrics['macro_f1']:.4f}; accuracy={metrics['accuracy']:.4f}")
    print(f"Report: {(output/'report.html').resolve()}")
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description='SatQKD-Sentinel: offline research simulator')
    parser.add_argument('--version',action='version',version=__version__)
    sub=parser.add_subparsers(dest='command')
    demo=sub.add_parser('demo',help='simulate, evaluate and export a complete report')
    demo.add_argument('--output',default='results/demo')
    demo.add_argument('--train',type=positive_int,default=30)
    demo.add_argument('--test',type=positive_int,default=20)
    demo.add_argument('--seed',type=int,default=42)
    demo.add_argument('--full',action='store_true',help='compare all three classifiers (slower)')
    sim=sub.add_parser('simulate',help='export synthetic telemetry CSV')
    sim.add_argument('--passes',type=positive_int,default=20)
    sim.add_argument('--seed',type=int,default=42)
    sim.add_argument('--output',default='results/telemetry.csv')
    pred=sub.add_parser('predict',help='classify telemetry CSV using a trusted local model')
    pred.add_argument('--model',required=True)
    pred.add_argument('--input',required=True)
    pred.add_argument('--output',default='results/predictions.csv')
    sub.add_parser('doctor',help='print runtime and dependency versions')
    args=parser.parse_args(argv)
    if args.command is None:
        return main(['demo'])
    try:
        if args.command=='demo':
            run_demo(args.output,args.train,args.test,args.seed,args.full)
        elif args.command=='doctor':
            print(json.dumps(versions(),indent=2))
        elif args.command=='simulate':
            path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
            generate_dataset(Link(),args.passes,seed=args.seed).to_csv(path,index=False)
            print(path.resolve())
        elif args.command=='predict':
            # joblib/pickle artifacts must come from a trusted local source.
            bundle=joblib.load(args.model)
            if bundle['version'] != __version__ or bundle['feature_names'] != FEATURE_NAMES:
                raise ValueError('Model version or feature schema differs; retrain with this release')
            if bundle.get('sklearn_version') != importlib.metadata.version('scikit-learn'):
                raise ValueError('scikit-learn version differs from the saved model; run demo to retrain locally')
            df=pd.read_csv(args.input);X=extract_features(df)
            df['prediction']=predict(bundle['model'],X)
            df['confidence']=predict_proba(bundle['model'],X).max(axis=1)
            path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
            df.to_csv(path,index=False);print(path.resolve())
    except (ValueError,OSError,KeyError) as exc:
        parser.error(str(exc))
    return 0
