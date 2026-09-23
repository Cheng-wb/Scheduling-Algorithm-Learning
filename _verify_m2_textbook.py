from pathlib import Path
import re
import runpy

root = Path(__file__).resolve().parent
base = root/'Month_02_精确算法与参数学习'
docs = [base/'README.md', *base.glob('教材/*.md'), *base.glob('week*.md'), *base.glob('Week_*/Day*.md')]
count = 0
for path in docs:
    content = path.read_text(encoding='utf-8')
    assert '\ufffd' not in content, path
    assert content.count('```') % 2 == 0, path
    assert content.count('$$') % 2 == 0, path
    for target in re.findall(r'\]\(([^)]+)\)', content):
        if target.startswith(('http://','https://','#')):
            continue
        assert (path.parent/target.split('#')[0]).exists(), (path,target)
        count += 1
chapter = base/'教材/05_CP_SAT与调度建模.md'
blocks = re.findall(r'```python\n(.*?)\n```', chapter.read_text(encoding='utf-8'), re.S)
assert len(blocks) == 2
print('Running the complete code block from chapter 5:')
scope = {}
exec(compile(blocks[0], str(chapter), 'exec'), scope)
assert scope['solver'].objective_value == 2
assert scope['status'] == scope['cp_model'].OPTIMAL
print(f'PASS: {len(docs)} documents, {count} local links, math/code delimiters, standalone tutorial code.')
print('Textbook prose characters:', sum(len(p.read_text(encoding='utf-8')) for p in base.glob('教材/0*.md')))
