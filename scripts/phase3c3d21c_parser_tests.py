import ast, pathlib, re
src=pathlib.Path(__file__).with_name('phase3c3d21c_player_id_parser_fixed.py').read_text()
tree=ast.parse(src)
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='extract_athlete_id')
ns={'re':re};exec(compile(ast.Module(body=[node],type_ignores=[]),'<test>','exec'),ns)
f=ns['extract_athlete_id']
cases=[({'links':[{'href':'https://www.espn.com/nfl/player/_/id/4567048/kenneth-walker-iii'}]},'4567048'),({'links':[{'href':'https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/4379399'}]},'4379399'),({'id':'4360310'},'4360310'),({'links':[{'href':'https://example.com/injuries/id/999'}]},''),({},'')]
for athlete,expected in cases:
 got=f(athlete,{'id':'987654'});assert got==expected,(athlete,got,expected)
print('5/5 parser fixtures passed')
