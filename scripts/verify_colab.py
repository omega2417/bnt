"""Run every notebook code cell in a fresh process, without injecting source paths.

Usage: python -I scripts/verify_colab.py /path/to/standalone/COLAB_START.ipynb
This exercises Python/IPython cells, not Google's hosted frontend.
"""
import argparse
import json
import os
from pathlib import Path
import time


def main():
    import nbformat
    from IPython.terminal.interactiveshell import TerminalInteractiveShell
    from IPython.utils.capture import capture_output
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('notebook')
    args=parser.parse_args()
    source=Path(args.notebook).resolve()
    os.chdir(source.parent)
    n=nbformat.read(source,as_version=4)
    nbformat.validate(n)
    shell=TerminalInteractiveShell.instance(simple_prompt=True)
    shell.display_formatter.active_types=['text/plain','text/html','image/png','image/svg+xml']
    records=[]
    for index,c in enumerate(n.cells):
        if c.cell_type!='code':continue
        number=len(records)+1
        print(f'Cell {number}/34 (notebook index {index}): running',flush=True)
        start=time.perf_counter()
        with capture_output() as captured:
            result=shell.run_cell(c.source,store_history=True)
        error=result.error_before_exec or result.error_in_exec
        outputs=[]
        for name,text in [('stdout',captured.stdout),('stderr',captured.stderr)]:
            if text:outputs.append(nbformat.v4.new_output('stream',name=name,text=text))
        for output in captured.outputs:
            outputs.append(nbformat.v4.new_output('display_data',data=output.data,metadata=output.metadata))
        c.outputs=outputs;c.execution_count=number
        records.append(dict(code_cell=number,notebook_index=index,status='failed' if error else 'passed',seconds=round(time.perf_counter()-start,3)))
        (source.parent/'cell_verification.json').write_text(json.dumps(records,indent=2))
        if error:
            print(captured.stdout,captured.stderr,flush=True)
            raise RuntimeError(f'Cell {number} failed') from error
        print(f'Cell {number}: PASS ({records[-1]["seconds"]} s)',flush=True)
    pngs=sum('image/png' in o.get('data',{}) for c in n.cells for o in c.get('outputs',[]))
    if len(records)!=34:
        raise RuntimeError(f'Expected 34 code cells, got {len(records)}')
    if pngs!=13:
        raise RuntimeError(f'Expected 13 inline PNGs, got {pngs}')
    if shell.user_ns['TEST_STATUS']['returncode']!=0:
        raise RuntimeError('Embedded test suite failed')
    archive=Path(shell.user_ns['RESULTS_ZIP'])
    if not archive.is_file():
        raise RuntimeError(f'Results archive not found: {archive}')
    n.metadata['execution_verification']={'runner':'verify_colab.py; isolated local IPython, not Google hosted runtime','code_cells':len(records),'pngs':pngs}
    nbformat.write(n,source.with_stem('COLAB_VERIFIED'))
    result={'code_cells':len(records),'inline_pngs':pngs,'results_zip':str(archive),'project_root':str(shell.user_ns['PROJECT_ROOT']),'environment':shell.user_ns['_run_info']['environment']}
    (source.parent/'verification_summary.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
