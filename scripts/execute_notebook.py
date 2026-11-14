"""Execute a trusted local notebook in-process, without TCP or a Jupyter server.

This runner supports this project's Python/IPython demonstration cells. It writes
only after all cells succeed and preserves rich inline matplotlib output.
"""
import argparse
from pathlib import Path
import os
import sys
import traceback


def main():
    import nbformat
    from IPython.terminal.interactiveshell import TerminalInteractiveShell
    from IPython.utils.capture import capture_output
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('notebook',nargs='?',default='notebooks/demo_satqkd_sentinel.ipynb')
    parser.add_argument('--output')
    args=parser.parse_args()
    source=Path(args.notebook).resolve()
    destination=Path(args.output).resolve() if args.output else source.with_stem(source.stem+'_executed')
    notebook=nbformat.read(source,as_version=4)
    shell=TerminalInteractiveShell.instance(simple_prompt=True)
    shell.display_formatter.active_types=['text/plain','text/html','image/png','image/svg+xml']
    shell.user_ns['__name__']='__main__'
    sys.path.insert(0,str(source.parent.parent))
    os.chdir(source.parent)
    count=0
    for i,cell in enumerate(notebook.cells):
        if cell.cell_type!='code':
            continue
        count+=1
        print(f'Executing cell {i+1} ({count})',flush=True)
        with capture_output() as captured:
            result=shell.run_cell(cell.source,store_history=True)
        error=result.error_before_exec or result.error_in_exec
        if error:
            sys.stderr.write(captured.stdout+captured.stderr)
            raise RuntimeError(f'Notebook failed in cell {i+1}') from error
        outputs=[]
        for name,text in [('stdout',captured.stdout),('stderr',captured.stderr)]:
            if text:
                outputs.append(nbformat.v4.new_output('stream',name=name,text=text))
        for display in captured.outputs:
            outputs.append(nbformat.v4.new_output('display_data',data=display.data,metadata=display.metadata))
        cell.outputs=outputs
        cell.execution_count=count
    notebook.metadata['execution']={'runner':'scripts/execute_notebook.py','code_cells':count}
    destination.parent.mkdir(parents=True,exist_ok=True)
    nbformat.write(notebook,destination)
    print(f'Executed {count} code cells: {destination}')

if __name__=='__main__':
    main()
