"""Reject private runtime files before they enter a source repository."""
import pathlib, re, subprocess, sys
files=subprocess.check_output(['git','ls-files','-z']).decode().split('\0')
bad=[]
for name in filter(None,files):
 p=pathlib.PurePosixPath(name); n=p.name.lower()
 if (n=='.env' or (n.startswith('.env.') and n not in {'.env.example','.env.sample','.env.template'})):
  bad.append(name)
 elif re.search(r'(^|/)(service[_-]?account[^/]*\.json|service_key\.json|credentials\.json|[^/]*cookies\.json|[^/]*\.(pem|key|p12|pfx|sqlite|sqlite3|db))$',name,re.I):
  bad.append(name)
if bad:
 print('Private runtime files are tracked:\n'+'\n'.join(bad));sys.exit(1)
print('Tracked-file privacy check passed.')
